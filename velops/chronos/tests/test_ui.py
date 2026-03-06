import unittest
from unittest.mock import MagicMock, patch
import uuid

# We need to ensure GTK is initialized for widgets to be created,
# even if we don't show the window.
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from velops.chronos import ui
from velops.chronos.db import DatabaseManager


class TestFieldDialog(unittest.TestCase):
    def test_dialog_values(self):
        """Test that FieldDialog collects values from entries correctly."""
        # Use a unique ID to prevent DBus name collision
        app_id = f"eu.velops.chronos.tests.field.dialog"
        app = Gtk.Application(application_id=app_id)
        app.register(None)
        parent = Gtk.Window(application=app)

        fields = [("Label 1", "key1", "hint1"), ("Label 2", "key2", "hint2")]

        dlg = ui.FieldDialog(parent, "Test Dialog", fields)

        # Manually set text in the entries
        # We access the private _entries dict to inject values for the test
        dlg._entries["key1"].set_text("Value A")
        dlg._entries["key2"].set_text("Value B")

        expected = {"key1": "Value A", "key2": "Value B"}
        self.assertEqual(dlg.values(), expected)

        # Clean up
        dlg.destroy()
        parent.destroy()


class TestTimesheetDialog(unittest.TestCase):
    def test_dialog_population(self):
        """Test that the TimesheetDialog populates the ListStore from DB data."""
        mock_db = MagicMock(spec=DatabaseManager)

        # Mock return data matching the structure in db.py
        mock_sessions = [
            {
                "id": 1,
                "entry_type": "work",
                "start_time": "2023-01-01T10:00:00",
                "end_time": "2023-01-01T11:00:00",
                "duration_seconds": 3600,
            },
            {
                "id": 2,
                "entry_type": "freetime",
                "start_time": "2023-01-01T12:00:00",
                "end_time": None,
                "duration_seconds": 0,
            },
        ]
        mock_db.get_sessions.return_value = mock_sessions

        app_id = f"eu.velops.chronos.tests.timesheet"
        app = Gtk.Application(application_id=app_id)
        app.register(None)
        parent = Gtk.Window(application=app)

        dlg = ui.TimesheetDialog(parent, mock_db, "Test Project", 1, None)

        # Find the TreeView to inspect its model
        # The dialog structure in ui.py is Dialog -> ContentArea -> Box -> ScrolledWindow -> TreeView
        content_area = dlg.get_content_area()
        # Depending on GTK internals, children might vary, but we know we added a ScrolledWindow
        scrolled_window = content_area.get_first_child()
        while scrolled_window and not isinstance(scrolled_window, Gtk.ScrolledWindow):
            scrolled_window = scrolled_window.get_next_sibling()

        self.assertIsNotNone(scrolled_window, "Could not find ScrolledWindow in Dialog")
        tree_view = scrolled_window.get_child()
        self.assertIsInstance(tree_view, Gtk.TreeView)

        model = tree_view.get_model()
        self.assertEqual(len(model), 2)

        # Check first row (Work)
        iter1 = model.get_iter_from_string("0")
        self.assertEqual(model.get_value(iter1, 0), 1)  # ID
        self.assertIn("work", model.get_value(iter1, 1))  # Type
        self.assertEqual(model.get_value(iter1, 4), "01:00:00")  # Duration fmt

        dlg.destroy()
        parent.destroy()


class TestMainWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Initialize GTK once for the class if not already done
        if not Gtk.is_initialized():
            Gtk.init()

    def setUp(self):
        self.mock_db = MagicMock(spec=DatabaseManager)
        self.mock_db.get_projects.return_value = []  
        unique_id = f"eu.velops.chronos.tests.diag_field_{uuid.uuid4()}"
        self.app = Gtk.Application(application_id=unique_id)

        # Initialize application to allow window creation
        self.app.register(None)

        # Patch CSS loading to prevent IO/Resource errors during test
        # with patch.object(ui.MainWindow, "_load_css"):
        self.win = ui.MainWindow(self.app, self.mock_db)

    def tearDown(self):
        self.win.destroy()
        # It's good practice to quit the app, though in tests the garbage collector
        # usually handles it. Quitting helps release resources faster.
        self.app.quit()

    def test_initial_state(self):
        """Test initial button states."""
        self.assertFalse(self.win._btn_add_task.get_sensitive())
        self.assertFalse(self.win._btn_del.get_sensitive())
        self.assertFalse(self.win._btn_stop.get_sensitive())
        self.assertEqual(self.win._active, None)

    @patch("velops.chronos.ui.FieldDialog")
    def test_add_project_logic(self, MockDialog):
        """Test the logic flow when adding a project."""
        # 1. Simulate clicking "Add Project"
        self.win._on_add_project(None)

        # 2. Check that Dialog was created
        MockDialog.assert_called()
        dlg_instance = MockDialog.return_value

        # 3. Simulate the dialog returning OK with data
        dlg_instance.values.return_value = {"name": "New Proj", "desc": "Test"}

        # Manually trigger the response callback
        self.win._resp_add_project(dlg_instance, Gtk.ResponseType.OK)

        # 4. Verify DB interaction
        self.mock_db.add_project.assert_called_with("New Proj", "Test")
        # 5. Verify tree refresh was called (get_projects called again)
        self.assertGreater(self.mock_db.get_projects.call_count, 1)

    @patch("velops.chronos.ui.ConfirmDialog")
    def test_delete_logic(self, MockDialog):
        """Test deletion logic for a selected item."""
        # Simulate a selection: Project ID 10
        # Format: (label, kind, id, pid, status)
        with patch.object(
            self.win, "_selected", return_value=("Proj X", "project", 10, 0, "")
        ):
            self.win._on_delete(None)

            MockDialog.assert_called()
            dlg_instance = MockDialog.return_value

            # Simulate confirming delete
            self.win._resp_delete(dlg_instance, Gtk.ResponseType.OK, "project", 10)

            self.mock_db.delete_project.assert_called_with(10)

    def test_selection_logic_project(self):
        """Test internal state changes when a project is selected."""
        # Mock the _selected method to return a project tuple
        with patch.object(
            self.win, "_selected", return_value=("Alpha", "project", 5, 0, "")
        ):
            self.win._on_tree_sel(None)

            self.assertEqual(self.win._sel_project_id, 5)
            self.assertIsNone(self.win._sel_task_id)
            self.assertTrue(self.win._btn_add_task.get_sensitive())
            self.assertTrue(self.win._btn_ts.get_sensitive())

    def test_selection_logic_task(self):
        """Test internal state changes when a task is selected."""
        # Mock selection: Task ID 20, belonging to Project ID 5
        with patch.object(
            self.win, "_selected", return_value=("Task A", "task", 20, 5, "pending")
        ):
            self.win._on_tree_sel(None)

            self.assertEqual(self.win._sel_project_id, 5)
            self.assertEqual(self.win._sel_task_id, 20)
            # Cannot add a task to a task
            self.assertFalse(self.win._btn_add_task.get_sensitive())
            self.assertTrue(self.win._btn_ts.get_sensitive())

    @patch("time.monotonic")
    @patch("gi.repository.GLib.timeout_add")
    def test_timer_workflow(self, mock_timeout, mock_monotonic):
        """
        Test the complete timer workflow:
        Start -> Work 1h -> Switch -> Freetime 30m -> Stop
        """
        mock_monotonic.return_value = 1000.0

        # 1. Select a task
        with patch.object(
            self.win, "_selected", return_value=("Coding", "task", 99, 1, "pending")
        ):
            self.win._on_tree_sel(None)

            # 2. START (Work)
            self.win._on_start_switch(None)

            self.assertEqual(self.win._active, "work")
            self.assertIsNotNone(self.win._work_t0)
            self.assertTrue(self.win._btn_stop.get_sensitive())
            mock_timeout.assert_called()  # Check GLib timer started

            # 3. Advance time by 3600 seconds and SWITCH to Free Time
            mock_monotonic.return_value = 4600.0  # +1 hour

            self.win._on_start_switch(None)  # Switch

            # Check Work accumulated correctly
            self.assertEqual(self.win._work_secs, 3600)
            self.assertIsNone(self.win._work_t0)  # Reset because paused

            # Check Free Time started
            self.assertEqual(self.win._active, "freetime")
            self.assertIsNotNone(self.win._free_t0)

            # 4. Advance time by 1800 seconds and STOP
            mock_monotonic.return_value = 6400.0  # +1 hour (prev) + 30 mins

            # Ensure we have a valid project/task set for recording
            self.win._sel_project_id = 1
            self.win._sel_task_id = 99

            self.win._on_stop_record(None)

            # 5. Verify Database calls
            # Expect two calls: one for work, one for freetime
            self.assertEqual(self.mock_db.record_session.call_count, 2)

            calls = self.mock_db.record_session.call_args_list

            # Validate Work Entry
            args_work = calls[0].args
            self.assertEqual(args_work[2], "work")
            self.assertEqual(args_work[5], 3600)  # Duration

            # Validate FreeTime Entry
            args_free = calls[1].args
            self.assertEqual(args_free[2], "freetime")
            self.assertEqual(args_free[5], 1800)  # Duration

            # 6. Verify Reset State
            self.assertIsNone(self.win._active)
            self.assertEqual(self.win._work_secs, 0)
            self.assertEqual(self.win._free_secs, 0)
            self.assertFalse(self.win._btn_stop.get_sensitive())

    def test_format_helper(self):
        """Test the static time formatting helper."""
        fmt = ui.MainWindow._fmt
        self.assertEqual(fmt(0), "00:00:00")
        self.assertEqual(fmt(65), "00:01:05")
        self.assertEqual(fmt(3661), "01:01:01")


if __name__ == "__main__":
    unittest.main()
