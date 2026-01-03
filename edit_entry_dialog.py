"""Reusable dialog for editing time entries."""
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
from datetime import datetime, timedelta
from typing import Optional, Dict
from database import TimeTrackerDB


class EditEntryDialog(Gtk.Dialog):
    """Reusable dialog for editing time entry properties."""

    def __init__(self, parent, db: TimeTrackerDB, entry_data: Optional[Dict] = None):
        """Initialize the edit entry dialog.

        Args:
            parent: Parent window
            db: Database instance
            entry_data: Optional dict with entry data to edit. If None, creates new entry.
                       Expected keys: id, task_id, start_time, end_time, duration_seconds, note
        """
        super().__init__(
            title="Editera tidsinmatning",
            parent=parent,
            modal=True,
            destroy_with_parent=True
        )

        self.db = db
        self.entry_data = entry_data or {}
        self._updating = False  # Flag to prevent recursive updates

        self.set_default_size(500, 400)
        self.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)

        self._build_ui()
        self._populate_fields()

        # Add buttons
        self.add_button("Avbryt", Gtk.ResponseType.CANCEL)
        save_button = self.add_button("Spara", Gtk.ResponseType.OK)
        save_button.get_style_context().add_class("suggested-action")

    def _build_ui(self):
        """Build the dialog UI."""
        content = self.get_content_area()
        content.set_spacing(15)
        content.set_margin_top(20)
        content.set_margin_bottom(20)
        content.set_margin_start(20)
        content.set_margin_end(20)

        # Task selection
        task_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        task_label = Gtk.Label(label="Uppgift:")
        task_label.set_width_chars(12)
        task_label.set_xalign(0)
        task_box.pack_start(task_label, False, False, 0)

        self.task_combo = Gtk.ComboBoxText()
        tasks = self.db.get_tasks(active_only=False)
        for task in tasks:
            self.task_combo.append(str(task['id']), task['name'])
        task_box.pack_start(self.task_combo, True, True, 0)
        content.pack_start(task_box, False, False, 0)

        # Separator
        content.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 5)

        # Start time
        start_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        start_label = Gtk.Label(label="Starttid:")
        start_label.set_width_chars(12)
        start_label.set_xalign(0)
        start_box.pack_start(start_label, False, False, 0)

        self.start_entry = Gtk.Entry()
        self.start_entry.set_placeholder_text("ÅÅÅÅ-MM-DD HH:MM:SS")
        self.start_entry.connect("changed", self._on_start_changed)
        start_box.pack_start(self.start_entry, True, True, 0)
        content.pack_start(start_box, False, False, 0)

        # End time
        end_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        end_label = Gtk.Label(label="Sluttid:")
        end_label.set_width_chars(12)
        end_label.set_xalign(0)
        end_box.pack_start(end_label, False, False, 0)

        self.end_entry = Gtk.Entry()
        self.end_entry.set_placeholder_text("ÅÅÅÅ-MM-DD HH:MM:SS")
        self.end_entry.connect("changed", self._on_end_changed)
        end_box.pack_start(self.end_entry, True, True, 0)
        content.pack_start(end_box, False, False, 0)

        # Duration
        duration_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        duration_label = Gtk.Label(label="Duration:")
        duration_label.set_width_chars(12)
        duration_label.set_xalign(0)
        duration_box.pack_start(duration_label, False, False, 0)

        # Duration input: hours, minutes, seconds
        time_input_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)

        self.hours_spin = Gtk.SpinButton()
        self.hours_spin.set_range(0, 999)
        self.hours_spin.set_increments(1, 5)
        self.hours_spin.set_value(0)
        self.hours_spin.connect("value-changed", self._on_duration_changed)
        time_input_box.pack_start(self.hours_spin, True, True, 0)
        time_input_box.pack_start(Gtk.Label(label="h"), False, False, 0)

        self.minutes_spin = Gtk.SpinButton()
        self.minutes_spin.set_range(0, 59)
        self.minutes_spin.set_increments(1, 15)
        self.minutes_spin.set_value(0)
        self.minutes_spin.connect("value-changed", self._on_duration_changed)
        time_input_box.pack_start(self.minutes_spin, True, True, 0)
        time_input_box.pack_start(Gtk.Label(label="m"), False, False, 0)

        self.seconds_spin = Gtk.SpinButton()
        self.seconds_spin.set_range(0, 59)
        self.seconds_spin.set_increments(1, 10)
        self.seconds_spin.set_value(0)
        self.seconds_spin.connect("value-changed", self._on_duration_changed)
        time_input_box.pack_start(self.seconds_spin, True, True, 0)
        time_input_box.pack_start(Gtk.Label(label="s"), False, False, 0)

        duration_box.pack_start(time_input_box, True, True, 0)
        content.pack_start(duration_box, False, False, 0)

        # Separator
        content.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 5)

        # Note
        note_label = Gtk.Label(label="Anteckning:")
        note_label.set_xalign(0)
        content.pack_start(note_label, False, False, 0)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_min_content_height(100)

        self.note_textview = Gtk.TextView()
        self.note_textview.set_wrap_mode(Gtk.WrapMode.WORD)
        scrolled.add(self.note_textview)
        content.pack_start(scrolled, True, True, 0)

        content.show_all()

    def _populate_fields(self):
        """Populate fields with existing entry data."""
        if not self.entry_data:
            # Default to current time
            now = datetime.now()
            self.start_entry.set_text(now.strftime("%Y-%m-%d %H:%M:%S"))
            return

        # Task
        if 'task_id' in self.entry_data:
            self.task_combo.set_active_id(str(self.entry_data['task_id']))

        # Start time
        if 'start_time' in self.entry_data:
            start_dt = datetime.fromisoformat(self.entry_data['start_time'])
            self.start_entry.set_text(start_dt.strftime("%Y-%m-%d %H:%M:%S"))

        # End time
        if 'end_time' in self.entry_data and self.entry_data['end_time']:
            end_dt = datetime.fromisoformat(self.entry_data['end_time'])
            self.end_entry.set_text(end_dt.strftime("%Y-%m-%d %H:%M:%S"))

        # Duration
        if 'duration_seconds' in self.entry_data and self.entry_data['duration_seconds']:
            self._set_duration_from_seconds(self.entry_data['duration_seconds'])

        # Note
        if 'note' in self.entry_data and self.entry_data['note']:
            buffer = self.note_textview.get_buffer()
            buffer.set_text(self.entry_data['note'])

    def _set_duration_from_seconds(self, total_seconds: int):
        """Set duration spinners from total seconds."""
        self._updating = True
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60

        self.hours_spin.set_value(hours)
        self.minutes_spin.set_value(minutes)
        self.seconds_spin.set_value(seconds)
        self._updating = False

    def _get_duration_seconds(self) -> int:
        """Get total duration in seconds from spinners."""
        hours = int(self.hours_spin.get_value())
        minutes = int(self.minutes_spin.get_value())
        seconds = int(self.seconds_spin.get_value())
        return hours * 3600 + minutes * 60 + seconds

    def _on_start_changed(self, widget):
        """Handle start time change - update duration."""
        if self._updating:
            return

        try:
            start_text = self.start_entry.get_text()
            end_text = self.end_entry.get_text()

            if not start_text or not end_text:
                return

            start_dt = datetime.strptime(start_text, "%Y-%m-%d %H:%M:%S")
            end_dt = datetime.strptime(end_text, "%Y-%m-%d %H:%M:%S")

            if end_dt > start_dt:
                duration = int((end_dt - start_dt).total_seconds())
                self._set_duration_from_seconds(duration)

        except ValueError:
            # Invalid datetime format, ignore
            pass

    def _on_end_changed(self, widget):
        """Handle end time change - update duration."""
        if self._updating:
            return

        try:
            start_text = self.start_entry.get_text()
            end_text = self.end_entry.get_text()

            if not start_text or not end_text:
                return

            start_dt = datetime.strptime(start_text, "%Y-%m-%d %H:%M:%S")
            end_dt = datetime.strptime(end_text, "%Y-%m-%d %H:%M:%S")

            if end_dt > start_dt:
                duration = int((end_dt - start_dt).total_seconds())
                self._set_duration_from_seconds(duration)

        except ValueError:
            # Invalid datetime format, ignore
            pass

    def _on_duration_changed(self, widget):
        """Handle duration change - update end time."""
        if self._updating:
            return

        try:
            start_text = self.start_entry.get_text()
            if not start_text:
                return

            start_dt = datetime.strptime(start_text, "%Y-%m-%d %H:%M:%S")
            duration_seconds = self._get_duration_seconds()

            end_dt = start_dt + timedelta(seconds=duration_seconds)

            self._updating = True
            self.end_entry.set_text(end_dt.strftime("%Y-%m-%d %H:%M:%S"))
            self._updating = False

        except ValueError:
            # Invalid datetime format, ignore
            pass

    def get_entry_data(self) -> Optional[Dict]:
        """Get the edited entry data.

        Returns:
            Dict with entry data or None if validation fails
        """
        try:
            # Validate and parse data
            task_id = self.task_combo.get_active_id()
            if not task_id:
                self._show_error("Välj en uppgift")
                return None

            start_text = self.start_entry.get_text()
            start_time = datetime.strptime(start_text, "%Y-%m-%d %H:%M:%S")

            end_text = self.end_entry.get_text()
            end_time = datetime.strptime(end_text, "%Y-%m-%d %H:%M:%S") if end_text else None

            if end_time and end_time <= start_time:
                self._show_error("Sluttid måste vara efter starttid")
                return None

            duration_seconds = self._get_duration_seconds()

            buffer = self.note_textview.get_buffer()
            note = buffer.get_text(
                buffer.get_start_iter(),
                buffer.get_end_iter(),
                False
            ).strip()

            return {
                'id': self.entry_data.get('id'),
                'task_id': int(task_id),
                'start_time': start_time,
                'end_time': end_time,
                'duration_seconds': duration_seconds,
                'note': note if note else None
            }

        except ValueError as e:
            self._show_error(f"Ogiltigt datumformat. Använd ÅÅÅÅ-MM-DD HH:MM:SS")
            return None

    def _show_error(self, message: str):
        """Show error dialog."""
        dialog = Gtk.MessageDialog(
            parent=self,
            modal=True,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text=message
        )
        dialog.run()
        dialog.destroy()
