"""Ingredients, suppliers, deliveries, expiry tracking and stock adjustments.

Owner: Ahmed Zahil Zahir
"""
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

import pymysql

from .. import audit, config, db
from ..errors import BusinessRuleError, ValidationError
from . import validate

UNITS = ("kg", "g", "L", "ml", "pcs")


# ---------- suppliers ----------

def list_suppliers(active_only=False):
    sql = "SELECT * FROM suppliers"
    if active_only:
        sql += " WHERE is_active = TRUE"
    return db.fetch_all(sql + " ORDER BY name")


def add_supplier(user, name, contact_person, phone, email):
    user.require("suppliers.manage")
    name = validate.required_text(name, "Supplier name")
    phone = (phone or "").strip()
    email = (email or "").strip()
    if email and "@" not in email:
        raise ValidationError("Email address does not look right.")
    try:
        with db.transaction() as cur:
            cur.execute(
                "INSERT INTO suppliers (name, contact_person, phone, email) VALUES (%s,%s,%s,%s)",
                (name, (contact_person or "").strip(), phone, email),
            )
            return cur.lastrowid
    except pymysql.err.IntegrityError:
        raise ValidationError(f"A supplier called {name} already exists.")


# ---------- ingredients ----------

def list_ingredients(search=""):
    """Ingredients with a status column: OK / LOW / OUT."""
    sql = (
        "SELECT i.*, s.name AS supplier, "
        "  (SELECT MIN(b.expiry_date) FROM ingredient_batches b "
        "    WHERE b.ingredient_id = i.ingredient_id AND b.quantity_remaining > 0) AS next_expiry "
        "FROM ingredients i LEFT JOIN suppliers s ON s.supplier_id = i.supplier_id"
    )
    params = []
    if search:
        sql += " WHERE i.name LIKE %s OR i.ingredient_code LIKE %s"
        params = [f"%{search}%", f"%{search}%"]
    rows = db.fetch_all(sql + " ORDER BY i.name", params)
    for r in rows:
        r["status"] = stock_status(r["current_quantity"], r["reorder_level"])
    return rows


def stock_status(quantity, reorder_level):
    if quantity <= 0:
        return "OUT"
    if quantity <= reorder_level:
        return "LOW"
    return "OK"


def add_ingredient(user, code, name, unit, reorder_level, supplier_id=None):
    user.require("suppliers.manage")
    code = validate.required_text(code, "Ingredient code", 20).upper()
    name = validate.required_text(name, "Ingredient name")
    if unit not in UNITS:
        raise ValidationError("Choose a unit of measurement.")
    reorder_level = validate.money(reorder_level, "Reorder level")
    try:
        with db.transaction() as cur:
            cur.execute(
                "INSERT INTO ingredients (ingredient_code, name, unit, reorder_level, supplier_id) "
                "VALUES (%s,%s,%s,%s,%s)",
                (code, name, unit, reorder_level, supplier_id or None),
            )
            return cur.lastrowid
    except pymysql.err.IntegrityError:
        raise ValidationError(f"Ingredient code {code} already exists.")


def low_stock_ingredients():
    """Ingredients at or below their reorder level (business rule: warn authorised users)."""
    return db.fetch_all(
        "SELECT ingredient_code, name, unit, current_quantity, reorder_level FROM ingredients "
        "WHERE current_quantity <= reorder_level ORDER BY current_quantity / NULLIF(reorder_level,0)"
    )


def usable_quantity(cur, ingredient_id):
    """Stock that can actually be used: current quantity minus anything in expired batches."""
    cur.execute(
        "SELECT i.current_quantity - COALESCE(("
        "  SELECT SUM(b.quantity_remaining) FROM ingredient_batches b "
        "  WHERE b.ingredient_id = i.ingredient_id AND b.expiry_date < CURDATE()), 0) AS usable "
        "FROM ingredients i WHERE i.ingredient_id = %s",
        (ingredient_id,),
    )
    row = cur.fetchone()
    return max(row["usable"], Decimal(0)) if row else Decimal(0)


def expiring_batches(days=None):
    """Batches with stock left that are expired or expire within `days`."""
    days = config.NEAR_EXPIRY_DAYS if days is None else days
    rows = db.fetch_all(
        "SELECT b.batch_id, b.batch_number, b.quantity_remaining, b.expiry_date, "
        "       i.name AS ingredient, i.unit "
        "FROM ingredient_batches b JOIN ingredients i ON i.ingredient_id = b.ingredient_id "
        "WHERE b.quantity_remaining > 0 AND b.expiry_date <= %s ORDER BY b.expiry_date",
        (date.today() + timedelta(days=days),),
    )
    for r in rows:
        r["state"] = "EXPIRED" if r["expiry_date"] < date.today() else "NEAR EXPIRY"
    return rows


# ---------- deliveries ----------

def receive_delivery(user, supplier_id, reference, delivery_date, lines):
    """Record a delivery. lines = [(ingredient_id, batch_number, quantity, expiry_date), ...]

    All lines are saved together: if one line is wrong nothing is saved.
    """
    user.require("deliveries.receive")
    if not supplier_id:
        raise ValidationError("Choose the supplier.")
    reference = validate.required_text(reference, "Delivery reference", 50)
    delivery_date = validate.parse_date(delivery_date, "Delivery date")
    if delivery_date > date.today():
        raise ValidationError("Delivery date cannot be in the future.")
    if not lines:
        raise ValidationError("Add at least one ingredient to the delivery.")

    clean = []
    for ingredient_id, batch_number, quantity, expiry in lines:
        batch_number = validate.required_text(batch_number, "Batch number", 40)
        quantity = validate.positive_decimal(quantity, "Delivered quantity")
        expiry = validate.parse_date(expiry, "Expiry date")
        if expiry <= delivery_date:
            raise ValidationError(f"Batch {batch_number}: expiry date must be after the delivery date.")
        clean.append((ingredient_id, batch_number, quantity, expiry))

    try:
        with db.transaction() as cur:
            cur.execute(
                "INSERT INTO ingredient_deliveries (supplier_id, delivery_date, reference, received_by) "
                "VALUES (%s,%s,%s,%s)",
                (supplier_id, delivery_date, reference, user.user_id),
            )
            delivery_id = cur.lastrowid
            for ingredient_id, batch_number, quantity, expiry in clean:
                cur.execute(
                    "INSERT INTO ingredient_batches (delivery_id, ingredient_id, batch_number, "
                    "quantity_received, quantity_remaining, expiry_date) VALUES (%s,%s,%s,%s,%s,%s)",
                    (delivery_id, ingredient_id, batch_number, quantity, quantity, expiry),
                )
                cur.execute(
                    "UPDATE ingredients SET current_quantity = current_quantity + %s WHERE ingredient_id=%s",
                    (quantity, ingredient_id),
                )
                cur.execute(
                    "INSERT INTO stock_movements (ingredient_id, movement_type, quantity, reference, user_id) "
                    "VALUES (%s,'DELIVERY',%s,%s,%s)",
                    (ingredient_id, quantity, f"Delivery {reference}", user.user_id),
                )
            return delivery_id
    except pymysql.err.IntegrityError as e:
        raise ValidationError(f"Delivery not saved: duplicate reference or batch number ({e.args[1]}).")


def consume_batches(cur, ingredient_id, quantity):
    """Take `quantity` out of the ingredient's batches, earliest expiry first (FEFO).

    Expired batches are skipped. Must be called inside a transaction.
    """
    remaining = quantity
    cur.execute(
        "SELECT batch_id, quantity_remaining FROM ingredient_batches "
        "WHERE ingredient_id=%s AND quantity_remaining > 0 AND expiry_date >= CURDATE() "
        "ORDER BY expiry_date, batch_id FOR UPDATE",
        (ingredient_id,),
    )
    for batch in cur.fetchall():
        if remaining <= 0:
            break
        take = min(batch["quantity_remaining"], remaining)
        cur.execute(
            "UPDATE ingredient_batches SET quantity_remaining = quantity_remaining - %s WHERE batch_id=%s",
            (take, batch["batch_id"]),
        )
        remaining -= take
    return remaining  # > 0 means some stock had no batch record (e.g. older manual adjustment)


# ---------- adjustments ----------

def adjust_stock(user, ingredient_id, change, reason):
    """Authorised correction (spillage, count difference). change is + or -."""
    user.require("stock.adjust")
    reason = validate.required_text(reason, "Reason", 200)
    try:
        change = Decimal(str(change).strip())
    except (InvalidOperation, AttributeError):
        raise ValidationError("Adjustment must be a number, e.g. -2.5 or 10.")
    if change == 0:
        raise ValidationError("Adjustment cannot be 0.")

    with db.transaction() as cur:
        cur.execute("SELECT * FROM ingredients WHERE ingredient_id=%s FOR UPDATE", (ingredient_id,))
        ing = cur.fetchone()
        if ing is None:
            raise ValidationError("That ingredient no longer exists.")
        new_qty = ing["current_quantity"] + change
        if new_qty < 0:
            raise BusinessRuleError(
                f"Only {ing['current_quantity']} {ing['unit']} of {ing['name']} in stock; "
                f"cannot remove {-change}."
            )
        cur.execute("UPDATE ingredients SET current_quantity=%s WHERE ingredient_id=%s",
                    (new_qty, ingredient_id))
        if change < 0:
            consume_batches(cur, ingredient_id, -change)
        cur.execute(
            "INSERT INTO stock_movements (ingredient_id, movement_type, quantity, reference, user_id) "
            "VALUES (%s,'ADJUSTMENT',%s,%s,%s)",
            (ingredient_id, change, reason, user.user_id),
        )
        audit.log(cur, user.user_id, "STOCK_ADJUSTMENT", "ingredients", ingredient_id,
                  f"{ing['name']}: {ing['current_quantity']} -> {new_qty} ({reason})")


def movement_history(ingredient_id=None, limit=200):
    sql = (
        "SELECT m.created_at, m.movement_type, m.quantity, m.reference, u.username, "
        "       COALESCE(i.name, p.name) AS item "
        "FROM stock_movements m JOIN users u ON u.user_id = m.user_id "
        "LEFT JOIN ingredients i ON i.ingredient_id = m.ingredient_id "
        "LEFT JOIN products p ON p.product_id = m.product_id"
    )
    params = []
    if ingredient_id:
        sql += " WHERE m.ingredient_id = %s"
        params.append(ingredient_id)
    sql += " ORDER BY m.created_at DESC, m.movement_id DESC LIMIT %s"
    params.append(limit)
    return db.fetch_all(sql, params)
