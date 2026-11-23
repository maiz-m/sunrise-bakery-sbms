"""Production planning, recipes and batch recording.

Owner: Ahmed Zahil Zahir

Rule from the case study: production staff must not finalise a batch if the required
ingredient quantities are not available. complete_batch() re-checks stock inside the
same transaction that deducts it, so two people finishing batches at the same time
cannot both use the same flour.
"""
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from .. import db
from ..errors import BusinessRuleError, ValidationError
from . import inventory, validate


def current_recipe(product_id, cur=None):
    sql = ("SELECT * FROM recipes WHERE product_id=%s AND is_current=TRUE "
           "ORDER BY created_at DESC LIMIT 1")
    if cur is None:
        return db.fetch_one(sql, (product_id,))
    cur.execute(sql, (product_id,))
    return cur.fetchone()


def recipe_lines(recipe_id, cur=None):
    sql = ("SELECT ri.ingredient_id, ri.quantity, i.name, i.unit, i.ingredient_code "
           "FROM recipe_ingredients ri JOIN ingredients i ON i.ingredient_id = ri.ingredient_id "
           "WHERE ri.recipe_id=%s ORDER BY i.name")
    if cur is None:
        return db.fetch_all(sql, (recipe_id,))
    cur.execute(sql, (recipe_id,))
    return cur.fetchall()


def _scale(per_yield, standard_yield, planned):
    needed = Decimal(per_yield) * Decimal(planned) / Decimal(standard_yield)
    return needed.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


def estimate_requirements(product_id, planned_quantity, cur=None):
    """Ingredients needed for a planned batch, with what is available and any shortfall."""
    planned_quantity = validate.positive_int(planned_quantity, "Planned quantity")
    recipe = current_recipe(product_id, cur)
    if recipe is None:
        raise BusinessRuleError("This product has no recipe yet, so ingredients cannot be estimated.")

    own_conn = cur is None
    conn = db.get_connection() if own_conn else None
    c = conn.cursor() if own_conn else cur
    try:
        result = []
        for line in recipe_lines(recipe["recipe_id"], c):
            needed = _scale(line["quantity"], recipe["standard_yield"], planned_quantity)
            available = inventory.usable_quantity(c, line["ingredient_id"])
            result.append({
                "ingredient_id": line["ingredient_id"],
                "ingredient": line["name"],
                "unit": line["unit"],
                "needed": needed,
                "available": available,
                "short": max(needed - available, Decimal(0)),
            })
        return recipe, result
    finally:
        if own_conn:
            conn.close()


def plan_batch(user, product_id, planned_quantity, production_date):
    """Manager adds a product and target quantity to a day's production plan."""
    user.require("production.plan")
    if not product_id:
        raise ValidationError("Choose a product.")
    planned_quantity = validate.positive_int(planned_quantity, "Planned quantity")
    production_date = validate.parse_date(production_date, "Production date")
    if production_date < date.today():
        raise ValidationError("Production date cannot be in the past.")
    recipe, needs = estimate_requirements(product_id, planned_quantity)
    with db.transaction() as cur:
        cur.execute(
            "INSERT INTO production_batches (product_id, recipe_id, planned_quantity, "
            "production_date, staff_id) VALUES (%s,%s,%s,%s,%s)",
            (product_id, recipe["recipe_id"], planned_quantity, production_date, user.user_id),
        )
        batch_id = cur.lastrowid
    # Shortages are returned so the screen can warn the manager straight away.
    return batch_id, [n for n in needs if n["short"] > 0]


def list_batches(production_date=None, status=None):
    sql = ("SELECT b.*, p.name AS product, p.product_code, u.full_name AS staff "
           "FROM production_batches b JOIN products p ON p.product_id=b.product_id "
           "JOIN users u ON u.user_id=b.staff_id WHERE 1=1")
    params = []
    if production_date:
        sql += " AND b.production_date=%s"
        params.append(validate.parse_date(production_date))
    if status:
        sql += " AND b.status=%s"
        params.append(status)
    return db.fetch_all(sql + " ORDER BY b.production_date DESC, b.production_batch_id DESC", params)


def complete_batch(user, batch_id, actual_quantity, wasted_quantity):
    """Production staff record output. Ingredients for the planned quantity are deducted.

    Raises BusinessRuleError listing every short ingredient if stock is insufficient;
    in that case nothing is changed.
    """
    user.require("production.record")
    actual_quantity = validate.positive_int(actual_quantity, "Actual quantity", allow_zero=True)
    wasted_quantity = validate.positive_int(wasted_quantity, "Wasted quantity", allow_zero=True)

    with db.transaction() as cur:
        cur.execute("SELECT * FROM production_batches WHERE production_batch_id=%s FOR UPDATE",
                    (batch_id,))
        batch = cur.fetchone()
        if batch is None:
            raise ValidationError("That batch no longer exists.")
        if batch["status"] != "Planned":
            raise BusinessRuleError(f"This batch is already {batch['status'].lower()}.")
        if actual_quantity + wasted_quantity > batch["planned_quantity"] * 2:
            raise ValidationError("Actual plus wasted is more than double the plan. Check the numbers.")

        # Lock the ingredient rows so the stock check and the deduction see the same numbers.
        lines = recipe_lines(batch["recipe_id"], cur)
        cur.execute("SELECT standard_yield FROM recipes WHERE recipe_id=%s", (batch["recipe_id"],))
        standard_yield = cur.fetchone()["standard_yield"]
        ids = [l["ingredient_id"] for l in lines]
        if ids:
            cur.execute(
                f"SELECT ingredient_id FROM ingredients WHERE ingredient_id IN ({','.join(['%s'] * len(ids))}) FOR UPDATE",
                ids,
            )

        shortages = []
        usage = []
        for line in lines:
            needed = _scale(line["quantity"], standard_yield, batch["planned_quantity"])
            available = inventory.usable_quantity(cur, line["ingredient_id"])
            if needed > available:
                shortages.append(f"{line['name']}: need {needed} {line['unit']}, have {available}")
            usage.append((line, needed))
        if shortages:
            raise BusinessRuleError(
                "Batch cannot be finalised - not enough stock:\n" + "\n".join(shortages)
            )

        ref = f"Batch #{batch_id}"
        for line, needed in usage:
            cur.execute(
                "UPDATE ingredients SET current_quantity = current_quantity - %s WHERE ingredient_id=%s",
                (needed, line["ingredient_id"]),
            )
            inventory.consume_batches(cur, line["ingredient_id"], needed)
            cur.execute(
                "INSERT INTO production_ingredient_usage (production_batch_id, ingredient_id, quantity_used) "
                "VALUES (%s,%s,%s)",
                (batch_id, line["ingredient_id"], needed),
            )
            cur.execute(
                "INSERT INTO stock_movements (ingredient_id, movement_type, quantity, reference, user_id) "
                "VALUES (%s,'PRODUCTION_USE',%s,%s,%s)",
                (line["ingredient_id"], -needed, ref, user.user_id),
            )

        # Good units go on the shelf; wasted units are recorded but never added to stock.
        if actual_quantity:
            cur.execute("UPDATE products SET stock_quantity = stock_quantity + %s WHERE product_id=%s",
                        (actual_quantity, batch["product_id"]))
            cur.execute(
                "INSERT INTO stock_movements (product_id, movement_type, quantity, reference, user_id) "
                "VALUES (%s,'PRODUCTION_OUTPUT',%s,%s,%s)",
                (batch["product_id"], actual_quantity, ref, user.user_id),
            )
        if wasted_quantity:
            cur.execute(
                "INSERT INTO stock_movements (product_id, movement_type, quantity, reference, user_id) "
                "VALUES (%s,'WASTE',%s,%s,%s)",
                (batch["product_id"], -wasted_quantity, ref, user.user_id),
            )
        cur.execute(
            "UPDATE production_batches SET actual_quantity=%s, wasted_quantity=%s, status='Completed', "
            "completed_at=NOW(), staff_id=%s WHERE production_batch_id=%s",
            (actual_quantity, wasted_quantity, user.user_id, batch_id),
        )


def cancel_batch(user, batch_id):
    user.require("production.plan")
    with db.transaction() as cur:
        cur.execute("SELECT status FROM production_batches WHERE production_batch_id=%s FOR UPDATE",
                    (batch_id,))
        row = cur.fetchone()
        if row is None or row["status"] != "Planned":
            raise BusinessRuleError("Only planned batches can be cancelled.")
        cur.execute("UPDATE production_batches SET status='Cancelled' WHERE production_batch_id=%s",
                    (batch_id,))
