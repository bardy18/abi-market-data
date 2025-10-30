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

### Usage

#### Collecting Market Data

1. Launch Arena Breakout: Infinite
2. Set to windowed mode (1600x900)
3. Position window in upper-left corner
4. Navigate to Market screen
5. Run collector:
   ```bash
   capture_market.bat
   ```
   Or:
   ```bash
   python collector/continuous_capture.py
   ```

6. **Controls**:
   - `SPACE` - Start/pause capture
   - `ESC` - Save and finish
   - `Q` - Quit without saving

7. **Navigate** through categories and scroll through items
8. Watch for visual feedback:
   - 🟢 **Green borders** = New items captured
   - 🟠 **Orange borders** = Already captured
   - 🟣 **Magenta box** = Current category detected

#### Viewing Data

Launch the trading app:
```bash
view_market_data.bat
```
Or:
```bash
python trading_app/main.py
```

Browse all captured items, search by category or name, and view price trends.

## Project Structure

```
ABIMarketData/
├── collector/                 # Data collection module
│   ├── continuous_capture.py  # Main collector script
│   ├── vision_utils.py        # Computer vision & OCR
│   ├── utils.py               # Helper functions
│   └── config.yaml            # Collector settings
├── trading_app/               # GUI application
│   ├── main.py                # GUI interface
│   ├── utils.py               # Data processing
│   └── config.yaml            # App settings
├── snapshots/                 # Market data snapshots
│   └── .gitkeep
├── map_items.py               # Item name mapping utility
├── capture_market.bat         # Windows launcher for collector
├── view_market_data.bat       # Windows launcher for GUI
├── COLLECTION_GUIDE.md        # Detailed collection instructions
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

Snapshots are saved as JSON:
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

OCR may produce variations for the same item. Use the mapping tool to normalize names:

```bash
python map_items.py
```

This creates/updates `item_names.json` for cleaner display names in the GUI.

## Tips for Best Results

### Collection
- **Consistency**: Scan at the same time each day/week
- **Completeness**: Capture all categories in each scan
- **Patience**: Pause briefly on each screen for the flash
- **Navigation**: Orange borders show already-captured items

### Analysis
- **Multiple Snapshots**: Need 3+ snapshots for trend analysis
- **Regular Intervals**: Daily/weekly scans reveal patterns
- **Category Focus**: Track specific categories for targeted trading

## Troubleshooting

### "Window Not Found"
- Ensure game is in windowed mode (not fullscreen)
- Position window in upper-left corner
- Check window title matches config

### Poor OCR Accuracy
- Verify Tesseract is installed and in PATH
- Check game resolution is 1600x900
- Ensure UI is not scaled/zoomed

### Missing Items
- Scroll slower to give time for capture
- Watch for white flash confirming capture
- Adjust `navigation.scroll_pause` in config

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
