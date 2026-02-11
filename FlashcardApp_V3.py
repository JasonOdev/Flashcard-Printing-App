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

    conn.commit()
    conn.close()


# ------------------ Settings ------------------

def load_settings():
    """Load settings from JSON file, return defaults if file doesn't exist."""
    default_settings = {
        "cards_per_page": "6",
        "orientation": "Portrait",
        "font_size": "60",
        "auto_fill_language": "Disabled",
        "pen_color": "#000000",
        "pen_width": "2",
        "column_widths": {
            "0": 60,
            "1": 100,
            "2": 150,
            "3": 150,
            "4": 80,
            "5": 60,
            "6": 80,
            "7": 120
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
        form.addRow("Font Size:", self.font_size)
        
        # Auto-fill language
        self.auto_fill_lang = QComboBox()
        languages = ["Disabled", "Spanish", "French", "German", "Italian", "Portuguese", "Chinese", "Japanese"]
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
        self.settings["auto_fill_language"] = self.auto_fill_lang.currentText()
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
                    
                    if lesson and front and back:
                        rows_to_insert.append((lesson, front, back))
            
            # Batch insert for better performance
            if rows_to_insert:
                c.executemany("""
                    INSERT INTO flashcards (lesson, front, back, selected, copies)
                    VALUES (?, ?, ?, 0, 1)
                """, rows_to_insert)
                imported = len(rows_to_insert)
            
            conn.commit()
            conn.close()
            
            QMessageBox.information(
                self,
                "Import Complete",
                f"Imported {imported} flashcards from CSV."
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
            "flashcards.csv",
            "CSV Files (*.csv);;All Files (*)"
        )
        
        if not filename:
            return
        
        try:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['lesson', 'front', 'back', 'copies', 'printed_count', 'last_printed'])
                
                for row in c.execute("SELECT lesson, front, back, copies, printed_count, last_printed FROM flashcards"):
                    writer.writerow(row)
            
            conn.close()
            
            QMessageBox.information(
                self,
                "Export Complete",
                f"Exported flashcards to {filename}"
            )
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Export Error",
                f"Failed to export CSV: {str(e)}"
            )


# ------------------ Main App ------------------

class FlashcardApp(QWidget):
    """Main application window for managing flashcards."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Flashcard Printer")
        self.resize(1100, 600)
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

        controls2.addWidget(self.print_btn)
        controls2.addWidget(self.options_btn)
        controls2.addStretch()

        layout.addLayout(controls2)

        # Table
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels([
            "Print", "Lesson", "Front", "Back",
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

        add_btn = QPushButton("Add Flashcard")
        add_btn.clicked.connect(self.add_flashcard)

        entry.addWidget(self.lesson_input)
        entry.addWidget(self.front_input)
        entry.addWidget(self.back_input)
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

        # Build optimized query with filter at database level
        if filter_text:
            query = """
                SELECT id, lesson, front, back, selected, copies, printed_count, last_printed
                FROM flashcards
                WHERE lesson LIKE ? OR front LIKE ? OR back LIKE ?
                ORDER BY lesson, id
            """
            filter_param = f"%{filter_text}%"
            params = (filter_param, filter_param, filter_param)

        elif self.filter_selected:
            query = """
                SELECT id, lesson, front, back, selected, copies, printed_count, last_printed
                FROM flashcards
                WHERE selected = 1
                ORDER BY lesson, id
            """
            params = ()
        else:
            query = """
                SELECT id, lesson, front, back, selected, copies, printed_count, last_printed
                FROM flashcards
                ORDER BY lesson, id
            """
            params = ()

        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()

        # Fetch all matching rows
        rows = c.execute(query, params).fetchall()
        conn.close()

        self.table.blockSignals(True)
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        self.table.setRowCount(len(rows))

       # Populate table in batch
        for row_idx, row in enumerate(rows):
            card_id, lesson, front, back, selected, copies, printed_count, last_printed = row

            # Highlight if this is the last added card
            is_last_added = (card_id == self.last_added_id)

            # Select checkbox
            chk_item = QTableWidgetItem()
            chk_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            chk_item.setCheckState(Qt.Checked if selected else Qt.Unchecked)
            chk_item.setData(Qt.UserRole, card_id)
            self.table.setItem(row_idx, 0, chk_item)
            
            # Other columns
            self.table.setItem(row_idx, 1, QTableWidgetItem(lesson))
            self.table.setItem(row_idx, 2, QTableWidgetItem(front))
            self.table.setItem(row_idx, 3, QTableWidgetItem(back))
            copies_item = QTableWidgetItem(str(copies))
            copies_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 4, copies_item)

            # Column 5: Delete button
            delete_btn = QPushButton("Delete")
            delete_btn.clicked.connect(lambda checked, cid=card_id: self.delete_row(cid))
            self.table.setCellWidget(row_idx, 5, delete_btn)

            printed_count_item = QTableWidgetItem(str(printed_count))
            printed_count_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 6, printed_count_item)
            #self.table.setItem(row_idx, 5, QTableWidgetItem(str(printed_count)))
            self.table.setItem(row_idx, 7, QTableWidgetItem(last_printed or ""))
            
            # Actions buttons
            # actions_widget = QWidget()
            # actions_layout = QHBoxLayout(actions_widget)
            # actions_layout.setContentsMargins(2, 2, 2, 2)
            
            # edit_btn = QPushButton("Edit")
            # edit_btn.clicked.connect(lambda checked, cid=card_id: self.edit_card(cid))
            # actions_layout.addWidget(edit_btn)
            
            # delete_btn = QPushButton("Del")
            # delete_btn.clicked.connect(lambda checked, cid=card_id: self.delete_card(cid))
            # actions_layout.addWidget(delete_btn)
            
            # self.table.setCellWidget(row_idx, 7, actions_widget)

            # Apply light blue background to last added card
            if is_last_added:
                for col in range(self.table.columnCount()):
                    item = self.table.item(row_idx, col)
                    if item:
                        item.setBackground(QColor(173, 216, 230))
    

        self.table.setSortingEnabled(True)
        self.table.blockSignals(False)

        # Scroll to the last added card if it exists
        if self.last_added_id:
            for row in range(self.table.rowCount()):
                item = self.table.item(row, 0)
                if item and item.data(Qt.UserRole) == self.last_added_id:
                    self.table.scrollToItem(item)
                    break
        else:
            self.table.scrollToBottom()

    
    def add_flashcard(self):
        """Add a new flashcard to the database."""
        lesson = self.lesson_input.text().strip()
        front = self.front_input.text().strip()
        back = self.back_input.text().strip()

        if not front or not back:
            QMessageBox.warning(self, "Missing Data", "Front and back text is required.")
            return

        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("""
            INSERT INTO flashcards (lesson, front, back, selected, copies)
            VALUES (?, ?, ?, 0, 1)
        """, (lesson, front, back))
        self.last_added_id = c.lastrowid
        conn.commit()
        conn.close()

        self.last_lesson = lesson
        self.lesson_input.setText(self.last_lesson)
        self.front_input.clear()
        self.back_input.clear()
        self.front_input.setFocus()

        self.load_data()

    def update_cell(self, row, col):
        """Update database when a cell is changed."""
        item = self.table.item(row, 0)
        if not item:
            return
            
        card_id = item.data(Qt.UserRole)
        if not card_id:
            return

        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()

        if col == 0:  # Checkbox
            selected = 1 if item.checkState() == Qt.Checked else 0
            c.execute("UPDATE flashcards SET selected=? WHERE id=?",
                      (selected, card_id))

        elif col == 1:  # Lesson
            value = self.table.item(row, col).text()
            c.execute("UPDATE flashcards SET lesson=? WHERE id=?", (value, card_id))

        elif col == 2:  # Front
            value = self.table.item(row, col).text()
            c.execute("UPDATE flashcards SET front=? WHERE id=?", (value, card_id))

        elif col == 3:  # Back
            value = self.table.item(row, col).text()
            c.execute("UPDATE flashcards SET back=? WHERE id=?", (value, card_id))

        elif col == 4:  # Copies
            try:
                copies_text = self.table.item(row, col).text()
                copies = int(copies_text)
                if copies < 1:
                    copies = 1
                c.execute("UPDATE flashcards SET copies=? WHERE id=?",
                          (copies, card_id))
            except (ValueError, AttributeError):
                # Reset to 1 if invalid
                self.table.blockSignals(True)
                self.table.item(row, col).setText("1")
                self.table.blockSignals(False)
                c.execute("UPDATE flashcards SET copies=1 WHERE id=?", (card_id,))

        conn.commit()
        conn.close()

    def delete_row(self, card_id):
        """Delete a single flashcard after confirmation."""
        reply = QMessageBox.question(
            self, 
            "Confirm Delete",
            "Are you sure you want to delete this flashcard?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("DELETE FROM flashcards WHERE id=?", (card_id,))
            conn.commit()
            conn.close()
            self.load_data()

    def delete_selected(self):
        """Delete all selected flashcards after confirmation."""
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        
        # Count selected cards
        count = c.execute("SELECT COUNT(*) FROM flashcards WHERE selected=1").fetchone()[0]
        
        if count == 0:
            QMessageBox.information(self, "No Selection", "No flashcards are selected.")
            conn.close()
            return
        
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete {count} selected flashcard(s)?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            c.execute("DELETE FROM flashcards WHERE selected=1")
            conn.commit()
            conn.close()
            self.load_data()
        else:
            conn.close()

    def select_all(self):
        """Select all flashcards."""
        # conn = sqlite3.connect(DB_FILE)
        # c = conn.cursor()
        # c.execute("UPDATE flashcards SET selected=1")
        # conn.commit()
        # conn.close()
        # self.load_data()

        """Select all visible flashcards (OPTIMIZED)."""
        # Get filtered card IDs
        card_ids = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                card_id = item.data(Qt.UserRole)
                if card_id:
                    card_ids.append((card_id,))
        
        if not card_ids:
            return
        
        # Batch update
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
        c.execute("UPDATE flashcards SET selected=0")
        conn.commit()
        conn.close()
        self.load_data()

    def select_all_unprinted(self):
        """Select all unprinted flashcards and unselect others."""
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("UPDATE flashcards SET selected=0")
        c.execute("UPDATE flashcards SET selected=1 WHERE printed_count=0")
        conn.commit()
        conn.close()
        self.load_data()

    def debounced_filter(self):
        """Debounce filter input - wait 300ms after user stops typing."""
        self.filter_timer.stop()
        self.filter_timer.start(300)

    def on_search_changed(self):
        """Handle search text changes - always search ALL cards."""
        if self.search.text():
            self.filter_selected = False
        self.filter_timer.stop()  # Stop any pending filter
        self.load_data()

    def show_all(self):
        """Clear search and show all flashcards."""
        self.search.clear()
        self.filter_selected = False
        self.load_data()

    def show_selected(self):
        """Clear search and show only selected flashcards."""
        self.search.clear()
        self.filter_selected = True
        self.load_data()

    def show_options(self):
        """Show the options dialog."""
        dialog = OptionsDialog(self)
        dialog.exec()

    def auto_fill_back(self):
        """Auto-fill back text with translation if enabled."""
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

    def print_selected(self):
        """Print selected flashcards."""
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        cards = []

        for row in c.execute("SELECT * FROM flashcards WHERE selected=1 ORDER BY lesson"):
            _, lesson, front, back, _, copies, _, _ = row
            for _ in range(copies):
                cards.append((lesson, front, back))

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
            font_size = int(self.settings.get("font_size", 12))
            if font_size < 6 or font_size > 120:
                raise ValueError
        except ValueError:
            QMessageBox.warning(self, "Invalid Setting", "Font size must be between 6 and 120.")
            return

        # Store cards and settings for printing
        self.cards_to_print = cards
        self.print_cpp = cpp
        self.print_font_size = font_size

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

        painter = QPainter()
        if not painter.begin(printer):
            return
        
        # Get pen settings
        pen_color = self.settings.get("pen_color", "#000000")
        pen_width = int(self.settings.get("pen_width", 2))
        
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

                lesson, front, _ = cards[index + i]
                
                # Draw card border
                pen.setColor(pen_color) #set the pen for the cut line color
                pen.setWidthF(pen_width)
                pen.setCosmetic(True)
                painter.setPen(pen)
                painter.drawRect(x, y, card_w, card_h)

                pen.setColor("black") #reset the pen before doing the text
                painter.setPen(pen)

                # Draw lesson number with fixed 16pt font at top
                lesson_font = QFont()
                lesson_font.setPointSize(16)
                painter.setFont(lesson_font)
                lesson_rect = painter.boundingRect(
                    x + 10, y + 300,
                    card_w - 400, 30,
                    Qt.AlignRight,
                    f"{lesson}"
                )
                painter.drawText(lesson_rect, Qt.AlignCenter, f"{lesson}")
                
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

                _, _, back = cards[index + i]
                
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
