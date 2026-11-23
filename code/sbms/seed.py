"""Create the SBMS database and fill it with realistic sample data for testing and the demo.

Run:  python -m sbms.seed            (creates/overwrites database `sbms`)
      python -m sbms.seed sbms_test  (used by the automated tests)

All demo accounts use the password in DEMO_PASSWORD. Change them before any real use.
"""
import random
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from . import config, db
from .services.auth import hash_password

DEMO_PASSWORD = "Bakery2026"

USERS = [
    ("admin", "Aishath Shiuna Ahmed", "Administrator"),
    ("manager", "Hassan Rasheed Moosa", "Manager"),
    ("baker", "Mohamed Ziyad Ibrahim", "Production"),
    ("counter", "Mariyam Leena Hussain", "Sales"),
    ("store", "Ali Shareef Abdulla", "Inventory"),
]

CATEGORIES = ["Bread", "Cakes", "Pastries", "Biscuits", "Short Eats"]

# code, name, category, description, price (MVR), shelf stock
PRODUCTS = [
    ("BRD-001", "White Sandwich Loaf", "Bread", "Sliced 600g loaf", "28.00", 20),
    ("BRD-002", "Wholemeal Loaf", "Bread", "Sliced 600g wholemeal", "32.00", 12),
    ("BRD-003", "Dinner Rolls (6 pack)", "Bread", "Soft milk rolls", "18.00", 15),
    ("CAK-001", "Chocolate Fudge Cake", "Cakes", "8 inch, serves 10", "325.00", 3),
    ("CAK-002", "Vanilla Sponge Cake", "Cakes", "8 inch, serves 10", "275.00", 2),
    ("CAK-003", "Cupcake (single)", "Cakes", "Buttercream cupcake", "22.00", 30),
    ("PST-001", "Butter Croissant", "Pastries", "Freshly baked each morning", "20.00", 18),
    ("PST-002", "Chocolate Danish", "Pastries", "Laminated pastry, chocolate filling", "24.00", 10),
    ("BIS-001", "Coconut Biscuits (250g)", "Biscuits", "Made with local coconut", "35.00", 25),
    ("BIS-002", "Butter Cookies (250g)", "Biscuits", "Classic butter cookies", "40.00", 4),
    ("SHT-001", "Bajiya", "Short Eats", "Tuna and onion pastry", "5.00", 60),
    ("SHT-002", "Gulha", "Short Eats", "Fried tuna and coconut balls", "5.00", 50),
    ("SHT-003", "Masroshi", "Short Eats", "Baked roshi filled with tuna and coconut", "6.00", 40),
    ("BRD-004", "Roshi (5 pack)", "Bread", "Maldivian flatbread, made fresh each morning", "15.00", 20),
    ("CAK-004", "Foni Boakiba (slice)", "Cakes", "Sweet rice-flour and coconut cake", "12.00", 24),
]

SUPPLIERS = [
    ("Maafannu Flour & Grocery Traders", "Ibrahim Faisal", "7712345", "orders@maafannutraders.mv"),
    ("Hulhumale' Dairy Supplies", "Fathimath Rifa Ali", "7723456", "sales@hmdairy.mv"),
    ("Thoddoo Fresh Produce", "Ahmed Nashid Mohamed", "9734567", "thoddoofresh@mail.mv"),
    ("Kaafu Atoll Fisheries", "Moosa Hameed Hassan", "7745678", "info@kaafufisheries.mv"),
]

# code, name, unit, reorder level, supplier index
INGREDIENTS = [
    ("ING-FLR", "Plain Flour", "kg", 50, 0),
    ("ING-WHL", "Wholemeal Flour", "kg", 20, 0),
    ("ING-SUG", "Sugar", "kg", 25, 0),
    ("ING-YST", "Dry Yeast", "kg", 2, 0),
    ("ING-BUT", "Butter", "kg", 15, 1),
    ("ING-MLK", "Fresh Milk", "L", 20, 1),
    ("ING-EGG", "Eggs", "pcs", 120, 2),
    ("ING-COC", "Cocoa Powder", "kg", 5, 0),
    ("ING-CHC", "Dark Chocolate", "kg", 4, 0),
    ("ING-CNT", "Grated Coconut", "kg", 8, 2),
    ("ING-TUN", "Tuna (cooked)", "kg", 6, 3),
    ("ING-ONI", "Onion", "kg", 5, 2),
    ("ING-OIL", "Cooking Oil", "L", 10, 0),
    ("ING-RCF", "Rice Flour", "kg", 10, 0),
]

# product code -> (standard yield, {ingredient code: quantity for that yield})
RECIPES = {
    "BRD-001": (10, {"ING-FLR": 6, "ING-YST": 0.1, "ING-SUG": 0.2, "ING-MLK": 1, "ING-BUT": 0.3}),
    "BRD-002": (10, {"ING-WHL": 6, "ING-YST": 0.1, "ING-SUG": 0.15}),
    "BRD-003": (10, {"ING-FLR": 3, "ING-YST": 0.05, "ING-MLK": 1, "ING-BUT": 0.3, "ING-EGG": 6}),
    "CAK-001": (1, {"ING-FLR": 0.4, "ING-SUG": 0.4, "ING-BUT": 0.3, "ING-EGG": 6, "ING-COC": 0.15, "ING-CHC": 0.3}),
    "CAK-002": (1, {"ING-FLR": 0.4, "ING-SUG": 0.35, "ING-BUT": 0.3, "ING-EGG": 6, "ING-MLK": 0.2}),
    "CAK-003": (12, {"ING-FLR": 0.3, "ING-SUG": 0.3, "ING-BUT": 0.25, "ING-EGG": 4}),
    "PST-001": (20, {"ING-FLR": 2, "ING-BUT": 1.2, "ING-YST": 0.04, "ING-MLK": 0.5, "ING-SUG": 0.1}),
    "PST-002": (20, {"ING-FLR": 2, "ING-BUT": 1.2, "ING-CHC": 0.6, "ING-YST": 0.04}),
    "BIS-001": (10, {"ING-FLR": 1.5, "ING-SUG": 0.8, "ING-CNT": 1, "ING-BUT": 0.5}),
    "BIS-002": (10, {"ING-FLR": 1.5, "ING-SUG": 0.6, "ING-BUT": 1, "ING-EGG": 4}),
    "SHT-001": (50, {"ING-FLR": 1.5, "ING-TUN": 1, "ING-ONI": 0.5, "ING-OIL": 1}),
    "SHT-002": (50, {"ING-FLR": 1, "ING-TUN": 1, "ING-CNT": 0.8, "ING-OIL": 1}),
    "SHT-003": (40, {"ING-FLR": 2, "ING-TUN": 1.2, "ING-CNT": 0.8, "ING-ONI": 0.4, "ING-OIL": 0.3}),
    "BRD-004": (50, {"ING-FLR": 3, "ING-OIL": 0.2}),
    "CAK-004": (24, {"ING-RCF": 1.5, "ING-SUG": 1, "ING-CNT": 1, "ING-EGG": 6, "ING-BUT": 0.2}),
}

# ingredient code -> list of (quantity remaining, days until expiry). Negative days = expired.
STOCK = {
    "ING-FLR": [(40, 60), (45, 120)],
    "ING-WHL": [(30, 45)],
    "ING-SUG": [(60, 200)],
    "ING-YST": [(3, 90)],
    "ING-BUT": [(8, 2), (10, 20)],        # one batch near expiry
    "ING-MLK": [(6, -1), (18, 4)],        # one batch already expired
    "ING-EGG": [(300, 12)],
    "ING-COC": [(0.4, 150)],              # below reorder level - chocolate cake will be short
    "ING-CHC": [(5, 100)],
    "ING-CNT": [(4, 3)],                  # low and near expiry
    "ING-TUN": [(12, 2)],
    "ING-ONI": [(9, 10)],
    "ING-OIL": [(25, 180)],
    "ING-RCF": [(18, 90)],
}


def run_schema(cur):
    sql = (Path(__file__).parent / "schema.sql").read_text()
    lines = [l for l in sql.splitlines() if not l.strip().startswith("--")]
    for statement in "\n".join(lines).split(";"):
        if statement.strip():
            cur.execute(statement)


def seed(database):
    rnd = random.Random(2026)  # fixed seed so every member gets the same data
    conn = db.get_connection(database="")
    with conn.cursor() as cur:
        cur.execute(f"CREATE DATABASE IF NOT EXISTS `{database}` CHARACTER SET utf8mb4")
    conn.close()

    conn = db.get_connection(database=database)
    cur = conn.cursor()
    run_schema(cur)

    pw = hash_password(DEMO_PASSWORD)
    user_ids = {}
    for username, name, role in USERS:
        cur.execute("INSERT INTO users (username, password_hash, full_name, role) VALUES (%s,%s,%s,%s)",
                    (username, pw, name, role))
        user_ids[username] = cur.lastrowid
    cur.execute("INSERT INTO users (username, password_hash, full_name, role, is_active) "
                "VALUES ('former', %s, 'Former Staff', 'Sales', FALSE)", (pw,))

    cat_ids = {}
    for c in CATEGORIES:
        cur.execute("INSERT INTO product_categories (name) VALUES (%s)", (c,))
        cat_ids[c] = cur.lastrowid

    prod_ids = {}
    for code, name, cat, desc, price, stock in PRODUCTS:
        cur.execute("INSERT INTO products (product_code, name, category_id, description, selling_price, "
                    "stock_quantity) VALUES (%s,%s,%s,%s,%s,%s)",
                    (code, name, cat_ids[cat], desc, price, stock))
        prod_ids[code] = cur.lastrowid

    sup_ids = []
    for s in SUPPLIERS:
        cur.execute("INSERT INTO suppliers (name, contact_person, phone, email) VALUES (%s,%s,%s,%s)", s)
        sup_ids.append(cur.lastrowid)

    ing_ids = {}
    for code, name, unit, reorder, sup in INGREDIENTS:
        cur.execute("INSERT INTO ingredients (ingredient_code, name, unit, reorder_level, supplier_id) "
                    "VALUES (%s,%s,%s,%s,%s)", (code, name, unit, reorder, sup_ids[sup]))
        ing_ids[code] = cur.lastrowid

    # One delivery per supplier a week ago, holding the batches in STOCK.
    today = date.today()
    deliveries = {}
    for i, sid in enumerate(sup_ids):
        cur.execute("INSERT INTO ingredient_deliveries (supplier_id, delivery_date, reference, received_by) "
                    "VALUES (%s,%s,%s,%s)", (sid, today - timedelta(days=7 - i), f"INV-{2400 + i}", user_ids["store"]))
        deliveries[sid] = cur.lastrowid
    sup_of = {code: sup_ids[s] for code, _, _, _, s in INGREDIENTS}
    for code, batches in STOCK.items():
        total = Decimal(0)
        for n, (qty, days) in enumerate(batches, start=1):
            qty = Decimal(str(qty))
            cur.execute("INSERT INTO ingredient_batches (delivery_id, ingredient_id, batch_number, "
                        "quantity_received, quantity_remaining, expiry_date) VALUES (%s,%s,%s,%s,%s,%s)",
                        (deliveries[sup_of[code]], ing_ids[code], f"{code[4:]}-{today:%y%m}-{n:02d}",
                         qty, qty, today + timedelta(days=days)))
            cur.execute("INSERT INTO stock_movements (ingredient_id, movement_type, quantity, reference, "
                        "user_id, created_at) VALUES (%s,'DELIVERY',%s,%s,%s,%s)",
                        (ing_ids[code], qty, "Opening stock", user_ids["store"],
                         datetime.combine(today - timedelta(days=7), datetime.min.time())))
            total += qty
        cur.execute("UPDATE ingredients SET current_quantity=%s WHERE ingredient_id=%s", (total, ing_ids[code]))

    recipe_ids = {}
    for code, (yield_, lines) in RECIPES.items():
        cur.execute("INSERT INTO recipes (product_id, standard_yield) VALUES (%s,%s)", (prod_ids[code], yield_))
        recipe_ids[code] = cur.lastrowid
        for ing, qty in lines.items():
            cur.execute("INSERT INTO recipe_ingredients (recipe_id, ingredient_id, quantity) VALUES (%s,%s,%s)",
                        (recipe_ids[code], ing_ids[ing], qty))

    # 30 days of history: completed production batches and counter sales.
    prices = {p[0]: Decimal(p[4]) for p in PRODUCTS}
    def add_sales(day, count, latest=None):
        start = datetime.combine(day, datetime.min.time()) + timedelta(hours=7)
        end = latest or datetime.combine(day, datetime.min.time()) + timedelta(hours=21)
        if end <= start:
            return
        for _ in range(count):
            when = start + timedelta(seconds=rnd.randint(0, int((end - start).total_seconds())))
            basket = rnd.sample([p[0] for p in PRODUCTS], rnd.randint(1, 3))
            lines = [(c, rnd.randint(1, 6) if c[:3] in ("SHT", "PST", "BRD") else 1) for c in basket]
            total = sum(prices[c] * q for c, q in lines)
            cur.execute("INSERT INTO sales (sale_datetime, staff_id, total, payment_method) VALUES (%s,%s,%s,%s)",
                        (when, user_ids["counter"], total, rnd.choice(["Cash", "Cash", "Card", "Bank Transfer"])))
            sid = cur.lastrowid
            for c, q in lines:
                cur.execute("INSERT INTO sale_items (sale_id, product_id, quantity, unit_price) VALUES (%s,%s,%s,%s)",
                            (sid, prod_ids[c], q, prices[c]))

    daily = ["BRD-001", "BRD-003", "BRD-004", "PST-001", "SHT-001", "SHT-002", "SHT-003", "CAK-003"]
    for d in range(30, 0, -1):
        day = today - timedelta(days=d)
        for code in daily + rnd.sample([p[0] for p in PRODUCTS if p[0] not in daily], 2):
            planned = {"SHT": 100, "BRD": 30, "PST": 40, "CAK": 24, "BIS": 20}[code[:3]]
            if code in ("CAK-001", "CAK-002"):
                planned = 3
            wasted = rnd.randint(0, max(1, planned // 10))
            actual = planned - wasted - rnd.randint(0, max(1, planned // 20))
            cur.execute("INSERT INTO production_batches (product_id, recipe_id, planned_quantity, actual_quantity, "
                        "wasted_quantity, production_date, staff_id, status, completed_at) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s,'Completed',%s)",
                        (prod_ids[code], recipe_ids[code], planned, actual, wasted, day, user_ids["baker"],
                         datetime.combine(day, datetime.min.time()) + timedelta(hours=6)))
        add_sales(day, rnd.randint(12, 25))
    # A few sales earlier today so the dashboard has today's figures.
    add_sales(today, 6, latest=datetime.now())

    # Today's plan: one batch that has enough stock, one that will be short (cocoa).
    for code, qty in (("BRD-001", 30), ("CAK-001", 4), ("SHT-001", 100)):
        cur.execute("INSERT INTO production_batches (product_id, recipe_id, planned_quantity, production_date, "
                    "staff_id) VALUES (%s,%s,%s,%s,%s)",
                    (prod_ids[code], recipe_ids[code], qty, today, user_ids["manager"]))

    # Customers and orders in different stages.
    customers = [("Aminath Shifa Rasheed", "7901122"), ("Ibrahim Rameez Ali", "7912233"),
                 ("Hawwa Nazeera Mohamed", "9923344"), ("Yoosuf Areef Hassan", "7934455"),
                 ("Fathimath Raufa Ibrahim", "9945566"), ("Ahmed Shifaz Abdulla", "7956677")]
    cust_ids = []
    for name, phone in customers:
        cur.execute("INSERT INTO customers (full_name, phone) VALUES (%s,%s)", (name, phone))
        cust_ids.append(cur.lastrowid)
    orders = [
        (0, "Received", False, [("BRD-003", 5), ("SHT-001", 30)], 1, None),
        (1, "Confirmed", True, [("CAK-001", 1)], 2,
         ("Happy 10th Birthday Zaid in blue icing", "10 inch", "Chocolate", "Football theme, blue and white")),
        (2, "In Preparation", False, [("PST-001", 12), ("PST-002", 6)], 1, None),
        (3, "Collected", False, [("BIS-001", 2)], -3, None),
        (4, "Ready for Collection", False, [("SHT-003", 30), ("SHT-001", 30)], 1, None),
        (5, "Received", True, [("CAK-002", 2)], 5,
         ("Wedding cake with 'Shifaz & Raufa' in gold lettering", "2 tier", "Vanilla and pandan",
          "White icing with frangipani flowers")),
    ]
    for n, (ci, status, special, items, days, sp) in enumerate(orders, start=1):
        total = sum(prices[c] * q for c, q in items)
        cur.execute(
            "INSERT INTO customer_orders (order_ref, customer_id, order_date, collection_datetime, total_cost, "
            "status, is_special, special_instructions, cake_size, flavour, design_notes, items_prepared, created_by) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (f"ORD-{today:%y%m%d}-S{n:02d}", cust_ids[ci], datetime.now() - timedelta(days=2),
             datetime.combine(today + timedelta(days=days), datetime.min.time()) + timedelta(hours=16),
             total, status, special, *(sp or (None, None, None, None)), status in ("Collected", "Ready for Collection"),
             user_ids["counter"]))
        oid = cur.lastrowid
        for c, q in items:
            cur.execute("INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (%s,%s,%s,%s)",
                        (oid, prod_ids[c], q, prices[c]))

    conn.commit()
    conn.close()


if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else config.DB_NAME
    seed(name)
    print(f"Database '{name}' created with sample data. Demo password for all accounts: {DEMO_PASSWORD}")
