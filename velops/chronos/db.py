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

from pathlib import Path
import sqlite3
from typing import List


_connection = None


def get_connection():
    """
    Singleton pattern to get the database connection.
    Initializes the connection only when first requested.
    """
    global _connection
    if _connection is None:
        data_dir = Path.home() / ".local" / "share" / "velops" / "chronos"
        data_dir.mkdir(parents=True, exist_ok=True)
        db_path = data_dir / "data.db"
        _connection = sqlite3.connect(str(db_path), check_same_thread=False)
        _connection.row_factory = sqlite3.Row
        _connection.execute("PRAGMA foreign_keys = ON")

    return _connection


def get_cursor():
    """Helper to get a cursor from the active connection."""
    return get_connection().cursor()


class DatabaseManager:
    """
    SQLite connector.
    Creates (if not exist) three tables: project · task · timesheet
    """

    def __init__(self, db_path: str | None = None):
        if db_path is None:
            base = Path.home() / ".local" / "share" / "velops"
            base.mkdir(parents=True, exist_ok=True)
            db_path = str(base / "chronos.db")
        self._path = db_path
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        self._create_schema()

    def _create_schema(self) -> None:
        conn = get_connection()
        conn.executescript(
            """
        CREATE TABLE IF NOT EXISTS project (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL UNIQUE,
            description TEXT    NOT NULL DEFAULT '',
            color       TEXT    NOT NULL DEFAULT '#3584e4',
            created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
            updated_at  TEXT    NOT NULL DEFAULT (datetime('now'))
        );

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
        """
        )
        conn.commit()

    def get_projects(self) -> list:
        conn = get_connection()
        return conn.execute(
            "SELECT id, name, description, color FROM project ORDER BY name"
        ).fetchall()

    def add_project(
        self, name: str, description: str = "", color: str = "#3584e4"
    ) -> int:
        conn = get_connection()
        cur = conn.execute(
            "INSERT INTO project(name,description,color) VALUES(?,?,?)",
            (name, description, color),
        )
        conn.commit()
        return cur.lastrowid

    def delete_project(self, pid: int) -> None:
        conn = get_connection()
        conn.execute("DELETE FROM project WHERE id=?", (pid,))
        conn.commit()

    def get_tasks(self, project_id: int) -> list:
        conn = get_connection()
        return conn.execute(
            "SELECT id, project_id, name, description, status "
            "FROM task WHERE project_id=? ORDER BY name",
            (project_id,),
        ).fetchall()

    def add_task(
        self, project_id: int, name: str, description: str = "", status: str = "pending"
    ) -> int:
        conn = get_connection()
        cur = conn.execute(
            "INSERT INTO task(project_id,name,description,status) VALUES(?,?,?,?)",
            (project_id, name, description, status),
        )
        conn.commit()
        return cur.lastrowid

    def delete_task(self, tid: int) -> None:
        conn = get_connection()
        conn.execute("DELETE FROM task WHERE id=?", (tid,))
        conn.commit()

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
        conn = get_connection()
        cur = conn.execute(
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
        conn.commit()
        return cur.lastrowid

    def get_sessions(self, project_id=None, task_id=None, limit: int = 200) -> List:
        conn = get_connection()
        where, params = [], []
        if project_id:
            where.append("ts.project_id=?")
            params.append(project_id)
        if task_id:
            where.append("ts.task_id=?")
            params.append(task_id)
        clause = ("WHERE " + " AND ".join(where)) if where else ""
        return conn.execute(
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
        conn = get_connection()
        if conn:
            conn.close()
