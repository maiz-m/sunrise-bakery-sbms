"""Product catalogue.

Owner: Ahmed Zahil Zahir
"""
import pymysql

from .. import audit, db
from ..errors import ValidationError
from . import validate


def list_categories():
    return db.fetch_all("SELECT * FROM product_categories ORDER BY name")


def list_products(search="", category_id=None, active_only=False):
    sql = (
        "SELECT p.*, c.name AS category FROM products p "
        "JOIN product_categories c ON c.category_id = p.category_id WHERE 1=1"
    )
    params = []
    if search:
        sql += " AND (p.name LIKE %s OR p.product_code LIKE %s OR p.description LIKE %s)"
        like = f"%{search.strip()}%"
        params += [like, like, like]
    if category_id:
        sql += " AND p.category_id = %s"
        params.append(category_id)
    if active_only:
        sql += " AND p.is_active = TRUE"
    sql += " ORDER BY c.name, p.name"
    return db.fetch_all(sql, params)


def get_product(product_id):
    return db.fetch_one("SELECT * FROM products WHERE product_id = %s", (product_id,))


def _clean(code, name, category_id, description, price):
    code = validate.required_text(code, "Product code", 20).upper()
    name = validate.required_text(name, "Product name")
    if not category_id:
        raise ValidationError("Choose a category.")
    description = (description or "").strip()[:255]
    price = validate.money(price, "Selling price")
    return code, name, category_id, description, price


def add_product(user, code, name, category_id, description, price):
    user.require("products.edit")
    code, name, category_id, description, price = _clean(code, name, category_id, description, price)
    try:
        with db.transaction() as cur:
            cur.execute(
                "INSERT INTO products (product_code, name, category_id, description, selling_price) "
                "VALUES (%s, %s, %s, %s, %s)",
                (code, name, category_id, description, price),
            )
            return cur.lastrowid
    except pymysql.err.IntegrityError:
        raise ValidationError(f"Product code {code} already exists.")


def update_product(user, product_id, code, name, category_id, description, price):
    user.require("products.edit")
    code, name, category_id, description, price = _clean(code, name, category_id, description, price)
    old = get_product(product_id)
    if old is None:
        raise ValidationError("That product no longer exists.")
    price_changed = old["selling_price"] != price
    if price_changed:
        user.require("prices.change")
    try:
        with db.transaction() as cur:
            cur.execute(
                "UPDATE products SET product_code=%s, name=%s, category_id=%s, description=%s, "
                "selling_price=%s WHERE product_id=%s",
                (code, name, category_id, description, price, product_id),
            )
            if price_changed:
                audit.log(cur, user.user_id, "PRICE_CHANGE", "products", product_id,
                          f"{code}: {old['selling_price']} -> {price}")
    except pymysql.err.IntegrityError:
        raise ValidationError(f"Product code {code} already exists.")


def set_active(user, product_id, active):
    user.require("products.edit")
    with db.transaction() as cur:
        cur.execute("UPDATE products SET is_active=%s WHERE product_id=%s", (active, product_id))
        audit.log(cur, user.user_id, "ACTIVATE_PRODUCT" if active else "DEACTIVATE_PRODUCT",
                  "products", product_id)
