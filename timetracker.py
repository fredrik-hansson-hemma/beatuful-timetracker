#!/usr/bin/env python3
"""Beautiful Time Tracker - Main application."""
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib
import signal
import sys
from datetime import datetime, timedelta
from pydbus import SessionBus
from database import TimeTrackerDB
from main_window import MainWindow
from unlock_dialog import UnlockDialog


class TimeTrackerApp:
    """Main time tracker application with lock/unlock handling."""

    def __init__(self):
        """Initialize the application."""
        self.db = TimeTrackerDB()
        self.main_window = MainWindow(self.db)
        self.bus = SessionBus()
        self.lock_time = None

        # Setup DBus signal listeners for screen lock/unlock
        self._setup_dbus_listeners()

        # Check if we were locked and need to show unlock dialog
        self._check_unlock_on_startup()

        # Show main window
        self.main_window.show_all()

    def _setup_dbus_listeners(self):
        """Setup DBus listeners for lock/unlock signals."""
        try:
            # Listen to screensaver signals (works for GNOME, Unity, etc.)
            screensaver = self.bus.get(
                'org.gnome.ScreenSaver',
                '/org/gnome/ScreenSaver'
            )
            screensaver.ActiveChanged.connect(self._on_lock_state_changed)
        except Exception as e:
            print(f"Warning: Could not connect to screensaver DBus: {e}")

        try:
            # Also listen to login1 (systemd) signals as fallback
            login1 = self.bus.get(
                'org.freedesktop.login1',
                '/org/freedesktop/login1'
            )
            login1.PrepareForSleep.connect(self._on_prepare_for_sleep)
        except Exception as e:
            print(f"Warning: Could not connect to login1 DBus: {e}")

    def _on_lock_state_changed(self, locked):
        """Handle screen lock state change.

        Args:
            locked: True if screen was locked, False if unlocked
        """
        if locked:
            self._on_lock()
        else:
            self._on_unlock()

    def _on_prepare_for_sleep(self, sleeping):
        """Handle system suspend/resume.

        Args:
            sleeping: True if going to sleep, False if waking up
        """
        if sleeping:
            self._on_lock()
        else:
            self._on_unlock()

    def _on_lock(self):
        """Handle screen lock event."""
        print("Screen locked")

        # Check if there's an active task
        state = self.db.get_session_state()
        if state and state['active_task_id']:
            # Record the lock time
            self.lock_time = datetime.now()
            self.db.set_lock_time(self.lock_time)
            print(f"Active task detected, lock time recorded: {self.lock_time}")

    def _on_unlock(self):
        """Handle screen unlock event."""
        print("Screen unlocked")
        self._show_unlock_dialog_if_needed()

    def _check_unlock_on_startup(self):
        """Check on startup if we need to show unlock dialog."""
        state = self.db.get_session_state()

        if state and state['lock_time'] and state['active_task_id']:
            print("Detected previous lock, showing unlock dialog")
            # Delay slightly to ensure window manager is ready
            GLib.timeout_add(500, self._show_unlock_dialog_if_needed)

    def _show_unlock_dialog_if_needed(self):
        """Show unlock dialog if there was an active task when locked."""
        state = self.db.get_session_state()

        if not state or not state['lock_time'] or not state['active_task_id']:
            return False

        lock_time = datetime.fromisoformat(state['lock_time'])
        unlock_time = datetime.now()
        locked_duration = unlock_time - lock_time

        # Only show dialog if locked for more than 1 minute
        if locked_duration.total_seconds() < 60:
            self.db.clear_lock_time()
            return False

        # Get task info
        task = self.db.get_task_by_id(state['active_task_id'])
        if not task:
            self.db.clear_lock_time()
            return False

        # Show dialog
        dialog = UnlockDialog(self.db, task['name'], locked_duration)
        action, other_task_id = dialog.run_and_get_result()
        dialog.destroy()

        # Handle user's choice
        if action == 'continue':
            # Continue logging on the same task - update entry end time
            if state['last_entry_id']:
                self.db.stop_time_entry(state['last_entry_id'], unlock_time)
                # Start a new entry from lock_time to now
                entry_id = self.db.start_time_entry(state['active_task_id'], lock_time)
                self.db.stop_time_entry(entry_id, unlock_time)
                # Resume tracking
                self.main_window.start_tracking(state['active_task_id'])

        elif action == 'other':
            # Log to a different task
            if state['last_entry_id']:
                self.db.stop_time_entry(state['last_entry_id'], lock_time)

            # Create entry for the locked period on the other task
            entry_id = self.db.start_time_entry(other_task_id, lock_time)
            self.db.stop_time_entry(entry_id, unlock_time)

            # Don't auto-start tracking after this

        elif action == 'skip':
            # Don't log the time - just stop the entry at lock time
            if state['last_entry_id']:
                self.db.stop_time_entry(state['last_entry_id'], lock_time)

        # Clear lock state
        self.db.clear_lock_time()

        # Update UI
        self.main_window._check_active_entry()
        self.main_window._load_tasks()

        return False  # Don't repeat timeout

    def run(self):
        """Run the application."""
        # Handle Ctrl+C gracefully
        signal.signal(signal.SIGINT, signal.SIG_DFL)

        try:
            Gtk.main()
        finally:
            self.cleanup()

    def cleanup(self):
        """Cleanup before exit."""
        self.main_window.cleanup()
        self.db.close()

    def quit(self):
        """Quit the application."""
        Gtk.main_quit()


def main():
    """Main entry point."""
    app = TimeTrackerApp()
    app.run()


if __name__ == '__main__':
    main()
