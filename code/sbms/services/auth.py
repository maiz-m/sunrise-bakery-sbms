"""Login, password hashing and role-based access control.

Owner: Ahmed Maaiz Mohamed
"""
from dataclasses import dataclass
from datetime import datetime, timedelta

import bcrypt

from .. import audit, config, db
from ..errors import LoginFailed, PermissionDenied, ValidationError

ROLES = ("Administrator", "Manager", "Production", "Sales", "Inventory")

# What each role is allowed to do. Checked in the service layer, not just by hiding
# buttons, so a screen that forgets to hide a button still cannot break the rule.
PERMISSIONS = {
    "Administrator": {
        "users.manage", "products.view", "products.edit", "prices.change",
        "inventory.view", "suppliers.manage", "deliveries.receive", "stock.adjust",
        "production.plan", "production.record", "orders.manage", "orders.cancel",
        "sales.record", "reports.view", "reports.admin",
    },
    "Manager": {
        "products.view", "products.edit", "prices.change", "inventory.view",
        "suppliers.manage", "deliveries.receive", "stock.adjust", "production.plan",
        "production.record", "orders.manage", "orders.cancel", "sales.record",
        "reports.view",
    },
    "Production": {"products.view", "inventory.view", "production.record"},
    "Sales": {"products.view", "orders.manage", "sales.record"},
    "Inventory": {"products.view", "inventory.view", "deliveries.receive", "stock.adjust"},
}


@dataclass
class User:
    user_id: int
    username: str
    full_name: str
    role: str

    def can(self, permission):
        return permission in PERMISSIONS.get(self.role, set())

    def require(self, permission):
        if not self.can(permission):
            raise PermissionDenied(f"Your role ({self.role}) is not allowed to do this.")


def hash_password(password):
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def check_password(password, password_hash):
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def login(username, password):
    username = (username or "").strip()
    if not username or not password:
        raise LoginFailed("Enter your username and password.")
    row = db.fetch_one("SELECT * FROM users WHERE username = %s", (username,))
    # Same message for a wrong username and a wrong password, so we don't reveal which accounts exist.
    if row is None:
        raise LoginFailed("Username or password is incorrect.")

    # 1. Is the account locked right now? Checked before the password, so guessing stops working.
    if row["locked_until"] and row["locked_until"] > datetime.now():
        raise LoginFailed(f"This account is locked after too many wrong passwords. Try again after "
                          f"{row['locked_until']:%H:%M} or ask the administrator to unlock it.")

    # 2. Wrong password: count it, and lock the account when the limit is reached.
    if not check_password(password, row["password_hash"]):
        record_failed_login(row)
        raise LoginFailed("Username or password is incorrect.")

    if not row["is_active"]:
        raise LoginFailed("This account has been deactivated. Contact the administrator.")

    # 3. Correct password: start counting from zero again.
    with db.transaction() as cur:
        cur.execute("UPDATE users SET failed_logins = 0, locked_until = NULL WHERE user_id = %s",
                    (row["user_id"],))
    return User(row["user_id"], row["username"], row["full_name"], row["role"])


def record_failed_login(row):
    """Add one to the wrong-password count. At the limit, lock the account and log it."""
    failures = row["failed_logins"] + 1
    with db.transaction() as cur:
        if failures >= config.MAX_FAILED_LOGINS:
            until = datetime.now() + timedelta(minutes=config.LOCKOUT_MINUTES)
            cur.execute("UPDATE users SET failed_logins = 0, locked_until = %s WHERE user_id = %s",
                        (until, row["user_id"]))
            audit.log(cur, row["user_id"], "ACCOUNT_LOCKED", "users", row["user_id"],
                      f"{failures} wrong passwords in a row")
        else:
            cur.execute("UPDATE users SET failed_logins = %s WHERE user_id = %s",
                        (failures, row["user_id"]))


def validate_password(password):
    if len(password) < 8:
        raise ValidationError("Password must be at least 8 characters.")
    if password.isalpha() or password.isdigit():
        raise ValidationError("Password must contain both letters and numbers.")


def list_users():
    return db.fetch_all(
        "SELECT user_id, username, full_name, role, is_active, created_at FROM users ORDER BY username"
    )


def create_user(admin, username, full_name, role, password):
    admin.require("users.manage")
    username = (username or "").strip().lower()
    full_name = (full_name or "").strip()
    if not username or not full_name:
        raise ValidationError("Username and full name are required.")
    if role not in ROLES:
        raise ValidationError("Choose a valid role.")
    validate_password(password)
    if db.fetch_one("SELECT 1 FROM users WHERE username = %s", (username,)):
        raise ValidationError(f"Username '{username}' is already taken.")
    with db.transaction() as cur:
        cur.execute(
            "INSERT INTO users (username, password_hash, full_name, role) VALUES (%s, %s, %s, %s)",
            (username, hash_password(password), full_name, role),
        )
        new_id = cur.lastrowid
        audit.log(cur, admin.user_id, "CREATE_USER", "users", new_id, f"{username} as {role}")
    return new_id


def set_user_active(admin, user_id, active):
    admin.require("users.manage")
    if user_id == admin.user_id and not active:
        raise ValidationError("You cannot deactivate your own account.")
    with db.transaction() as cur:
        cur.execute("UPDATE users SET is_active = %s WHERE user_id = %s", (active, user_id))
        audit.log(cur, admin.user_id, "ACTIVATE_USER" if active else "DEACTIVATE_USER",
                  "users", user_id)


def change_role(admin, user_id, role):
    admin.require("users.manage")
    if role not in ROLES:
        raise ValidationError("Choose a valid role.")
    with db.transaction() as cur:
        cur.execute("UPDATE users SET role = %s WHERE user_id = %s", (role, user_id))
        audit.log(cur, admin.user_id, "CHANGE_ROLE", "users", user_id, f"new role {role}")
