"""Window for managing categories - view, add, edit, deactivate, and delete."""
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib
from datetime import datetime
from typing import Optional
from database import TimeTrackerDB


class CategoriesWindow(Gtk.Window):
    """Window for managing categories."""

    def __init__(self, db: TimeTrackerDB, parent=None):
        """Initialize the categories window.

        Args:
            db: Database instance
            parent: Parent window (optional)
        """
        super().__init__(title="Hantera kategorier")
        self.db = db
        self.parent_window = parent

        # Set window properties
        self.set_default_size(800, 500)
        self.set_border_width(10)
        if parent:
            self.set_transient_for(parent)
            self.set_modal(False)

        # Build UI
        self._build_ui()

        # Load categories
        self._refresh_categories()

    def _build_ui(self):
        """Build the user interface."""
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.add(main_box)

        # Search section
        search_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        main_box.pack_start(search_box, False, False, 0)

        search_label = Gtk.Label(label="Sök:")
        search_box.pack_start(search_label, False, False, 0)

        self.search_entry = Gtk.Entry()
        self.search_entry.set_placeholder_text("Filtrera på kategorinamn...")
        self.search_entry.connect("changed", self._on_search_changed)
        search_box.pack_start(self.search_entry, True, True, 0)

        # Show inactive checkbox
        self.show_inactive_check = Gtk.CheckButton(label="Visa inaktiva kategorier")
        self.show_inactive_check.connect("toggled", self._on_show_inactive_toggled)
        search_box.pack_start(self.show_inactive_check, False, False, 0)

        # Categories list
        list_frame = Gtk.Frame(label="Kategorier")
        main_box.pack_start(list_frame, True, True, 0)

        # ScrolledWindow for the TreeView
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        list_frame.add(scrolled)

        # TreeView for categories
        # Columns: id, name, description, color, active
        self.categories_store = Gtk.ListStore(int, str, str, str, bool)
        self.categories_tree = Gtk.TreeView(model=self.categories_store)
        self.categories_tree.set_headers_visible(True)
        scrolled.add(self.categories_tree)

        # Color column with colored cell
        renderer_color = Gtk.CellRendererText()
        column_color = Gtk.TreeViewColumn("Färg", renderer_color)
        column_color.set_cell_data_func(renderer_color, self._color_cell_data_func)
        column_color.set_resizable(True)
        self.categories_tree.append_column(column_color)

        # Name column
        renderer_name = Gtk.CellRendererText()
        column_name = Gtk.TreeViewColumn("Kategori", renderer_name, text=1)
        column_name.set_resizable(True)
        column_name.set_expand(True)
        column_name.set_sort_column_id(1)
        self.categories_tree.append_column(column_name)

        # Description column
        renderer_desc = Gtk.CellRendererText()
        column_desc = Gtk.TreeViewColumn("Beskrivning", renderer_desc, text=2)
        column_desc.set_resizable(True)
        column_desc.set_expand(True)
        self.categories_tree.append_column(column_desc)

        # Active column
        renderer_active = Gtk.CellRendererText()
        column_active = Gtk.TreeViewColumn("Status", renderer_active)
        column_active.set_cell_data_func(renderer_active, self._active_cell_data_func)
        column_active.set_resizable(True)
        self.categories_tree.append_column(column_active)

        # Action buttons
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        button_box.set_margin_top(10)
        main_box.pack_start(button_box, False, False, 0)

        self.btn_add = Gtk.Button(label="Lägg till")
        self.btn_add.connect("clicked", self._on_add_category)
        button_box.pack_start(self.btn_add, False, False, 0)

        self.btn_edit = Gtk.Button(label="Editera")
        self.btn_edit.connect("clicked", self._on_edit_category)
        self.btn_edit.set_sensitive(False)
        button_box.pack_start(self.btn_edit, False, False, 0)

        self.btn_toggle_active = Gtk.Button(label="Inaktivera")
        self.btn_toggle_active.connect("clicked", self._on_toggle_active)
        self.btn_toggle_active.set_sensitive(False)
        button_box.pack_start(self.btn_toggle_active, False, False, 0)

        self.btn_delete = Gtk.Button(label="Ta bort")
        self.btn_delete.connect("clicked", self._on_delete_category)
        self.btn_delete.set_sensitive(False)
        button_box.pack_start(self.btn_delete, False, False, 0)

        # Close button
        btn_close = Gtk.Button(label="Stäng")
        btn_close.connect("clicked", lambda w: self.close())
        button_box.pack_end(btn_close, False, False, 0)

        # Selection handling
        selection = self.categories_tree.get_selection()
        selection.connect("changed", self._on_selection_changed)

    def _color_cell_data_func(self, column, cell, model, iter, data):
        """Custom cell renderer for color."""
        color = model[iter][3]
        cell.set_property("text", "  ██  ")
        cell.set_property("foreground", color)

    def _active_cell_data_func(self, column, cell, model, iter, data):
        """Custom cell renderer for active status."""
        is_active = model[iter][4]
        if is_active:
            cell.set_property("text", "Aktiv")
            cell.set_property("foreground", "#2e7d32")  # Green
        else:
            cell.set_property("text", "Inaktiv")
            cell.set_property("foreground", "#757575")  # Gray

    def _on_selection_changed(self, selection):
        """Handle selection changes in the tree view."""
        model, tree_iter = selection.get_selected()
        has_selection = tree_iter is not None
        self.btn_edit.set_sensitive(has_selection)
        self.btn_toggle_active.set_sensitive(has_selection)
        self.btn_delete.set_sensitive(has_selection)

        # Update toggle button label based on active status
        if has_selection:
            is_active = model[tree_iter][4]
            if is_active:
                self.btn_toggle_active.set_label("Inaktivera")
            else:
                self.btn_toggle_active.set_label("Aktivera")

    def _on_search_changed(self, entry):
        """Handle search entry changes."""
        # Use a small delay to avoid refreshing on every keystroke
        if hasattr(self, '_search_timeout'):
            GLib.source_remove(self._search_timeout)
        self._search_timeout = GLib.timeout_add(300, self._refresh_categories)

    def _on_show_inactive_toggled(self, checkbox):
        """Handle show inactive checkbox toggle."""
        self._refresh_categories()

    def _refresh_categories(self):
        """Refresh the categories list with current filters."""
        self.categories_store.clear()

        search_text = self.search_entry.get_text().strip()
        show_inactive = self.show_inactive_check.get_active()

        # Get categories from database
        if search_text:
            categories = self.db.get_all_categories(search=search_text, active_only=not show_inactive)
        else:
            categories = self.db.get_all_categories(active_only=not show_inactive)

        for category in categories:
            self.categories_store.append([
                category['id'],
                category['name'],
                category['description'] or "",
                category['color'] or "#757575",
                bool(category['active'])
            ])

        # Remove timeout if exists
        if hasattr(self, '_search_timeout'):
            delattr(self, '_search_timeout')

        return False  # Don't call again

    def _on_add_category(self, button):
        """Handle add category button."""
        dialog = Gtk.Dialog(
            title="Lägg till kategori",
            transient_for=self,
            flags=0
        )
        dialog.add_buttons(
            "Avbryt", Gtk.ResponseType.CANCEL,
            "Lägg till", Gtk.ResponseType.OK
        )

        content = dialog.get_content_area()
        content.set_spacing(10)
        content.set_margin_top(10)
        content.set_margin_bottom(10)
        content.set_margin_start(10)
        content.set_margin_end(10)

        # Name entry
        name_label = Gtk.Label(label="Namn:")
        name_label.set_xalign(0)
        content.pack_start(name_label, False, False, 0)

        name_entry = Gtk.Entry()
        name_entry.set_activates_default(True)
        content.pack_start(name_entry, False, False, 0)

        # Description entry
        desc_label = Gtk.Label(label="Beskrivning (valfritt):")
        desc_label.set_xalign(0)
        content.pack_start(desc_label, False, False, 0)

        desc_entry = Gtk.Entry()
        content.pack_start(desc_entry, False, False, 0)

        # Color button
        color_label = Gtk.Label(label="Färg:")
        color_label.set_xalign(0)
        content.pack_start(color_label, False, False, 0)

        color_button = Gtk.ColorButton()
        rgba = Gdk.RGBA()
        rgba.parse("#757575")
        color_button.set_rgba(rgba)
        content.pack_start(color_button, False, False, 0)

        dialog.set_default_response(Gtk.ResponseType.OK)
        dialog.show_all()

        response = dialog.run()
        name = name_entry.get_text().strip()
        description = desc_entry.get_text().strip()
        rgba = color_button.get_rgba()
        color = rgba.to_string()
        # Convert to hex format
        color = "#{:02x}{:02x}{:02x}".format(
            int(rgba.red * 255),
            int(rgba.green * 255),
            int(rgba.blue * 255)
        )
        dialog.destroy()

        if response == Gtk.ResponseType.OK and name:
            try:
                self.db.add_category(name, description, color)
                self._refresh_categories()
            except Exception as e:
                error_dialog = Gtk.MessageDialog(
                    transient_for=self,
                    flags=0,
                    message_type=Gtk.MessageType.ERROR,
                    buttons=Gtk.ButtonsType.OK,
                    text="Kunde inte skapa kategori"
                )
                error_dialog.format_secondary_text(str(e))
                error_dialog.run()
                error_dialog.destroy()

    def _on_edit_category(self, button):
        """Handle edit category button."""
        selection = self.categories_tree.get_selection()
        model, tree_iter = selection.get_selected()

        if tree_iter:
            category_id = model[tree_iter][0]
            current_name = model[tree_iter][1]
            current_desc = model[tree_iter][2]
            current_color = model[tree_iter][3]

            dialog = Gtk.Dialog(
                title="Editera kategori",
                transient_for=self,
                flags=0
            )
            dialog.add_buttons(
                "Avbryt", Gtk.ResponseType.CANCEL,
                "Spara", Gtk.ResponseType.OK
            )

            content = dialog.get_content_area()
            content.set_spacing(10)
            content.set_margin_top(10)
            content.set_margin_bottom(10)
            content.set_margin_start(10)
            content.set_margin_end(10)

            # Name entry
            name_label = Gtk.Label(label="Namn:")
            name_label.set_xalign(0)
            content.pack_start(name_label, False, False, 0)

            name_entry = Gtk.Entry()
            name_entry.set_text(current_name)
            name_entry.set_activates_default(True)
            content.pack_start(name_entry, False, False, 0)

            # Description entry
            desc_label = Gtk.Label(label="Beskrivning:")
            desc_label.set_xalign(0)
            content.pack_start(desc_label, False, False, 0)

            desc_entry = Gtk.Entry()
            desc_entry.set_text(current_desc)
            content.pack_start(desc_entry, False, False, 0)

            # Color button
            color_label = Gtk.Label(label="Färg:")
            color_label.set_xalign(0)
            content.pack_start(color_label, False, False, 0)

            color_button = Gtk.ColorButton()
            rgba = Gdk.RGBA()
            rgba.parse(current_color)
            color_button.set_rgba(rgba)
            content.pack_start(color_button, False, False, 0)

            dialog.set_default_response(Gtk.ResponseType.OK)
            dialog.show_all()

            response = dialog.run()
            name = name_entry.get_text().strip()
            description = desc_entry.get_text().strip()
            rgba = color_button.get_rgba()
            color = "#{:02x}{:02x}{:02x}".format(
                int(rgba.red * 255),
                int(rgba.green * 255),
                int(rgba.blue * 255)
            )
            dialog.destroy()

            if response == Gtk.ResponseType.OK and name:
                try:
                    self.db.update_category(category_id, name, description, color)
                    self._refresh_categories()
                except Exception as e:
                    error_dialog = Gtk.MessageDialog(
                        transient_for=self,
                        flags=0,
                        message_type=Gtk.MessageType.ERROR,
                        buttons=Gtk.ButtonsType.OK,
                        text="Kunde inte uppdatera kategori"
                    )
                    error_dialog.format_secondary_text(str(e))
                    error_dialog.run()
                    error_dialog.destroy()

    def _on_toggle_active(self, button):
        """Handle toggle active/inactive button."""
        selection = self.categories_tree.get_selection()
        model, tree_iter = selection.get_selected()

        if tree_iter:
            category_id = model[tree_iter][0]
            category_name = model[tree_iter][1]
            is_active = model[tree_iter][4]

            if is_active:
                # Deactivate
                success = self.db.deactivate_category(category_id)
                action = "inaktiverad"
            else:
                # Activate
                success = self.db.activate_category(category_id)
                action = "aktiverad"

            if success:
                self._refresh_categories()
            else:
                error_dialog = Gtk.MessageDialog(
                    transient_for=self,
                    flags=0,
                    message_type=Gtk.MessageType.ERROR,
                    buttons=Gtk.ButtonsType.OK,
                    text=f"Kunde inte markera kategori som {action}"
                )
                error_dialog.run()
                error_dialog.destroy()

    def _on_delete_category(self, button):
        """Handle delete category button."""
        selection = self.categories_tree.get_selection()
        model, tree_iter = selection.get_selected()

        if tree_iter:
            category_id = model[tree_iter][0]
            category_name = model[tree_iter][1]

            # Confirmation dialog
            dialog = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.QUESTION,
                buttons=Gtk.ButtonsType.YES_NO,
                text="Bekräfta borttagning"
            )
            dialog.format_secondary_text(
                f"Är du säker på att du vill ta bort kategorin?\n\n"
                f"Kategori: {category_name}\n\n"
                f"OBS: Kategorier med kopplade uppgifter kan inte raderas, "
                f"men kan inaktiveras istället."
            )

            response = dialog.run()
            dialog.destroy()

            if response == Gtk.ResponseType.YES:
                success, error_msg = self.db.delete_category(category_id)

                if success:
                    self._refresh_categories()
                else:
                    error_dialog = Gtk.MessageDialog(
                        transient_for=self,
                        flags=0,
                        message_type=Gtk.MessageType.ERROR,
                        buttons=Gtk.ButtonsType.OK,
                        text="Kunde inte radera kategori"
                    )
                    error_dialog.format_secondary_text(error_msg)
                    error_dialog.run()
                    error_dialog.destroy()
