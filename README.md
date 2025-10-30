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
   - `ESC` - Finish and save snapshot
   - `Q` - Quit without saving

4. **Collection Process**:
   - Press `SPACE` to start
   - Navigate through each category in the left menu
   - The system will automatically detect which category you're viewing
   - Scroll slowly through items in each category
   - Wait for the white **flash** after each screen to confirm capture
   - Watch for visual feedback:
     - 🟢 **Green borders** = New items captured
     - 🟠 **Orange borders** = Already captured (duplicates)
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
- Sights and Magazines have the most items
- You can pause (`SPACE`) and resume anytime

### Accuracy
- Pause briefly on each screen before scrolling
- Let items fully load before the flash
- Orange borders mean you've already captured those items - safe to scroll past

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
│   ├── main.py                # Main collector script
│   ├── utils.py               # Utilities (config, OCR, computer vision)
│   └── config.yaml            # Collector settings
├── trading_app/               # GUI application
│   ├── main.py                # GUI interface
│   ├── utils.py               # Data processing utilities
│   └── config.yaml            # App settings
├── mappings/                  # Item name mappings
│   ├── ocr_mappings.json      # OCR name → Display name
│   └── display_mappings.json  # ItemKey → Friendly name
├── scripts/                   # Launcher scripts
│   ├── capture_market_data.bat  # Windows launcher for collector
│   └── view_market_data.bat     # Windows launcher for GUI
├── snapshots/                 # Market data snapshots
│   └── .gitkeep
├── requirements.txt           # Python dependencies
└── README.md                  # This file
```

## How It Works

### Computer Vision Pipeline

1. **Window Capture** - Screenshots game window at 2-second intervals
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
      {"itemName": "SH12 Military Helmet", "price": 43400},
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

The Trading App loads ALL snapshots automatically for historical analysis.

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

The system uses a three-tier naming approach for maximum flexibility:

1. **OCR Name** (raw capture): What the OCR reads from the card
2. **Display Name** (normalized): Clean version for deduplication and tracking
3. **Friendly Name** (full name): Complete item name shown in the GUI

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

Maps itemKeys to full friendly names for GUI display. Edit `mappings/display_mappings.json` manually:

```json
{
  "Helmet:SH40 Tactical...": "SH40 Tactical Helmet",
  "Body Armor:SH40 Tactical...": "SH40 Tactical Armor",
  "Helmet:Aviator Helmet": "Aviator Flight Helmet"
}
```

**Key format**: `"Category:DisplayName": "Full Friendly Name"`

This is purely cosmetic - backend tracking still uses the itemKey.

### Benefits

- **Cleaner Snapshots**: No duplicate items from OCR errors
- **Handles Truncated Names**: Items with "..." ellipsis are correctly separated by category
- **Better Historical Analysis**: Items are tracked consistently across snapshots by category + name
- **Accurate Trending**: Price history isn't split between OCR variations or confused across categories
- **Smart Visual Feedback**: Green borders only for truly new items in current category
- **Correct GUI Charts**: Trading app properly trends items by category, preventing false price swings
- **User-Friendly Display**: GUI shows full item names while backend uses efficient keys for tracking

## Troubleshooting

### Window Not Found
- Ensure game is in windowed mode (not fullscreen)
- Position window in upper-left corner
- Check window title matches: "Arena Breakout Infinite"

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
- Watch for white flash confirming capture
- Orange borders show already-captured items
- Adjust `navigation.scroll_pause` in config if needed

### Items Captured Multiple Times
- Orange borders indicate duplicates - these are handled automatically
- Only unique items are saved to the snapshot

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
