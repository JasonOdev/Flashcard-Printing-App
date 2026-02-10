# Flashcard Printer

A desktop application for creating, managing, and printing double-sided flashcards.

## Installation

### Requirements

* Python 3.7 or higher
* PySide6 (required)
* deep-translator (optional, for auto-fill translation feature)

### Install Dependencies

```bash
# Required
pip install PySide6

# Optional - for auto-fill translation
pip install deep-translator
```

## Running the Application

```bash
python flashcard_app.py
```

## Features

* **Create flashcards** with lesson numbers, front text, and back text
* **Print double-sided flashcards** on standard letter-size paper
* **Auto-fill translation** (if deep-translator is installed)
* **Import/Export** flashcards via CSV
* **Track printing** - see which cards have been printed and when
* **Customizable settings** - cards per page, orientation, font size, pen color/width

## How to Use

### Adding Flashcards

1. **Enter lesson number** in the "Lesson" field
2. **Type front text** in the "Front text" field
3. **Press Tab** to move to the "Back text" field

   * If Auto-Fill is enabled, this will automatically translate the front text

4. **Type back text** (or accept the auto-filled translation)
5. **Press Enter** or click "Add Flashcard"

   * The lesson number persists for easy batch entry
   * Focus returns to the Front text field
   * You can keep adding cards without re-typing the lesson number

### Auto-Fill Feature

The Auto-Fill feature can automatically translate front text to the back text:

1. Open **Options** (Options button)
2. Select a language from the **Auto-Fill Language** dropdown
3. When you type text in the Front field and press Tab, it will automatically translate to the selected language in the Back field
4. You can still edit the auto-filled text before adding the flashcard

**Note:** Requires the `deep-translator` package to be installed.

### Managing Flashcards

* **Search**: Type in the search box to filter by lesson, front text, or back text
* **Filter**: Use the dropdown to show "All" or "Selected Only"
* **Select All**: Select all flashcards in the current view
* **Unselect All**: Deselect all flashcards
* **Select Unprinted**: Automatically select all cards that haven't been printed yet
* **Delete Selected**: Delete all currently selected flashcards (with confirmation)
* **Print checkbox**: Check/uncheck individual cards for printing
* **Copies**: Change the number in the "Copies" column to print multiple copies of a card
* **Delete button**: Delete individual flashcards (with confirmation)

### Printing Flashcards

#### Important Printer Settings

**CRITICAL:** When you print, you must configure your printer with these settings:

1. **Enable Duplex Printing** (double-sided printing)
2. **Flip on the correct edge**:

   * **Portrait orientation**: Flip on **long edge**
   * **Landscape orientation**: Flip on **short edge**

If you don't set this correctly, the backs won't align with the fronts!

#### Printing Steps

1. **Select flashcards** - Check the boxes in the "Print" column for cards you want to print
2. **Click "Print Selected"**
3. **Preview your cards** in the print preview dialog
4. **Click the Print button** - this will open a dialog to save the output as a PDF file

   * You'll need to then open the PDF file and actually print that
   * Make sure to set duplex printing and flipping correctly
   * The extra steps of exporting as PDF and then actually printing that file is necessary to get the alignment to print correctly



### Customizing Settings

Click the **Options** button to access:

* **Cards per Page**: How many cards to print per sheet (1-12, needs to be an even number)
* **Orientation**: Portrait (tall) or Landscape (wide)
* **Font Size**: Size of text on cards
* **Auto-Fill Language**: Language for automatic translation
* **Pen Color**: Color of the card borders
* **Pen Width**: Thickness of the card borders

Settings are automatically saved to `flashcard\_settings.json`.

### Importing/Exporting CSV

#### Export

1. Click **Options** button
2. Click **Export CSV**
3. Choose a filename
4. All flashcards will be exported

#### Import

1. Click **Options** button
2. Click **Import CSV**
3. Select your CSV file
4. Cards will be added to the database

**CSV Format:**

```csv
lesson,front,back,copies,printed_count,last_printed
1,Hello,Hola,1,0,
2,Goodbye,Adiós,1,0,
```

Only `lesson`, `front`, and `back` are required for import. Other fields are optional.

### Column Widths

* **Resize columns** by dragging the column headers
* **Widths are saved automatically** to your settings file
* **Widths persist** between sessions

## Files Created

* `flashcards.db` - SQLite database containing all your flashcards
* `flashcard_settings.json` - Your preferences and column widths

## Tips

* The "Select Unprinted" button is great for printing only new cards
* You can edit the Copies column to print multiple copies at once
* The search function searches across lesson, front, and back text
* Back up your `flashcards.db` file periodically to save your work, **OR** export the flashcards as a CSV file for backup

## Troubleshooting

**Auto-Fill doesn't work:**

* Make sure you've installed `deep-translator`: `pip install deep-translator`
* Check your internet connection (translation requires online access)

**Printed backs don't align with fronts:**

* Ensure duplex printing is enabled
* Check that you're flipping on the correct edge (long edge for Portrait, short edge for Landscape)
* Some printers may need calibration

**Database issues:**

* The database file is `flashcards.db` in the same folder as the script
* If corrupted, delete `flashcards.db` and restart the app (you'll lose your data!)
* Export to CSV regularly as a backup

## License

This software is provided as-is for personal and educational use.

