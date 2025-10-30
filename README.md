# ABI Market Data Tracker

A computer vision-based market intelligence system for Arena Breakout: Infinite. Automatically captures and tracks marketplace prices across all categories using OCR and image processing.

## Features

- 🤖 **Automated Data Collection** - Computer vision captures items as you navigate
- 📊 **Real-time Visual Feedback** - See exactly what's being captured with on-screen borders
- 🎯 **Smart Category Detection** - Automatically identifies which category you're viewing
- 📈 **Historical Price Tracking** - Analyze trends across multiple snapshots
- 🖥️ **Interactive GUI** - Browse, search, and visualize market data
- 🔍 **OCR-Powered** - Reads item names and prices with high accuracy
- 💾 **JSON Export** - All data saved in structured, portable format

## Quick Start

### Installation

1. **Prerequisites**:
   - Python 3.11+
   - Tesseract OCR ([Download](https://github.com/UB-Mannheim/tesseract/wiki))
   - Arena Breakout: Infinite (1600x900 windowed mode)

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Tesseract** (if not in PATH):
   - Edit `collector/config.yaml`
   - Set `tesseract_path` to your Tesseract installation

### Collecting Market Data

1. **Setup Game**:
   - Launch Arena Breakout: Infinite
   - Set to **Windowed mode** at **1600x900** resolution
   - Position the window in the **upper-left corner** of your screen
   - Navigate to the **Market** screen

2. **Start Collection**:
   ```bash
   scripts\capture_market_data.bat
   ```
   Or:
   ```bash
   python collector/main.py
   ```

3. **Controls**:
   - `SPACE` - Start/pause capturing
   - Click preview window - Capture current screen
   - `ESC` - Finish and save snapshot
   - `Q` - Quit without saving

4. **Collection Process**:
   - Press `SPACE` to start
   - **Keep your mouse in the game window** - click and navigate freely
   - Click the preview window to capture each screen
   - The system will automatically detect which category you're viewing
   - Scroll slowly through items in each category
   - Watch for visual feedback in the preview window:
     - 🟢 **Green borders** = New items captured
     - 🔵 **Light blue borders** = Already captured (duplicates)
     - 🔷 **Cyan thin borders** = Detected card positions (not all may be fully visible)
     - 🟣 **Magenta box** = Category being detected
   - Press `ESC` when you've captured all categories

5. **What Gets Saved**:
   - Snapshot file: `snapshots/YYYY-MM-DD_HH-MM.json`
   - All items grouped by category
   - Prices at time of capture

### Viewing Your Data

Launch the trading app:
```bash
scripts\view_market_data.bat
```
Or:
```bash
python trading_app/main.py
```

The GUI lets you:
- Browse all captured items
- Search/filter by category or name
- View price history (with multiple snapshots)
- Track trends and volatility

## Recommended Scanning Schedule

For best market tracking:

- **Daily**: Capture once per day (same time each day)
- **Weekly**: Capture 2-3 times per week
- **Event-based**: After major game updates or events

More frequent captures = better trend analysis!

## Tips for Best Results

### Speed
- Each full marketplace scan takes **5-10 minutes**
- Processing time is shown after each capture (typically 1-3 seconds)
- Watch the processing time to gauge your capture rhythm
- You can pause (`SPACE`) and resume anytime
- Sights and Magazines have the most items

### Accuracy
- Click the preview window when items are fully loaded and visible
- A "PROCESSING..." overlay appears immediately when you click
- Watch for green borders on newly captured items
- Light blue borders mean you've already captured those items - safe to scroll past
- Processing time displayed shows OCR was completed

### Coverage
- Always scan in the same order for consistency
- Complete categories (typical item counts):
  - Helmet (~40 items)
  - Mask (~11 items)
  - Body Armor (~30 items)
  - Unarmored Chest Rigs (~17 items)
  - Armored Rig (~17 items)
  - Backpack (~20 items)
  - Headset (~5 items)
  - Gas Mask (~9 items)
  - Sights (~100 items)
  - Magazine (~150 items)

### After Collection
- Review the summary showing items per category
- Check `snapshots/` folder for your new snapshot
- Open Trading App to analyze your data

## Project Structure

```
ABIMarketData/
├── collector/                 # Data collection module
│   ├── main.py                  # Main collector script
│   ├── utils.py                 # Utilities (config, OCR, computer vision)
│   ├── cleanup_thumbs.py        # Thumbnail de-duplication/cleanup tool
│   └── config.yaml              # Collector settings
├── trading_app/               # GUI application
│   ├── main.py                # GUI interface
│   ├── utils.py               # Data processing utilities
│   └── config.yaml            # App settings
├── mappings/                  # Item name mappings
│   ├── ocr_mappings.json      # OCR name → Display name
│   └── display_mappings.json  # ItemKey → Friendly name
├── scripts/                     # Launcher scripts
│   ├── capture_market_data.bat  # Windows launcher for collector
│   ├── view_market_data.bat     # Windows launcher for GUI
│   └── cleanup_thumbs.bat       # Windows launcher for thumbnail cleanup
├── snapshots/                   # Market data snapshots
│   ├── YYYY-MM-DD_HH-MM.json    # Snapshot files
│   └── thumbs/                  # Thumbnail images used by the GUI
├── requirements.txt           # Python dependencies
└── README.md                  # This file
```

## How It Works

### Computer Vision Pipeline

1. **Window Capture** - User-triggered capture via preview click (live preview shown)
2. **Category Detection** - Identifies orange-highlighted menu item via HSV color detection
3. **Grid Detection** - Finds item cards using contour detection
4. **Visibility Filter** - Only captures fully visible items (name + price)
5. **OCR Extraction** - Reads item names and prices using Tesseract
6. **Deduplication** - Tracks unique items across scrolling
7. **JSON Export** - Saves organized snapshot with categories

### Data Format

Snapshots are saved as JSON in the `snapshots/` directory:

```json
{
  "timestamp": 1234567890,
  "categories": {
    "Helmet": [
      {"itemName": "SH12 Military Helmet", "price": 43400, "thumbHash": "01003c3c3c3c0000"},
      ...
    ],
    "Weapon": [...],
    ...
  }
}
```

Example directory structure:
```
snapshots/
  2025-10-29_22-25.json  (388 items)
  2025-10-30_22-30.json  (next scan)
  ...
```

The Trading App loads ALL snapshots automatically for historical analysis. Each item includes a `thumbHash`; the thumbnail image is saved at `snapshots/thumbs/<thumbHash>.png` and is displayed in the GUI.

## Configuration

### Collector Settings (`collector/config.yaml`)

- **Resolution**: 1600x900 (adjustable for other resolutions)
- **UI Regions**: Coordinates for navigation tree, item grid
- **Item Card**: Grid layout and internal structure
- **OCR Settings**: Tesseract path and preprocessing options
- **Navigation**: Delays and timing

### Trading App Settings (`trading_app/config.yaml`)

- **Max Snapshots**: Limit for loaded snapshots
- **Alerts**: Price change thresholds
- **Display**: UI preferences

## Item Name Mapping

The system uses a two-tier naming approach, plus an optional GUI display name:

1. **OCR Name** (raw capture): What the OCR reads from the card
2. **Clean Name** (normalized): Used for deduplication and tracking
3. **Display Name** (GUI-only): Optional label mapped by exact `itemKey` for presentation

Notes:
- The Trading App shows the Display Name if present; otherwise it shows the Clean Name.
- Display names are mapped in `mappings/display_mappings.json` or set via double-click in the GUI.
- Backend tracking and grouping always use the exact `itemKey` (category + clean name, with optional `#hash`).

### How It Works

1. **During Collection**: The collector checks `mappings/ocr_mappings.json` and uses display names as unique identifiers
2. **Category-Aware Deduplication**: Items are uniquely identified by **category + display name** combination
   - "SH40 Tactical..." in Helmet category is separate from "SH40 Tactical..." in Body Armor category
   - Handles truncated names that look identical but are different items
3. **Automatic Deduplication**: If OCR reads "Aviotor Helmet" after already capturing "Aviator Helmet" (same category), and both map to the same display name, only one item is kept
4. **Duplicate Detection**: After collection, the system alerts you to potential duplicates (similar names with same price in same category)

### OCR Mappings (`ocr_mappings.json`)

Maps OCR variations to clean display names for deduplication. Edit `mappings/ocr_mappings.json` manually:

Example:
```json
{
  "Aviotor Helmet": "Aviator Helmet",
  "Avjator Helmet": "Aviator Helmet"
}
```

### Display Mappings (`display_mappings.json`)

Maps exact `itemKey` values to GUI display labels (presentation only; tracking still uses the exact `itemKey`). Edit `mappings/display_mappings.json` manually:

```json
{
  "Helmet:SH40 Tactical...": "SH40 Tactical Helmet",
  "Body Armor:SH40 Tactical...": "SH40 Tactical Armor",
  "Helmet:Aviator Helmet": "Aviator Flight Helmet"
}
```

**Key format**: `"Category:CleanName[#hash]": "GUI display label"`

This is purely cosmetic - backend tracking still uses the exact `itemKey`.

### Benefits

- **Cleaner Snapshots**: No duplicate items from OCR errors
- **Handles Truncated Names**: Items with "..." ellipsis are correctly separated by category
- **Better Historical Analysis**: Items are tracked consistently across snapshots by category + name
- **Accurate Trending**: Price history isn't split between OCR variations or confused across categories
- **Smart Visual Feedback**: Green borders only for truly new items in current category
- **Correct GUI Charts**: Trading app properly trends items by category, preventing false price swings
- **User-Friendly Display**: GUI shows full item names while backend uses efficient keys for tracking

## Troubleshooting

### Screenshot Issues
- Ensure game is in windowed mode (not fullscreen)
- Position window in upper-left corner of your screen
- Game resolution must be 1600x900

### Category Shows "Unknown"
- The magenta box should highlight the selected menu item
- Make sure you've clicked on a category in the left menu
- The orange highlight must be visible

### Poor OCR Accuracy
- Verify Tesseract is installed and in PATH
- Check game resolution is 1600x900
- Ensure UI is not scaled/zoomed

### Missing Items
- Scroll slower and pause on each screen
- Watch for green borders confirming new item capture
- Light blue borders show already-captured items
- Cyan thin borders mean the card was detected but may not be fully visible yet - pause before scrolling

### Items Captured Multiple Times
- Light blue borders indicate duplicates - these are handled automatically
- Only unique items are saved to the snapshot

## Maintenance

### Clean up thumbnails

Over time, the `snapshots/thumbs/` folder can accumulate near-duplicate thumbnails. Use the cleanup tool to de-duplicate and prune similar images.

Run via script (recommended):
```
scripts\cleanup_thumbs.bat
```

Or directly:
```
python collector/cleanup_thumbs.py --apply --threshold 8 --snapshots snapshots
```

Notes:
- Lower `--threshold` is stricter (fewer images considered duplicates). Default is 8.
- Without `--apply`, the tool performs a dry run.

## What's Next?

After your first few snapshots, you'll be able to:
- Track price changes over time
- Identify market trends
- Find arbitrage opportunities
- Get alerts on price spikes/drops
- Calculate moving averages and volatility

Happy trading! 🚀

## Contributing

Contributions welcome! Areas for improvement:
- Support for other game resolutions
- Additional trading metrics
- Enhanced UI features
- OCR accuracy improvements

## License

MIT License - see LICENSE file for details

## Acknowledgments

Built with:
- [PySide6](https://www.qt.io/qt-for-python) - GUI framework
- [OpenCV](https://opencv.org/) - Computer vision
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) - Text recognition
- [Pandas](https://pandas.pydata.org/) - Data analysis
- [Matplotlib](https://matplotlib.org/) - Visualization

## Disclaimer

This tool is for educational and personal use only. Use responsibly and in accordance with Arena Breakout: Infinite's terms of service.