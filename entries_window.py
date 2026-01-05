"""Window for managing time entries - view, add, edit, and delete."""
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk
from datetime import datetime, timedelta
from typing import Optional
from database import TimeTrackerDB
from edit_entry_dialog import EditEntryDialog


class EntriesWindow(Gtk.Window):
    """Window for managing time entries."""

    def __init__(self, db: TimeTrackerDB, parent=None):
        """Initialize the entries window.

        Args:
            db: Database instance
            parent: Parent window (optional)
        """
        super().__init__(title="Hantera tidsinmatningar")
        self.db = db
        self.parent_window = parent

        # Set window properties
        self.set_default_size(900, 600)
        self.set_border_width(10)
        if parent:
            self.set_transient_for(parent)
            self.set_modal(False)

        # Current filter settings
        self.current_start_date = None
        self.current_end_date = None
        self.current_task_id = None

        # Build UI
        self._build_ui()

        # Apply default filter (today)
        self._apply_filter_today()

    def _build_ui(self):
        """Build the user interface."""
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.add(main_box)

        # Filter section
        filter_frame = Gtk.Frame(label="Filter")
        filter_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        filter_box.set_margin_top(10)
        filter_box.set_margin_bottom(10)
        filter_box.set_margin_start(10)
        filter_box.set_margin_end(10)
        filter_frame.add(filter_box)
        main_box.pack_start(filter_frame, False, False, 0)

        # Quick filter buttons
        quick_filter_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        filter_box.pack_start(quick_filter_box, False, False, 0)

        quick_filter_label = Gtk.Label(label="Snabbfilter:")
        quick_filter_box.pack_start(quick_filter_label, False, False, 0)

        self.btn_today = Gtk.Button(label="Idag")
        self.btn_today.connect("clicked", self._on_filter_today)
        quick_filter_box.pack_start(self.btn_today, False, False, 0)

        self.btn_this_week = Gtk.Button(label="Denna vecka")
        self.btn_this_week.connect("clicked", self._on_filter_this_week)
        quick_filter_box.pack_start(self.btn_this_week, False, False, 0)

        self.btn_last_7_days = Gtk.Button(label="Senaste 7 dagarna")
        self.btn_last_7_days.connect("clicked", self._on_filter_last_7_days)
        quick_filter_box.pack_start(self.btn_last_7_days, False, False, 0)

        self.btn_this_month = Gtk.Button(label="Denna månad")
        self.btn_this_month.connect("clicked", self._on_filter_this_month)
        quick_filter_box.pack_start(self.btn_this_month, False, False, 0)

        # Task filter
        task_filter_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        filter_box.pack_start(task_filter_box, False, False, 0)

        task_filter_label = Gtk.Label(label="Uppgift:")
        task_filter_box.pack_start(task_filter_label, False, False, 0)

        # ComboBox for task selection
        self.task_combo = Gtk.ComboBoxText()
        self.task_combo.append("all", "Alla uppgifter")
        self.task_combo.set_active_id("all")
        self.task_combo.connect("changed", self._on_task_filter_changed)
        task_filter_box.pack_start(self.task_combo, True, True, 0)

        # Load tasks into combo box
        self._load_tasks()

        # Entries list
        list_frame = Gtk.Frame(label="Tidsinmatningar")
        main_box.pack_start(list_frame, True, True, 0)

        # ScrolledWindow for the TreeView
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        list_frame.add(scrolled)

        # TreeView for entries
        self.entries_store = Gtk.ListStore(int, str, str, str, str, str, str)  # id, task, start, end, duration, note, task_id
        self.entries_tree = Gtk.TreeView(model=self.entries_store)
        self.entries_tree.set_headers_visible(True)
        scrolled.add(self.entries_tree)

        # Columns
        columns = [
            ("Uppgift", 1),
            ("Starttid", 2),
            ("Sluttid", 3),
            ("Varaktighet", 4),
            ("Anteckning", 5)
        ]

        for i, (title, col_id) in enumerate(columns):
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(title, renderer, text=col_id)
            column.set_resizable(True)
            column.set_sort_column_id(col_id)
            self.entries_tree.append_column(column)

        # Action buttons
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        button_box.set_margin_top(10)
        main_box.pack_start(button_box, False, False, 0)

        self.btn_add = Gtk.Button(label="Lägg till")
        self.btn_add.connect("clicked", self._on_add_entry)
        button_box.pack_start(self.btn_add, False, False, 0)

        self.btn_edit = Gtk.Button(label="Editera")
        self.btn_edit.connect("clicked", self._on_edit_entry)
        self.btn_edit.set_sensitive(False)
        button_box.pack_start(self.btn_edit, False, False, 0)

        self.btn_delete = Gtk.Button(label="Ta bort")
        self.btn_delete.connect("clicked", self._on_delete_entry)
        self.btn_delete.set_sensitive(False)
        button_box.pack_start(self.btn_delete, False, False, 0)

        # Close button
        btn_close = Gtk.Button(label="Stäng")
        btn_close.connect("clicked", lambda w: self.close())
        button_box.pack_end(btn_close, False, False, 0)

        # Selection handling
        selection = self.entries_tree.get_selection()
        selection.connect("changed", self._on_selection_changed)

    def _load_tasks(self):
        """Load tasks into the combo box."""
        tasks = self.db.get_all_tasks()
        for task in tasks:
            self.task_combo.append(str(task['id']), task['name'])

    def _on_selection_changed(self, selection):
        """Handle selection changes in the tree view."""
        model, tree_iter = selection.get_selected()
        has_selection = tree_iter is not None
        self.btn_edit.set_sensitive(has_selection)
        self.btn_delete.set_sensitive(has_selection)

    def _apply_filter_today(self):
        """Apply 'today' filter."""
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        self.current_start_date = today
        self.current_end_date = today
        self._refresh_entries()

    def _on_filter_today(self, button):
        """Handle 'today' filter button."""
        self._apply_filter_today()

    def _on_filter_this_week(self, button):
        """Handle 'this week' filter button."""
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        # Monday is 0, Sunday is 6
        start_of_week = today - timedelta(days=today.weekday())
        self.current_start_date = start_of_week
        self.current_end_date = today
        self._refresh_entries()

    def _on_filter_last_7_days(self, button):
        """Handle 'last 7 days' filter button."""
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        seven_days_ago = today - timedelta(days=6)
        self.current_start_date = seven_days_ago
        self.current_end_date = today
        self._refresh_entries()

    def _on_filter_this_month(self, button):
        """Handle 'this month' filter button."""
        today = datetime.now()
        start_of_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_of_month = today.replace(hour=0, minute=0, second=0, microsecond=0)
        self.current_start_date = start_of_month
        self.current_end_date = end_of_month
        self._refresh_entries()

    def _on_task_filter_changed(self, combo):
        """Handle task filter change."""
        task_id_str = combo.get_active_id()
        if task_id_str == "all":
            self.current_task_id = None
        else:
            self.current_task_id = int(task_id_str)
        self._refresh_entries()

    def _refresh_entries(self):
        """Refresh the entries list with current filters."""
        self.entries_store.clear()

        entries = self.db.get_entries(
            start_date=self.current_start_date,
            end_date=self.current_end_date,
            task_id=self.current_task_id
        )

        for entry in entries:
            # Format times
            start_time = datetime.fromisoformat(entry['start_time']).strftime('%Y-%m-%d %H:%M:%S')

            if entry['end_time']:
                end_time = datetime.fromisoformat(entry['end_time']).strftime('%Y-%m-%d %H:%M:%S')
            else:
                end_time = "Pågående"

            # Format duration
            if entry['duration_seconds']:
                hours = entry['duration_seconds'] // 3600
                minutes = (entry['duration_seconds'] % 3600) // 60
                duration = f"{hours}h {minutes}m"
            else:
                duration = "—"

            note = entry['note'] if entry['note'] else ""

            self.entries_store.append([
                entry['id'],
                entry['task_name'],
                start_time,
                end_time,
                duration,
                note,
                str(entry['task_id'])
            ])

    def _on_add_entry(self, button):
        """Handle add entry button."""
        dialog = EditEntryDialog(self.db, parent=self)
        response = dialog.run()

        if response == Gtk.ResponseType.OK:
            result = dialog.get_result()
            if result:
                # Add new entry to database
                start_dt = datetime.strptime(result['start_time'], "%Y-%m-%d %H:%M:%S")
                end_dt = datetime.strptime(result['end_time'], "%Y-%m-%d %H:%M:%S")
                duration = int((end_dt - start_dt).total_seconds())

                cursor = self.db.conn.cursor()
                cursor.execute("""
                    INSERT INTO time_entries (task_id, start_time, end_time, duration_seconds, note)
                    VALUES (?, ?, ?, ?, ?)
                """, (result['task_id'], start_dt, end_dt, duration, result['note']))
                self.db.conn.commit()

                self._refresh_entries()

        dialog.destroy()

    def _on_edit_entry(self, button):
        """Handle edit entry button."""
        selection = self.entries_tree.get_selection()
        model, tree_iter = selection.get_selected()

        if tree_iter:
            entry_id = model[tree_iter][0]

            # Get full entry data
            cursor = self.db.conn.cursor()
            cursor.execute("""
                SELECT te.*, t.name as task_name
                FROM time_entries te
                JOIN tasks t ON te.task_id = t.id
                WHERE te.id = ?
            """, (entry_id,))
            entry = cursor.fetchone()

            if entry:
                dialog = EditEntryDialog(parent=self, db=self.db, entry_data=dict(entry))
                response = dialog.run()

                if response == Gtk.ResponseType.OK:
                    result = dialog.get_entry_data()
                    if result:
                        # Update entry - result already contains datetime objects
                        success = self.db.update_time_entry(
                            entry_id,
                            result['task_id'],
                            result['start_time'],
                            result['end_time'],
                            result['duration_seconds'],
                            result['note']
                        )

                        if success:
                            self._refresh_entries()

                dialog.destroy()

    def _on_delete_entry(self, button):
        """Handle delete entry button."""
        selection = self.entries_tree.get_selection()
        model, tree_iter = selection.get_selected()

        if tree_iter:
            entry_id = model[tree_iter][0]
            task_name = model[tree_iter][1]
            start_time = model[tree_iter][2]

            # Confirmation dialog
            dialog = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.QUESTION,
                buttons=Gtk.ButtonsType.YES_NO,
                text="Bekräfta borttagning"
            )
            dialog.format_secondary_text(
                f"Är du säker på att du vill ta bort tidsinmatningen?\n\n"
                f"Uppgift: {task_name}\n"
                f"Starttid: {start_time}"
            )

            response = dialog.run()
            dialog.destroy()

            if response == Gtk.ResponseType.YES:
                success = self.db.delete_time_entry(entry_id)
                if success:
                    self._refresh_entries()
