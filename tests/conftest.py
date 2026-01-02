"""Pytest configuration and fixtures for Beautiful Time Tracker tests."""
import pytest
import tempfile
import os
from datetime import datetime
from database import TimeTrackerDB


@pytest.fixture
def temp_db():
    """Create a temporary test database.

    Yields:
        TimeTrackerDB: A database instance using a temporary file
    """
    # Create a temporary database file
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db') as f:
        db_path = f.name

    # Create database instance
    db = TimeTrackerDB(db_path)

    yield db

    # Cleanup
    db.close()
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def db_with_tasks(temp_db):
    """Create a database with sample tasks.

    Args:
        temp_db: Temporary database fixture

    Yields:
        tuple: (TimeTrackerDB, dict) where dict contains task_ids
    """
    task1_id = temp_db.add_task("Programming", "Writing code")
    task2_id = temp_db.add_task("Meetings", "Team meetings")
    task3_id = temp_db.add_task("Documentation", "Writing docs")

    yield temp_db, {
        'programming': task1_id,
        'meetings': task2_id,
        'documentation': task3_id
    }


@pytest.fixture
def fixed_time():
    """Provide a fixed datetime for testing.

    Returns:
        datetime: A fixed datetime (2024-01-15 10:00:00)
    """
    return datetime(2024, 1, 15, 10, 0, 0)
