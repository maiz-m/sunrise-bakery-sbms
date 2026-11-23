"""Product catalogue screen.

Owner: Ahmed Zahil Zahir
"""
import tkinter as tk
from tkinter import messagebox, ttk

from .. import config
from ..services import products
from . import widgets


class ProductsTab(ttk.Frame):
    def __init__(self, master, user):
        super().__init__(master, padding=10)
        self.user = user
        self.can_edit = user.can("products.edit")

        # search bar
        bar = ttk.Frame(self)
        bar.pack(fill="x")
        ttk.Label(bar, text="Search").pack(side="left")
        self.search = ttk.Entry(bar, width=30)
        self.search.pack(side="left", padx=6)
        self.search.bind("<Return>", lambda _e: self.refresh())
        ttk.Label(bar, text="Category").pack(side="left", padx=(12, 0))
        self.category_filter = widgets.ComboMap(bar, id_key="category_id", label=lambda r: r["name"], width=14)
        self.category_filter.pack(side="left", padx=6)
        self.category_filter.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        ttk.Button(bar, text="Search", command=self.refresh).pack(side="left")
        ttk.Button(bar, text="Clear", command=self.clear_filters).pack(side="left", padx=4)

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True, pady=8)
        self.table = widgets.DataTable(
            body,
            ("product_code", "name", "category", "selling_price", "stock_quantity", "availability", "active"),
            ("Code", "Name", "Category", "Price (MVR)", "On shelf", "Availability", "Active"),
            (90, 220, 110, 100, 80, 110, 60), height=18)
        self.table.pack(side="left", fill="both", expand=True)
        self.table.on_select(self.fill_form)

        # edit form (only for roles allowed to edit)
        form = ttk.LabelFrame(body, text="Product details", padding=10)
        form.pack(side="right", fill="y", padx=(10, 0))
        self.code = widgets.labelled(form, "Code", ttk.Entry(form, width=24), 0)
        self.name = widgets.labelled(form, "Name", ttk.Entry(form, width=24), 1)
        self.category = widgets.labelled(
            form, "Category", widgets.ComboMap(form, id_key="category_id", label=lambda r: r["name"], width=22), 2)
        self.price = widgets.labelled(form, "Price (MVR)", ttk.Entry(form, width=24), 3)
        ttk.Label(form, text="Description").grid(row=4, column=0, sticky="nw", pady=4)
        self.description = tk.Text(form, width=24, height=4, font=("Helvetica", 12))
        self.description.grid(row=4, column=1, pady=4)
        buttons = ttk.Frame(form)
        buttons.grid(row=5, column=0, columnspan=2, pady=(10, 0))
        self.add_btn = ttk.Button(buttons, text="Add new", style="Accent.TButton", command=self.add)
        self.save_btn = ttk.Button(buttons, text="Save changes", command=self.save)
        self.toggle_btn = ttk.Button(buttons, text="Deactivate", command=self.toggle_active)
        for b in (self.add_btn, self.save_btn, self.toggle_btn):
            b.pack(fill="x", pady=2)
        ttk.Button(buttons, text="New / clear form", command=self.clear_form).pack(fill="x", pady=2)
        if not self.can_edit:
            for w in (self.add_btn, self.save_btn, self.toggle_btn):
                w.state(["disabled"])
            ttk.Label(form, text="View only for your role", style="Muted.TLabel").grid(row=6, column=0, columnspan=2)

        self.rows = {}
        self.refresh()

    def refresh(self):
        cats = products.list_categories()
        self.category.set_rows(cats)
        self.category_filter.set_rows(cats)
        rows = products.list_products(self.search.get(), self.category_filter.get_id())
        for r in rows:
            if not r["is_active"]:
                r["availability"] = "Inactive"
            elif r["stock_quantity"] == 0:
                r["availability"] = "Sold out"
            elif r["stock_quantity"] <= config.LOW_PRODUCT_STOCK:
                r["availability"] = "Low"
            else:
                r["availability"] = "Available"
            r["active"] = bool(r["is_active"])
        self.rows = {str(r["product_id"]): r for r in rows}
        tags = {"Available": "OK", "Low": "LOW", "Sold out": "BAD", "Inactive": "BAD"}
        self.table.load(rows, key="product_id", tag=lambda r: tags[r["availability"]])

    def clear_filters(self):
        self.search.delete(0, "end")
        self.category_filter.set("")
        self.refresh()

    def fill_form(self):
        row = self.rows.get(self.table.selected())
        if not row:
            return
        self.clear_form(keep_selection=True)
        self.code.insert(0, row["product_code"])
        self.name.insert(0, row["name"])
        self.category.select_id(row["category_id"])
        self.price.insert(0, str(row["selling_price"]))
        self.description.insert("1.0", row["description"] or "")
        self.toggle_btn.config(text="Deactivate" if row["is_active"] else "Reactivate")

    def clear_form(self, keep_selection=False):
        for e in (self.code, self.name, self.price):
            e.delete(0, "end")
        self.category.set("")
        self.description.delete("1.0", "end")
        if not keep_selection:
            self.table.tree.selection_remove(self.table.tree.selection())

    def _values(self):
        return (self.code.get(), self.name.get(), self.category.get_id(),
                self.description.get("1.0", "end"), self.price.get())

    def add(self):
        if widgets.run_action(self, lambda: products.add_product(self.user, *self._values()),
                              "Product added."):
            self.clear_form()
            self.refresh()

    def save(self):
        pid = self.table.selected()
        if not pid:
            return messagebox.showinfo("Select a product", "Select a product in the table first.", parent=self)
        if widgets.run_action(self, lambda: products.update_product(self.user, int(pid), *self._values()) or True,
                              "Product updated."):
            self.refresh()

    def toggle_active(self):
        pid = self.table.selected()
        if not pid:
            return
        active = not self.rows[pid]["is_active"]
        widgets.run_action(self, lambda: products.set_active(self.user, int(pid), active))
        self.refresh()
