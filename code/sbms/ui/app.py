"""Main window: login screen, then one tab per module the user's role can use.

Owner: Ahmed Maaiz Mohamed
"""
import tkinter as tk
from datetime import date
from tkinter import messagebox, ttk

from .. import config
from ..errors import SBMSError
from ..services import auth, inventory
from . import widgets
from .admin_tab import AdminTab
from .dashboard_tab import DashboardTab
from .inventory_tab import InventoryTab
from .orders_tab import OrdersTab
from .production_tab import ProductionTab
from .products_tab import ProductsTab
from .sales_tab import SalesTab

# (tab title, class, permission needed to see it)
TABS = [
    ("Dashboard & Reports", DashboardTab, "reports.view"),
    ("Products", ProductsTab, "products.view"),
    ("Ingredients & Suppliers", InventoryTab, "inventory.view"),
    ("Production", ProductionTab, "production.record"),
    ("Customer Orders", OrdersTab, "orders.manage"),
    ("Counter Sales", SalesTab, "sales.record"),
    ("Users", AdminTab, "users.manage"),
]

ICONS = {
    "Dashboard & Reports": "\u25A6", "Products": "\u25CE", "Ingredients & Suppliers": "\u2756",
    "Production": "\u2668", "Customer Orders": "\u270E", "Counter Sales": "\u25A4", "Users": "\u263A",
}


class LoginFrame(ttk.Frame):
    """Centred login card."""

    def __init__(self, master, on_success):
        super().__init__(master)
        self.on_success = on_success
        C = widgets.COLOURS
        band = tk.Frame(self, bg=C["sidebar"], height=150)
        band.pack(fill="x")
        tk.Label(band, text="\u2600  Sunrise Bakery", bg=C["sidebar"], fg="white",
                 font=(widgets.FONT, 26, "bold")).pack(pady=(42, 2))
        tk.Label(band, text="Bakery Management System", bg=C["sidebar"], fg=C["sidebar_text"],
                 font=(widgets.FONT, 14)).pack()

        card = ttk.Frame(self, style="Card.TFrame", padding=32)
        card.place(relx=0.5, rely=0.55, anchor="center")
        ttk.Label(card, text="Staff login", style="CardHeader.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(card, text="Use the account given to you by the administrator.",
                  style="CardTitle.TLabel").grid(row=1, column=0, columnspan=2, sticky="w", pady=(2, 18))
        ttk.Label(card, text="Username", style="Card.TLabel").grid(row=2, column=0, sticky="w")
        self.username = ttk.Entry(card, width=32)
        self.username.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(2, 10))
        ttk.Label(card, text="Password", style="Card.TLabel").grid(row=4, column=0, sticky="w")
        self.password = ttk.Entry(card, width=32, show="\u2022")
        self.password.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(2, 6))
        self.message = ttk.Label(card, text="", foreground="#B00020", style="Card.TLabel")
        self.message.grid(row=6, column=0, columnspan=2, sticky="w", pady=4)
        ttk.Button(card, text="Log in", style="Accent.TButton", command=self.login).grid(
            row=7, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        self.password.bind("<Return>", lambda _e: self.login())
        self.username.bind("<Return>", lambda _e: self.password.focus_set())
        self.username.focus_set()

    def login(self):
        try:
            user = auth.login(self.username.get(), self.password.get())
        except SBMSError as e:
            self.message.config(text=str(e))
            self.password.delete(0, "end")
            return
        except Exception:
            widgets.log.exception("Login failed")
            self.message.config(text="Cannot reach the database. Is MySQL running?")
            return
        self.on_success(user)


class MainFrame(ttk.Frame):
    def __init__(self, master, user, on_logout):
        super().__init__(master)
        self.user = user
        C = widgets.COLOURS

        # header bar
        header = tk.Frame(self, bg=C["sidebar"], height=56)
        header.pack(fill="x")
        tk.Label(header, text="\u2600  Sunrise Bakery", bg=C["sidebar"], fg="white",
                 font=(widgets.FONT, 18, "bold")).pack(side="left", padx=18, pady=12)
        ttk.Button(header, text="Log out", style="Header.TButton", command=on_logout).pack(side="right", padx=14)
        tk.Label(header, text=f" {user.role} ", bg=C["brand"], fg="white",
                 font=(widgets.FONT, 11, "bold")).pack(side="right", padx=(6, 8))
        tk.Label(header, text=user.full_name, bg=C["sidebar"], fg=C["sidebar_text"],
                 font=(widgets.FONT, 13)).pack(side="right")

        # status bar
        status = tk.Frame(self, bg="#EADFD1", height=26)
        status.pack(side="bottom", fill="x")
        tk.Label(status, text=f"Connected to MySQL database '{config.DB_NAME}'", bg="#EADFD1",
                 fg=C["muted"], font=(widgets.FONT, 11)).pack(side="left", padx=12, pady=3)
        tk.Label(status, text=date.today().strftime("%A %d %B %Y"), bg="#EADFD1", fg=C["muted"],
                 font=(widgets.FONT, 11)).pack(side="right", padx=12)

        # sidebar navigation + pages
        self.notebook = ttk.Notebook(self, style="Side.TNotebook")
        self.notebook.pack(fill="both", expand=True)
        self.tabs = []
        for title, cls, permission in TABS:
            if user.can(permission):
                tab = cls(self.notebook, user)
                self.notebook.add(tab, text=f"  {ICONS.get(title, '')}  {title}")
                self.tabs.append(tab)
        # Refresh a tab whenever it is opened so numbers are never stale.
        self.notebook.bind("<<NotebookTabChanged>>", self._tab_changed)

    def _tab_changed(self, _event):
        tab = self.notebook.nametowidget(self.notebook.select())
        if hasattr(tab, "refresh"):
            widgets.run_action(self, tab.refresh)

    def show_stock_warnings(self):
        """Business rule: warn authorised users when stock is at/below reorder level."""
        if not self.user.can("inventory.view"):
            return
        low = inventory.low_stock_ingredients()
        expiring = inventory.expiring_batches()
        if not low and not expiring:
            return
        lines = []
        if low:
            lines.append("Low stock (at or below reorder level):")
            lines += [f"  - {r['name']}: {r['current_quantity']} {r['unit']} (reorder at {r['reorder_level']})"
                      for r in low]
        if expiring:
            lines.append("")
            lines.append("Expired / near expiry:")
            lines += [f"  - {r['ingredient']} batch {r['batch_number']}: {r['state']} {r['expiry_date']}"
                      for r in expiring]
        messagebox.showwarning("Stock warnings", "\n".join(lines), parent=self)


class SBMSApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Sunrise Bakery Management System")
        self.geometry("1440x880")
        self.minsize(1100, 680)
        widgets.apply_style(self)
        self.current = None
        self.show_login()

    def _swap(self, frame):
        if self.current is not None:
            self.current.destroy()
        self.current = frame
        frame.pack(fill="both", expand=True)

    def show_login(self):
        self._swap(LoginFrame(self, self.show_main))

    def show_main(self, user):
        main = MainFrame(self, user, self.show_login)
        self._swap(main)
        self.after(300, lambda: widgets.run_action(main, main.show_stock_warnings))


def main():
    SBMSApp().mainloop()
