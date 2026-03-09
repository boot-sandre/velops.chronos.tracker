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
from velops.chronos.db import DatabaseManager

import gi

gi.require_version("Gtk", "4.0")  # noqa
from gi.repository import Gtk, Pango


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

