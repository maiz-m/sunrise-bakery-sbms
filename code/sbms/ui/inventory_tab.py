"""Ingredients, suppliers, deliveries and stock adjustments screen.

Owner: Ahmed Zahil Zahir
"""
import tkinter as tk
from datetime import date, timedelta
from tkinter import messagebox, simpledialog, ttk

from ..services import inventory
from . import widgets


class InventoryTab(ttk.Frame):
    def __init__(self, master, user):
        super().__init__(master, padding=10)
        self.user = user
        inner = ttk.Notebook(self)
        inner.pack(fill="both", expand=True)

        # --- ingredients ---
        ing = ttk.Frame(inner, padding=8)
        inner.add(ing, text="Ingredient stock")
        bar = ttk.Frame(ing)
        bar.pack(fill="x")
        self.receive_btn = ttk.Button(bar, text="Receive delivery", style="Accent.TButton", command=self.receive)
        self.adjust_btn = ttk.Button(bar, text="Adjust stock", command=self.adjust)
        self.new_ing_btn = ttk.Button(bar, text="New ingredient", command=self.new_ingredient)
        for b, perm in ((self.receive_btn, "deliveries.receive"), (self.adjust_btn, "stock.adjust"),
                        (self.new_ing_btn, "suppliers.manage")):
            b.pack(side="left", padx=(0, 6))
            if not user.can(perm):
                b.state(["disabled"])
        ttk.Label(bar, text="Yellow = low stock, red = out of stock", style="Muted.TLabel").pack(side="right")
        self.ingredients = widgets.DataTable(
            ing, ("ingredient_code", "name", "unit", "current_quantity", "reorder_level", "status",
                  "next_expiry", "supplier"),
            ("Code", "Ingredient", "Unit", "In stock", "Reorder at", "Status", "Next expiry", "Supplier"),
            (90, 170, 50, 90, 90, 70, 100, 170), height=12)
        self.ingredients.pack(fill="both", expand=True, pady=8)
        ttk.Label(ing, text="Expired and near-expiry batches", font=("Helvetica", 13, "bold")).pack(anchor="w")
        self.expiry = widgets.DataTable(
            ing, ("ingredient", "batch_number", "quantity_remaining", "unit", "expiry_date", "state"),
            ("Ingredient", "Batch", "Remaining", "Unit", "Expiry", "State"), (170, 130, 90, 50, 100, 110), height=5)
        self.expiry.pack(fill="x", pady=4)

        # --- suppliers ---
        sup = ttk.Frame(inner, padding=8)
        inner.add(sup, text="Suppliers")
        add_sup = ttk.Button(sup, text="Add supplier", command=self.add_supplier)
        add_sup.pack(anchor="w")
        if not user.can("suppliers.manage"):
            add_sup.state(["disabled"])
        self.suppliers = widgets.DataTable(sup, ("name", "contact_person", "phone", "email", "is_active"),
                                           ("Supplier", "Contact", "Phone", "Email", "Active"),
                                           (220, 160, 100, 220, 60), height=14)
        self.suppliers.pack(fill="both", expand=True, pady=8)

        # --- movements ---
        mov = ttk.Frame(inner, padding=8)
        inner.add(mov, text="Stock movement history")
        self.movements = widgets.DataTable(mov, ("created_at", "item", "movement_type", "quantity", "reference", "username"),
                                           ("When", "Item", "Type", "Qty", "Reference", "By"),
                                           (150, 180, 140, 80, 220, 90), height=18)
        self.movements.pack(fill="both", expand=True)

        self.refresh()

    def refresh(self):
        tags = {"OK": "OK", "LOW": "LOW", "OUT": "BAD"}
        self.ingredient_rows = inventory.list_ingredients()
        self.ingredients.load(self.ingredient_rows, key="ingredient_id", tag=lambda r: tags[r["status"]])
        self.expiry.load(inventory.expiring_batches(), key="batch_id",
                         tag=lambda r: "BAD" if r["state"] == "EXPIRED" else "LOW")
        self.supplier_rows = inventory.list_suppliers()
        self.suppliers.load(self.supplier_rows, key="supplier_id")
        self.movements.load(inventory.movement_history(limit=300))

    def adjust(self):
        iid = self.ingredients.selected()
        if not iid:
            return messagebox.showinfo("Select an ingredient", "Select an ingredient in the table first.", parent=self)
        row = next(r for r in self.ingredient_rows if str(r["ingredient_id"]) == iid)
        change = simpledialog.askstring(
            "Adjust stock", f"{row['name']}: {row['current_quantity']} {row['unit']} in stock.\n"
                            "Enter the change (e.g. -2 for spillage, 5 for a count correction):", parent=self)
        if change is None:
            return
        reason = simpledialog.askstring("Reason", "Why is this adjustment needed?", parent=self)
        if reason is None:
            return
        widgets.run_action(self, lambda: inventory.adjust_stock(self.user, int(iid), change, reason),
                           "Stock adjusted and recorded in the audit log.")
        self.refresh()

    def receive(self):
        DeliveryDialog(self, self.user, self.supplier_rows, self.ingredient_rows, on_saved=self.refresh)

    def add_supplier(self):
        dlg = FormDialog(self, "Add supplier", ["Name", "Contact person", "Phone", "Email"])
        if dlg.values and widgets.run_action(self, lambda: inventory.add_supplier(self.user, *dlg.values),
                                             "Supplier added."):
            self.refresh()

    def new_ingredient(self):
        dlg = FormDialog(self, "New ingredient", ["Code", "Name", "Unit (kg, g, L, ml, pcs)", "Reorder level"])
        if dlg.values and widgets.run_action(self, lambda: inventory.add_ingredient(self.user, *dlg.values),
                                             "Ingredient added."):
            self.refresh()


class FormDialog(tk.Toplevel):
    """Small modal form. After closing, .values is a list of strings or None if cancelled."""

    def __init__(self, master, title, fields):
        super().__init__(master)
        self.title(title)
        self.transient(master)
        self.values = None
        frame = ttk.Frame(self, padding=14)
        frame.pack(fill="both", expand=True)
        self.entries = [widgets.labelled(frame, f, ttk.Entry(frame, width=30), i) for i, f in enumerate(fields)]
        btns = ttk.Frame(frame)
        btns.grid(row=len(fields), column=0, columnspan=2, pady=(10, 0))
        ttk.Button(btns, text="Save", style="Accent.TButton", command=self.ok).pack(side="left", padx=4)
        ttk.Button(btns, text="Cancel", command=self.destroy).pack(side="left")
        self.entries[0].focus_set()
        self.grab_set()
        self.wait_window()

    def ok(self):
        self.values = [e.get() for e in self.entries]
        self.destroy()


class DeliveryDialog(tk.Toplevel):
    """Record one supplier delivery with one or more ingredient batches."""

    def __init__(self, master, user, suppliers, ingredients, on_saved):
        super().__init__(master)
        self.title("Receive ingredient delivery")
        self.transient(master)
        self.user, self.on_saved, self.lines = user, on_saved, []
        f = ttk.Frame(self, padding=14)
        f.pack(fill="both", expand=True)
        self.supplier = widgets.labelled(f, "Supplier", widgets.ComboMap(
            f, [s for s in suppliers if s["is_active"]], "supplier_id", lambda r: r["name"], width=28), 0)
        self.reference = widgets.labelled(f, "Invoice / reference", ttk.Entry(f, width=30), 1)
        self.delivery_date = widgets.labelled(f, "Delivery date", widgets.date_field(f), 2)

        box = ttk.LabelFrame(f, text="Add a batch", padding=8)
        box.grid(row=3, column=0, columnspan=2, sticky="ew", pady=8)
        self.ingredient = widgets.labelled(box, "Ingredient", widgets.ComboMap(
            box, ingredients, "ingredient_id", lambda r: f"{r['name']} ({r['unit']})", width=26), 0)
        self.batch = widgets.labelled(box, "Batch number", ttk.Entry(box, width=28), 1)
        self.qty = widgets.labelled(box, "Quantity", ttk.Entry(box, width=28), 2)
        self.expiry = widgets.labelled(box, "Expiry date", widgets.date_field(box, date.today() + timedelta(days=30)), 3)
        ttk.Button(box, text="Add batch to delivery", command=self.add_line).grid(row=4, column=1, sticky="e")

        self.table = widgets.DataTable(f, ("ingredient", "batch", "qty", "expiry"),
                                       ("Ingredient", "Batch", "Qty", "Expiry"), (180, 120, 70, 100), height=5)
        self.table.grid(row=4, column=0, columnspan=2, sticky="ew")
        btns = ttk.Frame(f)
        btns.grid(row=5, column=0, columnspan=2, pady=(10, 0))
        ttk.Button(btns, text="Save delivery", style="Accent.TButton", command=self.save).pack(side="left", padx=4)
        ttk.Button(btns, text="Cancel", command=self.destroy).pack(side="left")
        self.grab_set()

    def add_line(self):
        if not self.ingredient.get_id():
            return messagebox.showwarning("Missing", "Choose an ingredient.", parent=self)
        self.lines.append((self.ingredient.get_id(), self.batch.get(), self.qty.get(), self.expiry.get()))
        self.table.load(self._rows())
        self.batch.delete(0, "end")
        self.qty.delete(0, "end")

    def _rows(self):
        names = {v: k for k, v in self.ingredient._map.items()}
        return [{"ingredient": names[i], "batch": b, "qty": q, "expiry": e} for (i, b, q, e) in self.lines]

    def save(self):
        ok = widgets.run_action(self, lambda: inventory.receive_delivery(
            self.user, self.supplier.get_id(), self.reference.get(), self.delivery_date.get(), self.lines),
            "Delivery saved and stock updated.")
        if ok:
            self.on_saved()
            self.destroy()
