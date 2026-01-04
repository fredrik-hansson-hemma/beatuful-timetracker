"""Dialog for handling crash recovery when orphaned entries are detected."""
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
from datetime import datetime, timedelta
from typing import Optional, Tuple
from database import TimeTrackerDB
from edit_entry_dialog import EditEntryDialog


class CrashRecoveryDialog(Gtk.Dialog):
    """Dialog shown when an orphaned time entry is detected at startup."""

    def __init__(self, db: TimeTrackerDB, entry_data: dict):
        """Initialize the crash recovery dialog.

        Args:
            db: Database instance
            entry_data: Dict with the orphaned entry data
        """
        super().__init__(
            title="Crash Recovery - Oväntat avslut",
            modal=True,
            destroy_with_parent=True
        )

        self.db = db
        self.entry_data = entry_data
        self.result_action = None  # 'continue', 'stop', 'delete', 'edit'
        self.edited_entry_data = None

        self.set_default_size(550, 350)
        self.set_position(Gtk.WindowPosition.CENTER)

        # Make dialog stay on top and grab focus
        self.set_keep_above(True)
        self.set_urgency_hint(True)

        self._build_ui()

    def _build_ui(self):
        """Build the dialog UI."""
        content = self.get_content_area()
        content.set_spacing(15)
        content.set_margin_top(20)
        content.set_margin_bottom(20)
        content.set_margin_start(20)
        content.set_margin_end(20)

        # Warning icon + header
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=15)

        icon = Gtk.Image.new_from_icon_name("dialog-warning", Gtk.IconSize.DIALOG)
        header_box.pack_start(icon, False, False, 0)

        header_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        header = Gtk.Label()
        header.set_markup("<span size='large' weight='bold'>Programmet avslutades oväntat</span>")
        header.set_xalign(0)
        header_vbox.pack_start(header, False, False, 0)

        subheader = Gtk.Label()
        subheader.set_markup("<span size='small'>En pågående tidsinmatning hittades från förra sessionen</span>")
        subheader.set_xalign(0)
        subheader.get_style_context().add_class("dim-label")
        header_vbox.pack_start(subheader, False, False, 0)

        header_box.pack_start(header_vbox, True, True, 0)
        content.pack_start(header_box, False, False, 0)

        # Separator
        content.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 0)

        # Entry details
        details_frame = Gtk.Frame()
        details_frame.set_shadow_type(Gtk.ShadowType.IN)
        details_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        details_box.set_margin_top(10)
        details_box.set_margin_bottom(10)
        details_box.set_margin_start(10)
        details_box.set_margin_end(10)

        # Task name
        task_label = Gtk.Label()
        task_label.set_markup(f"<b>Uppgift:</b> {self.entry_data['task_name']}")
        task_label.set_xalign(0)
        details_box.pack_start(task_label, False, False, 0)

        # Start time
        start_time = datetime.fromisoformat(self.entry_data['start_time'])
        start_label = Gtk.Label()
        start_label.set_markup(f"<b>Starttid:</b> {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        start_label.set_xalign(0)
        details_box.pack_start(start_label, False, False, 0)

        # Time elapsed
        elapsed = datetime.now() - start_time
        hours = int(elapsed.total_seconds() // 3600)
        minutes = int((elapsed.total_seconds() % 3600) // 60)
        elapsed_label = Gtk.Label()
        elapsed_label.set_markup(f"<b>Tid sedan start:</b> {hours}h {minutes}m")
        elapsed_label.set_xalign(0)
        details_box.pack_start(elapsed_label, False, False, 0)

        # Estimated crash time (if heartbeat available)
        if self.entry_data.get('last_heartbeat'):
            last_heartbeat = datetime.fromisoformat(self.entry_data['last_heartbeat'])

            # Estimate crash time as last_heartbeat + 1 minute
            # (since heartbeat updates every 60 seconds)
            estimated_crash = last_heartbeat + timedelta(minutes=1)

            crash_label = Gtk.Label()
            crash_label.set_markup(f"<b>Estimerad krashtid:</b> {estimated_crash.strftime('%Y-%m-%d %H:%M:%S')}")
            crash_label.set_xalign(0)
            details_box.pack_start(crash_label, False, False, 0)

        details_frame.add(details_box)
        content.pack_start(details_frame, False, False, 10)

        # Question
        question = Gtk.Label(label="Vad vill du göra med denna tidsinmatning?")
        question.set_xalign(0)
        question.set_margin_top(10)
        content.pack_start(question, False, False, 0)

        # Radio buttons for actions
        self.radio_continue = Gtk.RadioButton.new_with_label_from_widget(
            None,
            "Fortsätt logga (behåll entry och fortsätt ticka)"
        )
        content.pack_start(self.radio_continue, False, False, 5)

        self.radio_stop = Gtk.RadioButton.new_with_label_from_widget(
            self.radio_continue,
            "Stoppa nu (loggar all tid sedan start inklusive crash-period)"
        )
        content.pack_start(self.radio_stop, False, False, 5)

        self.radio_edit = Gtk.RadioButton.new_with_label_from_widget(
            self.radio_continue,
            "Editera tidsinmatningen (ändra tider manuellt)"
        )
        content.pack_start(self.radio_edit, False, False, 5)

        self.radio_delete = Gtk.RadioButton.new_with_label_from_widget(
            self.radio_continue,
            "Radera tidsinmatningen"
        )
        content.pack_start(self.radio_delete, False, False, 5)

        # Buttons
        self.add_button("Avbryt", Gtk.ResponseType.CANCEL)
        ok_button = self.add_button("OK", Gtk.ResponseType.OK)
        ok_button.get_style_context().add_class("suggested-action")

        self.show_all()

    def run_and_get_result(self) -> Tuple[str, Optional[dict]]:
        """Run dialog and return the user's choice.

        Returns:
            Tuple of (action, entry_data) where:
            - action: 'continue', 'stop', 'delete', or 'edit'
            - entry_data: Updated entry data if action is 'edit', otherwise None
        """
        while True:
            response = self.run()

            if response != Gtk.ResponseType.OK:
                # User cancelled
                return ('cancel', None)

            if self.radio_continue.get_active():
                return ('continue', None)

            elif self.radio_stop.get_active():
                return ('stop', None)

            elif self.radio_delete.get_active():
                # Confirm deletion
                confirm = self._confirm_delete()
                if confirm:
                    return ('delete', None)
                # If not confirmed, continue loop to let user choose again

            elif self.radio_edit.get_active():
                # Open edit dialog
                edited_data = self._show_edit_dialog()
                if edited_data:
                    return ('edit', edited_data)
                # If edit was cancelled, continue loop

    def _confirm_delete(self) -> bool:
        """Confirm deletion with user.

        Returns:
            True if user confirms deletion
        """
        dialog = Gtk.MessageDialog(
            parent=self,
            modal=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.YES_NO,
            text="Är du säker?"
        )
        dialog.format_secondary_text(
            "Detta kommer permanent radera tidsinmatningen. "
            "All tid som loggades kommer att förloras."
        )

        response = dialog.run()
        dialog.destroy()

        return response == Gtk.ResponseType.YES

    def _show_edit_dialog(self) -> Optional[dict]:
        """Show edit entry dialog.

        Returns:
            Updated entry data or None if cancelled
        """
        # Prepare entry data for edit dialog
        edit_data = {
            'id': self.entry_data['id'],
            'task_id': self.entry_data['task_id'],
            'start_time': self.entry_data['start_time'],
            'end_time': None,  # Not set yet
            'duration_seconds': None,  # Will be calculated
            'note': self.entry_data.get('note')
        }

        edit_dialog = EditEntryDialog(self, self.db, edit_data)
        response = edit_dialog.run()

        if response == Gtk.ResponseType.OK:
            result = edit_dialog.get_entry_data()
            edit_dialog.destroy()
            return result
        else:
            edit_dialog.destroy()
            return None
