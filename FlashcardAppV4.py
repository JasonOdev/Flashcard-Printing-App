"""
Flashcard Printer Application

A desktop application for creating, managing, and printing double-sided flashcards.

Dependencies:
- PySide6 (required): pip install PySide6
- deep-translator (optional, for auto-fill translation): pip install deep-translator

If deep-translator is not installed, the auto-fill language feature will be disabled.
"""

import sys
import sqlite3
import json
import csv
from datetime import datetime
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QPushButton,
    QLineEdit, QLabel, QMessageBox, QComboBox, QFileDialog,
    QDialog, QFormLayout, QColorDialog, QSpinBox, QDialogButtonBox
)
from PySide6.QtCore import Qt, QMarginsF, QRect, QTimer
from PySide6.QtPrintSupport import QPrinter, QPrintPreviewDialog
from PySide6.QtGui import QPainter, QPen, QPageSize, QFont, QPageLayout, QColor

# Optional translation support
try:
    from deep_translator import GoogleTranslator
    TRANSLATION_AVAILABLE = True
except ImportError:
    TRANSLATION_AVAILABLE = False


DB_FILE = "flashcards.db"
SETTINGS_FILE = "flashcard_settings.json"


# ------------------ Database ------------------

def init_db():
    """Initialize the SQLite database with flashcards table."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS flashcards (
            id INTEGER PRIMARY KEY,
            lesson TEXT,
            front TEXT,
            back TEXT,
            additional_note TEXT,
            selected INTEGER DEFAULT 0,
            copies INTEGER DEFAULT 1,
            printed_count INTEGER DEFAULT 0,
            last_printed TEXT
        )
    """)

    # Create indexes for better query performance
    c.execute("CREATE INDEX IF NOT EXISTS idx_lesson ON flashcards(lesson)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_selected ON flashcards(selected)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_front ON flashcards(front)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_back ON flashcards(back)")
    
    # Add additional_note column if it doesn't exist (for existing databases)
    try:
        c.execute("SELECT additional_note FROM flashcards LIMIT 1")
    except sqlite3.OperationalError:
        c.execute("ALTER TABLE flashcards ADD COLUMN additional_note TEXT DEFAULT ''")

    conn.commit()
    conn.close()


# ------------------ Settings ------------------

def load_settings():
    """Load settings from JSON file, return defaults if file doesn't exist."""
    default_settings = {
        "cards_per_page": "6",
        "orientation": "Portrait",
        "font_size": "60",
        "lesson_font_size": "16",
        "lesson_position": "Front",
        "note_position": "Front",
        "auto_fill_language": "Disabled",
        "auto_fill_note": "Disabled",
        "pen_color": "#000000",
        "pen_width": "2",
        "column_widths": {
            "0": 60,
            "1": 100,
            "2": 150,
            "3": 150,
            "4": 120,
            "5": 120,
            "6": 60,
            "7": 80,
            "8": 150
        }
    }
    try:
        with open(SETTINGS_FILE, 'r') as f:
            loaded = json.load(f)
            # Merge with defaults to ensure all keys exist
            for key in default_settings:
                if key not in loaded:
                    loaded[key] = default_settings[key]
            # Ensure column_widths is a dict with all columns
            if "column_widths" not in loaded or not isinstance(loaded["column_widths"], dict):
                loaded["column_widths"] = default_settings["column_widths"]
            return loaded
    except (FileNotFoundError, json.JSONDecodeError):
        return default_settings


def save_settings(settings):
    """Save settings to JSON file."""
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings, f, indent=2)


# ------------------ Options Dialog ------------------

class OptionsDialog(QDialog):
    """Dialog for managing application settings and import/export."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Options")
        self.setModal(True)
        self.parent_app = parent
        self.settings = parent.settings.copy()
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Settings form
        form = QFormLayout()
        
        # Cards per page
        self.cards_per_page = QSpinBox()
        self.cards_per_page.setRange(1, 12)
        self.cards_per_page.setValue(int(self.settings.get("cards_per_page", 6)))
        form.addRow("Cards per Page:", self.cards_per_page)
        
        # Orientation
        self.orientation = QComboBox()
        self.orientation.addItems(["Portrait", "Landscape"])
        self.orientation.setCurrentText(self.settings.get("orientation", "Portrait"))
        form.addRow("Orientation:", self.orientation)
        
        # Font size
        self.font_size = QSpinBox()
        self.font_size.setRange(6, 120)
        self.font_size.setValue(int(self.settings.get("font_size", 60)))
        form.addRow("Content Font Size:", self.font_size)
        
        # Lesson font size
        self.lesson_font_size = QSpinBox()
        self.lesson_font_size.setRange(6, 72)
        self.lesson_font_size.setValue(int(self.settings.get("lesson_font_size", 16)))
        form.addRow("Lesson Number Font Size:", self.lesson_font_size)
        
        # Lesson position
        self.lesson_position = QComboBox()
        self.lesson_position.addItems(["Front", "Back", "Both", "None"])
        self.lesson_position.setCurrentText(self.settings.get("lesson_position", "Front"))
        form.addRow("Lesson Number Position:", self.lesson_position)
        
        # Note position
        self.note_position = QComboBox()
        self.note_position.addItems(["Front", "Back", "Both", "None"])
        self.note_position.setCurrentText(self.settings.get("note_position", "Front"))
        form.addRow("Additional Note Position:", self.note_position)

        # Auto-fill note
        self.auto_fill_note = QComboBox()
        note_options = [
            "Disabled"
        ]
        self.auto_fill_note.addItems(note_options)
        self.auto_fill_note.setCurrentText(self.settings.get("auto_fill_note", "Disabled"))
        form.addRow("Auto-Fill Additional Note:", self.auto_fill_note)
        
        # Auto-fill language
        self.auto_fill_lang = QComboBox()
        languages = ["Disabled", "Spanish", "French", "German", "Italian", "Portuguese", "Latin", "Chinese", "Japanese"]
        self.auto_fill_lang.addItems(languages)
        self.auto_fill_lang.setCurrentText(self.settings.get("auto_fill_language", "Disabled"))
        if not TRANSLATION_AVAILABLE:
            self.auto_fill_lang.setEnabled(False)
            self.auto_fill_lang.setToolTip("Install 'deep-translator' package to enable: pip install deep-translator")
        form.addRow("Auto-Fill Language:", self.auto_fill_lang)
        
        
        # Pen color
        pen_layout = QHBoxLayout()
        self.pen_color = self.settings.get("pen_color", "#000000")
        self.pen_color_btn = QPushButton()
        self.pen_color_btn.setStyleSheet(f"background-color: {self.pen_color}; min-width: 80px;")
        self.pen_color_btn.clicked.connect(self.choose_pen_color)
        pen_layout.addWidget(self.pen_color_btn)
        pen_layout.addStretch()
        form.addRow("Pen Color:", pen_layout)
        
        # Pen width
        self.pen_width = QSpinBox()
        self.pen_width.setRange(1, 10)
        self.pen_width.setValue(int(self.settings.get("pen_width", 2)))
        form.addRow("Pen Width:", self.pen_width)
        
        layout.addLayout(form)
        
        # Import/Export section
        layout.addWidget(QLabel("\nImport/Export:"))
        
        import_export_layout = QHBoxLayout()
        
        import_btn = QPushButton("Import CSV")
        import_btn.clicked.connect(self.import_csv)
        import_export_layout.addWidget(import_btn)
        
        export_btn = QPushButton("Export CSV")
        export_btn.clicked.connect(self.export_csv)
        import_export_layout.addWidget(export_btn)
        
        layout.addLayout(import_export_layout)
        
        # Dialog buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept_settings)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
    def choose_pen_color(self):
        """Open color picker dialog."""
        color = QColorDialog.getColor(QColor(self.pen_color), self, "Choose Pen Color")
        if color.isValid():
            self.pen_color = color.name()
            self.pen_color_btn.setStyleSheet(f"background-color: {self.pen_color}; min-width: 80px;")
    
    def accept_settings(self):
        """Save settings and close dialog."""
        self.settings["cards_per_page"] = str(self.cards_per_page.value())
        self.settings["orientation"] = self.orientation.currentText()
        self.settings["font_size"] = str(self.font_size.value())
        self.settings["lesson_font_size"] = str(self.lesson_font_size.value())
        self.settings["lesson_position"] = self.lesson_position.currentText()
        self.settings["note_position"] = self.note_position.currentText()
        self.settings["auto_fill_language"] = self.auto_fill_lang.currentText()
        self.settings["auto_fill_note"] = self.auto_fill_note.currentText()
        self.settings["pen_color"] = self.pen_color
        self.settings["pen_width"] = str(self.pen_width.value())
        
        self.parent_app.settings = self.settings
        self.parent_app.apply_settings()
        save_settings(self.settings)
        self.accept()
    
    def import_csv(self):
        """Import flashcards from CSV file."""
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Import CSV",
            "",
            "CSV Files (*.csv);;All Files (*)"
        )
        
        if not filename:
            return
        
        try:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            imported = 0
            
            # Read all rows first for batch insert
            rows_to_insert = []
            with open(filename, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    lesson = row.get('lesson', '').strip()
                    front = row.get('front', '').strip()
                    back = row.get('back', '').strip()
                    additional_note = row.get('additional_note', '').strip()
                    
                    if lesson and front and back:
                        rows_to_insert.append((lesson, front, back, additional_note))
            
            # Batch insert for better performance
            if rows_to_insert:
                c.executemany("""
                    INSERT INTO flashcards (lesson, front, back, additional_note, selected, copies)
                    VALUES (?, ?, ?, ?, 0, 1)
                """, rows_to_insert)
                imported = len(rows_to_insert)
            
            conn.commit()
            conn.close()
            
            QMessageBox.information(
                self,
                "Import Complete",
                f"Successfully imported {imported} flashcards."
            )
            
            if self.parent_app:
                self.parent_app.load_data()
                
        except Exception as e:
            QMessageBox.critical(
                self,
                "Import Error",
                f"Failed to import CSV: {str(e)}"
            )
    
    def export_csv(self):
        """Export all flashcards to CSV file."""
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export CSV",
            "flashcards_export.csv",
            "CSV Files (*.csv);;All Files (*)"
        )
        
        if not filename:
            return
        
        try:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['lesson', 'front', 'back', 'additional_note', 'copies', 'printed_count', 'last_printed'])
                
                for row in c.execute("SELECT lesson, front, back, additional_note, copies, printed_count, last_printed FROM flashcards ORDER BY lesson, id"):
                    writer.writerow(row)
            
            conn.close()
            
            QMessageBox.information(
                self,
                "Export Complete",
                f"Successfully exported flashcards to {filename}"
            )
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Export Error",
                f"Failed to export CSV: {str(e)}"
            )


# ------------------ Main Application ------------------

class FlashcardApp(QWidget):
    """Main application window for managing flashcards."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Flashcard Printer")
        self.resize(1200, 600)
        init_db()
        self.settings = load_settings()
        self.build_ui()
        self.filter_selected = False
        self.last_added_id = None
        self.last_lesson = ""
        self.lesson_input.setText(self.last_lesson)
        self.filter_timer = QTimer()
        self.filter_timer.setSingleShot(True)
        self.filter_timer.timeout.connect(self.on_search_changed)
        self.apply_settings()
        self.load_data()

    def build_ui(self):
        """Build the user interface."""
        layout = QVBoxLayout(self)

        # Controls Row 1 - Search and Actions
        controls1 = QHBoxLayout()
        
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search lesson, front, or back...")
        self.search.textChanged.connect(self.debounced_filter)

        self.show_all_btn = QPushButton("Show All")
        self.show_all_btn.clicked.connect(self.show_all)

        self.show_selected_btn = QPushButton("Show Selected")
        self.show_selected_btn.clicked.connect(self.show_selected)

        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.clicked.connect(self.select_all)

        self.unselect_btn = QPushButton("Unselect All")
        self.unselect_btn.clicked.connect(self.unselect_all)

        self.select_unprinted_btn = QPushButton("Select Unprinted")
        self.select_unprinted_btn.clicked.connect(self.select_all_unprinted)

        self.delete_selected_btn = QPushButton("Delete Selected")
        self.delete_selected_btn.clicked.connect(self.delete_selected)

        controls1.addWidget(QLabel("Search:"))
        controls1.addWidget(self.search)
        controls1.addWidget(self.show_all_btn)
        controls1.addWidget(self.show_selected_btn)
        controls1.addWidget(self.select_all_btn)
        controls1.addWidget(self.unselect_btn)
        controls1.addWidget(self.select_unprinted_btn)
        controls1.addWidget(self.delete_selected_btn)

        layout.addLayout(controls1)

        # Controls Row 2 - Print and Options
        controls2 = QHBoxLayout()
        
        self.print_btn = QPushButton("Print Selected")
        self.print_btn.clicked.connect(self.print_selected)

        self.options_btn = QPushButton("Options...")
        self.options_btn.clicked.connect(self.show_options)

        help_label = QLabel(
            "<i>Tip: Fill in the fields at the bottom of the window and press Enter to add a card.</i>"
        )
        help_label.setStyleSheet("color: #666;")

        controls2.addWidget(self.print_btn)
        controls2.addWidget(self.options_btn)
        controls2.addSpacing(15)
        controls2.addWidget(help_label)
        controls2.addStretch()

        layout.addLayout(controls2)

        # Table (now with 9 columns to include Additional Note)
        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels([
            "Print", "Lesson", "Front", "Back", "Note",
            "Copies", "Delete", "Printed", "Last Printed"
        ])
        self.table.cellChanged.connect(self.update_cell)
        
        # Connect header resize event to save column widths
        header = self.table.horizontalHeader()
        header.sectionResized.connect(self.on_column_resized)

        layout.addWidget(self.table)

        # Add Flashcard Entry
        entry = QHBoxLayout()

        self.lesson_input = QLineEdit()
        self.lesson_input.setPlaceholderText("Lesson")

        self.front_input = QLineEdit()
        self.front_input.setPlaceholderText("Front text")
        self.front_input.editingFinished.connect(self.auto_fill_back)

        self.back_input = QLineEdit()
        self.back_input.setPlaceholderText("Back text (press Enter to add)")
        self.back_input.returnPressed.connect(self.add_flashcard)
        
        self.note_input = QLineEdit()
        self.note_input.setPlaceholderText("Additional Note (press Enter to add)")
        self.note_input.editingFinished.connect(self.auto_fill_note)
        self.note_input.returnPressed.connect(self.add_flashcard)

        add_btn = QPushButton("Add Flashcard")
        add_btn.clicked.connect(self.add_flashcard)

        entry.addWidget(self.lesson_input)
        entry.addWidget(self.front_input)
        entry.addWidget(self.back_input)
        entry.addWidget(self.note_input)
        entry.addWidget(add_btn)

        layout.addLayout(entry)

    def apply_settings(self):
        """Apply loaded settings to UI controls."""
        # Apply column widths
        column_widths = self.settings.get("column_widths", {})
        for col_str, width in column_widths.items():
            try:
                col_idx = int(col_str)
                if 0 <= col_idx < self.table.columnCount():
                    self.table.setColumnWidth(col_idx, width)
            except (ValueError, TypeError):
                pass

    def on_column_resized(self, logical_index, old_size, new_size):
        """Save column width when user resizes a column."""
        if "column_widths" not in self.settings:
            self.settings["column_widths"] = {}
        self.settings["column_widths"][str(logical_index)] = new_size
        save_settings(self.settings)

    def load_data(self):
        """Load flashcards from database and populate table."""
        filter_text = self.search.text().strip()

        # Build query with WHERE clauses
        where_clauses = []
        params = []

        if filter_text:
            where_clauses.append("(lesson LIKE ? OR front LIKE ? OR back LIKE ? OR additional_note LIKE ?)")
            search_param = f"%{filter_text}%"
            params.extend([search_param, search_param, search_param, search_param])

        if self.filter_selected:
            where_clauses.append("selected = 1")

        where = " AND ".join(where_clauses) if where_clauses else "1=1"

        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()

        query = f"""
            SELECT id, lesson, front, back, additional_note, selected, copies, printed_count, last_printed
            FROM flashcards
            WHERE {where}
            ORDER BY lesson, id
        """

        rows = c.execute(query, params).fetchall()
        conn.close()

        # Block signals during bulk table update
        self.table.blockSignals(True)
        self.table.setRowCount(len(rows))

        for row_idx, row_data in enumerate(rows):
            card_id, lesson, front, back, additional_note, selected, copies, printed_count, last_printed = row_data

            # Print checkbox
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            chk.setCheckState(Qt.Checked if selected else Qt.Unchecked)
            chk.setData(Qt.UserRole, card_id)
            self.table.setItem(row_idx, 0, chk)

            # Editable text columns
            self.table.setItem(row_idx, 1, QTableWidgetItem(lesson))
            self.table.setItem(row_idx, 2, QTableWidgetItem(front))
            self.table.setItem(row_idx, 3, QTableWidgetItem(back))
            self.table.setItem(row_idx, 4, QTableWidgetItem(additional_note or ""))

            # Copies (editable)
            copies_item = QTableWidgetItem(str(copies))
            self.table.setItem(row_idx, 5, copies_item)

            # Delete button
            del_btn = QPushButton("Delete")
            del_btn.clicked.connect(lambda checked, cid=card_id: self.delete_single(cid))
            self.table.setCellWidget(row_idx, 6, del_btn)

            # Printed count (read-only)
            printed_item = QTableWidgetItem(str(printed_count))
            printed_item.setFlags(printed_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row_idx, 7, printed_item)

            # Last printed (read-only)
            last_printed_text = last_printed if last_printed else "Never"
            last_printed_item = QTableWidgetItem(last_printed_text)
            last_printed_item.setFlags(last_printed_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row_idx, 8, last_printed_item)

        self.table.blockSignals(False)

    def update_cell(self, row, col):
        """Called when a cell in the table is edited."""
        # Column 0: Print checkbox
        if col == 0:
            item = self.table.item(row, 0)
            if item is None:
                return
            card_id = item.data(Qt.UserRole)
            if card_id is None:
                return
            new_state = 1 if item.checkState() == Qt.Checked else 0
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("UPDATE flashcards SET selected = ? WHERE id = ?", (new_state, card_id))
            conn.commit()
            conn.close()

        # Columns 1-4: Lesson, Front, Back, Note (editable text)
        elif col in (1, 2, 3, 4):
            item_0 = self.table.item(row, 0)
            if item_0 is None:
                return
            card_id = item_0.data(Qt.UserRole)
            if card_id is None:
                return

            item = self.table.item(row, col)
            if item is None:
                return

            new_value = item.text().strip()

            # Map column to database field
            field_map = {1: "lesson", 2: "front", 3: "back", 4: "additional_note"}
            field = field_map[col]

            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute(f"UPDATE flashcards SET {field} = ? WHERE id = ?", (new_value, card_id))
            conn.commit()
            conn.close()

        # Column 5: Copies (editable)
        elif col == 5:
            item_0 = self.table.item(row, 0)
            if item_0 is None:
                return
            card_id = item_0.data(Qt.UserRole)
            if card_id is None:
                return

            item = self.table.item(row, col)
            if item is None:
                return

            try:
                new_copies = int(item.text())
                if new_copies < 1:
                    new_copies = 1
                    item.setText("1")
            except ValueError:
                item.setText("1")
                new_copies = 1

            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("UPDATE flashcards SET copies = ? WHERE id = ?", (new_copies, card_id))
            conn.commit()
            conn.close()

    def debounced_filter(self):
        """Start or restart the 300ms filter timer."""
        self.filter_timer.stop()
        self.filter_timer.start(300)

    def on_search_changed(self):
        """Called 300ms after the user stops typing in the search box."""
        self.load_data()

    def show_all(self):
        """Show all flashcards (clear both search and filter_selected)."""
        self.filter_selected = False
        self.search.clear()
        self.load_data()

    def show_selected(self):
        """Show only selected flashcards."""
        self.filter_selected = True
        self.load_data()

    def select_all(self):
        """Select all currently visible flashcards."""
        # Get all currently visible card IDs
        card_ids = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                card_id = item.data(Qt.UserRole)
                if card_id:
                    card_ids.append((card_id,))

        if not card_ids:
            return

        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.executemany("UPDATE flashcards SET selected = 1 WHERE id = ?", card_ids)
        conn.commit()
        conn.close()

        self.load_data()

    def unselect_all(self):
        """Unselect all flashcards."""
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("UPDATE flashcards SET selected = 0")
        conn.commit()
        conn.close()
        self.load_data()

    def select_all_unprinted(self):
        """Select all flashcards that have never been printed."""
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("UPDATE flashcards SET selected = 1 WHERE printed_count = 0")
        conn.commit()
        conn.close()
        self.load_data()

    def delete_selected(self):
        """Delete all selected flashcards."""
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        count = c.execute("SELECT COUNT(*) FROM flashcards WHERE selected = 1").fetchone()[0]
        conn.close()

        if count == 0:
            QMessageBox.information(self, "Nothing Selected", "No cards are selected.")
            return

        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete {count} selected flashcard(s)?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("DELETE FROM flashcards WHERE selected = 1")
            conn.commit()
            conn.close()
            self.load_data()

    def delete_single(self, card_id):
        """Delete a single flashcard by ID."""
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            "Delete this flashcard?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("DELETE FROM flashcards WHERE id = ?", (card_id,))
            conn.commit()
            conn.close()
            self.load_data()

    def add_flashcard(self):
        """Add a new flashcard from the entry fields."""
        lesson = self.lesson_input.text().strip()
        front = self.front_input.text().strip()
        back = self.back_input.text().strip()
        note = self.note_input.text().strip()

        if not lesson or not front or not back:
            QMessageBox.warning(self, "Missing Data", "Please fill in Lesson, Front, and Back fields.")
            return

        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("""
            INSERT INTO flashcards (lesson, front, back, additional_note, selected, copies)
            VALUES (?, ?, ?, ?, 0, 1)
        """, (lesson, front, back, note))
        self.last_added_id = c.lastrowid
        conn.commit()
        conn.close()

        # Remember the lesson for next card
        self.last_lesson = lesson

        # Clear inputs
        self.front_input.clear()
        self.back_input.clear()
        self.note_input.clear()
        self.lesson_input.setText(self.last_lesson)

        self.load_data()

        # Scroll to the newly added card so it's visible
        self.scroll_to_card(self.last_added_id)

        self.front_input.setFocus()

    def scroll_to_card(self, card_id):
        """Scroll the table so the row with the given card_id is visible."""
        if card_id is None:
            return

        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.data(Qt.UserRole) == card_id:
                self.table.scrollToItem(item, QTableWidget.PositionAtCenter)
                # Also briefly highlight the row by selecting it
                # self.table.selectRow(row)
                break

    def auto_fill_back(self):
        """Auto-fill back field using translation if enabled."""
        if not TRANSLATION_AVAILABLE:
            return

        lang = self.settings.get("auto_fill_language", "Disabled")
        if lang == "Disabled":
            return

        front_text = self.front_input.text().strip()
        if not front_text:
            self.back_input.clear()
            return

        # Don't overwrite if back already has text
        if self.back_input.text().strip():
            return

        # Map language names to language codes
        lang_codes = {
            "Spanish": "es",
            "French": "fr",
            "German": "de",
            "Italian": "it",
            "Portuguese": "pt",
            "Latin": "la",
            "Chinese": "zh-CN",
            "Japanese": "ja"
        }

        target_lang = lang_codes.get(lang)
        if not target_lang:
            return

        try:
            translator = GoogleTranslator(source='auto', target=target_lang)
            translation = translator.translate(front_text)
            self.back_input.setText(translation)
        except Exception:
            # Silently fail - user can manually type if translation fails
            pass

    def auto_fill_note(self):
        """Auto-fill note field based on selected preset."""
        note_setting = self.settings.get("auto_fill_note", "Disabled")
        
        if note_setting == "Disabled":
            return
        
        # Don't overwrite if note already has text
        if self.note_input.text().strip():
            return
        
        # Map settings to actual text
        note_map = {
            "Part of Speech (noun)": "noun",
            "Part of Speech (verb)": "verb",
            "Part of Speech (adj)": "adj",
            "Part of Speech (adv)": "adv",
            "Gender (m)": "m",
            "Gender (f)": "f",
            "Gender (n)": "n",
            "1st Declension": "1st decl",
            "2nd Declension": "2nd decl",
            "3rd Declension": "3rd decl",
            "4th Declension": "4th decl",
            "5th Declension": "5th decl",
            "1st Conjugation": "1st conj",
            "2nd Conjugation": "2nd conj",
            "3rd Conjugation": "3rd conj",
            "4th Conjugation": "4th conj",
            "Irregular": "irregular",
            "Singular": "sing",
            "Plural": "pl"
        }
        
        note_text = note_map.get(note_setting, "")
        if note_text:
            self.note_input.setText(note_text)

    def show_options(self):
        """Show the options dialog."""
        dialog = OptionsDialog(self)
        dialog.exec()

    def print_selected(self):
        """Print selected flashcards."""
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        cards = []

        # Fetch selected cards with additional_note
        for row in c.execute("SELECT lesson, front, back, additional_note, copies FROM flashcards WHERE selected=1 ORDER BY lesson"):
            lesson, front, back, additional_note, copies = row
            for _ in range(copies):
                cards.append((lesson, front, back, additional_note or ""))

        conn.close()

        if not cards:
            QMessageBox.information(self, "Nothing to Print", "No cards selected.")
            return

        # Parse settings
        try:
            cpp = int(self.settings.get("cards_per_page", 6))
            if cpp < 1 or cpp > 12:
                raise ValueError
        except ValueError:
            QMessageBox.warning(self, "Invalid Setting", "Cards per page must be between 1 and 12.")
            return

        try:
            font_size = int(self.settings.get("font_size", 60))
            if font_size < 6 or font_size > 120:
                raise ValueError
        except ValueError:
            QMessageBox.warning(self, "Invalid Setting", "Font size must be between 6 and 120.")
            return

        try:
            lesson_font_size = int(self.settings.get("lesson_font_size", 16))
            if lesson_font_size < 6 or lesson_font_size > 72:
                raise ValueError
        except ValueError:
            QMessageBox.warning(self, "Invalid Setting", "Lesson font size must be between 6 and 72.")
            return

        # Store cards and settings for printing
        self.cards_to_print = cards
        self.print_cpp = cpp
        self.print_font_size = font_size
        self.print_lesson_font_size = lesson_font_size

        # Create printer
        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setPageSize(QPageSize(QPageSize.Letter))

        if self.settings.get("orientation", "Portrait") == "Landscape":
            printer.setPageOrientation(QPageLayout.Orientation.Landscape)
        else:
            printer.setPageOrientation(QPageLayout.Orientation.Portrait)

        printer.setPageMargins(QMarginsF(0, 0, 0, 0))

        # Use print preview dialog
        preview = QPrintPreviewDialog(printer, self)
        preview.paintRequested.connect(self.render_document)

        if preview.exec() != QPrintPreviewDialog.Accepted:
            return

        # Update print stats
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        now = datetime.now().isoformat(sep=" ", timespec="seconds")
        c.execute("""
            UPDATE flashcards
            SET printed_count = printed_count + copies,
                last_printed = ?
            WHERE selected = 1
        """, (now,))
        conn.commit()
        conn.close()

        self.load_data()

    def render_document(self, printer):
        """Render the flashcards to the printer/preview."""
        cards = self.cards_to_print
        cpp = self.print_cpp
        font_size = self.print_font_size
        lesson_font_size = self.print_lesson_font_size

        painter = QPainter()
        if not painter.begin(printer):
            return

        # Get pen settings
        pen_color = self.settings.get("pen_color", "#000000")
        pen_width = int(self.settings.get("pen_width", 2))
        
        # Get position settings
        lesson_position = self.settings.get("lesson_position", "Front")
        note_position = self.settings.get("note_position", "Front")

        pen = QPen(QColor(pen_color))
        painter.setPen(pen)

        dpi = printer.resolution()

        # Letter size in inches
        PAGE_W_IN = 8.5
        PAGE_H_IN = 11.0

        if printer.pageLayout().orientation() == QPageLayout.Landscape:
            PAGE_W_IN, PAGE_H_IN = PAGE_H_IN, PAGE_W_IN

        page_width_px = int(PAGE_W_IN * dpi)
        page_height_px = int(PAGE_H_IN * dpi)

        page_rect = QRect(0, 0, page_width_px, page_height_px)
        rows = cpp // 2
        card_w = page_rect.width() / 2
        card_h = page_rect.height() / rows

        index = 0

        while index < len(cards):
            # FRONT SIDE
            for i in range(cpp):
                if index + i >= len(cards):
                    break
                r = i // 2
                c = i % 2
                x = c * card_w
                y = r * card_h

                lesson, front, _, additional_note = cards[index + i]

                # Draw card border
                pen.setColor(pen_color)
                pen.setWidthF(pen_width)
                pen.setCosmetic(True)
                painter.setPen(pen)
                painter.drawRect(x, y, card_w, card_h)

                pen.setColor("black")
                painter.setPen(pen)

                # Draw lesson number if set to Front or Both
                if lesson_position in ("Front", "Both"):
                    lesson_font = QFont()
                    lesson_font.setPointSize(lesson_font_size)
                    painter.setFont(lesson_font)
                    lesson_rect = painter.boundingRect(
                        x + 10, y + 200,
                        card_w - 400, 30,
                        Qt.AlignRight,
                        f"{lesson}"
                    )
                    painter.drawText(lesson_rect, Qt.AlignLeft, f"{lesson}")

                # Draw additional note if set to Front or Both
                if note_position in ("Front", "Both") and additional_note:
                    note_font = QFont()
                    note_font.setPointSize(lesson_font_size)
                    painter.setFont(note_font)
                    note_rect = painter.boundingRect(
                        x + 10, y + 200,
                        card_w - 20, 30,
                        Qt.AlignCenter,
                        additional_note
                    )
                    painter.drawText(note_rect, Qt.AlignCenter, additional_note)

                # Draw front text with user-specified font size, centered
                content_font = QFont()
                content_font.setPointSize(font_size)
                painter.setFont(content_font)
                painter.drawText(
                    x + 10, y + 20,
                    card_w - 20, card_h - 40,
                    Qt.AlignCenter | Qt.TextWordWrap,
                    front
                )

            printer.newPage()

            # BACK SIDE (mirrored horizontally)
            for i in range(cpp):
                if index + i >= len(cards):
                    break
                r = i // 2
                c = 1 - (i % 2)
                x = c * card_w
                y = r * card_h

                lesson, _, back, additional_note = cards[index + i]

                pen.setColor("black")
                painter.setPen(pen)

                # Draw lesson number if set to Back or Both
                if lesson_position in ("Back", "Both"):
                    lesson_font = QFont()
                    lesson_font.setPointSize(lesson_font_size)
                    painter.setFont(lesson_font)
                    lesson_rect = painter.boundingRect(
                        x + 10, y + 200,
                        card_w - 400, 30,
                        Qt.AlignRight,
                        f"{lesson}"
                    )
                    painter.drawText(lesson_rect, Qt.AlignLeft, f"{lesson}")

                # Draw additional note if set to Back or Both
                if note_position in ("Back", "Both") and additional_note:
                    note_font = QFont()
                    note_font.setPointSize(lesson_font_size)
                    painter.setFont(note_font)
                    note_rect = painter.boundingRect(
                        x + 10, y + 200,
                        card_w - 20, 30,
                        Qt.AlignCenter,
                        additional_note
                    )
                    painter.drawText(note_rect, Qt.AlignCenter, additional_note)

                # Draw back text with user-specified font size, centered
                content_font = QFont()
                content_font.setPointSize(font_size)
                painter.setFont(content_font)
                painter.drawText(
                    x + 10, y + 20,
                    card_w - 20, card_h - 40,
                    Qt.AlignCenter | Qt.TextWordWrap,
                    back
                )

            index += cpp
            if index < len(cards):
                printer.newPage()

        painter.end()


# ------------------ Run ------------------

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = FlashcardApp()
    w.show()
    sys.exit(app.exec())
