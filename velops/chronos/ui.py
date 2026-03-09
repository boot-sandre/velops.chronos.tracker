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

import importlib.resources
from velops.chronos.db import DatabaseManager
from velops.chronos.session import SessionTracker
from velops.chronos.dialog import ConfirmDialog, FieldDialog, TimesheetDialog

import gi

gi.require_version("Gtk", "4.0")  # noqa
from gi.repository import Gtk, GLib, Gdk, Pango  # noqa


class MainWindow(Gtk.ApplicationWindow):
    _C_LABEL = 0  # str  — visible name
    _C_KIND = 1  # str  — 'project' | 'task'
    _C_ID = 2  # int  — DB row id
    _C_PID = 3  # int  — project_id (tasks) | 0 (projects)
    _C_STATUS = 4  # str  — task status | ''

    def __init__(self, application: Gtk.Application, db: DatabaseManager):
        super().__init__(application=application)
        self.db = db
        self.tracker = SessionTracker(db)
        self.set_title("VelOps — Time Tracker")
        self.set_default_size(860, 740)

        # User current selection
        self._sel_project_id: int | None = None
        self._sel_task_id: int | None = None
        self._sel_label: str = ""

        # UI state management
        self._tick_src: int | None = None
        self._is_minimal_mode: bool = False

        # Build
        self._load_css()
        self._build_ui()
        self._refresh_tree()

    def _load_css(self) -> None:
        prov = Gtk.CssProvider()
        css_resource = importlib.resources.files("velops.chronos") / "assets" / "style.css"

        with importlib.resources.as_file(css_resource) as css_path:
            prov.load_from_path(str(css_path))

        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), prov, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def _build_ui(self) -> None:
        self._root_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_child(self._root_box)

        # header bar
        self._hb = Gtk.HeaderBar()
        self._hb.set_show_title_buttons(True)
        ttl = Gtk.Label()
        ttl.set_markup("<b>🦁  VelOps — Time Tracker</b>")
        self._hb.set_title_widget(ttl)
        self.set_titlebar(self._hb)

        self._toolbar = self._mk_toolbar()
        self._root_box.append(self._toolbar)

        self._sep1 = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        self._root_box.append(self._sep1)

        self._tree_sw = Gtk.ScrolledWindow()
        self._tree_sw.set_vexpand(True)
        # self._tree_sw.set_min_content_height(230)
        self._tree_sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self._tree_sw.set_child(self._mk_tree())
        # self._root_box.append(self._tree_sw)

        self._sep2 = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        self._root_box.append(self._sep2)

        self._chrono_panel = self._mk_chrono()
        self._root_box.append(self._chrono_panel)

        self._statusbar = self._mk_statusbar()
        self._root_box.append(self._statusbar)

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

        self._btn_mode = Gtk.Button(label="🔽  Minimal")
        self._btn_mode.set_sensitive(False)
        self._btn_mode.connect("clicked", self._on_toggle_mode)

        self._sel_info = Gtk.Label(label="Nothing selected")
        self._sel_info.set_hexpand(True)
        self._sel_info.set_xalign(1.0)
        self._sel_info.add_css_class("dim-label")

        for w in (
            self._btn_add_proj,
            self._btn_add_task,
            self._btn_del,
            self._btn_ts,
            self._btn_mode,
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
            if not self.tracker.is_active:  #
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

        if not self.tracker.is_active:
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

    def _on_toggle_mode(self, _btn) -> None:
        self._is_minimal_mode = not self._is_minimal_mode

        if self._is_minimal_mode:
            self._btn_mode.set_label("🔼  Standard")
            # Save the window size right before we shrink it
            self._saved_width = self.get_width()
            self._saved_height = self.get_height()
            
            self._hb.set_visible(False)
            
            # Completely remove elements from the layout tree
            self._root_box.remove(self._toolbar)
            self._root_box.remove(self._sep1)
            self._root_box.remove(self._tree_sw)
            self._root_box.remove(self._sep2)
            self._root_box.remove(self._statusbar)

            # We DO NOT use self.set_resizable(False) anymore.
            # Leaving it resizable allows the user to manually shrink the window 
            # to fit the remaining content perfectly.
            self.set_default_size(self._saved_width, 1)
        else:
            self._btn_mode.set_label("🔽  Minimal")
            
            self._hb.set_visible(True)

            # Restore elements into the layout in the correct sequence
            self._root_box.insert_child_after(self._toolbar, None)          # First item
            self._root_box.insert_child_after(self._sep1, self._toolbar)    # After toolbar
            self._root_box.insert_child_after(self._tree_sw, self._sep1)    # After sep1
            self._root_box.insert_child_after(self._sep2, self._tree_sw)    # After tree
            # (self._chrono_panel remains securely in the layout)
            self._root_box.insert_child_after(self._statusbar, self._chrono_panel) # After chrono

            # Restore the previous dimensions
            w = getattr(self, "_saved_width", 860)
            h = getattr(self, "_saved_height", 740)
            self.set_default_size(w, h)

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

    def _tick(self) -> bool:
        """GLib 500 ms heartbeat — refresh the running counter display."""
        work_s, free_s = self.tracker.get_elapsed()  #
        self._work_disp.set_text(self._fmt(work_s))
        self._free_disp.set_text(self._fmt(free_s))
        return True

    def _on_start_switch(self, _btn) -> None:
        if not self.tracker.is_active:  #
            self.tracker.start_or_switch("work")  #
            self._set_card_state("work", "active")
            self._set_card_state("freetime", "paused")
            self._btn_start.set_label("⇄  Switch → Free Time")
            self._btn_stop.set_sensitive(True)
            self._tick_src = GLib.timeout_add(500, self._tick)
            self._info.set_text(f"⏱  Working on: {self._sel_label or '(no selection)'}")

        elif self.tracker.active_kind == "work":  #
            self.tracker.start_or_switch("freetime")  #
            self._set_card_state("work", "paused")
            self._set_card_state("freetime", "active")
            self._btn_start.set_label("⇄  Switch → Work")
            self._info.set_text("☕  Free time running…")

        else:
            self.tracker.start_or_switch("work")  #
            self._set_card_state("freetime", "paused")
            self._set_card_state("work", "active")
            self._btn_start.set_label("⇄  Switch → Free Time")
            self._info.set_text(f"⏱  Working on: {self._sel_label or '(no selection)'}")

    def _on_stop_record(self, _btn) -> None:
        if not self.tracker.is_active:  #
            return

        saved_w, saved_f = self.tracker.stop_and_save(  #
            self._sel_project_id, self._sel_task_id
        )

        if self._tick_src is not None:
            GLib.source_remove(self._tick_src)
            self._tick_src = None

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