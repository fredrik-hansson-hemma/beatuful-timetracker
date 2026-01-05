"""Tests for crash recovery functionality."""
import pytest
from datetime import datetime, timedelta
from freezegun import freeze_time


class TestCrashRecovery:
    """Tests for crash recovery and orphaned entry detection."""

    @freeze_time("2024-01-15 10:00:00")
    def test_orphaned_entry_detection(self, db_with_tasks):
        """Test that orphaned entries are detected."""
        db, tasks = db_with_tasks

        # Create an entry that started 2 hours ago (simulating a crash)
        old_start = datetime(2024, 1, 15, 8, 0, 0)
        entry_id = db.start_time_entry(tasks['programming'], old_start)

        # Check that it's detected as active
        active = db.get_active_entry()
        assert active is not None
        assert active['id'] == entry_id

        # Calculate elapsed time
        now = datetime(2024, 1, 15, 10, 0, 0)
        start_time = datetime.fromisoformat(active['start_time'])
        elapsed = now - start_time

        # Should be 2 hours old
        assert elapsed.total_seconds() == 7200

    @freeze_time("2024-01-15 10:00:00")
    def test_recent_entry_not_orphaned(self, db_with_tasks):
        """Test that recent entries are not treated as orphaned."""
        db, tasks = db_with_tasks

        # Create an entry that started 2 minutes ago
        recent_start = datetime(2024, 1, 15, 9, 58, 0)
        entry_id = db.start_time_entry(tasks['programming'], recent_start)

        # Check elapsed time
        active = db.get_active_entry()
        now = datetime(2024, 1, 15, 10, 0, 0)
        start_time = datetime.fromisoformat(active['start_time'])
        elapsed = now - start_time

        # Should be 2 minutes (120 seconds)
        assert elapsed.total_seconds() == 120

        # This should NOT trigger crash recovery (< 5 minutes threshold)
        assert elapsed.total_seconds() < 300

    @freeze_time("2024-01-15 10:00:00")
    def test_orphaned_entry_no_lock_time(self, db_with_tasks):
        """Test that orphaned entry is detected when there's no lock_time."""
        db, tasks = db_with_tasks

        # Create orphaned entry
        old_start = datetime(2024, 1, 15, 8, 0, 0)
        entry_id = db.start_time_entry(tasks['programming'], old_start)

        # Check session state - should NOT have lock_time
        state = db.get_session_state()
        assert state['active_task_id'] == tasks['programming']
        assert state['lock_time'] is None  # No lock time!
        assert state['last_entry_id'] == entry_id

        # This is the condition for crash recovery
        active = db.get_active_entry()
        assert active is not None
        assert state['lock_time'] is None


class TestUpdateEntry:
    """Tests for updating time entries."""

    @freeze_time("2024-01-15 10:00:00")
    def test_update_entry_basic(self, db_with_tasks):
        """Test updating a time entry."""
        db, tasks = db_with_tasks

        # Create an entry
        start = datetime(2024, 1, 15, 10, 0, 0)
        end = datetime(2024, 1, 15, 11, 0, 0)
        entry_id = db.start_time_entry(tasks['programming'], start)
        db.stop_time_entry(entry_id, end)

        # Update the entry (change times)
        new_start = datetime(2024, 1, 15, 9, 0, 0)
        new_end = datetime(2024, 1, 15, 10, 30, 0)
        new_duration = int((new_end - new_start).total_seconds())

        success = db.update_time_entry(
            entry_id,
            tasks['programming'],
            new_start,
            new_end,
            new_duration,
            "Updated via crash recovery"
        )

        assert success is True

        # Verify update
        cursor = db.conn.cursor()
        cursor.execute("SELECT * FROM time_entries WHERE id = ?", (entry_id,))
        entry = cursor.fetchone()

        assert datetime.fromisoformat(entry['start_time']) == new_start
        assert datetime.fromisoformat(entry['end_time']) == new_end
        assert entry['duration_seconds'] == new_duration
        assert entry['note'] == "Updated via crash recovery"

    @freeze_time("2024-01-15 10:00:00")
    def test_update_entry_change_task(self, db_with_tasks):
        """Test updating an entry to a different task."""
        db, tasks = db_with_tasks

        # Create entry for programming
        start = datetime(2024, 1, 15, 10, 0, 0)
        entry_id = db.start_time_entry(tasks['programming'], start)
        db.stop_time_entry(entry_id)

        # Update to meetings task
        success = db.update_time_entry(
            entry_id,
            tasks['meetings'],  # Different task!
            start,
            datetime(2024, 1, 15, 11, 0, 0),
            3600,
            None
        )

        assert success is True

        # Verify task changed
        cursor = db.conn.cursor()
        cursor.execute("SELECT task_id FROM time_entries WHERE id = ?", (entry_id,))
        entry = cursor.fetchone()
        assert entry['task_id'] == tasks['meetings']

    def test_update_nonexistent_entry(self, temp_db):
        """Test updating an entry that doesn't exist."""
        success = temp_db.update_time_entry(
            99999,
            1,
            datetime.now(),
            datetime.now(),
            3600,
            None
        )

        assert success is False


class TestDeleteEntry:
    """Tests for deleting time entries."""

    @freeze_time("2024-01-15 10:00:00")
    def test_delete_entry(self, db_with_tasks):
        """Test deleting a time entry."""
        db, tasks = db_with_tasks

        # Create and stop an entry
        entry_id = db.start_time_entry(tasks['programming'])
        db.stop_time_entry(entry_id)

        # Verify it exists
        cursor = db.conn.cursor()
        cursor.execute("SELECT * FROM time_entries WHERE id = ?", (entry_id,))
        assert cursor.fetchone() is not None

        # Delete it
        success = db.delete_time_entry(entry_id)
        assert success is True

        # Verify it's gone
        cursor.execute("SELECT * FROM time_entries WHERE id = ?", (entry_id,))
        assert cursor.fetchone() is None

    @freeze_time("2024-01-15 10:00:00")
    def test_delete_active_entry_clears_state(self, db_with_tasks):
        """Test that deleting active entry clears session state."""
        db, tasks = db_with_tasks

        # Create active entry
        entry_id = db.start_time_entry(tasks['programming'])

        # Verify session state
        state = db.get_session_state()
        assert state['active_task_id'] == tasks['programming']
        assert state['last_entry_id'] == entry_id

        # Delete the active entry
        db.delete_time_entry(entry_id)

        # Session state should be cleared
        state = db.get_session_state()
        assert state['active_task_id'] is None
        assert state['last_entry_id'] is None

    def test_delete_nonexistent_entry(self, temp_db):
        """Test deleting an entry that doesn't exist."""
        success = temp_db.delete_time_entry(99999)
        assert success is False


class TestCrashRecoveryScenarios:
    """Tests for complete crash recovery scenarios."""

    @freeze_time("2024-01-15 10:00:00")
    def test_scenario_continue_tracking(self, db_with_tasks):
        """Test crash recovery: continue tracking scenario."""
        db, tasks = db_with_tasks

        # Simulate crash: entry from yesterday
        crash_start = datetime(2024, 1, 14, 16, 0, 0)
        entry_id = db.start_time_entry(tasks['programming'], crash_start)

        # User chooses "continue" - just let the entry stay active
        # No action needed - entry continues ticking

        # Entry should still be active (not stopped)
        cursor = db.conn.cursor()
        cursor.execute("SELECT * FROM time_entries WHERE id = ?", (entry_id,))
        entry = cursor.fetchone()
        assert entry['end_time'] is None  # Still active!
        assert entry['duration_seconds'] is None  # Not calculated yet

        # The same entry should be active
        active = db.get_active_entry()
        assert active is not None
        assert active['id'] == entry_id

        # Timer will continue to count from crash_start, including crash time
        # When eventually stopped, it will log all time since crash_start

    @freeze_time("2024-01-15 10:00:00")
    def test_scenario_stop_and_log_all(self, db_with_tasks):
        """Test crash recovery: stop and log all time scenario."""
        db, tasks = db_with_tasks

        # Simulate crash: entry from yesterday
        crash_start = datetime(2024, 1, 14, 16, 0, 0)
        entry_id = db.start_time_entry(tasks['programming'], crash_start)

        # User chooses "stop" - log all time
        now = datetime(2024, 1, 15, 10, 0, 0)
        duration = db.stop_time_entry(entry_id, now)

        # Should have logged ~18 hours
        expected_duration = int((now - crash_start).total_seconds())
        assert duration == expected_duration
        assert duration >= 64800  # At least 18 hours

        # No active entry
        active = db.get_active_entry()
        assert active is None

    @freeze_time("2024-01-15 10:00:00")
    def test_scenario_delete_orphaned(self, db_with_tasks):
        """Test crash recovery: delete orphaned entry scenario."""
        db, tasks = db_with_tasks

        # Simulate crash
        crash_start = datetime(2024, 1, 14, 16, 0, 0)
        entry_id = db.start_time_entry(tasks['programming'], crash_start)

        # User chooses "delete"
        success = db.delete_time_entry(entry_id)
        assert success is True

        # Entry should be gone
        cursor = db.conn.cursor()
        cursor.execute("SELECT * FROM time_entries WHERE id = ?", (entry_id,))
        assert cursor.fetchone() is None

        # No active entry
        active = db.get_active_entry()
        assert active is None

    @freeze_time("2024-01-15 10:00:00")
    def test_scenario_edit_entry(self, db_with_tasks):
        """Test crash recovery: edit entry scenario."""
        db, tasks = db_with_tasks

        # Simulate crash
        crash_start = datetime(2024, 1, 14, 16, 0, 0)
        entry_id = db.start_time_entry(tasks['programming'], crash_start)

        # User chooses "edit" and sets proper times
        correct_start = datetime(2024, 1, 14, 16, 0, 0)
        correct_end = datetime(2024, 1, 14, 17, 30, 0)  # 1.5 hours
        correct_duration = 5400  # 90 minutes

        success = db.update_time_entry(
            entry_id,
            tasks['programming'],
            correct_start,
            correct_end,
            correct_duration,
            "Manually corrected after crash"
        )

        assert success is True

        # Verify corrected entry
        cursor = db.conn.cursor()
        cursor.execute("SELECT * FROM time_entries WHERE id = ?", (entry_id,))
        entry = cursor.fetchone()

        assert entry['duration_seconds'] == correct_duration
        assert entry['note'] == "Manually corrected after crash"
        assert entry['end_time'] is not None


class TestHeartbeat:
    """Tests for heartbeat functionality."""

    @freeze_time("2024-01-15 10:00:00")
    def test_heartbeat_set_on_start(self, db_with_tasks):
        """Test that heartbeat is set when starting a time entry."""
        db, tasks = db_with_tasks

        # Start an entry
        start_time = datetime(2024, 1, 15, 10, 0, 0)
        entry_id = db.start_time_entry(tasks['programming'], start_time)

        # Check that heartbeat was set to start_time
        state = db.get_session_state()
        assert state['last_heartbeat'] is not None
        heartbeat = datetime.fromisoformat(state['last_heartbeat'])
        assert heartbeat == start_time

    @freeze_time("2024-01-15 10:00:00")
    def test_heartbeat_cleared_on_stop(self, db_with_tasks):
        """Test that heartbeat is cleared when stopping entry."""
        db, tasks = db_with_tasks

        # Start and stop an entry
        entry_id = db.start_time_entry(tasks['programming'])

        # Verify heartbeat is set
        state = db.get_session_state()
        assert state['last_heartbeat'] is not None

        # Stop the entry
        db.stop_time_entry(entry_id)

        # Heartbeat should be cleared
        state = db.get_session_state()
        assert state['last_heartbeat'] is None

    @freeze_time("2024-01-15 10:00:00")
    def test_update_heartbeat(self, db_with_tasks):
        """Test updating heartbeat."""
        db, tasks = db_with_tasks

        # Start an entry at 10:00:00
        start_time = datetime(2024, 1, 15, 10, 0, 0)
        entry_id = db.start_time_entry(tasks['programming'], start_time)

        # Initial heartbeat should be start_time
        state = db.get_session_state()
        heartbeat1 = datetime.fromisoformat(state['last_heartbeat'])
        assert heartbeat1 == start_time

        # Update heartbeat at 10:01:00
        with freeze_time("2024-01-15 10:01:00"):
            new_heartbeat = datetime(2024, 1, 15, 10, 1, 0)
            db.update_heartbeat(new_heartbeat)

            # Verify heartbeat was updated
            state = db.get_session_state()
            heartbeat2 = datetime.fromisoformat(state['last_heartbeat'])
            assert heartbeat2 == new_heartbeat
            assert heartbeat2 > heartbeat1

    @freeze_time("2024-01-15 10:00:00")
    def test_heartbeat_helps_estimate_crash_time(self, db_with_tasks):
        """Test that heartbeat helps estimate when crash occurred."""
        db, tasks = db_with_tasks

        # Simulate: User started tracking at 08:00
        crash_start = datetime(2024, 1, 15, 8, 0, 0)
        entry_id = db.start_time_entry(tasks['programming'], crash_start)

        # Simulate: Heartbeat was updated at 09:00 (last known activity)
        last_activity = datetime(2024, 1, 15, 9, 0, 0)
        db.update_heartbeat(last_activity)

        # Simulate: Now it's 10:00 and app restarts after crash
        # Entry has been running since 08:00 (2 hours)
        # But heartbeat shows activity at 09:00 (1 hour ago)

        state = db.get_session_state()
        active = db.get_active_entry()

        # Entry shows 2 hours elapsed
        start = datetime.fromisoformat(active['start_time'])
        elapsed = datetime.now() - start
        assert elapsed.total_seconds() == 7200  # 2 hours

        # But heartbeat shows crash likely at ~09:00
        heartbeat = datetime.fromisoformat(state['last_heartbeat'])
        time_since_heartbeat = datetime.now() - heartbeat
        assert time_since_heartbeat.total_seconds() == 3600  # 1 hour

        # This tells user: entry started 2h ago, but last activity was 1h ago
        # So crash probably happened ~1 hour ago

    @freeze_time("2024-01-15 10:00:00")
    def test_clear_heartbeat_method(self, db_with_tasks):
        """Test clear_heartbeat method."""
        db, tasks = db_with_tasks

        # Start entry (sets heartbeat)
        entry_id = db.start_time_entry(tasks['programming'])

        state = db.get_session_state()
        assert state['last_heartbeat'] is not None

        # Clear heartbeat
        db.clear_heartbeat()

        state = db.get_session_state()
        assert state['last_heartbeat'] is None

    @freeze_time("2024-01-15 10:00:00")
    def test_heartbeat_available_in_crash_recovery(self, db_with_tasks):
        """Test that heartbeat is available for crash recovery logic."""
        db, tasks = db_with_tasks

        # Simulate crash scenario
        crash_start = datetime(2024, 1, 14, 16, 0, 0)
        entry_id = db.start_time_entry(tasks['programming'], crash_start)

        # Update heartbeat to simulate periodic updates
        last_heartbeat = datetime(2024, 1, 14, 17, 30, 0)
        db.update_heartbeat(last_heartbeat)

        # Get state and active entry (what crash recovery would do)
        state = db.get_session_state()
        active = db.get_active_entry()

        # Verify both are available
        assert active is not None
        assert state['last_heartbeat'] is not None

        # Build entry_data as crash recovery dialog would receive it
        entry_data = {
            'id': active['id'],
            'task_id': active['task_id'],
            'task_name': active['task_name'],
            'start_time': active['start_time'],
            'end_time': active['end_time'],
            'duration_seconds': active['duration_seconds'],
            'note': active['note'] if 'note' in active.keys() else None,
            'last_heartbeat': state['last_heartbeat']
        }

        # Verify last_heartbeat is included and matches
        assert entry_data['last_heartbeat'] is not None
        stored_heartbeat = datetime.fromisoformat(entry_data['last_heartbeat'])
        assert stored_heartbeat == last_heartbeat
