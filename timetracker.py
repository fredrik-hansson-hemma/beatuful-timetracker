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
from away_time_dialog import AwayTimeDialog
from tray_indicator import TrayIndicator


class TimeTrackerApp:
    """Main time tracker application with lock/unlock handling."""

    def __init__(self):
        """Initialize the application."""
        self.db = TimeTrackerDB()
        self.main_window = MainWindow(self.db)
        self.bus = SessionBus()
        self.lock_time = None
        self.heartbeat_update_id = None

        # Setup system tray indicator
        self.tray = TrayIndicator(self)
        self.main_window.set_tray(self.tray)

        # Setup DBus signal listeners for screen lock/unlock
        self._setup_dbus_listeners()

        # Check if we were locked and need to show unlock dialog
        self._check_unlock_on_startup()

        # Start heartbeat timer (updates every 60 seconds while tracking)
        self._start_heartbeat_timer()

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
        """Check on startup if we need to show unlock dialog or handle crash recovery."""
        # First check for orphaned entries (crash recovery)
        active_entry = self.db.get_active_entry()
        state = self.db.get_session_state()

        if active_entry and not state['lock_time']:
            # We have an active entry but no lock time - likely a crash
            start_time = datetime.fromisoformat(active_entry['start_time'])
            elapsed = datetime.now() - start_time

            # If entry is older than 5 minutes, treat as orphaned
            if elapsed.total_seconds() > 300:
                print("Detected orphaned entry, showing crash recovery dialog")
                GLib.timeout_add(500, self._handle_crash_recovery, active_entry)
                return

        # Normal unlock dialog logic
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

        # Show dialog - is_crash=False for unlock scenario
        dialog = AwayTimeDialog(self.db, task['name'], locked_duration, is_crash=False)
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

            # Resume tracking on the original task (before the lock)
            self.main_window.start_tracking(state['active_task_id'])

        elif action == 'skip':
            # Don't log the time - just stop the entry at lock time
            if state['last_entry_id']:
                self.db.stop_time_entry(state['last_entry_id'], lock_time)

        # Clear lock state
        self.db.clear_lock_time()

        # Update UI
        self.main_window._check_active_entry()
        self.main_window._load_tasks()

        # Update tray
        self.tray.update_state()

        return False  # Don't repeat timeout

    def _handle_crash_recovery(self, orphaned_entry):
        """Handle crash recovery for orphaned time entry.

        Args:
            orphaned_entry: The orphaned time entry from database
        """
        # Calculate time since crash
        start_time = datetime.fromisoformat(orphaned_entry['start_time'])
        now = datetime.now()
        crash_duration = now - start_time

        # Show unified dialog - is_crash=True for crash scenario
        dialog = AwayTimeDialog(
            self.db,
            orphaned_entry['task_name'],
            crash_duration,
            is_crash=True,
            start_time=start_time
        )
        action, other_task_id = dialog.run_and_get_result()
        dialog.destroy()

        # Handle user's choice - same logic as unlock
        if action == 'continue':
            # Continue logging - entry remains active, will log all time since start
            print(f"Crash recovery: Continuing tracking on task {orphaned_entry['task_id']}")

        elif action == 'other':
            # Log crash time to a different task
            # Stop the orphaned entry at crash time (we use start_time as approximation)
            self.db.stop_time_entry(orphaned_entry['id'], start_time)

            # Create entry for crash time on the other task
            entry_id = self.db.start_time_entry(other_task_id, start_time)
            self.db.stop_time_entry(entry_id, now)

            # Resume tracking on the original task
            self.main_window.start_tracking(orphaned_entry['task_id'])
            print(f"Crash recovery: Logged time to different task")

        elif action == 'skip':
            # Don't log the crash time - just delete the orphaned entry
            self.db.delete_time_entry(orphaned_entry['id'])
            print(f"Crash recovery: Skipped/deleted orphaned entry")

        # Old edit action removed - users can edit entries via the entries window
        if False:  # Keeping old code structure for reference
            edited_data = None
            if edited_data:
                success = self.db.update_time_entry(
                    edited_data['id'],
                    edited_data['task_id'],
                    edited_data['start_time'],
                    edited_data['end_time'],
                    edited_data['duration_seconds'],
                    edited_data['note']
                )
                if success:
                    print(f"Crash recovery: Updated entry with edited data")
                else:
                    print(f"Crash recovery: Failed to update entry")

        elif action == 'cancel':
            # User cancelled - just stop the entry
            self.db.stop_time_entry(orphaned_entry['id'], now)
            print(f"Crash recovery: User cancelled, stopped entry")

        # Update UI
        self.main_window._check_active_entry()
        self.main_window._load_tasks()
        self.tray.update_state()

        return False  # Don't repeat timeout

    def _start_heartbeat_timer(self):
        """Start the heartbeat update timer."""
        if self.heartbeat_update_id:
            GLib.source_remove(self.heartbeat_update_id)

        # Update heartbeat every 60 seconds
        self.heartbeat_update_id = GLib.timeout_add(60000, self._update_heartbeat)

    def _update_heartbeat(self):
        """Update heartbeat if tracking is active."""
        active_entry = self.db.get_active_entry()

        if active_entry:
            self.db.update_heartbeat()

        return True  # Continue calling

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
        if self.heartbeat_update_id:
            GLib.source_remove(self.heartbeat_update_id)
        self.tray.cleanup()
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
