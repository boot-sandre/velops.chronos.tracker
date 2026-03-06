import unittest
from unittest.mock import Mock, patch
from velops.chronos.session import SessionTracker


class TestSessionTracker(unittest.TestCase):
    def setUp(self):
        # Create a mock for the DatabaseManager
        self.mock_db = Mock()
        self.tracker = SessionTracker(self.mock_db)

    def test_initial_state(self):
        """Test the state of the tracker upon initialization."""
        self.assertFalse(self.tracker.is_active)
        self.assertIsNone(self.tracker.active_kind)
        self.assertEqual(self.tracker.get_elapsed(), (0, 0))

    @patch("velops.chronos.session.time.monotonic")
    @patch("velops.chronos.session.datetime")
    def test_start_work_and_accumulate(self, mock_datetime, mock_time):
        """Test starting a work session and checking elapsed time."""
        # Setup start time
        mock_time.return_value = 1000.0
        self.tracker.start_or_switch("work")

        self.assertTrue(self.tracker.is_active)
        self.assertEqual(self.tracker.active_kind, "work")

        # Advance time by 60 seconds
        mock_time.return_value = 1060.0
        work, free = self.tracker.get_elapsed()

        self.assertEqual(work, 60)
        self.assertEqual(free, 0)

    @patch("velops.chronos.session.time.monotonic")
    @patch("velops.chronos.session.datetime")
    def test_switch_context(self, mock_datetime, mock_time):
        """Test switching from work to freetime."""
        # 1. Start Work at t=1000
        mock_time.return_value = 1000.0
        self.tracker.start_or_switch("work")

        # 2. Switch to Freetime at t=1030 (30s work elapsed)
        mock_time.return_value = 1030.0
        self.tracker.start_or_switch("freetime")

        self.assertEqual(self.tracker.active_kind, "freetime")

        # Check intermediate elapsed (30s work, 0s free just yet)
        # Note: get_elapsed calculates current segment. At 1030 we just switched.
        # Let's advance slightly to prove free time is now ticking.
        mock_time.return_value = 1040.0  # 10s into freetime

        work, free = self.tracker.get_elapsed()
        self.assertEqual(work, 30)
        self.assertEqual(free, 10)

    @patch("velops.chronos.session.time.monotonic")
    def test_switch_same_kind_is_noop(self, mock_time):
        """Test that switching to the same kind doesn't reset or mess up calculations."""
        mock_time.return_value = 1000.0
        self.tracker.start_or_switch("work")

        # Advance time
        mock_time.return_value = 1010.0

        # "Switch" to work again
        self.tracker.start_or_switch("work")

        # Advance time more
        mock_time.return_value = 1020.0

        work, free = self.tracker.get_elapsed()
        self.assertEqual(work, 20)  # Should be continuous 20s
        self.assertEqual(free, 0)

    @patch("velops.chronos.session.time.monotonic")
    @patch("velops.chronos.session.datetime")
    def test_stop_and_save(self, mock_datetime, mock_time):
        """Test stopping the timer and saving to the database."""
        # Setup mock return values
        mock_datetime.now.return_value.isoformat.return_value = "2026-01-01T12:00:00"

        # Start Work: t=1000
        mock_time.return_value = 1000.0
        self.tracker.start_or_switch("work")

        # Stop: t=3600 (1 hour later)
        mock_time.return_value = 4600.0

        project_id = 1
        task_id = 5

        w, f = self.tracker.stop_and_save(project_id, task_id)

        # 1. Check Return values
        self.assertEqual(w, 3600)
        self.assertEqual(f, 0)

        # 2. Check State Reset
        self.assertFalse(self.tracker.is_active)
        self.assertEqual(self.tracker.get_elapsed(), (0, 0))

        # 3. Check DB Call
        self.mock_db.record_session.assert_called_once_with(
            project_id,
            task_id,
            "work",
            "2026-01-01T12:00:00",  # start_dt
            "2026-01-01T12:00:00",  # end_dt (mocked same for simplicity)
            3600,
        )

    @patch("velops.chronos.session.time.monotonic")
    @patch("velops.chronos.session.datetime")
    def test_stop_and_save_mixed_session(self, mock_datetime, mock_time):
        """Test that mixed work/freetime sessions result in two DB calls."""
        mock_datetime.now.return_value.isoformat.return_value = "2026-01-01T10:00:00"

        # t=0: Start Work
        mock_time.return_value = 0.0
        self.tracker.start_or_switch("work")

        # t=100: Switch to Freetime
        mock_time.return_value = 100.0
        self.tracker.start_or_switch("freetime")

        # t=150: Stop
        mock_time.return_value = 150.0
        self.tracker.stop_and_save(1, 1)

        # Verify DB calls
        # We expect one call for work (100s) and one for freetime (50s)
        self.assertEqual(self.mock_db.record_session.call_count, 2)

        # Inspect calls
        calls = self.mock_db.record_session.call_args_list

        # Note: Args are (project_id, task_id, kind, start_dt, end_dt, seconds)
        # We check strictly the 'kind' and 'seconds' here
        work_call = [c for c in calls if c[0][2] == "work"][0]
        free_call = [c for c in calls if c[0][2] == "freetime"][0]

        self.assertEqual(work_call[0][5], 100)  # 100 seconds work
        self.assertEqual(free_call[0][5], 50)  # 50 seconds freetime

    def test_stop_when_idle(self):
        """Test stopping when nothing is running."""
        w, f = self.tracker.stop_and_save(1, 1)
        self.assertEqual((w, f), (0, 0))
        self.mock_db.record_session.assert_not_called()


if __name__ == "__main__":
    unittest.main()
