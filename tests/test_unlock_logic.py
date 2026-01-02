"""Tests for unlock logic and scenarios."""
import pytest
from datetime import datetime, timedelta
from freezegun import freeze_time
from unittest.mock import Mock, patch, MagicMock


class TestUnlockScenarios:
    """Tests for different unlock scenarios."""

    @freeze_time("2024-01-15 10:00:00")
    def test_lock_with_active_task_records_lock_time(self, db_with_tasks):
        """Test that locking with an active task records the lock time."""
        db, tasks = db_with_tasks

        # Start tracking a task
        entry_id = db.start_time_entry(tasks['programming'])

        # Simulate lock
        lock_time = datetime(2024, 1, 15, 11, 0, 0)
        db.set_lock_time(lock_time)

        # Verify lock time was recorded
        state = db.get_session_state()
        assert state['lock_time'] is not None
        assert state['active_task_id'] == tasks['programming']
        assert state['last_entry_id'] == entry_id

    @freeze_time("2024-01-15 10:00:00")
    def test_lock_without_active_task_no_lock_time(self, temp_db):
        """Test that locking without active task doesn't trigger special handling."""
        # No active task
        state = temp_db.get_session_state()
        assert state['active_task_id'] is None

        # In real app, we wouldn't call set_lock_time if no active task
        # This test documents the expected behavior

    @freeze_time("2024-01-15 10:00:00")
    def test_unlock_continue_same_task(self, db_with_tasks):
        """Test unlock scenario: continue logging on the same task."""
        db, tasks = db_with_tasks

        # Start tracking at 10:00
        entry_id = db.start_time_entry(tasks['programming'])

        # Lock at 11:00 (1 hour of work)
        lock_time = datetime(2024, 1, 15, 11, 0, 0)
        with freeze_time(lock_time):
            db.set_lock_time(lock_time)

        # Unlock at 14:00 (3 hours away)
        unlock_time = datetime(2024, 1, 15, 14, 0, 0)
        with freeze_time(unlock_time):
            # User chooses to continue on same task
            # Stop the old entry at lock time
            db.stop_time_entry(entry_id, lock_time)

            # Create new entry for the away period
            away_entry_id = db.start_time_entry(tasks['programming'], lock_time)
            db.stop_time_entry(away_entry_id, unlock_time)

            # Resume tracking
            new_entry_id = db.start_time_entry(tasks['programming'])

            # Verify total time: 1 hour before lock + 3 hours away = 4 hours
            total_time = db.get_task_total_time(tasks['programming'])
            assert total_time == 14400  # 4 hours in seconds

            # Verify we have an active entry
            active = db.get_active_entry()
            assert active is not None
            assert active['task_id'] == tasks['programming']

    @freeze_time("2024-01-15 10:00:00")
    def test_unlock_switch_to_other_task(self, db_with_tasks):
        """Test unlock scenario: log time to a different task."""
        db, tasks = db_with_tasks

        # Start tracking Programming at 10:00
        entry_id = db.start_time_entry(tasks['programming'])

        # Lock at 11:00
        lock_time = datetime(2024, 1, 15, 11, 0, 0)
        with freeze_time(lock_time):
            db.set_lock_time(lock_time)

        # Unlock at 12:00 (1 hour away)
        unlock_time = datetime(2024, 1, 15, 12, 0, 0)
        with freeze_time(unlock_time):
            # User chooses to log away time to "Meetings"
            # Stop the programming entry at lock time
            db.stop_time_entry(entry_id, lock_time)

            # Create entry for the away period on different task
            away_entry_id = db.start_time_entry(tasks['meetings'], lock_time)
            db.stop_time_entry(away_entry_id, unlock_time)

            # Clear lock state
            db.clear_lock_time()

            # Verify Programming has 1 hour
            programming_time = db.get_task_total_time(tasks['programming'])
            assert programming_time == 3600

            # Verify Meetings has 1 hour (the away time)
            meetings_time = db.get_task_total_time(tasks['meetings'])
            assert meetings_time == 3600

            # No active entry (user didn't resume)
            active = db.get_active_entry()
            assert active is None

    @freeze_time("2024-01-15 10:00:00")
    def test_unlock_skip_away_time(self, db_with_tasks):
        """Test unlock scenario: don't log the away time."""
        db, tasks = db_with_tasks

        # Start tracking Programming at 10:00
        entry_id = db.start_time_entry(tasks['programming'])

        # Lock at 11:00
        lock_time = datetime(2024, 1, 15, 11, 0, 0)
        with freeze_time(lock_time):
            db.set_lock_time(lock_time)

        # Unlock at 13:00 (2 hours away)
        unlock_time = datetime(2024, 1, 15, 13, 0, 0)
        with freeze_time(unlock_time):
            # User chooses to skip the away time
            # Stop the programming entry at lock time
            db.stop_time_entry(entry_id, lock_time)

            # Don't create any entry for the away period
            # Clear lock state
            db.clear_lock_time()

            # Verify Programming has only 1 hour (time before lock)
            programming_time = db.get_task_total_time(tasks['programming'])
            assert programming_time == 3600

            # No active entry
            active = db.get_active_entry()
            assert active is None

    @freeze_time("2024-01-15 10:00:00")
    def test_short_lock_duration_ignored(self, db_with_tasks):
        """Test that very short lock durations (< 1 minute) are ignored."""
        db, tasks = db_with_tasks

        # Start tracking
        entry_id = db.start_time_entry(tasks['programming'])

        # Lock at 10:00
        lock_time = datetime(2024, 1, 15, 10, 0, 0)
        db.set_lock_time(lock_time)

        # Unlock at 10:00:30 (30 seconds later)
        unlock_time = datetime(2024, 1, 15, 10, 0, 30)
        with freeze_time(unlock_time):
            # Check if we should show dialog
            state = db.get_session_state()
            if state and state['lock_time']:
                lock_dt = datetime.fromisoformat(state['lock_time'])
                locked_duration = unlock_time - lock_dt

                # Should not show dialog for < 1 minute
                should_show_dialog = locked_duration.total_seconds() >= 60
                assert should_show_dialog is False

            # Just clear lock time and continue
            db.clear_lock_time()

    @freeze_time("2024-01-15 10:00:00")
    def test_multiple_lock_unlock_cycles_same_task(self, db_with_tasks):
        """Test multiple lock/unlock cycles continuing on the same task."""
        db, tasks = db_with_tasks

        # Start tracking at 10:00
        entry_id = db.start_time_entry(tasks['programming'])

        # Cycle 1: Lock at 11:00, unlock at 11:30
        with freeze_time("2024-01-15 11:00:00"):
            db.stop_time_entry(entry_id, datetime(2024, 1, 15, 11, 0, 0))
            away1_id = db.start_time_entry(tasks['programming'], datetime(2024, 1, 15, 11, 0, 0))

        with freeze_time("2024-01-15 11:30:00"):
            db.stop_time_entry(away1_id, datetime(2024, 1, 15, 11, 30, 0))
            entry_id = db.start_time_entry(tasks['programming'])

        # Cycle 2: Lock at 12:00, unlock at 13:00
        with freeze_time("2024-01-15 12:00:00"):
            db.stop_time_entry(entry_id, datetime(2024, 1, 15, 12, 0, 0))
            away2_id = db.start_time_entry(tasks['programming'], datetime(2024, 1, 15, 12, 0, 0))

        with freeze_time("2024-01-15 13:00:00"):
            db.stop_time_entry(away2_id, datetime(2024, 1, 15, 13, 0, 0))
            entry_id = db.start_time_entry(tasks['programming'])

        # Stop final entry at 14:00
        with freeze_time("2024-01-15 14:00:00"):
            db.stop_time_entry(entry_id, datetime(2024, 1, 15, 14, 0, 0))

        # Total: 1h + 0.5h + 0.5h + 1h + 1h = 4 hours
        total_time = db.get_task_total_time(tasks['programming'])
        assert total_time == 14400

    @freeze_time("2024-01-15 10:00:00")
    def test_unlock_after_task_deleted(self, db_with_tasks):
        """Test unlock when the active task has been deleted."""
        db, tasks = db_with_tasks

        # Start tracking Programming
        entry_id = db.start_time_entry(tasks['programming'])

        # Lock at 11:00
        with freeze_time("2024-01-15 11:00:00"):
            db.set_lock_time()

        # "Delete" the task while locked (set inactive)
        cursor = db.conn.cursor()
        cursor.execute("UPDATE tasks SET active = 0 WHERE id = ?", (tasks['programming'],))
        db.conn.commit()

        # Unlock at 12:00
        with freeze_time("2024-01-15 12:00:00"):
            state = db.get_session_state()
            task = db.get_task_by_id(state['active_task_id'])

            # Task still exists but is inactive
            assert task is not None
            assert task['active'] == 0

            # In real app, we should handle this gracefully
            # For now, just verify we can still access the task


class TestUnlockDialogLogic:
    """Tests for the unlock dialog decision logic."""

    def test_calculate_locked_duration(self):
        """Test calculating the locked duration correctly."""
        lock_time = datetime(2024, 1, 15, 10, 0, 0)
        unlock_time = datetime(2024, 1, 15, 12, 30, 0)

        locked_duration = unlock_time - lock_time

        assert locked_duration.total_seconds() == 9000  # 2.5 hours
        hours = int(locked_duration.total_seconds() // 3600)
        minutes = int((locked_duration.total_seconds() % 3600) // 60)

        assert hours == 2
        assert minutes == 30

    def test_should_show_dialog_conditions(self, db_with_tasks):
        """Test the conditions for showing the unlock dialog."""
        db, tasks = db_with_tasks

        # Condition 1: No lock time - should NOT show dialog
        state = db.get_session_state()
        assert state['lock_time'] is None
        should_show = state['lock_time'] is not None and state['active_task_id'] is not None
        assert should_show is False

        # Condition 2: Lock time but no active task - should NOT show dialog
        db.set_lock_time(datetime(2024, 1, 15, 10, 0, 0))
        state = db.get_session_state()
        should_show = state['lock_time'] is not None and state['active_task_id'] is not None
        assert should_show is False

        # Condition 3: Lock time AND active task - SHOULD show dialog
        entry_id = db.start_time_entry(tasks['programming'])
        db.set_lock_time(datetime(2024, 1, 15, 10, 0, 0))
        state = db.get_session_state()
        should_show = state['lock_time'] is not None and state['active_task_id'] is not None
        assert should_show is True

    @freeze_time("2024-01-15 10:00:00")
    def test_duration_threshold_one_minute(self):
        """Test that only durations >= 1 minute trigger the dialog."""
        lock_time = datetime(2024, 1, 15, 10, 0, 0)

        # 59 seconds - should NOT show
        unlock_time_1 = datetime(2024, 1, 15, 10, 0, 59)
        duration_1 = unlock_time_1 - lock_time
        assert duration_1.total_seconds() < 60

        # 60 seconds - SHOULD show
        unlock_time_2 = datetime(2024, 1, 15, 10, 1, 0)
        duration_2 = unlock_time_2 - lock_time
        assert duration_2.total_seconds() >= 60

        # 61 seconds - SHOULD show
        unlock_time_3 = datetime(2024, 1, 15, 10, 1, 1)
        duration_3 = unlock_time_3 - lock_time
        assert duration_3.total_seconds() >= 60


class TestTimeCalculations:
    """Tests for accurate time calculations in unlock scenarios."""

    @freeze_time("2024-01-15 10:00:00")
    def test_exact_second_precision(self, db_with_tasks):
        """Test that time calculations are precise to the second."""
        db, tasks = db_with_tasks

        start_time = datetime(2024, 1, 15, 10, 0, 0)
        end_time = datetime(2024, 1, 15, 10, 0, 37)  # 37 seconds

        entry_id = db.start_time_entry(tasks['programming'], start_time)
        duration = db.stop_time_entry(entry_id, end_time)

        assert duration == 37

    @freeze_time("2024-01-15 23:00:00")
    def test_overnight_lock_duration(self, db_with_tasks):
        """Test lock duration calculation spanning overnight."""
        db, tasks = db_with_tasks

        # Lock at 23:00
        lock_time = datetime(2024, 1, 15, 23, 0, 0)
        # Unlock at 08:00 next day (9 hours later)
        unlock_time = datetime(2024, 1, 16, 8, 0, 0)

        duration = unlock_time - lock_time
        assert duration.total_seconds() == 32400  # 9 hours

    @freeze_time("2024-01-15 10:00:00")
    def test_weekend_lock_duration(self, db_with_tasks):
        """Test lock duration over a weekend."""
        db, tasks = db_with_tasks

        # Lock Friday evening
        lock_time = datetime(2024, 1, 12, 18, 0, 0)  # Friday 18:00
        # Unlock Monday morning
        unlock_time = datetime(2024, 1, 15, 9, 0, 0)  # Monday 09:00

        duration = unlock_time - lock_time
        hours = duration.total_seconds() / 3600

        assert hours == 63  # 2.5 days + night


class TestSessionStateIntegrity:
    """Tests for session state data integrity."""

    @freeze_time("2024-01-15 10:00:00")
    def test_session_state_cleanup_after_unlock(self, db_with_tasks):
        """Test that session state is properly cleaned after unlock."""
        db, tasks = db_with_tasks

        # Setup: active task with lock
        entry_id = db.start_time_entry(tasks['programming'])
        db.set_lock_time(datetime(2024, 1, 15, 11, 0, 0))

        # Verify state is set
        state = db.get_session_state()
        assert state['lock_time'] is not None
        assert state['active_task_id'] is not None
        assert state['last_entry_id'] is not None

        # Unlock and cleanup
        db.stop_time_entry(entry_id, datetime(2024, 1, 15, 11, 0, 0))
        db.clear_lock_time()

        # Verify state is cleared
        state = db.get_session_state()
        assert state['lock_time'] is None
        assert state['active_task_id'] is None
        assert state['last_entry_id'] is None

    @freeze_time("2024-01-15 10:00:00")
    def test_session_state_survives_database_close(self, db_with_tasks):
        """Test that session state persists after database close/reopen."""
        db, tasks = db_with_tasks

        # Setup state
        entry_id = db.start_time_entry(tasks['programming'])
        db.set_lock_time(datetime(2024, 1, 15, 11, 0, 0))

        db_path = db.db_path
        original_task_id = tasks['programming']

        # Close database
        db.close()

        # Reopen
        from database import TimeTrackerDB
        db2 = TimeTrackerDB(db_path)

        # State should persist
        state = db2.get_session_state()
        assert state['lock_time'] is not None
        assert state['active_task_id'] == original_task_id
        assert state['last_entry_id'] == entry_id

        db2.close()
