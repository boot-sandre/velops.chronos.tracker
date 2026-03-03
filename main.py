#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║  LynxAI Time Tracker  ·  v1.0                                  ║
║  Stack : GTK4 · Python 3.10+ · SQLite3 (stdlib)                ║
║  DB    : ~/.local/share/lynxai/timetracker.db                   ║
╠══════════════════════════════════════════════════════════════════╣
║  Install deps                                                   ║
║   Ubuntu/Debian : sudo apt install python3-gi gir1.2-gtk-4.0   ║
║   Fedora        : sudo dnf install python3-gobject gtk4         ║
║   Arch          : sudo pacman -S python-gobject gtk4            ║
╚══════════════════════════════════════════════════════════════════╝
"""

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib, Gdk, Pango

import sqlite3, time, os
from datetime import datetime
from pathlib import Path


# ══════════════════════════════════════════════════════════════════════════════
# § 1  DATABASE MANAGER
# ══════════════════════════════════════════════════════════════════════════════


class DatabaseManager:
    """
    SQLite connector.
    Creates (if not exist) three tables: project · task · timesheet
    """

    def __init__(self, db_path: str | None = None):
        if db_path is None:
            base = Path.home() / ".local" / "share" / "lynxai"
            base.mkdir(parents=True, exist_ok=True)
            db_path = str(base / "timetracker.db")
        self._path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._create_schema()

    # ── schema ────────────────────────────────────────────────────────────────
    def _create_schema(self) -> None:
        self._conn.executescript("""
        -- ── Table: project ──────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS project (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL UNIQUE,
            description TEXT    NOT NULL DEFAULT '',
            color       TEXT    NOT NULL DEFAULT '#3584e4',
            created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
            updated_at  TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        -- ── Table: task ──────────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS task (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id  INTEGER NOT NULL,
            name        TEXT    NOT NULL,
            description TEXT    NOT NULL DEFAULT '',
            status      TEXT    NOT NULL DEFAULT 'pending'
                                 CHECK (status IN
                                   ('pending','in_progress','done','cancelled')),
            created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
            updated_at  TEXT    NOT NULL DEFAULT (datetime('now')),
            UNIQUE (project_id, name),
            FOREIGN KEY (project_id) REFERENCES project(id) ON DELETE CASCADE
        );

        -- ── Table: timesheet ─────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS timesheet (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id       INTEGER,
            task_id          INTEGER,
            entry_type       TEXT    NOT NULL
                                     CHECK (entry_type IN ('work','freetime')),
            start_time       TEXT    NOT NULL,
            end_time         TEXT,
            duration_seconds INTEGER NOT NULL DEFAULT 0,
            notes            TEXT    NOT NULL DEFAULT '',
            created_at       TEXT    NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (project_id) REFERENCES project(id) ON DELETE SET NULL,
            FOREIGN KEY (task_id)    REFERENCES task(id)    ON DELETE SET NULL
        );

        CREATE INDEX IF NOT EXISTS idx_task_proj ON task(project_id);
        CREATE INDEX IF NOT EXISTS idx_ts_proj   ON timesheet(project_id);
        CREATE INDEX IF NOT EXISTS idx_ts_task   ON timesheet(task_id);
        CREATE INDEX IF NOT EXISTS idx_ts_start  ON timesheet(start_time);
        """)
        self._conn.commit()

    # ── project CRUD ──────────────────────────────────────────────────────────
    def get_projects(self) -> list:
        return self._conn.execute(
            "SELECT id, name, description, color FROM project ORDER BY name"
        ).fetchall()

    def add_project(
        self, name: str, description: str = "", color: str = "#3584e4"
    ) -> int:
        cur = self._conn.execute(
            "INSERT INTO project(name,description,color) VALUES(?,?,?)",
            (name, description, color),
        )
        self._conn.commit()
        return cur.lastrowid

    def delete_project(self, pid: int) -> None:
        self._conn.execute("DELETE FROM project WHERE id=?", (pid,))
        self._conn.commit()

    # ── task CRUD ─────────────────────────────────────────────────────────────
    def get_tasks(self, project_id: int) -> list:
        return self._conn.execute(
            "SELECT id, project_id, name, description, status "
            "FROM task WHERE project_id=? ORDER BY name",
            (project_id,),
        ).fetchall()

    def add_task(
        self, project_id: int, name: str, description: str = "", status: str = "pending"
    ) -> int:
        cur = self._conn.execute(
            "INSERT INTO task(project_id,name,description,status) VALUES(?,?,?,?)",
            (project_id, name, description, status),
        )
        self._conn.commit()
        return cur.lastrowid

    def delete_task(self, tid: int) -> None:
        self._conn.execute("DELETE FROM task WHERE id=?", (tid,))
        self._conn.commit()

    # ── timesheet ─────────────────────────────────────────────────────────────
    def record_session(
        self,
        project_id,
        task_id,
        entry_type: str,
        start_time: str,
        end_time: str,
        duration_seconds: int,
        notes: str = "",
    ) -> int:
        cur = self._conn.execute(
            "INSERT INTO timesheet"
            "(project_id,task_id,entry_type,start_time,end_time,"
            " duration_seconds,notes)"
            " VALUES(?,?,?,?,?,?,?)",
            (
                project_id,
                task_id,
                entry_type,
                start_time,
                end_time,
                duration_seconds,
                notes,
            ),
        )
        self._conn.commit()
        return cur.lastrowid

    def get_sessions(self, project_id=None, task_id=None, limit: int = 200) -> list:
        where, params = [], []
        if project_id:
            where.append("ts.project_id=?")
            params.append(project_id)
        if task_id:
            where.append("ts.task_id=?")
            params.append(task_id)
        clause = ("WHERE " + " AND ".join(where)) if where else ""
        return self._conn.execute(
            f"""
            SELECT ts.id, p.name AS proj, t.name AS task,
                   ts.entry_type, ts.start_time, ts.end_time, ts.duration_seconds
            FROM   timesheet ts
            LEFT JOIN project p ON ts.project_id = p.id
            LEFT JOIN task    t ON ts.task_id    = t.id
            {clause}
            ORDER BY ts.start_time DESC LIMIT ?
        """,
            params + [limit],
        ).fetchall()

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None


# ══════════════════════════════════════════════════════════════════════════════
# § 2  CSS  (Catppuccin Mocha palette)
# ══════════════════════════════════════════════════════════════════════════════

APP_CSS = """
/* ── root ──────────────────────────────────────────────────── */
window              { background-color: #1e1e2e; color: #cdd6f4; }

/* ── tree ──────────────────────────────────────────────────── */
treeview            { background-color: #181825; color: #cdd6f4; }
treeview:selected   { background-color: #45475a; color: #cdd6f4; }
treeview header button {
    background-color: #313244;
    color: #a6adc8;
    font-weight: bold;
    font-size: 12px;
    padding: 6px 10px;
    border: none;
    border-bottom: 1px solid #45475a;
}

/* ── toolbar ────────────────────────────────────────────────── */
.toolbar {
    background-color: #181825;
    padding: 6px 12px;
    border-bottom: 1px solid #313244;
}
.toolbar button { border-radius: 6px; padding: 5px 14px; font-size: 13px; }

/* ── chrono panel ───────────────────────────────────────────── */
.chrono-panel {
    background-color: #11111b;
    border-top: 1px solid #313244;
}
.chrono-title {
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 3px;
    color: #585b70;
}

/* ── timer card ─────────────────────────────────────────────── */
.timer-box {
    background-color: #1e1e2e;
    border-radius: 12px;
    padding: 14px 20px;
    margin: 4px;
    min-width: 200px;
    min-height: 108px;
}
.timer-work     { border-top: 3px solid #89b4fa; }
.timer-free     { border-top: 3px solid #a6e3a1; }
.timer-glow     { border: 2px solid #cba6f7; border-radius: 12px; }

.timer-title {
    font-size: 10px;
    font-weight: bold;
    letter-spacing: 2px;
    color: #a6adc8;
    margin-bottom: 6px;
}
.timer-display {
    font-size: 36px;
    font-weight: bold;
    font-family: "JetBrains Mono","Fira Code","Monospace";
    color: #cdd6f4;
    margin: 2px 0;
}
.timer-state { font-size: 11px; font-weight: bold; letter-spacing: 1px; }
.state-active { color: #a6e3a1; }
.state-paused { color: #fab387; }
.state-idle   { color: #585b70; }

/* ── action buttons ─────────────────────────────────────────── */
.btn-start {
    background-color: #89b4fa;
    color: #1e1e2e;
    font-weight: bold;
    border-radius: 999px;
    padding: 8px 28px;
    font-size: 13px;
    border: none;
    min-width: 190px;
}
.btn-start:hover  { background-color: #b4d0fb; }
.btn-start:disabled { opacity: 0.45; }

.btn-stop {
    background-color: #f38ba8;
    color: #1e1e2e;
    font-weight: bold;
    border-radius: 999px;
    padding: 8px 28px;
    font-size: 13px;
    border: none;
    min-width: 190px;
}
.btn-stop:hover    { background-color: #f7b8c8; }
.btn-stop:disabled { opacity: 0.35; }

/* suggested / destructive (dialogs) */
button.suggested-action  { background-color: #89b4fa; color: #1e1e2e; font-weight: bold; }
button.destructive-action{ background-color: #f38ba8; color: #1e1e2e; font-weight: bold; }

/* ── misc ───────────────────────────────────────────────────── */
.dim-label { color: #6c7086; font-size: 12px; }
.info-bar  { background-color: #181825; padding: 5px 14px;
             border-top: 1px solid #313244; }
"""


# ══════════════════════════════════════════════════════════════════════════════
# § 3  DIALOGS
# ══════════════════════════════════════════════════════════════════════════════


class FieldDialog(Gtk.Dialog):
    """Generic form dialog — one Gtk.Entry per field tuple (label, key, hint)."""

    def __init__(
        self, parent: Gtk.Window, title: str, fields: list[tuple[str, str, str]]
    ):
        super().__init__(
            title=title, transient_for=parent, modal=True, use_header_bar=1
        )
        self.set_default_size(380, -1)
        self.add_button("Cancel", Gtk.ResponseType.CANCEL)
        ok = self.add_button("  OK  ", Gtk.ResponseType.OK)
        ok.add_css_class("suggested-action")
        self.set_default_response(Gtk.ResponseType.OK)

        body = self.get_content_area()
        body.set_spacing(5)
        body.set_margin_top(14)
        body.set_margin_bottom(14)
        body.set_margin_start(18)
        body.set_margin_end(18)

        self._entries: dict[str, Gtk.Entry] = {}
        for lbl_text, key, hint in fields:
            lbl = Gtk.Label(label=lbl_text)
            lbl.set_xalign(0)
            lbl.add_css_class("dim-label")
            entry = Gtk.Entry()
            entry.set_placeholder_text(hint)
            entry.set_activates_default(True)
            body.append(lbl)
            body.append(entry)
            self._entries[key] = entry

    def values(self) -> dict[str, str]:
        return {k: e.get_text().strip() for k, e in self._entries.items()}


class TimesheetDialog(Gtk.Dialog):
    """
    Read-only timesheet viewer for a selected project or task.
    Columns: #  · Type · Start · End · Duration
    """

    def __init__(
        self,
        parent: Gtk.Window,
        db: DatabaseManager,
        label: str,
        project_id: int | None,
        task_id: int | None,
    ):
        super().__init__(
            title=f"Timesheet — {label}",
            transient_for=parent,
            modal=True,
            use_header_bar=1,
        )
        self.set_default_size(720, 400)
        close = self.add_button("Close", Gtk.ResponseType.CLOSE)
        close.add_css_class("suggested-action")
        self.connect("response", lambda d, _: d.destroy())

        # ── ListStore: id · type · start · end · duration ─────────────────
        store = Gtk.ListStore(int, str, str, str, str)
        rows = db.get_sessions(project_id=project_id, task_id=task_id)
        for r in rows:
            h, rem = divmod(r["duration_seconds"], 3600)
            m, s = divmod(rem, 60)
            store.append(
                [
                    r["id"],
                    "⚙ work" if r["entry_type"] == "work" else "☕ free",
                    (r["start_time"] or "")[:19],
                    (r["end_time"] or "")[:19],
                    f"{h:02d}:{m:02d}:{s:02d}",
                ]
            )

        tv = Gtk.TreeView(model=store)
        tv.set_headers_visible(True)
        tv.set_enable_tree_lines(False)

        def _col(title, idx, min_w, expand=False):
            r = Gtk.CellRendererText()
            r.set_property("ellipsize", Pango.EllipsizeMode.END)
            c = Gtk.TreeViewColumn(title, r, text=idx)
            c.set_min_width(min_w)
            c.set_expand(expand)
            c.set_resizable(True)
            tv.append_column(c)

        _col("#", 0, 50)
        _col("Type", 1, 90)
        _col("Start", 2, 160, expand=True)
        _col("End", 3, 160, expand=True)
        _col("Duration", 4, 90)

        sw = Gtk.ScrolledWindow()
        sw.set_vexpand(True)
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        sw.set_child(tv)

        # ── summary footer ─────────────────────────────────────────────────
        total_w = sum(r["duration_seconds"] for r in rows if r["entry_type"] == "work")
        total_f = sum(
            r["duration_seconds"] for r in rows if r["entry_type"] == "freetime"
        )

        def _fmt(s):
            h, r = divmod(s, 3600)
            m, sc = divmod(r, 60)
            return f"{h:02d}:{m:02d}:{sc:02d}"

        summary = Gtk.Label()
        summary.set_markup(
            f"<b>{len(rows)}</b> sessions  ·  "
            f"⚙ work <b>{_fmt(total_w)}</b>  ·  "
            f"☕ free <b>{_fmt(total_f)}</b>"
        )
        summary.add_css_class("dim-label")
        summary.set_margin_top(8)
        summary.set_margin_bottom(8)

        body = self.get_content_area()
        body.set_spacing(0)
        body.append(sw)
        body.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        body.append(summary)


class ConfirmDialog(Gtk.Dialog):
    """Minimal yes/no confirmation dialog."""

    def __init__(self, parent: Gtk.Window, heading: str, detail: str):
        super().__init__(
            title="Confirm", transient_for=parent, modal=True, use_header_bar=0
        )
        self.add_button("Cancel", Gtk.ResponseType.CANCEL)
        d = self.add_button("Delete", Gtk.ResponseType.OK)
        d.add_css_class("destructive-action")
        self.set_default_response(Gtk.ResponseType.CANCEL)

        area = self.get_content_area()
        area.set_spacing(6)
        area.set_margin_top(16)
        area.set_margin_bottom(16)
        area.set_margin_start(18)
        area.set_margin_end(18)

        h = Gtk.Label()
        h.set_markup(f"<b>{heading}</b>")
        h.set_xalign(0)
        b = Gtk.Label(label=detail)
        b.set_xalign(0)
        b.add_css_class("dim-label")
        area.append(h)
        area.append(b)


# ══════════════════════════════════════════════════════════════════════════════
# § 4  MAIN WINDOW
# ══════════════════════════════════════════════════════════════════════════════


class MainWindow(Gtk.ApplicationWindow):
    # TreeStore column indices ─────────────────────────────────────────────────
    _C_LABEL = 0  # str  — visible name
    _C_KIND = 1  # str  — 'project' | 'task'
    _C_ID = 2  # int  — DB row id
    _C_PID = 3  # int  — project_id (tasks) | 0 (projects)
    _C_STATUS = 4  # str  — task status | ''

    def __init__(self, application: Gtk.Application, db: DatabaseManager):
        super().__init__(application=application)
        self.db = db
        self.set_title("LynxAI — Time Tracker")
        self.set_default_size(860, 740)

        # ── selection state ───────────────────────────────────────────────────
        self._sel_project_id: int | None = None
        self._sel_task_id: int | None = None
        self._sel_label: str = ""

        # ── chronometer state ─────────────────────────────────────────────────
        self._active: str | None = None  # 'work' | 'freetime' | None
        self._work_secs: int = 0
        self._free_secs: int = 0
        self._work_t0: float | None = None
        self._free_t0: float | None = None
        self._tick_src: int | None = None
        self._session_start: str | None = None

        # ── build ─────────────────────────────────────────────────────────────
        self._load_css()
        self._build_ui()
        self._refresh_tree()

    # ── CSS ───────────────────────────────────────────────────────────────────
    def _load_css(self) -> None:
        prov = Gtk.CssProvider()
        prov.load_from_data(APP_CSS)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), prov, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    # ── UI builders ───────────────────────────────────────────────────────────
    def _build_ui(self) -> None:
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_child(root)

        # header bar
        hb = Gtk.HeaderBar()
        hb.set_show_title_buttons(True)
        ttl = Gtk.Label()
        ttl.set_markup("<b>🦁  LynxAI — Time Tracker</b>")
        hb.set_title_widget(ttl)
        self.set_titlebar(hb)

        root.append(self._mk_toolbar())
        root.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        sw = Gtk.ScrolledWindow()
        sw.set_vexpand(True)
        sw.set_min_content_height(230)
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        sw.set_child(self._mk_tree())
        root.append(sw)

        root.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        root.append(self._mk_chrono())
        root.append(self._mk_statusbar())

    # ── toolbar ───────────────────────────────────────────────────────────────
    def _mk_toolbar(self) -> Gtk.Box:
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        bar.add_css_class("toolbar")

        self._btn_add_proj = Gtk.Button(label="＋ Project")
        self._btn_add_proj.add_css_class("suggested-action")
        self._btn_add_proj.connect("clicked", self._on_add_project)

        self._btn_add_task = Gtk.Button(label="＋ Task")
        self._btn_add_task.add_css_class("suggested-action")
        self._btn_add_task.set_sensitive(False)
        self._btn_add_task.connect("clicked", self._on_add_task)

        self._btn_del = Gtk.Button(label="🗑  Delete")
        self._btn_del.add_css_class("destructive-action")
        self._btn_del.set_sensitive(False)
        self._btn_del.connect("clicked", self._on_delete)

        self._btn_ts = Gtk.Button(label="📊  Timesheet")
        self._btn_ts.set_sensitive(False)
        self._btn_ts.connect("clicked", self._on_show_timesheet)

        self._sel_info = Gtk.Label(label="Nothing selected")
        self._sel_info.set_hexpand(True)
        self._sel_info.set_xalign(1.0)
        self._sel_info.add_css_class("dim-label")

        for w in (
            self._btn_add_proj,
            self._btn_add_task,
            self._btn_del,
            self._btn_ts,
            self._sel_info,
        ):
            bar.append(w)
        return bar

    # ── tree view ─────────────────────────────────────────────────────────────
    def _mk_tree(self) -> Gtk.TreeView:
        # columns: label · kind · id · project_id · status
        self._store = Gtk.TreeStore(str, str, int, int, str)

        tv = Gtk.TreeView(model=self._store)
        tv.set_headers_visible(True)
        tv.set_enable_tree_lines(True)
        tv.get_selection().set_mode(Gtk.SelectionMode.SINGLE)
        tv.get_selection().connect("changed", self._on_tree_sel)
        self._tv = tv

        def _col(title, idx, min_w, expand=False):
            r = Gtk.CellRendererText()
            r.set_property("ellipsize", Pango.EllipsizeMode.END)
            c = Gtk.TreeViewColumn(title, r, text=idx)
            c.set_min_width(min_w)
            c.set_expand(expand)
            c.set_resizable(True)
            tv.append_column(c)

        _col("Project / Task", self._C_LABEL, 220, expand=True)
        _col("Type", self._C_KIND, 80)
        _col("Status", self._C_STATUS, 110)
        return tv

    # ── chronometer panel ─────────────────────────────────────────────────────
    def _mk_chrono(self) -> Gtk.Box:
        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        panel.add_css_class("chrono-panel")

        ttl = Gtk.Label(label="⏱   T I M E   T R A C K I N G")
        ttl.add_css_class("chrono-title")
        ttl.set_margin_top(14)
        ttl.set_margin_bottom(10)
        panel.append(ttl)

        # ── two timer cards ────────────────────────────────────────────────
        cards = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, spacing=14, homogeneous=True
        )
        cards.set_margin_start(16)
        cards.set_margin_end(16)
        cards.set_margin_bottom(12)
        cards.append(self._mk_card("work"))
        cards.append(self._mk_card("freetime"))
        panel.append(cards)

        # ── control buttons ────────────────────────────────────────────────
        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        btn_row.set_halign(Gtk.Align.CENTER)
        btn_row.set_margin_bottom(12)

        self._btn_start = Gtk.Button(label="▶  Start")
        self._btn_start.add_css_class("btn-start")
        self._btn_start.connect("clicked", self._on_start_switch)

        self._btn_stop = Gtk.Button(label="⏹  Stop & Record")
        self._btn_stop.add_css_class("btn-stop")
        self._btn_stop.set_sensitive(False)
        self._btn_stop.connect("clicked", self._on_stop_record)

        btn_row.append(self._btn_start)
        btn_row.append(self._btn_stop)
        panel.append(btn_row)
        return panel

    def _mk_card(self, kind: str) -> Gtk.Box:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        card.add_css_class("timer-box")
        card.add_css_class("timer-work" if kind == "work" else "timer-free")

        icon = "⚙" if kind == "work" else "☕"
        label = "WORK" if kind == "work" else "FREE TIME"

        ttl = Gtk.Label(label=f"{icon}  {label}")
        ttl.add_css_class("timer-title")
        ttl.set_xalign(0.5)

        disp = Gtk.Label(label="00:00:00")
        disp.add_css_class("timer-display")
        disp.set_xalign(0.5)

        state = Gtk.Label(label="● IDLE")
        state.add_css_class("timer-state")
        state.add_css_class("state-idle")
        state.set_xalign(0.5)

        card.append(ttl)
        card.append(disp)
        card.append(state)

        if kind == "work":
            self._work_disp = disp
            self._work_state = state
            self._work_card = card
        else:
            self._free_disp = disp
            self._free_state = state
            self._free_card = card
        return card

    # ── status bar ────────────────────────────────────────────────────────────
    def _mk_statusbar(self) -> Gtk.Box:
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        bar.add_css_class("info-bar")
        self._info = Gtk.Label(label="Select a project or task, then press  ▶ Start")
        self._info.add_css_class("dim-label")
        self._info.set_hexpand(True)
        self._info.set_xalign(0)
        bar.append(self._info)
        return bar

    # ── tree helpers ──────────────────────────────────────────────────────────
    def _refresh_tree(self) -> None:
        self._store.clear()
        for p in self.db.get_projects():
            pit = self._store.append(None, [p["name"], "project", p["id"], 0, ""])
            for t in self.db.get_tasks(p["id"]):
                self._store.append(
                    pit, [t["name"], "task", t["id"], t["project_id"], t["status"]]
                )
        self._tv.expand_all()

    def _selected(self) -> tuple | None:
        model, it = self._tv.get_selection().get_selected()
        if it is None:
            return None
        return tuple(model.get_value(it, i) for i in range(5))
        # → (label, kind, id, pid, status)

    # ── selection changed ─────────────────────────────────────────────────────
    def _on_tree_sel(self, _sel: Gtk.TreeSelection) -> None:
        data = self._selected()
        if data is None:
            self._btn_add_task.set_sensitive(False)
            self._btn_del.set_sensitive(False)
            self._sel_project_id = None
            self._sel_task_id = None
            self._sel_label = ""
            self._sel_info.set_text("Nothing selected")
            if self._active is None:
                self._info.set_text("Select a project or task, then press  ▶ Start")
            return

        label, kind, row_id, pid, status = data
        self._btn_del.set_sensitive(True)
        self._sel_label = label

        if kind == "project":
            self._sel_project_id = row_id
            self._sel_task_id = None
            self._btn_add_task.set_sensitive(True)
            self._btn_ts.set_sensitive(True)
            self._sel_info.set_text(f"📁  {label}")
        else:
            self._sel_project_id = pid
            self._sel_task_id = row_id
            self._btn_add_task.set_sensitive(False)
            self._btn_ts.set_sensitive(True)
            self._sel_info.set_text(f"📌  {label}  [{status}]")

        if self._active is None:
            self._info.set_text(
                f"Will track: {'project' if kind == 'project' else 'task'} — {label}"
            )

    def _on_show_timesheet(self, _btn) -> None:
        if self._sel_project_id is None and self._sel_task_id is None:
            return
        dlg = TimesheetDialog(
            self, self.db, self._sel_label, self._sel_project_id, self._sel_task_id
        )
        dlg.show()

    # ── CRUD — add project ────────────────────────────────────────────────────
    def _on_add_project(self, _btn) -> None:
        dlg = FieldDialog(
            self,
            "New Project",
            [
                ("Name", "name", "e.g. Backend API"),
                ("Description", "desc", "Optional description"),
            ],
        )
        dlg.connect("response", self._resp_add_project)
        dlg.show()

    def _resp_add_project(self, dlg: FieldDialog, resp: int) -> None:
        if resp == Gtk.ResponseType.OK:
            v = dlg.values()
            if v.get("name"):
                self.db.add_project(v["name"], v.get("desc", ""))
                self._refresh_tree()
        dlg.destroy()

    # ── CRUD — add task ───────────────────────────────────────────────────────
    def _on_add_task(self, _btn) -> None:
        if self._sel_project_id is None:
            return
        dlg = FieldDialog(
            self,
            "New Task",
            [
                ("Name", "name", "e.g. Implement OAuth"),
                ("Description", "desc", "Optional description"),
            ],
        )
        dlg.connect("response", self._resp_add_task)
        dlg.show()

    def _resp_add_task(self, dlg: FieldDialog, resp: int) -> None:
        if resp == Gtk.ResponseType.OK:
            v = dlg.values()
            if v.get("name") and self._sel_project_id:
                self.db.add_task(self._sel_project_id, v["name"], v.get("desc", ""))
                self._refresh_tree()
        dlg.destroy()

    # ── CRUD — delete ─────────────────────────────────────────────────────────
    def _on_delete(self, _btn) -> None:
        data = self._selected()
        if data is None:
            return
        label, kind, row_id, *_ = data
        extra = " All its tasks will also be removed." if kind == "project" else ""
        dlg = ConfirmDialog(
            self, f'Delete {kind} "{label}"?', f"This action cannot be undone.{extra}"
        )
        dlg.connect("response", self._resp_delete, kind, row_id)
        dlg.show()

    def _resp_delete(self, dlg, resp, kind, row_id) -> None:
        if resp == Gtk.ResponseType.OK:
            (self.db.delete_project if kind == "project" else self.db.delete_task)(
                row_id
            )
            self._refresh_tree()
        dlg.destroy()

    # ── timer helpers ─────────────────────────────────────────────────────────
    @staticmethod
    def _fmt(secs: int) -> str:
        h, r = divmod(max(0, secs), 3600)
        m, s = divmod(r, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    def _set_card_state(self, kind: str, state: str) -> None:
        """state ∈ { 'active', 'paused', 'idle' }"""
        lbl = self._work_state if kind == "work" else self._free_state
        card = self._work_card if kind == "work" else self._free_card
        for cls in ("state-active", "state-paused", "state-idle", "timer-glow"):
            lbl.remove_css_class(cls)
            card.remove_css_class(cls)
        if state == "active":
            lbl.set_text("● RUNNING")
            lbl.add_css_class("state-active")
            card.add_css_class("timer-glow")
        elif state == "paused":
            lbl.set_text("⏸  PAUSED")
            lbl.add_css_class("state-paused")
        else:
            lbl.set_text("● IDLE")
            lbl.add_css_class("state-idle")

    def _freeze_active(self) -> None:
        """Snapshot running elapsed time into accumulator."""
        now = time.monotonic()
        if self._active == "work" and self._work_t0 is not None:
            self._work_secs += int(now - self._work_t0)
            self._work_t0 = None
            self._work_disp.set_text(self._fmt(self._work_secs))
        elif self._active == "freetime" and self._free_t0 is not None:
            self._free_secs += int(now - self._free_t0)
            self._free_t0 = None
            self._free_disp.set_text(self._fmt(self._free_secs))

    def _tick(self) -> bool:
        """GLib 500 ms heartbeat — refresh the running counter display."""
        now = time.monotonic()
        if self._active == "work" and self._work_t0 is not None:
            self._work_disp.set_text(
                self._fmt(self._work_secs + int(now - self._work_t0))
            )
        elif self._active == "freetime" and self._free_t0 is not None:
            self._free_disp.set_text(
                self._fmt(self._free_secs + int(now - self._free_t0))
            )
        return True  # keep GLib source alive

    # ── ▶  START / SWITCH ─────────────────────────────────────────────────────
    def _on_start_switch(self, _btn) -> None:
        now = time.monotonic()

        if self._active is None:
            # ── initial start: begin WORK ─────────────────────────────────
            self._session_start = datetime.now().isoformat(timespec="seconds")
            self._work_t0 = now
            self._active = "work"
            self._set_card_state("work", "active")
            self._set_card_state("freetime", "paused")
            self._btn_start.set_label("⇄  Switch → Free Time")
            self._btn_stop.set_sensitive(True)
            self._tick_src = GLib.timeout_add(500, self._tick)
            self._info.set_text(f"⏱  Working on: {self._sel_label or '(no selection)'}")

        elif self._active == "work":
            # ── work → freetime ───────────────────────────────────────────
            self._freeze_active()
            self._free_t0 = now
            self._active = "freetime"
            self._set_card_state("work", "paused")
            self._set_card_state("freetime", "active")
            self._btn_start.set_label("⇄  Switch → Work")
            self._info.set_text("☕  Free time running…")

        else:
            # ── freetime → work ───────────────────────────────────────────
            self._freeze_active()
            self._work_t0 = now
            self._active = "work"
            self._set_card_state("freetime", "paused")
            self._set_card_state("work", "active")
            self._btn_start.set_label("⇄  Switch → Free Time")
            self._info.set_text(f"⏱  Working on: {self._sel_label or '(no selection)'}")

    # ── ⏹  STOP & RECORD ────────────────────────────────────────────────────
    def _on_stop_record(self, _btn) -> None:
        if self._active is None:
            return

        self._freeze_active()
        now_dt = datetime.now().isoformat(timespec="seconds")
        start = self._session_start or now_dt

        if self._work_secs > 0:
            self.db.record_session(
                self._sel_project_id,
                self._sel_task_id,
                "work",
                start,
                now_dt,
                self._work_secs,
            )

        if self._free_secs > 0:
            self.db.record_session(
                self._sel_project_id,
                self._sel_task_id,
                "freetime",
                start,
                now_dt,
                self._free_secs,
            )

        saved_w = self._work_secs
        saved_f = self._free_secs

        # ── full reset ────────────────────────────────────────────────────
        if self._tick_src is not None:
            GLib.source_remove(self._tick_src)
            self._tick_src = None

        self._active = None
        self._work_secs = self._free_secs = 0
        self._work_t0 = self._free_t0 = None
        self._session_start = None

        self._work_disp.set_text("00:00:00")
        self._free_disp.set_text("00:00:00")
        self._set_card_state("work", "idle")
        self._set_card_state("freetime", "idle")

        self._btn_start.set_label("▶  Start")
        self._btn_stop.set_sensitive(False)
        self._info.set_text(
            f"✅  Saved — work: {self._fmt(saved_w)}  |  free: {self._fmt(saved_f)}"
        )

    # ── cleanup ───────────────────────────────────────────────────────────────
    def do_close_request(self) -> bool:
        if self._tick_src is not None:
            GLib.source_remove(self._tick_src)
        return False  # allow window to close


# ══════════════════════════════════════════════════════════════════════════════
# § 5  APPLICATION ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════


class LynxAIApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="ai.lynx.timetracker")
        self._db: DatabaseManager | None = None

    def do_activate(self) -> None:
        self._db = DatabaseManager()
        win = MainWindow(application=self, db=self._db)
        win.connect("close-request", self._on_win_close)
        win.present()

    def _on_win_close(self, _win) -> bool:
        if self._db:
            self._db.close()
        return False


def main() -> None:
    LynxAIApp().run()


if __name__ == "__main__":
    main()
