"""Shared Tkinter pieces used by every screen: colours, table, date field, error handling."""
import logging
import tkinter as tk
from datetime import date, datetime
from tkinter import messagebox, ttk

from ..errors import SBMSError

try:
    from tkcalendar import DateEntry
except ImportError:  # app still works without the calendar, using a plain text box
    DateEntry = None

log = logging.getLogger("sbms")

COLOURS = {
    "bg": "#F6F1EA",          # page background (warm cream)
    "panel": "#FFFFFF",       # cards, tables, forms
    "sidebar": "#3B2A22",     # espresso brown sidebar and header
    "sidebar_text": "#EADBC8",
    "brand": "#D9822B",       # crust orange: main buttons, selected tab
    "brand_dark": "#A85F17",
    "text": "#2E2622",
    "muted": "#7D6E64",
    "line": "#E3D8CB",
    "ok": "#E4F3E7",
    "low": "#FFF1C9",
    "bad": "#FBDDDB",
}
FONT = "Helvetica"


def apply_style(root):
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    C = COLOURS
    root.configure(bg=C["bg"])
    # Plain tk widgets (Text, Listbox) follow macOS dark mode unless told otherwise.
    for widget in ("Text", "Listbox"):
        root.option_add(f"*{widget}.background", "white")
        root.option_add(f"*{widget}.foreground", C["text"])
        root.option_add(f"*{widget}.selectBackground", C["brand"])
        root.option_add(f"*{widget}.selectForeground", "white")
        root.option_add(f"*{widget}.relief", "flat")
        root.option_add(f"*{widget}.highlightThickness", 1)
        root.option_add(f"*{widget}.highlightColor", C["brand"])
        root.option_add(f"*{widget}.highlightBackground", C["line"])
    root.option_add("*Text.insertBackground", C["text"])

    style.configure(".", background=C["bg"], foreground=C["text"], font=(FONT, 13),
                    bordercolor=C["line"], lightcolor=C["panel"], darkcolor=C["line"])
    style.configure("TLabel", background=C["bg"])
    style.configure("TFrame", background=C["bg"])
    style.configure("TLabelframe", background=C["bg"], bordercolor=C["line"], relief="solid")
    style.configure("TLabelframe.Label", background=C["bg"], foreground=C["brand_dark"], font=(FONT, 13, "bold"))
    style.configure("Header.TLabel", font=(FONT, 20, "bold"), foreground=C["brand_dark"])
    style.configure("Muted.TLabel", foreground=C["muted"])
    style.configure("TEntry", fieldbackground="white", padding=4)
    style.configure("TCombobox", fieldbackground="white", padding=3)

    # cards on the dashboard and the login screen
    style.configure("Card.TFrame", background=C["panel"], relief="solid", borderwidth=1, bordercolor=C["line"])
    style.configure("Card.TLabel", background=C["panel"])
    style.configure("CardValue.TLabel", background=C["panel"], font=(FONT, 24, "bold"), foreground=C["text"])
    style.configure("CardTitle.TLabel", background=C["panel"], foreground=C["muted"], font=(FONT, 12))
    style.configure("CardHeader.TLabel", background=C["panel"], foreground=C["sidebar"], font=(FONT, 22, "bold"))

    # buttons
    style.configure("TButton", padding=(12, 6), background=C["panel"], bordercolor=C["line"])
    style.map("TButton", background=[("active", "#F1E7DA"), ("disabled", C["bg"])])
    style.configure("Accent.TButton", background=C["brand"], foreground="white", padding=(14, 7),
                    bordercolor=C["brand_dark"], font=(FONT, 13, "bold"))
    style.map("Accent.TButton", background=[("active", C["brand_dark"]), ("disabled", "#E9C9A6")])
    style.configure("Header.TButton", background=C["sidebar"], foreground=C["sidebar_text"],
                    bordercolor=C["sidebar_text"], padding=(12, 4))
    style.map("Header.TButton", background=[("active", "#56402F")])

    # tables
    style.configure("Treeview", rowheight=28, font=(FONT, 12), background="white", fieldbackground="white",
                    bordercolor=C["line"])
    style.configure("Treeview.Heading", font=(FONT, 12, "bold"), background="#EFE5D8", foreground=C["text"],
                    relief="flat", padding=(6, 6))
    style.map("Treeview", background=[("selected", C["brand"])], foreground=[("selected", "white")])

    # inner notebooks (e.g. Ingredients / Suppliers / History)
    style.configure("TNotebook", background=C["bg"], borderwidth=0)
    style.configure("TNotebook.Tab", padding=(14, 6), background="#EADFD1", foreground=C["text"])
    style.map("TNotebook.Tab", background=[("selected", C["panel"])], foreground=[("selected", C["brand_dark"])])

    # main navigation: tabs down the left side, styled as a sidebar
    style.configure("Side.TNotebook", tabposition="wn", background=C["sidebar"], borderwidth=0,
                    tabmargins=(0, 12, 0, 0), bordercolor=C["sidebar"], lightcolor=C["bg"], darkcolor=C["bg"])
    style.configure("Side.TNotebook.Tab", padding=(20, 12), width=22, anchor="w", font=(FONT, 13),
                    background=C["sidebar"], foreground=C["sidebar_text"], borderwidth=0,
                    bordercolor=C["sidebar"], lightcolor=C["sidebar"], darkcolor=C["sidebar"],
                    focuscolor=C["sidebar"])
    style.map("Side.TNotebook.Tab",
              background=[("selected", C["brand"]), ("active", "#4E392E")],
              foreground=[("selected", "white")],
              lightcolor=[("selected", C["brand"])], bordercolor=[("selected", C["brand"])],
              expand=[("selected", (0, 0, 0, 0))])


def run_action(parent, action, success=None):
    """Run a service call. Show friendly messages instead of crashing.

    Returns the action's result, or None if it failed.
    """
    try:
        result = action()
    except SBMSError as e:
        messagebox.showwarning("Cannot complete", str(e), parent=parent)
        return None
    except Exception:  # database down, bug, etc.
        log.exception("Unexpected error")
        messagebox.showerror("Something went wrong",
                             "The action could not be completed and nothing was saved.\n"
                             "Check the database connection and try again.", parent=parent)
        return None
    if success:
        messagebox.showinfo("Done", success, parent=parent)
    return result


class DataTable(ttk.Frame):
    """Treeview with a scrollbar. Rows are dicts; `key` column becomes the row id."""

    def __init__(self, master, columns, headings=None, widths=None, height=12):
        super().__init__(master)
        self.columns = list(columns)
        self.tree = ttk.Treeview(self, columns=self.columns, show="headings", height=height,
                                 selectmode="browse")
        headings = headings or [c.replace("_", " ").title() for c in self.columns]
        widths = widths or [120] * len(self.columns)
        for col, head, width in zip(self.columns, headings, widths):
            self.tree.heading(col, text=head)
            self.tree.column(col, width=width, anchor="w", stretch=True)
        bar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=bar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        bar.pack(side="right", fill="y")
        self.tree.tag_configure("OK", background=COLOURS["ok"])
        self.tree.tag_configure("LOW", background=COLOURS["low"])
        self.tree.tag_configure("BAD", background=COLOURS["bad"])

    def load(self, rows, key=None, tag=None):
        self.tree.delete(*self.tree.get_children())
        for i, row in enumerate(rows):
            values = [self._fmt(row.get(c), yes_no=c.startswith("is_")) for c in self.columns]
            iid = str(row[key]) if key else str(i)
            tags = (tag(row),) if tag else ()
            self.tree.insert("", "end", iid=iid, values=values, tags=tags)

    @staticmethod
    def _fmt(value, yes_no=False):
        if value is None:
            return ""
        if isinstance(value, bool) or yes_no:   # MySQL returns BOOLEAN columns as 0/1
            return "Yes" if value else "No"
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M")
        return str(value)

    def selected(self):
        sel = self.tree.selection()
        return sel[0] if sel else None

    def on_select(self, callback):
        self.tree.bind("<<TreeviewSelect>>", lambda _e: callback())


def date_field(master, initial=None, width=12):
    """Date picker if tkcalendar is installed, otherwise a YYYY-MM-DD text box."""
    initial = initial or date.today()
    if DateEntry is not None:
        field = DateEntry(master, width=width, date_pattern="yyyy-mm-dd")
        field.set_date(initial)
        return field
    field = ttk.Entry(master, width=width)
    field.insert(0, initial.isoformat())
    return field


def labelled(master, text, widget, row, column=0, **grid):
    ttk.Label(master, text=text).grid(row=row, column=column, sticky="w", padx=(0, 8), pady=4)
    grid.setdefault("sticky", "ew")
    widget.grid(row=row, column=column + 1, pady=4, **grid)
    return widget


class ComboMap(ttk.Combobox):
    """Combobox that shows names but returns the matching id."""

    def __init__(self, master, rows=(), id_key="id", label=lambda r: str(r), **kw):
        super().__init__(master, state="readonly", **kw)
        self.id_key, self.label = id_key, label
        self.set_rows(rows)

    def set_rows(self, rows):
        self._map = {self.label(r): r[self.id_key] for r in rows}
        self["values"] = list(self._map)

    def get_id(self):
        return self._map.get(self.get())

    def select_id(self, value):
        for text, rid in self._map.items():
            if rid == value:
                self.set(text)
                return
