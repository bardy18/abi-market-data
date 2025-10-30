# ABI Market Data Collection Guide

## Quick Start

### Running a Market Scan

1. **Setup Game**:
   - Launch Arena Breakout: Infinite
   - Set to **Windowed mode** at **1600x900** resolution
   - Position the window in the **upper-left corner** of your screen
   - Navigate to the **Market** screen

2. **Start Collection**:
   - Double-click `capture_market.bat`
   - Or run: `python collector/continuous_capture.py`

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
   - Watch for borders:
     - **Green borders** = New items captured
     - **Orange borders** = Already captured (duplicates)
     - **Magenta box** = Category being detected
   - Press `ESC` when you've captured all categories

5. **What Gets Saved**:
   - Snapshot file: `snapshots/YYYY-MM-DD_HH-MM.json`
   - All items grouped by category
   - Prices at time of capture

## Recommended Schedule

For best market tracking:

- **Daily**: Capture once per day (same time each day)
- **Weekly**: Capture 2-3 times per week
- **Event-based**: After major game updates or events

More frequent captures = better trend analysis!

## Tips for Best Results

### Speed
- Each full marketplace scan takes **5-10 minutes**
- Sights and Magazines have the most items
- You can pause (SPACE) and resume anytime

### Accuracy
- Pause briefly on each screen before scrolling
- Let items fully load before the flash
- Orange borders mean you've already captured those items - safe to scroll past

### Coverage
- Always scan in the same order for consistency
- Complete categories:
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
- Open Trading App to view your data: `view_market_data.bat`

## Viewing Your Data

Run the Trading App:
```bash
view_market_data.bat
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

## Troubleshooting

### Window Not Found
- Make sure game is in windowed mode (not fullscreen)
- Position window in upper-left corner
- Check window title matches: "Arena Breakout Infinite"

### Category Shows "Unknown"
- The magenta box should highlight the selected menu item
- Make sure you've clicked on a category in the left menu
- The orange highlight must be visible

### Missing Items
- Scroll slower and pause on each screen
- Watch for the white flash confirming capture
- Orange borders show already-captured items

### Items Captured Multiple Times
- Orange borders indicate duplicates - these are handled automatically
- Only unique items are saved to the snapshot

## Data Storage

All snapshots are saved to:
```
snapshots/
  2025-10-29_22-25.json  (388 items)
  2025-10-30_22-30.json  (next scan)
  ...
```

Each snapshot contains:
- Timestamp of capture
- Items grouped by category
- Item names and prices

The Trading App loads ALL snapshots automatically for historical analysis.

## What's Next?

After your first few snapshots, you'll be able to:
- Track price changes over time
- Identify market trends
- Find arbitrage opportunities
- Get alerts on price spikes/drops
- Calculate moving averages and volatility

Happy trading! 🚀

