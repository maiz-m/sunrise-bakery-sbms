"""Manager dashboard and reports screen.

Owner: Ahmed Maaiz Mohamed
"""
import tkinter as tk
from datetime import date, timedelta
from tkinter import ttk

from ..services import products, reports
from . import widgets


class DashboardTab(ttk.Frame):
    def __init__(self, master, user):
        super().__init__(master, padding=14)
        self.user = user

        cards = ttk.Frame(self)
        cards.pack(fill="x")
        self.cards = {}
        for key, title, colour in (("sales_today", "Sales today (MVR)", "#3C8D5A"),
                                   ("sales_month", "This month (MVR)", "#D9822B"),
                                   ("pending_orders", "Pending orders", "#3A6EA5"),
                                   ("batches_today", "To bake today", "#8A5A44"),
                                   ("low_stock", "Low stock", "#C99A06"),
                                   ("expiring", "Expiry alerts", "#C0392B")):
            card = ttk.Frame(cards, style="Card.TFrame")
            card.pack(side="left", fill="both", expand=True, padx=5)
            tk.Frame(card, bg=colour, width=6).pack(side="left", fill="y")
            body = ttk.Frame(card, style="Card.TFrame", padding=(12, 10))
            body.pack(side="left", fill="both", expand=True)
            ttk.Label(body, text=title, style="CardTitle.TLabel").pack(anchor="w")
            value = ttk.Label(body, text="-", style="CardValue.TLabel")
            value.pack(anchor="w")
            self.cards[key] = value

        filters = ttk.LabelFrame(self, text="Reports", padding=10)
        filters.pack(fill="x", pady=10)
        names = [n for n, (_f, _d, _c, admin_only) in reports.REPORTS.items()
                 if not admin_only or user.can("reports.admin")]
        self.report = ttk.Combobox(filters, state="readonly", values=names, width=24)
        self.report.set(names[0])
        self.report.bind("<<ComboboxSelected>>", lambda _e: self.update_filters())
        self.start = widgets.date_field(filters, date.today() - timedelta(days=30))
        self.end = widgets.date_field(filters)
        self.category = widgets.ComboMap(filters, id_key="category_id", label=lambda r: r["name"], width=14)
        for i, (label, w) in enumerate((("Report", self.report), ("From", self.start), ("To", self.end),
                                        ("Category", self.category))):
            ttk.Label(filters, text=label).grid(row=0, column=i * 2, padx=(8, 4))
            w.grid(row=0, column=i * 2 + 1)
        buttons = ttk.Frame(filters)
        buttons.grid(row=1, column=0, columnspan=8, sticky="w", pady=(8, 0))
        ttk.Button(buttons, text="Run report", style="Accent.TButton", command=self.run_report).pack(side="left", padx=(8, 6))
        ttk.Button(buttons, text="All categories", command=lambda: self.category.set("")).pack(side="left")

        self.table_holder = ttk.Frame(self)
        self.table_holder.pack(fill="both", expand=True)
        self.table = None
        self.refresh()

    def refresh(self):
        summary = reports.dashboard_summary()
        for key, label in self.cards.items():
            value = summary[key]
            label.config(text=f"{value:,.2f}" if key.startswith("sales") else str(value))
        self.category.set_rows(products.list_categories())
        self.update_filters()
        self.run_report()

    def update_filters(self):
        _fn, uses_dates, uses_category, _admin = reports.REPORTS[self.report.get()]
        for w in (self.start, self.end):
            w.configure(state="normal" if uses_dates else "disabled")
        self.category.configure(state="readonly" if uses_category else "disabled")

    def run_report(self):
        fn, uses_dates, uses_category, _admin = reports.REPORTS[self.report.get()]
        kwargs = {}
        if uses_dates:
            kwargs["start"], kwargs["end"] = self.start.get(), self.end.get()
        if uses_category:
            kwargs["category_id"] = self.category.get_id()
        result = widgets.run_action(self, lambda: fn(**kwargs))
        if result is None:
            return
        columns, rows = result
        if self.table is not None:
            self.table.destroy()
        self.table = widgets.DataTable(self.table_holder, columns, widths=[140] * len(columns), height=14)
        self.table.pack(fill="both", expand=True)
        self.table.load(rows)
