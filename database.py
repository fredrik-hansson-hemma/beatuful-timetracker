"""Database management for time tracking."""
import sqlite3
import os
from datetime import datetime
from typing import List, Optional, Tuple


class TimeTrackerDB:
    """Manages SQLite database for time tracking."""

    def __init__(self, db_path: str = None):
        """Initialize database connection."""
        if db_path is None:
            db_path = os.path.join(
                os.path.expanduser("~/.local/share"),
                "timetracker",
                "timetracker.db"
            )

        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        """Create necessary database tables."""
        cursor = self.conn.cursor()

        # Categories table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                color TEXT,
                active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Tasks table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                category_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                active INTEGER DEFAULT 1,
                FOREIGN KEY (category_id) REFERENCES categories(id)
            )
        """)

        # Time entries table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS time_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                start_time TIMESTAMP NOT NULL,
                end_time TIMESTAMP,
                duration_seconds INTEGER,
                note TEXT,
                FOREIGN KEY (task_id) REFERENCES tasks(id)
            )
        """)

        # Session state table (for tracking lock/unlock state)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS session_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                active_task_id INTEGER,
                lock_time TIMESTAMP,
                last_entry_id INTEGER,
                last_heartbeat TIMESTAMP,
                FOREIGN KEY (active_task_id) REFERENCES tasks(id),
                FOREIGN KEY (last_entry_id) REFERENCES time_entries(id)
            )
        """)

        # Initialize session state if not exists
        cursor.execute("""
            INSERT OR IGNORE INTO session_state (id, active_task_id, lock_time, last_entry_id, last_heartbeat)
            VALUES (1, NULL, NULL, NULL, NULL)
        """)

        # Create default categories if none exist
        cursor.execute("SELECT COUNT(*) as count FROM categories")
        if cursor.fetchone()['count'] == 0:
            default_categories = [
                ("Fakturerbar tid", "Tid som faktureras till kund", "#4CAF50"),
                ("Utbildning", "Kompetensutveckling och lärande", "#2196F3"),
                ("Interna möten", "Möten med kollegor och ledning", "#FF9800"),
                ("Interna projekt", "Projekt som inte faktureras", "#9C27B0"),
                ("Övrigt", "Övriga aktiviteter", "#757575")
            ]
            cursor.executemany(
                "INSERT INTO categories (name, description, color) VALUES (?, ?, ?)",
                default_categories
            )

        self.conn.commit()

    def add_task(self, name: str, description: str = "", category_id: int = None) -> int:
        """Add a new task."""
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO tasks (name, description, category_id) VALUES (?, ?, ?)",
            (name, description, category_id)
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_tasks(self, active_only: bool = True) -> List[sqlite3.Row]:
        """Get all tasks."""
        cursor = self.conn.cursor()
        if active_only:
            cursor.execute("SELECT * FROM tasks WHERE active = 1 ORDER BY name")
        else:
            cursor.execute("SELECT * FROM tasks ORDER BY name")
        return cursor.fetchall()

    def get_task_by_id(self, task_id: int) -> Optional[sqlite3.Row]:
        """Get a task by ID."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        return cursor.fetchone()

    def get_all_tasks(self, search: str = None, active_only: bool = False) -> List[sqlite3.Row]:
        """Get all tasks with optional search filter.

        Args:
            search: Optional search string to filter by name
            active_only: If True, only return active tasks

        Returns:
            List of task rows
        """
        cursor = self.conn.cursor()
        query = "SELECT * FROM tasks WHERE 1=1"
        params = []

        if active_only:
            query += " AND active = 1"

        if search:
            query += " AND name LIKE ?"
            params.append(f"%{search}%")

        query += " ORDER BY name"

        cursor.execute(query, params)
        return cursor.fetchall()

    def update_task(self, task_id: int, name: str, description: str = None, category_id: int = None) -> bool:
        """Update a task's name, description, and/or category.

        Args:
            task_id: ID of the task to update
            name: New name for the task
            description: New description (optional)
            category_id: New category ID (optional)

        Returns:
            True if update was successful, False otherwise
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE tasks SET name = ?, description = ?, category_id = ? WHERE id = ?",
            (name, description, category_id, task_id)
        )
        self.conn.commit()
        return cursor.rowcount > 0

    def deactivate_task(self, task_id: int) -> bool:
        """Deactivate a task.

        Args:
            task_id: ID of the task to deactivate

        Returns:
            True if deactivation was successful, False otherwise
        """
        cursor = self.conn.cursor()
        cursor.execute("UPDATE tasks SET active = 0 WHERE id = ?", (task_id,))
        self.conn.commit()
        return cursor.rowcount > 0

    def activate_task(self, task_id: int) -> bool:
        """Activate a task.

        Args:
            task_id: ID of the task to activate

        Returns:
            True if activation was successful, False otherwise
        """
        cursor = self.conn.cursor()
        cursor.execute("UPDATE tasks SET active = 1 WHERE id = ?", (task_id,))
        self.conn.commit()
        return cursor.rowcount > 0

    def delete_task(self, task_id: int) -> Tuple[bool, str]:
        """Delete a task if it has no logged time.

        Args:
            task_id: ID of the task to delete

        Returns:
            Tuple of (success: bool, error_message: str)
        """
        cursor = self.conn.cursor()

        # Check if task has any time entries
        cursor.execute(
            "SELECT COUNT(*) as count FROM time_entries WHERE task_id = ?",
            (task_id,)
        )
        count = cursor.fetchone()['count']

        if count > 0:
            return (False, f"Kan inte radera uppgift med {count} loggade tidsinmatningar. Inaktivera istället.")

        # Delete the task
        cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        self.conn.commit()

        if cursor.rowcount > 0:
            return (True, "")
        else:
            return (False, "Uppgiften hittades inte.")

    # Category management methods

    def add_category(self, name: str, description: str = "", color: str = "#757575") -> int:
        """Add a new category.

        Args:
            name: Category name
            description: Category description (optional)
            color: Hex color code for the category (optional)

        Returns:
            ID of the created category
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO categories (name, description, color) VALUES (?, ?, ?)",
            (name, description, color)
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_all_categories(self, search: str = None, active_only: bool = False) -> List[sqlite3.Row]:
        """Get all categories with optional search filter.

        Args:
            search: Optional search string to filter by name
            active_only: If True, only return active categories

        Returns:
            List of category rows
        """
        cursor = self.conn.cursor()
        query = "SELECT * FROM categories WHERE 1=1"
        params = []

        if active_only:
            query += " AND active = 1"

        if search:
            query += " AND name LIKE ?"
            params.append(f"%{search}%")

        query += " ORDER BY name"

        cursor.execute(query, params)
        return cursor.fetchall()

    def get_category_by_id(self, category_id: int) -> Optional[sqlite3.Row]:
        """Get a category by ID."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM categories WHERE id = ?", (category_id,))
        return cursor.fetchone()

    def update_category(self, category_id: int, name: str, description: str = None, color: str = None) -> bool:
        """Update a category's name, description, and/or color.

        Args:
            category_id: ID of the category to update
            name: New name for the category
            description: New description (optional)
            color: New color (optional)

        Returns:
            True if update was successful, False otherwise
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE categories SET name = ?, description = ?, color = ? WHERE id = ?",
            (name, description, color, category_id)
        )
        self.conn.commit()
        return cursor.rowcount > 0

    def deactivate_category(self, category_id: int) -> bool:
        """Deactivate a category.

        Args:
            category_id: ID of the category to deactivate

        Returns:
            True if deactivation was successful, False otherwise
        """
        cursor = self.conn.cursor()
        cursor.execute("UPDATE categories SET active = 0 WHERE id = ?", (category_id,))
        self.conn.commit()
        return cursor.rowcount > 0

    def activate_category(self, category_id: int) -> bool:
        """Activate a category.

        Args:
            category_id: ID of the category to activate

        Returns:
            True if activation was successful, False otherwise
        """
        cursor = self.conn.cursor()
        cursor.execute("UPDATE categories SET active = 1 WHERE id = ?", (category_id,))
        self.conn.commit()
        return cursor.rowcount > 0

    def delete_category(self, category_id: int) -> Tuple[bool, str]:
        """Delete a category if it has no associated tasks.

        Args:
            category_id: ID of the category to delete

        Returns:
            Tuple of (success: bool, error_message: str)
        """
        cursor = self.conn.cursor()

        # Check if category has any tasks
        cursor.execute(
            "SELECT COUNT(*) as count FROM tasks WHERE category_id = ?",
            (category_id,)
        )
        count = cursor.fetchone()['count']

        if count > 0:
            return (False, f"Kan inte radera kategori med {count} kopplade uppgifter. Inaktivera istället.")

        # Delete the category
        cursor.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        self.conn.commit()

        if cursor.rowcount > 0:
            return (True, "")
        else:
            return (False, "Kategorin hittades inte.")

    def start_time_entry(self, task_id: int, start_time: datetime = None) -> int:
        """Start a new time entry for a task."""
        if start_time is None:
            start_time = datetime.now()

        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO time_entries (task_id, start_time) VALUES (?, ?)",
            (task_id, start_time)
        )
        entry_id = cursor.lastrowid

        # Update session state and set initial heartbeat
        cursor.execute(
            "UPDATE session_state SET active_task_id = ?, last_entry_id = ?, last_heartbeat = ? WHERE id = 1",
            (task_id, entry_id, start_time)
        )

        self.conn.commit()
        return entry_id

    def stop_time_entry(self, entry_id: int, end_time: datetime = None) -> int:
        """Stop a time entry and calculate duration."""
        if end_time is None:
            end_time = datetime.now()

        cursor = self.conn.cursor()
        cursor.execute("SELECT start_time FROM time_entries WHERE id = ?", (entry_id,))
        row = cursor.fetchone()

        if not row:
            return 0

        start_time = datetime.fromisoformat(row['start_time'])
        duration = int((end_time - start_time).total_seconds())

        cursor.execute(
            "UPDATE time_entries SET end_time = ?, duration_seconds = ? WHERE id = ?",
            (end_time, duration, entry_id)
        )

        # Clear active task and heartbeat from session state
        cursor.execute(
            "UPDATE session_state SET active_task_id = NULL, last_entry_id = NULL, last_heartbeat = NULL WHERE id = 1"
        )

        self.conn.commit()
        return duration

    def update_time_entry(self, entry_id: int, task_id: int, start_time: datetime,
                         end_time: Optional[datetime], duration_seconds: int,
                         note: Optional[str] = None) -> bool:
        """Update an existing time entry.

        Args:
            entry_id: ID of entry to update
            task_id: New task ID
            start_time: New start time
            end_time: New end time (can be None)
            duration_seconds: New duration in seconds
            note: Optional note

        Returns:
            True if update successful, False otherwise
        """
        cursor = self.conn.cursor()

        # Check if entry exists
        cursor.execute("SELECT id FROM time_entries WHERE id = ?", (entry_id,))
        if not cursor.fetchone():
            return False

        cursor.execute("""
            UPDATE time_entries
            SET task_id = ?, start_time = ?, end_time = ?, duration_seconds = ?, note = ?
            WHERE id = ?
        """, (task_id, start_time, end_time, duration_seconds, note, entry_id))

        self.conn.commit()
        return True

    def delete_time_entry(self, entry_id: int) -> bool:
        """Delete a time entry.

        Args:
            entry_id: ID of entry to delete

        Returns:
            True if deletion successful, False otherwise
        """
        cursor = self.conn.cursor()

        # Clear from session state if it's the active entry
        cursor.execute("""
            UPDATE session_state
            SET active_task_id = NULL, last_entry_id = NULL
            WHERE last_entry_id = ?
        """, (entry_id,))

        # Delete the entry
        cursor.execute("DELETE FROM time_entries WHERE id = ?", (entry_id,))

        self.conn.commit()
        return cursor.rowcount > 0

    def get_session_state(self) -> Optional[sqlite3.Row]:
        """Get current session state."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM session_state WHERE id = 1")
        return cursor.fetchone()

    def set_lock_time(self, lock_time: datetime = None):
        """Record when the screen was locked."""
        if lock_time is None:
            lock_time = datetime.now()

        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE session_state SET lock_time = ? WHERE id = 1",
            (lock_time,)
        )
        self.conn.commit()

    def clear_lock_time(self):
        """Clear the lock time."""
        cursor = self.conn.cursor()
        cursor.execute("UPDATE session_state SET lock_time = NULL WHERE id = 1")
        self.conn.commit()

    def update_heartbeat(self, heartbeat_time: datetime = None):
        """Update the last heartbeat timestamp.

        This is called periodically while tracking to help estimate crash time.

        Args:
            heartbeat_time: Timestamp to record. If None, uses current time.
        """
        if heartbeat_time is None:
            heartbeat_time = datetime.now()

        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE session_state SET last_heartbeat = ? WHERE id = 1",
            (heartbeat_time,)
        )
        self.conn.commit()

    def clear_heartbeat(self):
        """Clear the heartbeat timestamp."""
        cursor = self.conn.cursor()
        cursor.execute("UPDATE session_state SET last_heartbeat = NULL WHERE id = 1")
        self.conn.commit()

    def get_active_entry(self) -> Optional[sqlite3.Row]:
        """Get the currently active time entry."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT te.*, t.name as task_name
            FROM time_entries te
            JOIN tasks t ON te.task_id = t.id
            WHERE te.end_time IS NULL
            ORDER BY te.start_time DESC
            LIMIT 1
        """)
        return cursor.fetchone()

    def get_task_total_time(self, task_id: int) -> int:
        """Get total time logged for a task in seconds."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT SUM(duration_seconds) as total FROM time_entries WHERE task_id = ?",
            (task_id,)
        )
        row = cursor.fetchone()
        return row['total'] or 0

    def get_entries(self, start_date: datetime = None, end_date: datetime = None,
                    task_id: int = None) -> list:
        """Get time entries with optional filtering.

        Args:
            start_date: Filter entries starting from this date (inclusive)
            end_date: Filter entries up to this date (inclusive)
            task_id: Filter entries for specific task

        Returns:
            List of time entry rows with task name included
        """
        cursor = self.conn.cursor()

        query = """
            SELECT te.*, t.name as task_name
            FROM time_entries te
            JOIN tasks t ON te.task_id = t.id
            WHERE 1=1
        """
        params = []

        if start_date:
            query += " AND te.start_time >= ?"
            params.append(start_date.isoformat())

        if end_date:
            # Add one day to end_date to make it inclusive
            end_date_inclusive = end_date + timedelta(days=1)
            query += " AND te.start_time < ?"
            params.append(end_date_inclusive.isoformat())

        if task_id:
            query += " AND te.task_id = ?"
            params.append(task_id)

        query += " ORDER BY te.start_time DESC"

        cursor.execute(query, params)
        return cursor.fetchall()

    def close(self):
        """Close database connection."""
        self.conn.close()
