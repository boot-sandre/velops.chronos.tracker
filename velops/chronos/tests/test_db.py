import unittest
import sqlite3
from datetime import datetime
from velops.chronos import db


class TestChronosDatabase(unittest.TestCase):
    def setUp(self):
        """
        Set up an in-memory database before each test.
        We monkey-patch db._connection to ensure we don't touch the file system.
        """
        # Reset the global connection in the module
        db._connection = None

        # Create a fresh in-memory connection
        self.conn = sqlite3.connect(":memory:", check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")

        # Inject this connection into the module so get_connection() returns it
        db._connection = self.conn

        # Initialize the Manager. We pass ':memory:' to avoid the __init__ logic
        # trying to create the default ~/.local directory structure.
        self.db_manager = db.DatabaseManager(db_path=":memory:")

    def tearDown(self):
        """Clean up the connection after each test."""
        if self.conn:
            self.conn.close()
        # Reset module global to avoid side effects on other tests
        db._connection = None

    # --- Project Tests ---

    def test_add_and_get_projects(self):
        """Test creating projects and retrieving them."""
        pid1 = self.db_manager.add_project("Project Alpha", "Description A", "#ff0000")
        pid2 = self.db_manager.add_project("Project Beta")  # Test defaults

        projects = self.db_manager.get_projects()
        self.assertEqual(len(projects), 2)

        # Verify Project Alpha
        p1 = next(p for p in projects if p["id"] == pid1)
        self.assertEqual(p1["name"], "Project Alpha")
        self.assertEqual(p1["description"], "Description A")
        self.assertEqual(p1["color"], "#ff0000")

        # Verify Project Beta (Defaults)
        p2 = next(p for p in projects if p["id"] == pid2)
        self.assertEqual(p2["name"], "Project Beta")
        self.assertEqual(p2["description"], "")
        self.assertEqual(p2["color"], "#3584e4")

    def test_project_unique_name_constraint(self):
        """Test that duplicate project names are rejected."""
        self.db_manager.add_project("Unique Name")
        with self.assertRaises(sqlite3.IntegrityError):
            self.db_manager.add_project("Unique Name")

    def test_delete_project(self):
        """Test deleting a project."""
        pid = self.db_manager.add_project("To Delete")
        self.db_manager.delete_project(pid)
        projects = self.db_manager.get_projects()
        self.assertEqual(len(projects), 0)

    # --- Task Tests ---

    def test_add_and_get_tasks(self):
        """Test creating tasks linked to a project."""
        pid = self.db_manager.add_project("My Project")
        tid1 = self.db_manager.add_task(pid, "Task 1", "Desc 1", "in_progress")
        tid2 = self.db_manager.add_task(pid, "Task 2")  # Defaults

        tasks = self.db_manager.get_tasks(pid)
        self.assertEqual(len(tasks), 2)

        t1 = next(t for t in tasks if t["id"] == tid1)
        self.assertEqual(t1["status"], "in_progress")

        t2 = next(t for t in tasks if t["id"] == tid2)
        self.assertEqual(t2["status"], "pending")  # Default status

    def test_task_status_constraint(self):
        """Test that tasks only accept valid status strings."""
        pid = self.db_manager.add_project("Status Check")
        with self.assertRaises(sqlite3.IntegrityError):
            self.db_manager.add_task(pid, "Bad Task", status="invalid_status")

    def test_task_unique_per_project(self):
        """Test that task names are unique per project, but allowed across projects."""
        p1 = self.db_manager.add_project("P1")
        p2 = self.db_manager.add_project("P2")

        self.db_manager.add_task(p1, "Design")

        # Should fail: same name, same project
        with self.assertRaises(sqlite3.IntegrityError):
            self.db_manager.add_task(p1, "Design")

        # Should succeed: same name, different project
        try:
            self.db_manager.add_task(p2, "Design")
        except sqlite3.IntegrityError:
            self.fail("Should allow same task name in different projects")

    def test_delete_task(self):
        """Test deleting a specific task."""
        pid = self.db_manager.add_project("P1")
        tid = self.db_manager.add_task(pid, "T1")
        self.db_manager.delete_task(tid)
        tasks = self.db_manager.get_tasks(pid)
        self.assertEqual(len(tasks), 0)

    # --- Timesheet Tests ---

    def test_record_and_get_sessions(self):
        """Test recording work sessions."""
        pid = self.db_manager.add_project("Work")
        tid = self.db_manager.add_task(pid, "Coding")

        start = datetime(2023, 1, 1, 10, 0, 0).isoformat()
        end = datetime(2023, 1, 1, 12, 0, 0).isoformat()

        sid = self.db_manager.record_session(
            pid, tid, "work", start, end, 7200, "Good session"
        )

        sessions = self.db_manager.get_sessions()
        self.assertEqual(len(sessions), 1)
        s = sessions[0]
        self.assertEqual(s["id"], sid)
        self.assertEqual(s["proj"], "Work")
        self.assertEqual(s["task"], "Coding")
        self.assertEqual(s["duration_seconds"], 7200)

    def test_session_type_constraint(self):
        """Test that entry_type must be 'work' or 'freetime'."""
        pid = self.db_manager.add_project("P")
        tid = self.db_manager.add_task(pid, "T")
        now = datetime.now().isoformat()

        with self.assertRaises(sqlite3.IntegrityError):
            self.db_manager.record_session(pid, tid, "sleeping", now, now, 0)

    def test_get_sessions_filters(self):
        """Test filtering sessions by project and task."""
        p1 = self.db_manager.add_project("P1")
        p2 = self.db_manager.add_project("P2")
        t1 = self.db_manager.add_task(p1, "T1")
        t2 = self.db_manager.add_task(p2, "T2")

        now = datetime.now().isoformat()

        self.db_manager.record_session(p1, t1, "work", now, now, 100)
        self.db_manager.record_session(p2, t2, "work", now, now, 200)

        # Filter by Project 1
        res_p1 = self.db_manager.get_sessions(project_id=p1)
        self.assertEqual(len(res_p1), 1)
        self.assertEqual(res_p1[0]["proj"], "P1")

        # Filter by Task 2
        res_t2 = self.db_manager.get_sessions(task_id=t2)
        self.assertEqual(len(res_t2), 1)
        self.assertEqual(res_t2[0]["task"], "T2")

    # --- Relationships & Cascades ---

    def test_delete_project_cascades_tasks(self):
        """
        Verify ON DELETE CASCADE between Project and Task.
        Deleting a project should delete its tasks.
        """
        pid = self.db_manager.add_project("To Delete")
        self.db_manager.add_task(pid, "Task A")
        self.db_manager.add_task(pid, "Task B")

        # Verify tasks exist
        self.assertEqual(len(self.db_manager.get_tasks(pid)), 2)

        # Delete Project
        self.db_manager.delete_project(pid)

        # Verify tasks are gone (querying directly as get_tasks relies on project_id)
        count = self.conn.execute("SELECT count(*) FROM task").fetchone()[0]
        self.assertEqual(count, 0)

    def test_delete_project_sets_timesheet_null(self):
        """
        Verify ON DELETE SET NULL between Project and Timesheet.
        Deleting a project should keep the timesheet entry but set project_id to NULL.
        """
        pid = self.db_manager.add_project("Project X")
        tid = self.db_manager.add_task(pid, "Task X")
        now = datetime.now().isoformat()

        sid = self.db_manager.record_session(pid, tid, "work", now, now, 60)

        self.db_manager.delete_project(pid)

        # Fetch raw session to check FKs
        row = self.conn.execute(
            "SELECT project_id, task_id FROM timesheet WHERE id=?", (sid,)
        ).fetchone()

        # project_id should be None (NULL)
        self.assertIsNone(row["project_id"])
        # task_id should also be None because the Task was deleted via cascade from Project
        # and Timesheet -> Task is also ON DELETE SET NULL
        self.assertIsNone(row["task_id"])

    def test_delete_task_sets_timesheet_null(self):
        """
        Verify ON DELETE SET NULL between Task and Timesheet.
        Deleting just the task should keep project_id but nullify task_id.
        """
        pid = self.db_manager.add_project("Project Y")
        tid = self.db_manager.add_task(pid, "Task Y")
        now = datetime.now().isoformat()

        sid = self.db_manager.record_session(pid, tid, "work", now, now, 60)

        self.db_manager.delete_task(tid)

        row = self.conn.execute(
            "SELECT project_id, task_id FROM timesheet WHERE id=?", (sid,)
        ).fetchone()

        self.assertEqual(row["project_id"], pid)  # Should still exist
        self.assertIsNone(row["task_id"])  # Should be NULL

    # --- Module Functions ---

    def test_get_connection_singleton(self):
        """Verify that get_connection returns the singleton instance."""
        c1 = db.get_connection()
        c2 = db.get_connection()
        self.assertIs(c1, c2)
        self.assertIs(c1, self.conn)

    def test_close(self):
        """Verify close method closes the connection."""
        self.db_manager.close()
        # Trying to execute on closed connection should fail
        with self.assertRaises(sqlite3.ProgrammingError):
            self.conn.execute("SELECT 1")


if __name__ == "__main__":
    unittest.main()
