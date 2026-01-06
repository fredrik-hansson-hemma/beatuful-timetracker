"""Dialog shown when unlocking to assign time spent while away."""
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib
from datetime import datetime, timedelta
from typing import Optional
from database import TimeTrackerDB


class UnlockDialog(Gtk.Dialog):
    """Dialog for assigning time after unlocking the computer."""

    def __init__(self, db: TimeTrackerDB, task_name: str, locked_duration: timedelta):
        """Initialize the unlock dialog.

        Args:
            db: Database instance
            task_name: Name of the task that was active when locked
            locked_duration: How long the computer was locked
        """
        super().__init__(
            title="Tidsinmatning - Du är tillbaka!",
            modal=True,
            destroy_with_parent=True
        )

        self.db = db
        self.task_name = task_name
        self.locked_duration = locked_duration
        self.result_task_id = None
        self.result_action = None  # 'continue', 'other', or 'skip'

        self.set_default_size(500, 300)
        self.set_position(Gtk.WindowPosition.CENTER)

        # Make dialog stay on top and grab focus
        self.set_keep_above(True)
        self.set_urgency_hint(True)

        self._build_ui()

    def _build_ui(self):
        """Build the dialog UI."""
        content = self.get_content_area()
        content.set_spacing(10)
        content.set_margin_top(20)
        content.set_margin_bottom(20)
        content.set_margin_start(20)
        content.set_margin_end(20)

        # Header
        header = Gtk.Label()
        header.set_markup("<span size='large' weight='bold'>Välkommen tillbaka!</span>")
        content.pack_start(header, False, False, 0)

        # Duration info
        hours = int(self.locked_duration.total_seconds() // 3600)
        minutes = int((self.locked_duration.total_seconds() % 3600) // 60)
        seconds = int(self.locked_duration.total_seconds() % 60)
        duration_text = f"Du var borta i {hours}:{minutes:02d}:{seconds:02d}"

        duration_label = Gtk.Label(label=duration_text)
        content.pack_start(duration_label, False, False, 0)

        # Task info
        task_info = Gtk.Label()
        task_info.set_markup(f"Du loggade tid på uppgiften: <b>{self.task_name}</b>")
        task_info.set_margin_top(10)
        content.pack_start(task_info, False, False, 0)

        # Question
        question = Gtk.Label(label="Vad vill du göra med tiden du var borta?")
        question.set_margin_top(20)
        content.pack_start(question, False, False, 0)

        # Radio buttons for choices
        self.radio_continue = Gtk.RadioButton.new_with_label_from_widget(
            None,
            f"Fortsätt logga på '{self.task_name}'"
        )
        content.pack_start(self.radio_continue, False, False, 5)

        self.radio_other = Gtk.RadioButton.new_with_label_from_widget(
            self.radio_continue,
            "Logga på en annan uppgift:"
        )
        content.pack_start(self.radio_other, False, False, 5)

        # Task selector (only enabled when "other" is selected)
        tasks = self.db.get_tasks()
        self.task_combo = Gtk.ComboBoxText()
        self.task_combo.set_margin_start(30)
        self.task_combo.set_sensitive(False)

        for task in tasks:
            if task['name'] != self.task_name:  # Don't show current task
                self.task_combo.append(str(task['id']), task['name'])

        if self.task_combo.get_model() and len(self.task_combo.get_model()) > 0:
            self.task_combo.set_active(0)

        content.pack_start(self.task_combo, False, False, 0)

        self.radio_skip = Gtk.RadioButton.new_with_label_from_widget(
            self.radio_continue,
            "Logga inte tiden (t.ex. lunch, rast)"
        )
        content.pack_start(self.radio_skip, False, False, 5)

        # Set default selection to CONTINUE (always log time unless user explicitly skips)
        self.radio_continue.set_active(True)

        # Connect radio button signals
        self.radio_other.connect("toggled", self._on_radio_toggled)

        # Buttons
        self.add_button("Avbryt", Gtk.ResponseType.CANCEL)
        ok_button = self.add_button("OK", Gtk.ResponseType.OK)
        ok_button.get_style_context().add_class("suggested-action")

        self.show_all()

    def _on_radio_toggled(self, button):
        """Enable/disable task combo based on radio selection."""
        self.task_combo.set_sensitive(self.radio_other.get_active())

    def run_and_get_result(self) -> tuple[Optional[str], Optional[int]]:
        """Run dialog and return the user's choice.

        Returns:
            Tuple of (action, task_id) where:
            - action: 'continue', 'other', or 'skip'
            - task_id: ID of task to log to (if action is 'other'), otherwise None

        Note: By default, time is ALWAYS logged (continue is pre-selected).
        User must explicitly choose 'skip' to not log time.
        If user cancels, time is logged to the current task by default.
        """
        response = self.run()

        if response == Gtk.ResponseType.OK:
            if self.radio_continue.get_active():
                return ('continue', None)
            elif self.radio_other.get_active():
                task_id = self.task_combo.get_active_id()
                if task_id:
                    return ('other', int(task_id))
                else:
                    # No other task available or selected - default to continue
                    return ('continue', None)
            elif self.radio_skip.get_active():
                return ('skip', None)

        # User cancelled or closed dialog - DEFAULT: continue with current task
        # This ensures time is logged by default unless user explicitly cancels
        return ('continue', None)
