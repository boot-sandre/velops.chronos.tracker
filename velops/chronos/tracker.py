#!/usr/bin/env python3
"""VelOps Chronos Tracker: Track your work time with effortless workflow
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
import sys
import gi

gi.require_version("Gtk", "4.0")  # noqa
from gi.repository import Gtk  # noqa

from velops.chronos.db import DatabaseManager  # noqa
from velops.chronos.ui import MainWindow  # noqa


class VelOpsApp(Gtk.Application):
    _db: DatabaseManager | None = None

    def __init__(self):
        res = super().__init__(application_id="eu.velops.chronos.tracker")
        return res

    def do_activate(self) -> None:
        self._db = DatabaseManager()
        win = MainWindow(application=self, db=self._db)
        win.connect("close-request", self._on_win_close)
        win.present()

    def _on_win_close(self, _win) -> bool:
        if self._db:
            self._db.close()
        return False


def launch_gui() -> None:
    VelOpsApp().run(sys.argv)


if __name__ == "__main__":
    launch_gui()
