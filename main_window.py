"""Main window for the time tracker application."""
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, Gio
from datetime import datetime, timedelta
from typing import Optional
from database import TimeTrackerDB
from tasks_window import TasksWindow
from categories_window import CategoriesWindow
from edit_entry_dialog import EditEntryDialog


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

        self.set_default_size(800, 600)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_resizable(True)

        # Connect close event to minimize to tray instead
        self.connect("delete-event", self._on_delete_event)

        self._build_ui()
        self._load_tasks()
        self._check_active_entry()

        # Load entries with "today" filter by default
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        self.current_start_date = today
        self.current_end_date = today
        self._refresh_entries()
        self._update_summary()

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

        # Task search box
        task_search_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        current_box.pack_start(task_search_box, False, False, 0)

        task_search_label = Gtk.Label(label="Loggar tid på:")
        task_search_box.pack_start(task_search_label, False, False, 0)

        # Entry with completion for task search
        self.task_search_entry = Gtk.Entry()
        self.task_search_entry.set_placeholder_text("Ingen aktiv uppgift")
        self.task_search_entry.set_hexpand(True)
        task_search_box.pack_start(self.task_search_entry, True, True, 0)

        # Setup completion
        self.task_completion = Gtk.EntryCompletion()
        self.task_completion_store = Gtk.ListStore(int, str)  # task_id, task_name
        self.task_completion.set_model(self.task_completion_store)
        self.task_completion.set_text_column(1)
        self.task_completion.set_minimum_key_length(1)
        self.task_completion.set_inline_completion(True)
        self.task_search_entry.set_completion(self.task_completion)

        # Connect signals
        self.task_search_entry.connect("activate", self._on_task_search_activate)
        self.task_search_entry.connect("focus-in-event", self._on_task_search_focus_in)
        self.task_search_entry.connect("focus-out-event", self._on_task_search_focus_out)
        self.task_completion.connect("match-selected", self._on_task_completion_match)

        # Flag to track if user is actively typing
        self.user_is_typing = False

        self.timer_label = Gtk.Label(label="00:00:00")
        self.timer_label.set_markup("<span size='xx-large' font_family='monospace'>00:00:00</span>")
        current_box.pack_start(self.timer_label, False, False, 5)

        # Stop button
        self.stop_button = Gtk.Button(label="Stoppa tidsinmatning")
        self.stop_button.set_sensitive(False)
        self.stop_button.connect("clicked", self._on_stop_clicked)
        current_box.pack_start(self.stop_button, False, False, 5)

        # Summary label - shows total time for today
        self.summary_label = Gtk.Label()
        self.summary_label.set_markup("<b>Totalt idag: 0:00:00</b>")
        self.summary_label.set_margin_top(10)
        vbox.pack_start(self.summary_label, False, False, 0)

        # Expandable entries section
        expander = Gtk.Expander(label="Tidsinmatningar")
        expander.set_expanded(False)
        vbox.pack_start(expander, True, True, 0)

        # Container for the expandable content
        expander_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        expander_box.set_margin_top(10)
        expander_box.set_margin_bottom(10)
        expander_box.set_margin_start(10)
        expander_box.set_margin_end(10)
        expander.add(expander_box)

        # Filter buttons
        filter_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        expander_box.pack_start(filter_box, False, False, 0)

        filter_label = Gtk.Label(label="Filter:")
        filter_box.pack_start(filter_label, False, False, 0)

        self.btn_today = Gtk.Button(label="Idag")
        self.btn_today.connect("clicked", self._on_filter_today)
        filter_box.pack_start(self.btn_today, False, False, 0)

        self.btn_this_week = Gtk.Button(label="Denna vecka")
        self.btn_this_week.connect("clicked", self._on_filter_this_week)
        filter_box.pack_start(self.btn_this_week, False, False, 0)

        self.btn_this_month = Gtk.Button(label="Denna månad")
        self.btn_this_month.connect("clicked", self._on_filter_this_month)
        filter_box.pack_start(self.btn_this_month, False, False, 0)

        self.btn_all = Gtk.Button(label="Allt")
        self.btn_all.connect("clicked", self._on_filter_all)
        filter_box.pack_start(self.btn_all, False, False, 0)

        # Scrolled window for entries list
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_min_content_height(300)
        expander_box.pack_start(scrolled, True, True, 0)

        # Entries TreeView
        self.entries_store = Gtk.ListStore(int, str, str, str, str, str, str)  # id, task, start, end, duration, note, task_id
        self.entries_tree = Gtk.TreeView(model=self.entries_store)
        self.entries_tree.set_headers_visible(True)
        scrolled.add(self.entries_tree)

        # Columns for entries
        columns = [
            ("Uppgift", 1),
            ("Starttid", 2),
            ("Sluttid", 3),
            ("Varaktighet", 4),
            ("Anteckning", 5)
        ]

        for title, col_id in columns:
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(title, renderer, text=col_id)
            column.set_resizable(True)
            column.set_sort_column_id(col_id)
            self.entries_tree.append_column(column)

        # Right-click context menu for entries
        self.entries_tree.connect("button-press-event", self._on_entries_button_press)

        # Bottom button box
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        button_box.set_margin_top(10)
        vbox.pack_start(button_box, False, False, 0)

        manage_tasks_button = Gtk.Button(label="Hantera uppgifter")
        manage_tasks_button.connect("clicked", self._on_manage_tasks_clicked)
        button_box.pack_start(manage_tasks_button, True, True, 0)

        manage_categories_button = Gtk.Button(label="Hantera kategorier")
        manage_categories_button.connect("clicked", self._on_manage_categories_clicked)
        button_box.pack_start(manage_categories_button, True, True, 0)

        # Filter state
        self.current_start_date = None
        self.current_end_date = None
        self.current_task_id = None

    def _load_tasks(self):
        """Load tasks from database into completion store."""
        self.task_completion_store.clear()
        tasks = self.db.get_tasks()

        for task in tasks:
            # Add active tasks to completion
            if task['active']:
                self.task_completion_store.append([task['id'], task['name']])

    def _check_active_entry(self):
        """Check if there's an active time entry and update UI."""
        active_entry = self.db.get_active_entry()

        if active_entry:
            self.current_task_id = active_entry['task_id']
            self.current_entry_id = active_entry['id']
            # Update search entry only if user is not typing
            if not self.user_is_typing:
                self.task_search_entry.set_text(active_entry['task_name'])
            self.stop_button.set_sensitive(True)
        else:
            self.current_task_id = None
            self.current_entry_id = None
            # Update search entry only if user is not typing
            if not self.user_is_typing:
                self.task_search_entry.set_text("")
            self.stop_button.set_sensitive(False)

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


    def _on_manage_tasks_clicked(self, button):
        """Handle manage tasks button click."""
        tasks_window = TasksWindow(self.db, parent=self)
        tasks_window.show_all()

    def _on_manage_categories_clicked(self, button):
        """Handle manage categories button click."""
        categories_window = CategoriesWindow(self.db, parent=self)
        categories_window.show_all()


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
            self.task_search_entry.set_text(task['name'])

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

            self.task_search_entry.set_text("")
            self.stop_button.set_sensitive(False)

            self._load_tasks()  # Refresh to show updated times
            self._refresh_entries()  # Refresh entries list
            self._update_summary()  # Update summary

            # Update tray
            if self.tray:
                self.tray.update_state()

    def _on_task_search_focus_in(self, widget, event):
        """Handle focus in on search entry."""
        self.user_is_typing = True
        return False

    def _on_task_search_focus_out(self, widget, event):
        """Handle focus out on search entry."""
        self.user_is_typing = False
        # Restore current task name
        self._check_active_entry()
        return False

    def _on_task_completion_match(self, completion, model, iter):
        """Handle selection from completion dropdown."""
        task_id = model[iter][0]
        task_name = model[iter][1]
        self._switch_to_task(task_id, task_name)
        return True

    def _on_task_search_activate(self, entry):
        """Handle Enter key in search entry."""
        text = entry.get_text().strip()
        if not text:
            return

        # Check if task exists
        tasks = self.db.get_tasks()
        matching_task = None
        for task in tasks:
            if task['name'].lower() == text.lower() and task['active']:
                matching_task = task
                break

        if matching_task:
            # Task exists, switch to it
            self._switch_to_task(matching_task['id'], matching_task['name'])
        else:
            # Task doesn't exist, ask to create
            self._ask_create_new_task(text)

    def _switch_to_task(self, task_id, task_name):
        """Switch time tracking to a different task."""
        # Stop current task if any
        if self.current_entry_id:
            self.db.stop_time_entry(self.current_entry_id)

        # Start new task
        entry_id = self.db.start_time_entry(task_id)
        self.current_task_id = task_id
        self.current_entry_id = entry_id

        # Update UI
        self.user_is_typing = False
        self._check_active_entry()
        self._load_tasks()

        # Update tray
        if self.tray:
            self.tray.update_state()

    def _ask_create_new_task(self, task_name):
        """Ask user if they want to create a new task."""
        dialog = Gtk.Dialog(
            title="Skapa ny uppgift",
            parent=self,
            modal=True,
            destroy_with_parent=True
        )
        dialog.add_button("Avbryt", Gtk.ResponseType.CANCEL)
        dialog.add_button("Skapa", Gtk.ResponseType.OK)

        content = dialog.get_content_area()
        content.set_spacing(10)
        content.set_margin_top(20)
        content.set_margin_bottom(20)
        content.set_margin_start(20)
        content.set_margin_end(20)

        # Question
        question_label = Gtk.Label()
        question_label.set_markup(f"Uppgiften <b>{task_name}</b> finns inte.\nVill du skapa den?")
        content.pack_start(question_label, False, False, 0)

        # Category selection
        category_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        category_box.set_margin_top(10)
        content.pack_start(category_box, False, False, 0)

        category_label = Gtk.Label(label="Kategori:")
        category_box.pack_start(category_label, False, False, 0)

        category_combo = Gtk.ComboBoxText()
        category_combo.append(None, "Ingen kategori")
        categories = self.db.get_all_categories()
        for cat in categories:
            if cat['active']:
                category_combo.append(str(cat['id']), cat['name'])
        category_combo.set_active(0)
        category_box.pack_start(category_combo, True, True, 0)

        dialog.show_all()
        response = dialog.run()

        if response == Gtk.ResponseType.OK:
            # Get selected category
            category_id_str = category_combo.get_active_id()
            category_id = int(category_id_str) if category_id_str else None

            # Create the task
            task_id = self.db.add_task(task_name, category_id=category_id)
            dialog.destroy()

            # Switch to the new task
            self._switch_to_task(task_id, task_name)
        else:
            dialog.destroy()
            # User cancelled, restore current task in entry
            self.user_is_typing = False
            self._check_active_entry()

    def _on_delete_event(self, widget, event):
        """Handle window close - hide instead of destroying."""
        self.hide()
        return True  # Prevent default destroy behavior

    def _on_filter_today(self, button):
        """Handle 'today' filter button."""
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        self.current_start_date = today
        self.current_end_date = today
        self._refresh_entries()
        self._update_summary()

    def _on_filter_this_week(self, button):
        """Handle 'this week' filter button."""
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        start_of_week = today - timedelta(days=today.weekday())
        self.current_start_date = start_of_week
        self.current_end_date = today
        self._refresh_entries()
        self._update_summary()

    def _on_filter_this_month(self, button):
        """Handle 'this month' filter button."""
        today = datetime.now()
        start_of_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_of_month = today.replace(hour=0, minute=0, second=0, microsecond=0)
        self.current_start_date = start_of_month
        self.current_end_date = end_of_month
        self._refresh_entries()
        self._update_summary()

    def _on_filter_all(self, button):
        """Handle 'all' filter button."""
        self.current_start_date = None
        self.current_end_date = None
        self._refresh_entries()
        self._update_summary()

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
                seconds = entry['duration_seconds'] % 60
                duration = f"{hours}:{minutes:02d}:{seconds:02d}"
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

    def _update_summary(self):
        """Update the summary label with total time for the current filter."""
        # Calculate total time for entries in current filter
        entries = self.db.get_entries(
            start_date=self.current_start_date,
            end_date=self.current_end_date,
            task_id=self.current_task_id
        )

        total_seconds = sum(entry['duration_seconds'] or 0 for entry in entries)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60

        # Determine label text based on filter
        if self.current_start_date and self.current_end_date:
            if self.current_start_date == self.current_end_date:
                # Single day
                if self.current_start_date == datetime.now().replace(hour=0, minute=0, second=0, microsecond=0):
                    label_text = "Totalt idag"
                else:
                    label_text = f"Totalt {self.current_start_date.strftime('%Y-%m-%d')}"
            else:
                # Date range
                label_text = f"Totalt {self.current_start_date.strftime('%Y-%m-%d')} - {self.current_end_date.strftime('%Y-%m-%d')}"
        else:
            label_text = "Totalt (alla)"

        self.summary_label.set_markup(f"<b>{label_text}: {hours}:{minutes:02d}:{seconds:02d}</b>")

    def _on_entries_button_press(self, widget, event):
        """Handle button press events on entries tree."""
        if event.button == 3:  # Right click
            # Get selection
            path_info = widget.get_path_at_pos(int(event.x), int(event.y))
            if path_info:
                path, column, cell_x, cell_y = path_info
                widget.get_selection().select_path(path)

                # Create context menu
                menu = Gtk.Menu()

                edit_item = Gtk.MenuItem(label="Editera")
                edit_item.connect("activate", self._on_edit_entry_menu)
                menu.append(edit_item)

                delete_item = Gtk.MenuItem(label="Ta bort")
                delete_item.connect("activate", self._on_delete_entry_menu)
                menu.append(delete_item)

                menu.show_all()
                menu.popup(None, None, None, None, event.button, event.time)

            return True
        return False

    def _on_edit_entry_menu(self, menu_item):
        """Handle edit entry from context menu."""
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
                        # Update entry
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
                            self._update_summary()
                            self._load_tasks()

                dialog.destroy()

    def _on_delete_entry_menu(self, menu_item):
        """Handle delete entry from context menu."""
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
                    self._update_summary()
                    self._load_tasks()

    def cleanup(self):
        """Cleanup before closing."""
        if self.timer_label_update_id:
            GLib.source_remove(self.timer_label_update_id)
