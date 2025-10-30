#!/usr/bin/env python3
"""
Continuous capture mode - takes screenshots while user navigates.
Press SPACE to start/stop, ESC to finish and save.
"""
import cv2
import sys
import os
import time
import json
import pygetwindow as gw
import pyautogui
import numpy as np
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from collector.utils import load_config
from collector.vision_utils import detect_card_positions, extract_item_from_card, detect_selected_category
from trading_app.utils import load_item_name_mapping, get_display_name
from difflib import SequenceMatcher


def focus_window(title: str):
    """Find and focus a window by title"""
    try:
        windows = gw.getWindowsWithTitle(title)
        if windows:
            window = windows[0]
            window.activate()
            time.sleep(0.3)
            return window
    except Exception as e:
        print(f"Warning: Could not focus window: {e}")
    return None


def make_snapshot_filename(base_dir: str, category: str = "Mixed") -> str:
    """Generate snapshot filename with timestamp"""
    timestamp_str = datetime.now().strftime('%Y-%m-%d_%H-%M')
    return os.path.join(base_dir, f"{timestamp_str}.json")

# Visual feedback overlay
def flash_screen(screenshot, duration=0.15):
    """Show a white flash overlay to indicate capture"""
    overlay = screenshot.copy()
    # Add white semi-transparent overlay
    white = (255, 255, 255)
    cv2.rectangle(overlay, (0, 0), (overlay.shape[1], overlay.shape[0]), white, -1)
    alpha = 0.3
    flashed = cv2.addWeighted(overlay, alpha, screenshot, 1 - alpha, 0)
    
    # Show the flash
    cv2.imshow('ABI Market Capture', flashed)
    cv2.waitKey(int(duration * 1000))
    
    # Show original
    cv2.imshow('ABI Market Capture', screenshot)
    cv2.waitKey(1)


def is_card_fully_visible(card_image, card_config):
    """
    Check if a card has enough visible to extract name and price.
    Requires name region at top AND at least the start of price region at bottom.
    """
    h, w = card_image.shape[:2]
    
    name_height = card_config['name_region_height']
    price_top = card_config['price_top']
    
    # Must have reasonable width
    if w < card_config['card_width'] * 0.8:
        return False
    
    # Require enough height for full name and most of price region
    price_height = card_config['price_height']
    min_price_visible = price_height * 0.7  # At least 70% of price must be visible
    min_required_height = price_top + min_price_visible
    if h < min_required_height:
        return False
    
    # Check name region has content (not all black/empty)
    if name_height >= h:
        return False
    name_region = card_image[0:name_height, :]
    if name_region.shape[0] == 0 or name_region.shape[1] == 0:
        return False
    name_gray = cv2.cvtColor(name_region, cv2.COLOR_BGR2GRAY) if len(name_region.shape) == 3 else name_region
    name_content = cv2.mean(name_gray)[0]
    
    # Check price region has sufficient content
    price_region = card_image[price_top:h, :]
    available_price_height = price_region.shape[0]
    if available_price_height < min_price_visible or price_region.shape[1] == 0:
        return False  # Need at least 70% of price visible
    price_gray = cv2.cvtColor(price_region, cv2.COLOR_BGR2GRAY) if len(price_region.shape) == 3 else price_region
    price_content = cv2.mean(price_gray)[0]
    
    # Both regions should have some content (very lenient threshold)
    return name_content > 5 and price_content > 5


def continuous_capture():
    """Main continuous capture loop"""
    print("\n" + "="*60)
    print("CONTINUOUS CAPTURE MODE")
    print("="*60)
    print("\nControls:")
    print("  SPACE - Start/Pause capture")
    print("  ESC   - Finish and save snapshot")
    print("  Q     - Quit without saving")
    print("\nInstructions:")
    print("  1. Start capture with SPACE")
    print("  2. Navigate categories and scroll at your own pace")
    print("  3. Screen will flash white when items are captured")
    print("  4. Pause briefly on each screen so items are fully visible")
    print("  5. Press ESC when done to save all captured items")
    print("\n" + "="*60)
    print("\nStarting in 3 seconds...")
    time.sleep(3)
    
    # Load config
    config = load_config('collector/config.yaml')
    
    # Load item name mapping for deduplication by display name
    print("Loading item name mappings...")
    load_item_name_mapping()  # Pre-load the mapping cache
    
    # Set tesseract path
    if config.tesseract_path:
        import pytesseract
        pytesseract.pytesseract.tesseract_cmd = config.tesseract_path
    
    # Try to focus window (optional - continues even if it fails)
    print("\nLooking for game window...")
    window = focus_window(config.window_title)
    if window:
        print(f"[OK] Found window: {window.title}")
    else:
        print(f"[!] Could not focus window, but continuing anyway...")
        print("    Make sure game is visible and in upper-left corner")
    time.sleep(1.0)
    
    # Initialize collection
    # Use category+display name as key for deduplication (handles truncated names)
    collected_items = {}  # "category:displayName" -> {ocrName, price, category}
    capturing = False
    capture_count = 0
    
    print("\n" + "="*60)
    print("READY! Press SPACE to start capturing...")
    print("="*60 + "\n")
    
    # Create preview window
    cv2.namedWindow('ABI Market Capture', cv2.WINDOW_NORMAL)
    cv2.resizeWindow('ABI Market Capture', 800, 450)
    
    # Show initial status
    init_screen = np.zeros((450, 800, 3), dtype=np.uint8)
    cv2.putText(init_screen, "Press SPACE to start", 
               (200, 180), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
    cv2.putText(init_screen, "Press C to capture each screen", 
               (160, 230), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
    cv2.putText(init_screen, "ESC to finish and save", 
               (220, 270), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.putText(init_screen, "Q to quit without saving", 
               (210, 310), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.imshow('ABI Market Capture', init_screen)
    
    try:
        # For manual capture control
        should_capture = False
        last_screenshot = None
        # Keep track of detected elements from last capture for persistent display
        last_detected_cards = []  # List of (x, y, w, h, is_new) from last capture
        last_card_positions = []  # All card positions (cyan borders)
        last_category_bbox = None  # Category bbox for magenta border
        last_current_category = ""  # Category name
        last_capture_time = 0  # Time when last capture was made
        border_display_duration = 3.0  # Show borders for 3 seconds after capture
        
        while True:
            # Check keyboard
            key = cv2.waitKey(30) & 0xFF  # ~33 FPS for responsive preview
            
            if key == ord('q'):
                print("\n[!] Cancelled by user")
                break
            elif key == ord(' '):
                capturing = not capturing
                if capturing:
                    print("\n[OK] READY - Press C to capture each screen")
                    print("     Navigate and scroll at your own pace")
                else:
                    print("\n[||] PAUSED - Press SPACE to resume")
            elif key == 27:  # ESC
                print("\n[OK] Finishing capture...")
                break
            elif key == ord('c'):  # C key to capture
                if capturing:
                    should_capture = True
            
            # Always take screenshot for preview
            try:
                # Capture only the game window area (upper-left corner at expected resolution)
                screenshot = pyautogui.screenshot(region=(0, 0, config.resolution[0], config.resolution[1]))
                screenshot = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
                last_screenshot = screenshot.copy()
            except Exception as e:
                print(f"[!] Screenshot failed: {e}")
                time.sleep(0.1)
                continue
            
            # If not capturing, just show preview
            if not capturing:
                display = cv2.resize(screenshot, (800, 450))
                cv2.putText(display, "PAUSED - Press SPACE to start", 
                           (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                cv2.imshow('ABI Market Capture', display)
                continue
            
            # If capturing mode but no capture triggered, show live preview with time-limited borders
            if not should_capture:
                preview = screenshot.copy()
                
                # Draw all borders from last capture if still within display duration
                elapsed = time.time() - last_capture_time
                if elapsed < border_display_duration:
                    grid_cfg = config.ui_regions['item_grid']
                    roi_x = grid_cfg['x']
                    roi_y = grid_cfg['y']
                    
                    # Draw cyan borders for all detected card positions
                    for (x, y, w, h) in last_card_positions:
                        screen_x = roi_x + x
                        screen_y = roi_y + y
                        cv2.rectangle(preview, (screen_x, screen_y), (screen_x + w, screen_y + h), (255, 255, 0), 1)
                    
                    # Draw green/orange borders for successfully read cards
                    for (x, y, w, h, is_new) in last_detected_cards:
                        screen_x = roi_x + x
                        screen_y = roi_y + y
                        color = (0, 255, 0) if is_new else (255, 165, 0)
                        thickness = 3 if is_new else 2
                        cv2.rectangle(preview, (screen_x, screen_y), (screen_x + w, screen_y + h), color, thickness)
                    
                    # Draw magenta category box
                    if last_category_bbox:
                        tree_cfg = config.ui_regions['tree_navigation']
                        cat_x, cat_y, cat_w, cat_h = last_category_bbox
                        screen_cat_x = tree_cfg['x'] + cat_x
                        screen_cat_y = tree_cfg['y'] + cat_y
                        cv2.rectangle(preview, 
                                    (screen_cat_x, screen_cat_y), 
                                    (screen_cat_x + cat_w, screen_cat_y + cat_h), 
                                    (255, 0, 255), 2)
                        cv2.putText(preview, f"Category: {last_current_category}", 
                                   (screen_cat_x, screen_cat_y - 5), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 255), 2)
                
                display = cv2.resize(preview, (800, 450))
                cv2.putText(display, "READY - Press C to capture", 
                           (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                cv2.putText(display, f"Items: {len(collected_items)}", 
                           (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                cv2.imshow('ABI Market Capture', display)
                continue
            
            # Reset capture flag
            should_capture = False
            
            # Detect the currently selected category from the left menu
            tree_cfg = config.ui_regions['tree_navigation']
            tree_region = screenshot[tree_cfg['y']:tree_cfg['y'] + tree_cfg['height'],
                                    tree_cfg['x']:tree_cfg['x'] + tree_cfg['width']]
            current_category, category_bbox = detect_selected_category(tree_region, config.tesseract_path)
            
            # Use grid region just to know where to look for cards
            grid_cfg = config.ui_regions['item_grid']
            
            # Create a region of interest - use the grid area but expand vertically to catch bottom cards
            roi_x = grid_cfg['x']
            roi_y = grid_cfg['y']
            roi_w = grid_cfg['width']
            roi_h = screenshot.shape[0] - roi_y  # Go all the way to bottom of screenshot
            
            # Extract ROI from full screenshot
            grid_region = screenshot[roi_y:roi_y + roi_h, roi_x:roi_x + roi_w]
            
            # Detect actual card positions dynamically (works with scrolling)
            card_positions = detect_card_positions(grid_region, config.item_card)
            
            # Extract items from visible cards
            new_items_this_capture = 0
            detected_cards = []  # Track which cards were successfully read
            
            cards_checked = 0
            cards_visible = 0
            cards_with_data = 0
            
            for (x, y, w, h) in card_positions:
                # detect_card_positions returns relative positions (0,0 = top-left of ROI)
                card_x = x
                card_y = y
                
                # Extract card from ROI (no bounds checking - take whatever the contour found)
                card_image = grid_region[card_y:card_y+h, card_x:card_x+w]
                cards_checked += 1
                
                # Check if fully visible
                is_visible = is_card_fully_visible(card_image, config.item_card)
                if is_visible:
                    cards_visible += 1
                
                # Extract item data
                item_data = None
                if is_visible:
                    item_data = extract_item_from_card(card_image, config.item_card)
                    if item_data:
                        cards_with_data += 1
                
                if item_data:
                    ocr_name = item_data['itemName']
                    display_name = get_display_name(ocr_name)  # Map to clean name
                    
                    # Create category-aware key to handle truncated names
                    # (e.g., "SH40 Tactical..." could be helmet or armor)
                    item_key = f"{current_category}:{display_name}"
                    
                    # Track this card for visual feedback (check by category+display name)
                    is_new = item_key not in collected_items
                    detected_cards.append((x, y, w, h, is_new))
                    
                    # Add or update item (category:display_name is the unique key)
                    if is_new:
                        collected_items[item_key] = {
                            'ocrName': ocr_name,  # Store original OCR for reference
                            'price': item_data['price'],
                            'category': current_category  # Use detected category from orange menu item
                        }
                        new_items_this_capture += 1
                        # Show both names if different
                        if ocr_name != display_name:
                            print(f"  [{current_category}] {display_name} (OCR: {ocr_name}) - ${item_data['price']:,}")
                        else:
                            print(f"  [{current_category}] {display_name} - ${item_data['price']:,}")
            
            # Optional: Uncomment to debug OCR success rate
            # print(f"[DEBUG] Detected: {len(card_positions)}, Checked: {cards_checked}, Visible: {cards_visible}, With data: {cards_with_data}")
            
            if new_items_this_capture > 0:
                capture_count += 1
                print(f"\n[{capture_count}] Captured {new_items_this_capture} new items (Total: {len(collected_items)})")
            
            # Draw borders around ALL detected card positions (not just those with data)
            screenshot_with_borders = screenshot.copy()
            
            # Draw borders for all detected positions (cyan for detected but no data)
            for (x, y, w, h) in card_positions:
                screen_x = roi_x + x
                screen_y = roi_y + y
                cv2.rectangle(screenshot_with_borders, (screen_x, screen_y), (screen_x + w, screen_y + h), (255, 255, 0), 1)  # Cyan thin border
            
            # Draw thicker borders for cards that were successfully read
            for (x, y, w, h, is_new) in detected_cards:
                # Green border for new items, orange for already captured
                color = (0, 255, 0) if is_new else (255, 165, 0)  # Green or Orange
                thickness = 3 if is_new else 2
                # Convert ROI-relative coords to screen coords
                screen_x = roi_x + x
                screen_y = roi_y + y
                cv2.rectangle(screenshot_with_borders, (screen_x, screen_y), (screen_x + w, screen_y + h), color, thickness)
            
            # Draw bounding box for the category OCR region (in magenta/purple)
            if category_bbox:
                cat_x, cat_y, cat_w, cat_h = category_bbox
                # Convert tree-region-relative coords to screen coords
                screen_cat_x = tree_cfg['x'] + cat_x
                screen_cat_y = tree_cfg['y'] + cat_y
                cv2.rectangle(screenshot_with_borders, 
                            (screen_cat_x, screen_cat_y), 
                            (screen_cat_x + cat_w, screen_cat_y + cat_h), 
                            (255, 0, 255), 2)  # Magenta border
                # Add label above the box
                cv2.putText(screenshot_with_borders, f"Category: {current_category}", 
                           (screen_cat_x, screen_cat_y - 5), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 255), 2)
            
            # Flash if new items detected
            if new_items_this_capture > 0:
                flash_screen(screenshot_with_borders)
            
            # Show current screenshot with borders
            display = cv2.resize(screenshot_with_borders, (800, 450))
            status = "CAPTURING" if capturing else "PAUSED"
            status_color = (0, 255, 0) if capturing else (0, 165, 255)
            cv2.putText(display, f"{status} | Items: {len(collected_items)} | This view: {len(detected_cards)}", 
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, status_color, 2)
            cv2.imshow('ABI Market Capture', display)
            
            # Save all border information and timestamp for time-limited display
            last_detected_cards = detected_cards.copy()
            last_card_positions = card_positions.copy()
            last_category_bbox = category_bbox
            last_current_category = current_category
            last_capture_time = time.time()
    
    except KeyboardInterrupt:
        print("\n[!] Interrupted by user")
    
    finally:
        cv2.destroyAllWindows()
    
    # Save results
    if collected_items:
        print("\n" + "="*60)
        print(f"CAPTURE COMPLETE - {len(collected_items)} unique items")
        print("="*60)
        
        # Group items by category
        # Use OCR names in snapshot for consistency with existing format
        categories = {}
        for item_key, data in collected_items.items():
            # item_key format: "category:displayName"
            category = data['category']
            if category not in categories:
                categories[category] = []
            # Store OCR name in snapshot (raw captured data)
            categories[category].append({'itemName': data['ocrName'], 'price': data['price']})
        
        # Create snapshot
        snapshot = {
            'timestamp': int(time.time()),
            'categories': categories
        }
        
        # Save (use current timestamp for filename)
        snapshot_filename = time.strftime('%Y-%m-%d_%H-%M.json')
        snapshot_path = os.path.join(config.snapshots_path, snapshot_filename)
        os.makedirs(config.snapshots_path, exist_ok=True)
        with open(snapshot_path, 'w', encoding='utf-8') as f:
            json.dump(snapshot, f, indent=2, ensure_ascii=False)
        
        print(f"\n[OK] Saved: {snapshot_path}")
        print(f"[OK] Total items: {len(collected_items)}")
        print(f"\nItems by category:")
        for category, items in sorted(categories.items()):
            print(f"  {category}: {len(items)} items")
        print("\nTop 10 items by price:")
        sorted_items = sorted(collected_items.items(), key=lambda x: x[1]['price'], reverse=True)
        for item_key, data in sorted_items[:10]:
            # item_key format: "category:displayName" - extract display name for output
            display_name = item_key.split(':', 1)[1] if ':' in item_key else item_key
            print(f"  ${data['price']:>8,} - [{data['category']}] {display_name}")
        
        # Check for potential OCR duplicates (similar names with same price in same category)
        # This helps identify items that should be mapped together
        potential_duplicates = []
        items_list = list(collected_items.items())
        for i, (key1, data1) in enumerate(items_list):
            for key2, data2 in items_list[i+1:]:
                # Same price and similar names (80%+ similarity) in same category
                if data1['price'] == data2['price'] and data1['category'] == data2['category']:
                    similarity = SequenceMatcher(None, data1['ocrName'].lower(), data2['ocrName'].lower()).ratio()
                    if similarity >= 0.8:
                        disp1 = key1.split(':', 1)[1] if ':' in key1 else key1
                        disp2 = key2.split(':', 1)[1] if ':' in key2 else key2
                        potential_duplicates.append((disp1, disp2, data1['ocrName'], data2['ocrName'], data1['price'], data1['category']))
        
        if potential_duplicates:
            print("\n" + "="*60)
            print("POTENTIAL OCR DUPLICATES DETECTED")
            print("="*60)
            print("These items have the same price and similar names in the same category.")
            print("Consider adding mappings to: mappings/ocr_mappings.json\n")
            for disp1, disp2, ocr1, ocr2, price, category in potential_duplicates:
                print(f"  [{category}] ${price:,} - '{ocr1}' vs '{ocr2}'")
                print(f"           (Display: '{disp1}' vs '{disp2}')")
            print("="*60)
    else:
        print("\n[!] No items captured")


if __name__ == '__main__':
    continuous_capture()

