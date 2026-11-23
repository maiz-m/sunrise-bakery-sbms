"""Production planning and batch recording screen.

Owner: Ahmed Zahil Zahir
"""
from datetime import date
from tkinter import messagebox, simpledialog, ttk

from ..services import production, products
from . import widgets


class ProductionTab(ttk.Frame):
    def __init__(self, master, user):
        super().__init__(master, padding=10)
        self.user = user

        # --- plan (managers) ---
        plan = ttk.LabelFrame(self, text="Plan a batch", padding=10)
        plan.pack(fill="x")
        self.product = widgets.ComboMap(plan, id_key="product_id",
                                        label=lambda r: f"{r['product_code']}  {r['name']}", width=34)
        self.qty = ttk.Entry(plan, width=8)
        self.day = widgets.date_field(plan)
        ttk.Label(plan, text="Product").grid(row=0, column=0, sticky="w")
        self.product.grid(row=0, column=1, padx=6)
        ttk.Label(plan, text="Quantity").grid(row=0, column=2)
        self.qty.grid(row=0, column=3, padx=6)
        ttk.Label(plan, text="Date").grid(row=0, column=4)
        self.day.grid(row=0, column=5, padx=6)
        buttons = ttk.Frame(plan)
        buttons.grid(row=1, column=0, columnspan=6, sticky="w", pady=(8, 0))
        ttk.Button(buttons, text="Estimate ingredients", command=self.estimate).pack(side="left", padx=(0, 6))
        self.plan_btn = ttk.Button(buttons, text="Add to plan", style="Accent.TButton", command=self.add_plan)
        self.plan_btn.pack(side="left")
        if not user.can("production.plan"):
            self.plan_btn.state(["disabled"])

        self.estimate_table = widgets.DataTable(
            self, ("ingredient", "unit", "needed", "available", "short"),
            ("Ingredient", "Unit", "Needed", "Available (not expired)", "Short by"), (200, 60, 100, 170, 100), height=6)
        self.estimate_table.pack(fill="x", pady=8)

        # --- batches ---
        bar = ttk.Frame(self)
        bar.pack(fill="x")
        ttk.Label(bar, text="Batches", font=("Helvetica", 13, "bold")).pack(side="left")
        self.status = ttk.Combobox(bar, state="readonly", values=["", "Planned", "Completed", "Cancelled"], width=12)
        self.status.set("Planned")
        self.status.pack(side="left", padx=8)
        self.status.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        ttk.Button(bar, text="Record output", style="Accent.TButton", command=self.complete).pack(side="right")
        cancel = ttk.Button(bar, text="Cancel batch", command=self.cancel)
        cancel.pack(side="right", padx=6)
        if not user.can("production.plan"):
            cancel.state(["disabled"])
        ttk.Button(bar, text="Check stock for selected", command=self.check_selected).pack(side="right")

        self.batches = widgets.DataTable(
            self, ("production_batch_id", "production_date", "product", "planned_quantity", "actual_quantity",
                   "wasted_quantity", "status", "staff"),
            ("#", "Date", "Product", "Planned", "Actual", "Wasted", "Status", "Staff"),
            (50, 100, 220, 80, 80, 80, 100, 150), height=12)
        self.batches.pack(fill="both", expand=True, pady=6)
        self.refresh()

    def refresh(self):
        self.product.set_rows(products.list_products(active_only=True))
        self.rows = {str(r["production_batch_id"]): r for r in production.list_batches(status=self.status.get() or None)}
        self.batches.load(list(self.rows.values()), key="production_batch_id",
                          tag=lambda r: {"Completed": "OK", "Cancelled": "BAD"}.get(r["status"], ""))

    def _show_estimate(self, needs):
        self.estimate_table.load(needs, key="ingredient_id", tag=lambda r: "BAD" if r["short"] > 0 else "OK")

    def estimate(self):
        if not self.product.get_id():
            return messagebox.showinfo("Choose a product", "Choose a product first.", parent=self)
        result = widgets.run_action(self, lambda: production.estimate_requirements(self.product.get_id(), self.qty.get()))
        if result:
            self._show_estimate(result[1])

    def add_plan(self):
        result = widgets.run_action(self, lambda: production.plan_batch(
            self.user, self.product.get_id(), self.qty.get(), self.day.get()))
        if result is None:
            return
        _batch_id, shortages = result
        if shortages:
            messagebox.showwarning(
                "Added, but stock is short",
                "The batch is planned, but it cannot be finalised until these arrive:\n" +
                "\n".join(f"- {s['ingredient']}: short by {s['short']} {s['unit']}" for s in shortages), parent=self)
        else:
            messagebox.showinfo("Planned", "Batch added to the plan. All ingredients are in stock.", parent=self)
        self.refresh()

    def _selected(self):
        bid = self.batches.selected()
        if not bid:
            messagebox.showinfo("Select a batch", "Select a batch in the table first.", parent=self)
        return bid

    def check_selected(self):
        bid = self._selected()
        if bid:
            row = self.rows[bid]
            result = widgets.run_action(self, lambda: production.estimate_requirements(
                row["product_id"], row["planned_quantity"]))
            if result:
                self._show_estimate(result[1])

    def complete(self):
        bid = self._selected()
        if not bid:
            return
        row = self.rows[bid]
        if row["status"] != "Planned":
            return messagebox.showinfo("Not planned", f"This batch is already {row['status'].lower()}.", parent=self)
        actual = simpledialog.askstring("Record output", f"{row['product']} - planned {row['planned_quantity']}.\n"
                                        "Good units produced:", parent=self)
        if actual is None:
            return
        wasted = simpledialog.askstring("Record waste", "Damaged or wasted units:", initialvalue="0", parent=self)
        if wasted is None:
            return
        widgets.run_action(self, lambda: production.complete_batch(self.user, int(bid), actual, wasted),
                           "Batch completed. Ingredients deducted and products added to the shelf.")
        self.refresh()

    def cancel(self):
        bid = self._selected()
        if bid and messagebox.askyesno("Cancel batch", "Cancel this planned batch?", parent=self):
            widgets.run_action(self, lambda: production.cancel_batch(self.user, int(bid)))
            self.refresh()
