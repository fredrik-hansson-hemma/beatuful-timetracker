"""System tray indicator for Beautiful Time Tracker."""
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('AppIndicator3', '0.1')
from gi.repository import Gtk, GLib, AppIndicator3
from datetime import datetime
from typing import Optional


class TrayIndicator:
    """System tray indicator with menu for time tracker."""

    def __init__(self, app):
        """Initialize the tray indicator.

        Args:
            app: The TimeTrackerApp instance
        """
        self.app = app
        self.db = app.db
        self.main_window = app.main_window

        # Create indicator
        self.indicator = AppIndicator3.Indicator.new(
            "beautiful-timetracker",
            "org.gnome.clocks",  # Default icon
            AppIndicator3.IndicatorCategory.APPLICATION_STATUS
        )
        self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
        self.indicator.set_title("Time Tracker")

        # Create menu
        self.menu = Gtk.Menu()
        self._build_menu()
        self.indicator.set_menu(self.menu)

        # Update timer display regularly
        self.timer_update_id = GLib.timeout_add(1000, self._update_timer_menu_item)

        # Track current active entry
        self.current_entry_id = None

    def _build_menu(self):
        """Build the tray menu."""
        # Status item (shows current task and timer)
        self.status_item = Gtk.MenuItem(label="Ingen aktiv uppgift")
        self.status_item.set_sensitive(False)
        self.menu.append(self.status_item)

        # Separator
        self.menu.append(Gtk.SeparatorMenuItem())

        # Show/Hide window
        self.show_window_item = Gtk.MenuItem(label="Visa fönster")
        self.show_window_item.connect("activate", self._on_toggle_window)
        self.menu.append(self.show_window_item)

        # Separator
        self.menu.append(Gtk.SeparatorMenuItem())

        # Start tracking submenu
        self.start_menu_item = Gtk.MenuItem(label="Starta tidsinmatning")
        self.start_submenu = Gtk.Menu()
        self.start_menu_item.set_submenu(self.start_submenu)
        self.menu.append(self.start_menu_item)

        # Stop tracking
        self.stop_item = Gtk.MenuItem(label="Stoppa tidsinmatning")
        self.stop_item.connect("activate", self._on_stop_tracking)
        self.stop_item.set_sensitive(False)
        self.menu.append(self.stop_item)

        # Separator
        self.menu.append(Gtk.SeparatorMenuItem())

        # Quit
        quit_item = Gtk.MenuItem(label="Avsluta")
        quit_item.connect("activate", self._on_quit)
        self.menu.append(quit_item)

        self.menu.show_all()

        # Initial update
        self._update_menu()

    def _update_menu(self):
        """Update menu items based on current state."""
        # Update start submenu with current tasks
        for item in self.start_submenu.get_children():
            self.start_submenu.remove(item)

        tasks = self.db.get_tasks()
        for task in tasks:
            task_item = Gtk.MenuItem(label=task['name'])
            task_item.connect("activate", self._on_start_tracking, task['id'])
            self.start_submenu.append(task_item)

        if not tasks:
            no_tasks = Gtk.MenuItem(label="Inga uppgifter")
            no_tasks.set_sensitive(False)
            self.start_submenu.append(no_tasks)

        self.start_submenu.show_all()

        # Update based on active entry
        active_entry = self.db.get_active_entry()
        if active_entry:
            self.current_entry_id = active_entry['id']
            self.stop_item.set_sensitive(True)
            self.start_menu_item.set_sensitive(False)
            self._update_icon_active()
        else:
            self.current_entry_id = None
            self.stop_item.set_sensitive(False)
            self.start_menu_item.set_sensitive(True)
            self._update_icon_inactive()

    def _update_timer_menu_item(self):
        """Update the timer display in the menu."""
        active_entry = self.db.get_active_entry()

        if active_entry:
            start_time = datetime.fromisoformat(active_entry['start_time'])
            elapsed = datetime.now() - start_time
            hours = int(elapsed.total_seconds() // 3600)
            minutes = int((elapsed.total_seconds() % 3600) // 60)
            seconds = int(elapsed.total_seconds() % 60)
            time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

            label = f"▶ {active_entry['task_name']} - {time_str}"
            self.status_item.set_label(label)
            self.indicator.set_title(f"Time Tracker - {time_str}")
        else:
            self.status_item.set_label("Ingen aktiv uppgift")
            self.indicator.set_title("Time Tracker")

        return True  # Continue calling

    def _update_icon_active(self):
        """Update icon to show tracking is active."""
        # Use a different icon to indicate active tracking
        self.indicator.set_icon("media-playback-start")

    def _update_icon_inactive(self):
        """Update icon to show tracking is inactive."""
        self.indicator.set_icon("org.gnome.clocks")

    def _on_toggle_window(self, widget):
        """Toggle main window visibility."""
        if self.main_window.get_visible():
            self.main_window.hide()
            self.show_window_item.set_label("Visa fönster")
        else:
            self.main_window.present()
            self.show_window_item.set_label("Dölj fönster")

    def _on_start_tracking(self, widget, task_id):
        """Start tracking a task from the menu.

        Args:
            widget: Menu item widget
            task_id: ID of task to start tracking
        """
        self.main_window.start_tracking(task_id)
        self._update_menu()

    def _on_stop_tracking(self, widget):
        """Stop tracking from the menu."""
        self.main_window.stop_tracking()
        self._update_menu()

    def _on_quit(self, widget):
        """Quit the application."""
        self.app.quit()

    def refresh_tasks(self):
        """Refresh the task list in the menu."""
        self._update_menu()

    def update_state(self):
        """Update the tray state based on current tracking state."""
        self._update_menu()

    def cleanup(self):
        """Cleanup before closing."""
        if self.timer_update_id:
            GLib.source_remove(self.timer_update_id)
