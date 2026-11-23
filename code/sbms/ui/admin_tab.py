"""User account management (Administrator only).

Owner: Ahmed Maaiz Mohamed
"""
from tkinter import messagebox, ttk

from ..services import auth
from . import widgets


class AdminTab(ttk.Frame):
    def __init__(self, master, user):
        super().__init__(master, padding=10)
        self.user = user
        self.table = widgets.DataTable(self, ("username", "full_name", "role", "is_active", "created_at"),
                                       ("Username", "Full name", "Role", "Active", "Created"),
                                       (120, 200, 120, 70, 160), height=12)
        self.table.pack(fill="both", expand=True)

        actions = ttk.Frame(self)
        actions.pack(fill="x", pady=8)
        ttk.Button(actions, text="Activate / deactivate", command=self.toggle).pack(side="left")
        self.new_role = ttk.Combobox(actions, state="readonly", values=auth.ROLES, width=14)
        self.new_role.pack(side="left", padx=(16, 4))
        ttk.Button(actions, text="Change role", command=self.change_role).pack(side="left")

        form = ttk.LabelFrame(self, text="Create account", padding=10)
        form.pack(fill="x")
        self.username = widgets.labelled(form, "Username", ttk.Entry(form, width=24), 0)
        self.full_name = widgets.labelled(form, "Full name", ttk.Entry(form, width=24), 1)
        self.role = widgets.labelled(form, "Role", ttk.Combobox(form, state="readonly", values=auth.ROLES, width=22), 2)
        self.password = widgets.labelled(form, "Temporary password", ttk.Entry(form, width=24, show="*"), 3)
        ttk.Label(form, text="At least 8 characters with letters and numbers. Stored as a bcrypt hash.",
                  style="Muted.TLabel").grid(row=4, column=1, sticky="w")
        ttk.Button(form, text="Create account", style="Accent.TButton", command=self.create).grid(row=5, column=1, sticky="w", pady=6)
        self.refresh()

    def refresh(self):
        self.rows = {str(r["user_id"]): r for r in auth.list_users()}
        self.table.load(list(self.rows.values()), key="user_id", tag=lambda r: "" if r["is_active"] else "BAD")

    def toggle(self):
        uid = self.table.selected()
        if not uid:
            return messagebox.showinfo("Select a user", "Select an account first.", parent=self)
        active = not self.rows[uid]["is_active"]
        widgets.run_action(self, lambda: auth.set_user_active(self.user, int(uid), active))
        self.refresh()

    def change_role(self):
        uid = self.table.selected()
        if uid and self.new_role.get():
            widgets.run_action(self, lambda: auth.change_role(self.user, int(uid), self.new_role.get()))
            self.refresh()

    def create(self):
        if widgets.run_action(self, lambda: auth.create_user(self.user, self.username.get(), self.full_name.get(),
                                                             self.role.get(), self.password.get()), "Account created."):
            for e in (self.username, self.full_name, self.password):
                e.delete(0, "end")
            self.refresh()
