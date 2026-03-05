#!/usr/bin/env python3
"""
VelOps Chronos Tracker: Track your work time with effortless workflow
Copyright (C) 2026  Simon ANDRÉ

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import time
from datetime import datetime
import importlib.resources
from velops.chronos.db import DatabaseManager

import gi

gi.require_version("Gtk", "4.0")  # noqa
from gi.repository import Gtk, GLib, Gdk, Pango  # noqa


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


class MainWindow(Gtk.ApplicationWindow):
    _C_LABEL = 0  # str  — visible name
    _C_KIND = 1  # str  — 'project' | 'task'
    _C_ID = 2  # int  — DB row id
    _C_PID = 3  # int  — project_id (tasks) | 0 (projects)
    _C_STATUS = 4  # str  — task status | ''

    def __init__(self, application: Gtk.Application, db: DatabaseManager):
        super().__init__(application=application)
        self.db = db
        self.set_title("VelOps — Time Tracker")
        self.set_default_size(860, 740)

        # User current selection
        self._sel_project_id: int | None = None
        self._sel_task_id: int | None = None
        self._sel_label: str = ""

        # Chronometer state
        self._active: str | None = None  # 'work' | 'freetime' | None
        self._work_secs: int = 0
        self._free_secs: int = 0
        self._work_t0: float | None = None
        self._free_t0: float | None = None
        self._tick_src: int | None = None
        self._session_start: str | None = None

        # Build
        self._load_css()
        self._build_ui()
        self._refresh_tree()

    def _load_css(self) -> None:
        prov = Gtk.CssProvider()
        css_resource = importlib.resources.files("velops.chronos") / "style.css"

        with importlib.resources.as_file(css_resource) as css_path:
            prov.load_from_path(str(css_path))

        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), prov, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def _build_ui(self) -> None:
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_child(root)

        # header bar
        hb = Gtk.HeaderBar()
        hb.set_show_title_buttons(True)
        ttl = Gtk.Label()
        ttl.set_markup("<b>🦁  VelOps — Time Tracker</b>")
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

    def _mk_chrono(self) -> Gtk.Box:
        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        panel.add_css_class("chrono-panel")

        ttl = Gtk.Label(label="⏱   T I M E   T R A C K I N G")
        ttl.add_css_class("chrono-title")
        ttl.set_margin_top(14)
        ttl.set_margin_bottom(10)
        panel.append(ttl)

        # Two timer cards
        cards = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, spacing=14, homogeneous=True
        )
        cards.set_margin_start(16)
        cards.set_margin_end(16)
        cards.set_margin_bottom(12)
        cards.append(self._mk_card("work"))
        cards.append(self._mk_card("freetime"))
        panel.append(cards)

        # Control buttons
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

    def _mk_statusbar(self) -> Gtk.Box:
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        bar.add_css_class("info-bar")
        self._info = Gtk.Label(label="Select a project or task, then press  ▶ Start")
        self._info.add_css_class("dim-label")
        self._info.set_hexpand(True)
        self._info.set_xalign(0)
        bar.append(self._info)
        return bar

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

    def _on_start_switch(self, _btn) -> None:
        now = time.monotonic()

        if self._active is None:
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
            self._freeze_active()
            self._free_t0 = now
            self._active = "freetime"
            self._set_card_state("work", "paused")
            self._set_card_state("freetime", "active")
            self._btn_start.set_label("⇄  Switch → Work")
            self._info.set_text("☕  Free time running…")

        else:
            self._freeze_active()
            self._work_t0 = now
            self._active = "work"
            self._set_card_state("freetime", "paused")
            self._set_card_state("work", "active")
            self._btn_start.set_label("⇄  Switch → Free Time")
            self._info.set_text(f"⏱  Working on: {self._sel_label or '(no selection)'}")

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
            f"Saved — work: {self._fmt(saved_w)}  |  free: {self._fmt(saved_f)}"
        )

    def do_close_request(self) -> bool:
        if self._tick_src is not None:
            GLib.source_remove(self._tick_src)
        return False  # allow window to close
