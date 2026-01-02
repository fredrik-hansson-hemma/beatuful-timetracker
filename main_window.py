"""Main window for the time tracker application."""
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, Gio
from datetime import datetime, timedelta
from typing import Optional
from database import TimeTrackerDB


class MainWindow(Gtk.Window):
    """Main application window for managing tasks and time tracking."""

    def __init__(self, db: TimeTrackerDB):
        """Initialize main window."""
        super().__init__(title="Beautiful Time Tracker")

        self.db = db
        self.current_task_id = None
        self.current_entry_id = None
        self.timer_label_update_id = None
        self.tray = None  # Will be set by TimeTrackerApp

        self.set_default_size(600, 400)
        self.set_position(Gtk.WindowPosition.CENTER)

        # Connect close event to minimize to tray instead
        self.connect("delete-event", self._on_delete_event)

        self._build_ui()
        self._load_tasks()
        self._check_active_entry()

        # Update timer every second
        self._start_timer_update()

    def set_tray(self, tray):
        """Set the tray indicator reference.

        Args:
            tray: TrayIndicator instance
        """
        self.tray = tray

    def _build_ui(self):
        """Build the main UI."""
        # Main container
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        vbox.set_margin_top(10)
        vbox.set_margin_bottom(10)
        vbox.set_margin_start(10)
        vbox.set_margin_end(10)
        self.add(vbox)

        # Header
        header = Gtk.Label()
        header.set_markup("<span size='x-large' weight='bold'>Time Tracker</span>")
        vbox.pack_start(header, False, False, 0)

        # Current task section
        current_frame = Gtk.Frame(label="Aktiv tidsinmatning")
        current_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        current_box.set_margin_top(10)
        current_box.set_margin_bottom(10)
        current_box.set_margin_start(10)
        current_box.set_margin_end(10)
        current_frame.add(current_box)
        vbox.pack_start(current_frame, False, False, 10)

        self.current_task_label = Gtk.Label(label="Ingen aktiv uppgift")
        current_box.pack_start(self.current_task_label, False, False, 0)

        self.timer_label = Gtk.Label(label="00:00:00")
        self.timer_label.set_markup("<span size='xx-large' font_family='monospace'>00:00:00</span>")
        current_box.pack_start(self.timer_label, False, False, 5)

        # Stop button
        self.stop_button = Gtk.Button(label="Stoppa tidsinmatning")
        self.stop_button.set_sensitive(False)
        self.stop_button.connect("clicked", self._on_stop_clicked)
        current_box.pack_start(self.stop_button, False, False, 5)

        # Task list section
        task_frame = Gtk.Frame(label="Uppgifter")
        task_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        task_box.set_margin_top(10)
        task_box.set_margin_bottom(10)
        task_box.set_margin_start(10)
        task_box.set_margin_end(10)
        task_frame.add(task_box)
        vbox.pack_start(task_frame, True, True, 0)

        # Scrolled window for task list
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_min_content_height(200)
        task_box.pack_start(scrolled, True, True, 0)

        # Task list
        self.task_store = Gtk.ListStore(int, str, str)  # id, name, total_time
        self.task_view = Gtk.TreeView(model=self.task_store)

        # Columns
        renderer_name = Gtk.CellRendererText()
        column_name = Gtk.TreeViewColumn("Uppgift", renderer_name, text=1)
        column_name.set_expand(True)
        self.task_view.append_column(column_name)

        renderer_time = Gtk.CellRendererText()
        column_time = Gtk.TreeViewColumn("Total tid", renderer_time, text=2)
        self.task_view.append_column(column_time)

        scrolled.add(self.task_view)

        # Task buttons
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        task_box.pack_start(button_box, False, False, 5)

        new_task_button = Gtk.Button(label="Ny uppgift")
        new_task_button.connect("clicked", self._on_new_task_clicked)
        button_box.pack_start(new_task_button, True, True, 0)

        self.start_button = Gtk.Button(label="Starta tidsinmatning")
        self.start_button.get_style_context().add_class("suggested-action")
        self.start_button.connect("clicked", self._on_start_clicked)
        button_box.pack_start(self.start_button, True, True, 0)

    def _load_tasks(self):
        """Load tasks from database into the list."""
        self.task_store.clear()
        tasks = self.db.get_tasks()

        for task in tasks:
            total_seconds = self.db.get_task_total_time(task['id'])
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            time_str = f"{hours}h {minutes}m"

            self.task_store.append([task['id'], task['name'], time_str])

    def _check_active_entry(self):
        """Check if there's an active time entry and update UI."""
        active_entry = self.db.get_active_entry()

        if active_entry:
            self.current_task_id = active_entry['task_id']
            self.current_entry_id = active_entry['id']
            self.current_task_label.set_text(f"Loggar tid på: {active_entry['task_name']}")
            self.stop_button.set_sensitive(True)
            self.start_button.set_sensitive(False)
        else:
            self.current_task_id = None
            self.current_entry_id = None
            self.current_task_label.set_text("Ingen aktiv uppgift")
            self.stop_button.set_sensitive(False)
            self.start_button.set_sensitive(True)

    def _start_timer_update(self):
        """Start updating the timer display."""
        if self.timer_label_update_id:
            GLib.source_remove(self.timer_label_update_id)

        self.timer_label_update_id = GLib.timeout_add(1000, self._update_timer)

    def _update_timer(self):
        """Update the timer display."""
        if self.current_entry_id:
            active_entry = self.db.get_active_entry()
            if active_entry:
                start_time = datetime.fromisoformat(active_entry['start_time'])
                elapsed = datetime.now() - start_time
                hours = int(elapsed.total_seconds() // 3600)
                minutes = int((elapsed.total_seconds() % 3600) // 60)
                seconds = int(elapsed.total_seconds() % 60)
                time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                self.timer_label.set_markup(
                    f"<span size='xx-large' font_family='monospace'>{time_str}</span>"
                )
        else:
            self.timer_label.set_markup(
                "<span size='xx-large' font_family='monospace'>00:00:00</span>"
            )

        return True  # Continue calling

    def _on_new_task_clicked(self, button):
        """Handle new task button click."""
        dialog = Gtk.Dialog(
            title="Ny uppgift",
            parent=self,
            modal=True,
            destroy_with_parent=True
        )
        dialog.add_button("Avbryt", Gtk.ResponseType.CANCEL)
        dialog.add_button("Skapa", Gtk.ResponseType.OK)

        content = dialog.get_content_area()
        content.set_spacing(10)
        content.set_margin_top(10)
        content.set_margin_bottom(10)
        content.set_margin_start(10)
        content.set_margin_end(10)

        label = Gtk.Label(label="Uppgiftens namn:")
        content.pack_start(label, False, False, 0)

        entry = Gtk.Entry()
        entry.set_activates_default(True)
        content.pack_start(entry, False, False, 0)

        dialog.set_default_response(Gtk.ResponseType.OK)
        dialog.show_all()

        response = dialog.run()
        task_name = entry.get_text().strip()
        dialog.destroy()

        if response == Gtk.ResponseType.OK and task_name:
            try:
                self.db.add_task(task_name)
                self._load_tasks()
                # Update tray menu with new task
                if self.tray:
                    self.tray.refresh_tasks()
            except Exception as e:
                error_dialog = Gtk.MessageDialog(
                    parent=self,
                    modal=True,
                    message_type=Gtk.MessageType.ERROR,
                    buttons=Gtk.ButtonsType.OK,
                    text=f"Kunde inte skapa uppgift: {e}"
                )
                error_dialog.run()
                error_dialog.destroy()

    def _on_start_clicked(self, button):
        """Handle start button click."""
        selection = self.task_view.get_selection()
        model, tree_iter = selection.get_selected()

        if tree_iter:
            task_id = model[tree_iter][0]
            self.start_tracking(task_id)
        else:
            dialog = Gtk.MessageDialog(
                parent=self,
                modal=True,
                message_type=Gtk.MessageType.WARNING,
                buttons=Gtk.ButtonsType.OK,
                text="Välj en uppgift först"
            )
            dialog.run()
            dialog.destroy()

    def _on_stop_clicked(self, button):
        """Handle stop button click."""
        self.stop_tracking()

    def start_tracking(self, task_id: int):
        """Start tracking time for a task."""
        if self.current_entry_id:
            self.stop_tracking()

        self.current_entry_id = self.db.start_time_entry(task_id)
        self.current_task_id = task_id

        task = self.db.get_task_by_id(task_id)
        if task:
            self.current_task_label.set_text(f"Loggar tid på: {task['name']}")

        self.stop_button.set_sensitive(True)
        self.start_button.set_sensitive(False)

        # Update tray
        if self.tray:
            self.tray.update_state()

    def stop_tracking(self):
        """Stop tracking the current task."""
        if self.current_entry_id:
            self.db.stop_time_entry(self.current_entry_id)
            self.current_entry_id = None
            self.current_task_id = None

            self.current_task_label.set_text("Ingen aktiv uppgift")
            self.stop_button.set_sensitive(False)
            self.start_button.set_sensitive(True)

            self._load_tasks()  # Refresh to show updated times

            # Update tray
            if self.tray:
                self.tray.update_state()

    def _on_delete_event(self, widget, event):
        """Handle window close - hide instead of destroying."""
        self.hide()
        return True  # Prevent default destroy behavior

    def cleanup(self):
        """Cleanup before closing."""
        if self.timer_label_update_id:
            GLib.source_remove(self.timer_label_update_id)
