"""Tests for database functionality."""
import pytest
from datetime import datetime, timedelta
from freezegun import freeze_time


class TestTaskManagement:
    """Tests for task creation and retrieval."""

    def test_add_task(self, temp_db):
        """Test adding a new task."""
        task_id = temp_db.add_task("Test Task", "Test description")
        assert task_id > 0

        task = temp_db.get_task_by_id(task_id)
        assert task is not None
        assert task['name'] == "Test Task"
        assert task['description'] == "Test description"
        assert task['active'] == 1

    def test_add_multiple_tasks(self, temp_db):
        """Test adding multiple tasks."""
        task1_id = temp_db.add_task("Task 1")
        task2_id = temp_db.add_task("Task 2")
        task3_id = temp_db.add_task("Task 3")

        assert task1_id != task2_id != task3_id

        tasks = temp_db.get_tasks()
        assert len(tasks) == 3

    def test_duplicate_task_name_fails(self, temp_db):
        """Test that adding duplicate task names raises an error."""
        temp_db.add_task("Duplicate Task")

        with pytest.raises(Exception):
            temp_db.add_task("Duplicate Task")

    def test_get_tasks_active_only(self, temp_db):
        """Test retrieving only active tasks."""
        temp_db.add_task("Active Task 1")
        temp_db.add_task("Active Task 2")

        # Manually set one task as inactive for testing
        cursor = temp_db.conn.cursor()
        cursor.execute("UPDATE tasks SET active = 0 WHERE name = 'Active Task 2'")
        temp_db.conn.commit()

        active_tasks = temp_db.get_tasks(active_only=True)
        assert len(active_tasks) == 1
        assert active_tasks[0]['name'] == "Active Task 1"

        all_tasks = temp_db.get_tasks(active_only=False)
        assert len(all_tasks) == 2

    def test_get_nonexistent_task(self, temp_db):
        """Test retrieving a task that doesn't exist."""
        task = temp_db.get_task_by_id(99999)
        assert task is None


class TestTimeEntries:
    """Tests for time entry functionality."""

    @freeze_time("2024-01-15 10:00:00")
    def test_start_time_entry(self, db_with_tasks):
        """Test starting a time entry."""
        db, tasks = db_with_tasks

        entry_id = db.start_time_entry(tasks['programming'])
        assert entry_id > 0

        # Verify entry was created
        cursor = db.conn.cursor()
        cursor.execute("SELECT * FROM time_entries WHERE id = ?", (entry_id,))
        entry = cursor.fetchone()

        assert entry is not None
        assert entry['task_id'] == tasks['programming']
        assert entry['end_time'] is None
        assert entry['duration_seconds'] is None

    @freeze_time("2024-01-15 10:00:00")
    def test_start_time_entry_with_custom_time(self, db_with_tasks):
        """Test starting a time entry with a custom start time."""
        db, tasks = db_with_tasks

        custom_time = datetime(2024, 1, 15, 9, 0, 0)
        entry_id = db.start_time_entry(tasks['programming'], custom_time)

        cursor = db.conn.cursor()
        cursor.execute("SELECT start_time FROM time_entries WHERE id = ?", (entry_id,))
        entry = cursor.fetchone()

        assert datetime.fromisoformat(entry['start_time']) == custom_time

    @freeze_time("2024-01-15 10:00:00")
    def test_stop_time_entry(self, db_with_tasks):
        """Test stopping a time entry and calculating duration."""
        db, tasks = db_with_tasks

        # Start entry
        entry_id = db.start_time_entry(tasks['programming'])

        # Move time forward 2 hours
        with freeze_time("2024-01-15 12:00:00"):
            duration = db.stop_time_entry(entry_id)

        # Should be 2 hours = 7200 seconds
        assert duration == 7200

        # Verify in database
        cursor = db.conn.cursor()
        cursor.execute("SELECT * FROM time_entries WHERE id = ?", (entry_id,))
        entry = cursor.fetchone()

        assert entry['end_time'] is not None
        assert entry['duration_seconds'] == 7200

    def test_stop_nonexistent_entry(self, temp_db):
        """Test stopping an entry that doesn't exist."""
        duration = temp_db.stop_time_entry(99999)
        assert duration == 0

    @freeze_time("2024-01-15 10:00:00")
    def test_stop_entry_with_custom_end_time(self, db_with_tasks):
        """Test stopping an entry with a custom end time."""
        db, tasks = db_with_tasks

        start_time = datetime(2024, 1, 15, 10, 0, 0)
        end_time = datetime(2024, 1, 15, 13, 30, 0)

        entry_id = db.start_time_entry(tasks['programming'], start_time)
        duration = db.stop_time_entry(entry_id, end_time)

        # 3.5 hours = 12600 seconds
        assert duration == 12600

    @freeze_time("2024-01-15 10:00:00")
    def test_multiple_entries_same_task(self, db_with_tasks):
        """Test creating multiple entries for the same task."""
        db, tasks = db_with_tasks

        # First entry: 1 hour
        entry1_id = db.start_time_entry(tasks['programming'])
        with freeze_time("2024-01-15 11:00:00"):
            db.stop_time_entry(entry1_id)

        # Second entry: 2 hours
        with freeze_time("2024-01-15 14:00:00"):
            entry2_id = db.start_time_entry(tasks['programming'])
        with freeze_time("2024-01-15 16:00:00"):
            db.stop_time_entry(entry2_id)

        # Total should be 3 hours = 10800 seconds
        total_time = db.get_task_total_time(tasks['programming'])
        assert total_time == 10800

    @freeze_time("2024-01-15 10:00:00")
    def test_get_active_entry(self, db_with_tasks):
        """Test retrieving the currently active entry."""
        db, tasks = db_with_tasks

        # No active entry initially
        active = db.get_active_entry()
        assert active is None

        # Start an entry
        entry_id = db.start_time_entry(tasks['programming'])

        # Should now have an active entry
        active = db.get_active_entry()
        assert active is not None
        assert active['id'] == entry_id
        assert active['task_name'] == "Programming"

        # Stop the entry
        db.stop_time_entry(entry_id)

        # No active entry again
        active = db.get_active_entry()
        assert active is None


class TestSessionState:
    """Tests for session state management (lock/unlock functionality)."""

    def test_initial_session_state(self, temp_db):
        """Test that session state is initialized properly."""
        state = temp_db.get_session_state()
        assert state is not None
        assert state['active_task_id'] is None
        assert state['lock_time'] is None
        assert state['last_entry_id'] is None

    @freeze_time("2024-01-15 10:00:00")
    def test_start_entry_updates_session_state(self, db_with_tasks):
        """Test that starting an entry updates session state."""
        db, tasks = db_with_tasks

        entry_id = db.start_time_entry(tasks['programming'])

        state = db.get_session_state()
        assert state['active_task_id'] == tasks['programming']
        assert state['last_entry_id'] == entry_id

    @freeze_time("2024-01-15 10:00:00")
    def test_stop_entry_clears_session_state(self, db_with_tasks):
        """Test that stopping an entry clears session state."""
        db, tasks = db_with_tasks

        entry_id = db.start_time_entry(tasks['programming'])
        db.stop_time_entry(entry_id)

        state = db.get_session_state()
        assert state['active_task_id'] is None
        assert state['last_entry_id'] is None

    @freeze_time("2024-01-15 10:00:00")
    def test_set_lock_time(self, temp_db):
        """Test setting lock time."""
        lock_time = datetime(2024, 1, 15, 10, 0, 0)
        temp_db.set_lock_time(lock_time)

        state = temp_db.get_session_state()
        assert state['lock_time'] is not None
        assert datetime.fromisoformat(state['lock_time']) == lock_time

    @freeze_time("2024-01-15 10:00:00")
    def test_set_lock_time_default(self, temp_db):
        """Test setting lock time with default (now)."""
        temp_db.set_lock_time()

        state = temp_db.get_session_state()
        assert state['lock_time'] is not None
        assert datetime.fromisoformat(state['lock_time']) == datetime(2024, 1, 15, 10, 0, 0)

    def test_clear_lock_time(self, temp_db):
        """Test clearing lock time."""
        # Set lock time first
        temp_db.set_lock_time(datetime(2024, 1, 15, 10, 0, 0))

        # Verify it's set
        state = temp_db.get_session_state()
        assert state['lock_time'] is not None

        # Clear it
        temp_db.clear_lock_time()

        # Verify it's cleared
        state = temp_db.get_session_state()
        assert state['lock_time'] is None


class TestTaskTotalTime:
    """Tests for calculating total time per task."""

    @freeze_time("2024-01-15 10:00:00")
    def test_task_with_no_entries(self, db_with_tasks):
        """Test total time for a task with no entries."""
        db, tasks = db_with_tasks

        total_time = db.get_task_total_time(tasks['programming'])
        assert total_time == 0

    @freeze_time("2024-01-15 10:00:00")
    def test_task_with_one_entry(self, db_with_tasks):
        """Test total time for a task with one entry."""
        db, tasks = db_with_tasks

        entry_id = db.start_time_entry(tasks['programming'])
        with freeze_time("2024-01-15 11:30:00"):  # 1.5 hours later
            db.stop_time_entry(entry_id)

        total_time = db.get_task_total_time(tasks['programming'])
        assert total_time == 5400  # 90 minutes = 5400 seconds

    @freeze_time("2024-01-15 10:00:00")
    def test_task_with_multiple_entries(self, db_with_tasks):
        """Test total time for a task with multiple entries."""
        db, tasks = db_with_tasks

        # Entry 1: 1 hour
        entry1_id = db.start_time_entry(tasks['meetings'])
        with freeze_time("2024-01-15 11:00:00"):
            db.stop_time_entry(entry1_id)

        # Entry 2: 30 minutes
        with freeze_time("2024-01-15 14:00:00"):
            entry2_id = db.start_time_entry(tasks['meetings'])
        with freeze_time("2024-01-15 14:30:00"):
            db.stop_time_entry(entry2_id)

        # Entry 3: 2 hours
        with freeze_time("2024-01-15 15:00:00"):
            entry3_id = db.start_time_entry(tasks['meetings'])
        with freeze_time("2024-01-15 17:00:00"):
            db.stop_time_entry(entry3_id)

        total_time = db.get_task_total_time(tasks['meetings'])
        assert total_time == 12600  # 3.5 hours = 12600 seconds

    @freeze_time("2024-01-15 10:00:00")
    def test_active_entry_not_counted_in_total(self, db_with_tasks):
        """Test that active (unfinished) entries are not counted in total time."""
        db, tasks = db_with_tasks

        # Completed entry: 1 hour
        entry1_id = db.start_time_entry(tasks['documentation'])
        with freeze_time("2024-01-15 11:00:00"):
            db.stop_time_entry(entry1_id)

        # Active entry (not finished)
        with freeze_time("2024-01-15 12:00:00"):
            db.start_time_entry(tasks['documentation'])

        # Move time forward but don't stop the entry
        with freeze_time("2024-01-15 15:00:00"):
            total_time = db.get_task_total_time(tasks['documentation'])

        # Should only count the completed entry
        assert total_time == 3600  # 1 hour = 3600 seconds


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    @freeze_time("2024-01-15 23:59:00")
    def test_entry_spanning_midnight(self, db_with_tasks):
        """Test an entry that spans midnight."""
        db, tasks = db_with_tasks

        # Start at 23:59
        entry_id = db.start_time_entry(tasks['programming'])

        # End at 00:30 next day
        with freeze_time("2024-01-16 00:30:00"):
            duration = db.stop_time_entry(entry_id)

        # Should be 31 minutes = 1860 seconds
        assert duration == 1860

    @freeze_time("2024-01-15 10:00:00")
    def test_very_short_entry(self, db_with_tasks):
        """Test a very short entry (less than a minute)."""
        db, tasks = db_with_tasks

        entry_id = db.start_time_entry(tasks['programming'])

        # 5 seconds later
        with freeze_time("2024-01-15 10:00:05"):
            duration = db.stop_time_entry(entry_id)

        assert duration == 5

    @freeze_time("2024-01-15 10:00:00")
    def test_zero_duration_entry(self, db_with_tasks):
        """Test an entry with zero duration (start and stop at same time)."""
        db, tasks = db_with_tasks

        start_time = datetime(2024, 1, 15, 10, 0, 0)
        entry_id = db.start_time_entry(tasks['programming'], start_time)
        duration = db.stop_time_entry(entry_id, start_time)

        assert duration == 0

    @freeze_time("2024-01-15 10:00:00")
    def test_multiple_lock_unlock_cycles(self, db_with_tasks):
        """Test multiple lock/unlock cycles."""
        db, tasks = db_with_tasks

        # Start tracking
        entry_id = db.start_time_entry(tasks['programming'])

        # Lock 1
        with freeze_time("2024-01-15 11:00:00"):
            db.set_lock_time()

        # Unlock and clear
        with freeze_time("2024-01-15 11:30:00"):
            db.clear_lock_time()

        # Lock 2
        with freeze_time("2024-01-15 12:00:00"):
            db.set_lock_time()

        # Unlock and clear
        with freeze_time("2024-01-15 13:00:00"):
            db.clear_lock_time()

        # Stop tracking
        with freeze_time("2024-01-15 14:00:00"):
            db.stop_time_entry(entry_id)

        # Should have 4 hours total
        total = db.get_task_total_time(tasks['programming'])
        assert total == 14400

    def test_database_persistence(self, temp_db):
        """Test that data persists after closing and reopening database."""
        # Add a task
        task_id = temp_db.add_task("Persistent Task")
        db_path = temp_db.db_path

        # Close database
        temp_db.close()

        # Reopen same database
        from database import TimeTrackerDB
        db2 = TimeTrackerDB(db_path)

        # Task should still exist
        task = db2.get_task_by_id(task_id)
        assert task is not None
        assert task['name'] == "Persistent Task"

        db2.close()
