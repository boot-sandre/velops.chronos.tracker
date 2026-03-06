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
from typing import Optional, Tuple
from velops.chronos.db import DatabaseManager


class SessionTracker:
    """
    Manages the state of a timing session.
    Separates the timing logic from the UI.
    """

    def __init__(self, db: DatabaseManager):
        self._db = db
        self._active_kind: Optional[str] = None  # 'work' | 'freetime' | None
        self._work_secs: int = 0
        self._free_secs: int = 0
        self._t0: Optional[float] = None
        self._session_start_dt: Optional[str] = None

    @property
    def active_kind(self) -> Optional[str]:
        return self._active_kind

    @property
    def is_active(self) -> bool:
        return self._active_kind is not None

    def start_or_switch(self, new_kind: str = "work") -> None:
        """
        Start a new session or switch the active type (work <-> freetime).
        """
        now = time.monotonic()

        # If starting from idle
        if self._active_kind is None:
            self._session_start_dt = datetime.now().isoformat(timespec="seconds")
            self._active_kind = new_kind
            self._t0 = now
            return

        # If switching or restarting same (no-op if same)
        if self._active_kind == new_kind:
            return

        # Snapshot current accumulator before switching
        self._accumulate(now)
        self._active_kind = new_kind
        self._t0 = now

    def _accumulate(self, now: float) -> None:
        if self._t0 is None or self._active_kind is None:
            return

        delta = int(now - self._t0)
        if self._active_kind == "work":
            self._work_secs += delta
        elif self._active_kind == "freetime":
            self._free_secs += delta

    def get_elapsed(self) -> Tuple[int, int]:
        """
        Return (work_seconds, free_seconds) including currently running time.
        """
        w, f = self._work_secs, self._free_secs
        if self._active_kind and self._t0 is not None:
            now = time.monotonic()
            delta = int(now - self._t0)
            if self._active_kind == "work":
                w += delta
            else:
                f += delta
        return w, f

    def stop_and_save(
        self, project_id: Optional[int], task_id: Optional[int]
    ) -> Tuple[int, int]:
        """
        Stop the timer, save to DB if any time accumulated, and reset.
        Returns the final (work_secs, free_secs) for display.
        """
        if self._active_kind is None:
            return 0, 0

        # Capture final partial segment
        now_ts = time.monotonic()
        self._accumulate(now_ts)

        end_dt = datetime.now().isoformat(timespec="seconds")
        start_dt = self._session_start_dt or end_dt

        # Persist
        if self._work_secs > 0:
            self._db.record_session(
                project_id, task_id, "work", start_dt, end_dt, self._work_secs
            )
        if self._free_secs > 0:
            self._db.record_session(
                project_id, task_id, "freetime", start_dt, end_dt, self._free_secs
            )

        saved_w, saved_f = self._work_secs, self._free_secs
        self._reset()
        return saved_w, saved_f

    def _reset(self) -> None:
        self._active_kind = None
        self._work_secs = 0
        self._free_secs = 0
        self._t0 = None
        self._session_start_dt = None
