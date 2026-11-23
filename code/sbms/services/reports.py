"""Manager dashboard and reports.

Owner: Ahmed Maaiz Mohamed

Each report returns (columns, rows) so one table widget can show any of them.
"""
from datetime import date, timedelta

from .. import db
from ..errors import ValidationError
from . import inventory, validate


def _range(start, end):
    start = validate.parse_date(start, "From date") if start else date.today() - timedelta(days=30)
    end = validate.parse_date(end, "To date") if end else date.today()
    if start > end:
        raise ValidationError("'From' date must be on or before the 'To' date.")
    return start, end


def dashboard_summary():
    today = db.fetch_one(
        "SELECT COUNT(*) AS n, COALESCE(SUM(total),0) AS total FROM sales WHERE DATE(sale_datetime)=CURDATE()")
    month = db.fetch_one(
        "SELECT COALESCE(SUM(total),0) AS total FROM sales "
        "WHERE YEAR(sale_datetime)=YEAR(CURDATE()) AND MONTH(sale_datetime)=MONTH(CURDATE())")
    pending = db.fetch_one(
        "SELECT COUNT(*) AS n FROM customer_orders WHERE status NOT IN ('Collected','Cancelled')")
    planned = db.fetch_one(
        "SELECT COUNT(*) AS n FROM production_batches WHERE status='Planned' AND production_date=CURDATE()")
    return {
        "sales_today": today["total"],
        "sales_today_count": today["n"],
        "sales_month": month["total"],
        "pending_orders": pending["n"],
        "batches_today": planned["n"],
        "low_stock": len(inventory.low_stock_ingredients()),
        "expiring": len(inventory.expiring_batches()),
    }


def daily_sales(start=None, end=None, category_id=None):
    start, end = _range(start, end)
    sql = ("SELECT DATE(s.sale_datetime) AS day, COUNT(DISTINCT s.sale_id) AS sales, "
           "SUM(si.quantity) AS items, SUM(si.quantity*si.unit_price) AS revenue "
           "FROM sales s JOIN sale_items si ON si.sale_id=s.sale_id "
           "JOIN products p ON p.product_id=si.product_id "
           "WHERE DATE(s.sale_datetime) BETWEEN %s AND %s")
    params = [start, end]
    if category_id:
        sql += " AND p.category_id=%s"
        params.append(category_id)
    rows = db.fetch_all(sql + " GROUP BY day ORDER BY day", params)
    return ("day", "sales", "items", "revenue"), rows


def monthly_sales(start=None, end=None, category_id=None):
    start, end = _range(start, end)
    sql = ("SELECT DATE_FORMAT(s.sale_datetime,'%%Y-%%m') AS month, COUNT(DISTINCT s.sale_id) AS sales, "
           "SUM(si.quantity*si.unit_price) AS revenue "
           "FROM sales s JOIN sale_items si ON si.sale_id=s.sale_id "
           "JOIN products p ON p.product_id=si.product_id "
           "WHERE DATE(s.sale_datetime) BETWEEN %s AND %s")
    params = [start, end]
    if category_id:
        sql += " AND p.category_id=%s"
        params.append(category_id)
    return ("month", "sales", "revenue"), db.fetch_all(sql + " GROUP BY month ORDER BY month", params)


def best_sellers(start=None, end=None, category_id=None, limit=10):
    start, end = _range(start, end)
    sql = ("SELECT p.product_code, p.name, c.name AS category, SUM(si.quantity) AS qty_sold, "
           "SUM(si.quantity*si.unit_price) AS revenue "
           "FROM sale_items si JOIN sales s ON s.sale_id=si.sale_id "
           "JOIN products p ON p.product_id=si.product_id "
           "JOIN product_categories c ON c.category_id=p.category_id "
           "WHERE DATE(s.sale_datetime) BETWEEN %s AND %s")
    params = [start, end]
    if category_id:
        sql += " AND p.category_id=%s"
        params.append(category_id)
    sql += " GROUP BY p.product_id ORDER BY qty_sold DESC LIMIT %s"
    params.append(limit)
    return ("product_code", "name", "category", "qty_sold", "revenue"), db.fetch_all(sql, params)


def pending_orders(status=None):
    sql = ("SELECT o.order_ref, c.full_name AS customer, o.collection_datetime, o.status, "
           "o.total_cost, IF(o.is_special,'Yes','No') AS special FROM customer_orders o "
           "JOIN customers c ON c.customer_id=o.customer_id "
           "WHERE o.status NOT IN ('Collected','Cancelled')")
    params = []
    if status:
        sql += " AND o.status=%s"
        params.append(status)
    return (("order_ref", "customer", "collection_datetime", "status", "total_cost", "special"),
            db.fetch_all(sql + " ORDER BY o.collection_datetime", params))


def ingredient_stock():
    rows = inventory.list_ingredients()
    return (("ingredient_code", "name", "unit", "current_quantity", "reorder_level", "status", "next_expiry"),
            rows)


def near_expiry():
    return ("ingredient", "batch_number", "quantity_remaining", "unit", "expiry_date", "state"), \
        inventory.expiring_batches()


def production_vs_waste(start=None, end=None, category_id=None):
    start, end = _range(start, end)
    sql = ("SELECT p.name AS product, COUNT(*) AS batches, SUM(b.planned_quantity) AS planned, "
           "SUM(b.actual_quantity) AS actual, SUM(b.wasted_quantity) AS wasted, "
           "ROUND(100*SUM(b.wasted_quantity)/NULLIF(SUM(b.planned_quantity),0),1) AS waste_pct "
           "FROM production_batches b JOIN products p ON p.product_id=b.product_id "
           "WHERE b.status='Completed' AND b.production_date BETWEEN %s AND %s")
    params = [start, end]
    if category_id:
        sql += " AND p.category_id=%s"
        params.append(category_id)
    return (("product", "batches", "planned", "actual", "wasted", "waste_pct"),
            db.fetch_all(sql + " GROUP BY p.product_id ORDER BY waste_pct DESC", params))


def supplier_deliveries(start=None, end=None):
    start, end = _range(start, end)
    rows = db.fetch_all(
        "SELECT d.delivery_date, s.name AS supplier, d.reference, COUNT(b.batch_id) AS lines_count, "
        "u.username AS received_by FROM ingredient_deliveries d "
        "JOIN suppliers s ON s.supplier_id=d.supplier_id JOIN users u ON u.user_id=d.received_by "
        "LEFT JOIN ingredient_batches b ON b.delivery_id=d.delivery_id "
        "WHERE d.delivery_date BETWEEN %s AND %s GROUP BY d.delivery_id ORDER BY d.delivery_date DESC",
        (start, end))
    return ("delivery_date", "supplier", "reference", "lines_count", "received_by"), rows


def audit_trail(start=None, end=None):
    start, end = _range(start, end)
    rows = db.fetch_all(
        "SELECT a.created_at, u.username, a.action, a.entity, a.entity_id, a.details "
        "FROM audit_log a JOIN users u ON u.user_id=a.user_id "
        "WHERE DATE(a.created_at) BETWEEN %s AND %s ORDER BY a.created_at DESC", (start, end))
    return ("created_at", "username", "action", "entity", "entity_id", "details"), rows


# name shown in the drop-down -> (function, uses date range, uses category, admin only)
REPORTS = {
    "Daily sales": (daily_sales, True, True, False),
    "Monthly sales": (monthly_sales, True, True, False),
    "Best-selling products": (best_sellers, True, True, False),
    "Pending customer orders": (pending_orders, False, False, False),
    "Ingredient stock levels": (ingredient_stock, False, False, False),
    "Ingredients nearing expiry": (near_expiry, False, False, False),
    "Production and wastage": (production_vs_waste, True, True, False),
    "Supplier deliveries": (supplier_deliveries, True, False, False),
    "Audit trail": (audit_trail, True, False, True),
}
