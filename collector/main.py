#!/usr/bin/env python3
"""
Continuous capture mode - takes screenshots while user navigates.
Press SPACE to start/stop, ESC to finish and save.
Click the preview window to capture each screen.
"""
import cv2
import re
import sys
import os
import time
import json
import pyautogui
import numpy as np
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from collector.utils import (
    load_config,
    detect_card_positions,
    extract_item_from_card,
    detect_selected_category,
    load_ocr_mapping,
    get_clean_name,
    compute_thumbnail_hash,
    hamming_distance_hex,
    compute_color_signature,
    hue_bin_distance,
    are_images_similar,
)
from difflib import SequenceMatcher


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
    print("  2. Click and navigate in the game")
    print("  3. Click the preview window to capture each screen")
    print("  4. Watch the processing time to gauge your capture speed")
    print("  5. Watch for green borders on newly captured items")
    print("  6. Pause briefly on each screen so items are fully visible")
    print("  7. Press ESC when done to save all captured items")
    print("\n" + "="*60)
    
    # Load config (relative to this script's location)
    config_path = Path(__file__).parent / 'config.yaml'
    config = load_config(str(config_path))
    
    # Load OCR mapping for deduplication by display name
    print("Loading OCR mappings...")
    load_ocr_mapping()  # Pre-load the mapping cache
    
    # Set tesseract path
    if config.tesseract_path:
        import pytesseract
        pytesseract.pytesseract.tesseract_cmd = config.tesseract_path
    
    print("\nMake sure:")
    print("  - Game is in windowed mode (1600x900)")
    print("  - Game window is positioned in upper-left corner")
    print("  - You're on the Market screen")
    # No startup wait; begin responsive loop immediately
    
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
    
    # Show initial status (no startup delay)
    init_screen = np.zeros((450, 800, 3), dtype=np.uint8)
    cv2.putText(init_screen, "Press SPACE to start", 
               (200, 180), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
    cv2.putText(init_screen, "Click preview to capture each screen", 
               (160, 230), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
    cv2.putText(init_screen, "ESC to finish and save", 
               (220, 270), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.putText(init_screen, "Q to quit without saving", 
               (210, 310), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.imshow('ABI Market Capture', init_screen)
    
    # Mouse click on preview triggers capture; keyboard only used when window has focus
    print("\n[INFO] Click the preview window to capture (SPACE to start, ESC to finish)")
    mouse_capture_requested = False
    def _on_mouse(event, x, y, flags, param):
        nonlocal mouse_capture_requested
        if event == cv2.EVENT_LBUTTONDOWN:
            mouse_capture_requested = True

    cv2.setMouseCallback('ABI Market Capture', _on_mouse)
    
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
        border_display_duration = 1.5  # Show borders for ~1.5 seconds after capture
        
        while True:
            # Keyboard (window focus required)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                print("\n[!] Cancelled by user")
                break
            elif key == 27:  # ESC
                print("\n[OK] Finishing capture...")
                break
            elif key == ord(' '):
                capturing = not capturing
                if capturing:
                    print("\n[OK] READY - Click preview to capture each screen")
                    print("     Navigate and scroll at your own pace")
                else:
                    print("\n[||] PAUSED - Press SPACE to resume")

            # Mouse click capture
            if mouse_capture_requested and capturing:
                should_capture = True
                mouse_capture_requested = False
            
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
                    # Draw cyan borders for all detected card positions (absolute coords)
                    for (abs_x, abs_y, w, h) in last_card_positions:
                        cv2.rectangle(preview, (abs_x, abs_y), (abs_x + w, abs_y + h), (255, 255, 0), 1)
                    
                    # Draw green/light blue borders for successfully read cards (absolute coords)
                    for (abs_x, abs_y, w, h, is_new) in last_detected_cards:
                        color = (0, 255, 0) if is_new else (255, 165, 0)
                        thickness = 3 if is_new else 2
                        cv2.rectangle(preview, (abs_x, abs_y), (abs_x + w, abs_y + h), color, thickness)
                    
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
                cv2.putText(display, "READY - Click preview to capture", 
                           (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                cv2.putText(display, f"Items: {len(collected_items)}", 
                           (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                cv2.imshow('ABI Market Capture', display)
                continue
            
            # CAPTURE TRIGGERED - Process immediately!
            should_capture = False
            capture_start_time = time.time()  # Track processing time
            
            # Show immediate feedback that capture is processing
            processing_overlay = screenshot.copy()
            # Add semi-transparent dark overlay
            overlay = processing_overlay.copy()
            cv2.rectangle(overlay, (0, 0), (overlay.shape[1], overlay.shape[0]), (0, 0, 0), -1)
            processing_overlay = cv2.addWeighted(overlay, 0.5, processing_overlay, 0.5, 0)
            # Add prominent text with outline for visibility
            text = "PROCESSING..."
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 2.0
            thickness = 4
            text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
            text_x = (processing_overlay.shape[1] - text_size[0]) // 2
            text_y = (processing_overlay.shape[0] + text_size[1]) // 2
            # Draw black outline
            cv2.putText(processing_overlay, text, (text_x, text_y), font, font_scale, (0, 0, 0), thickness+2)
            # Draw cyan text
            cv2.putText(processing_overlay, text, (text_x, text_y), font, font_scale, (0, 255, 255), thickness)
            display_processing = cv2.resize(processing_overlay, (800, 450))
            cv2.imshow('ABI Market Capture', display_processing)
            cv2.waitKey(1)  # Force immediate display update
            
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
            # Extend ROI to bottom of screenshot so full cards are captured
            roi_h = screenshot.shape[0] - roi_y
            
            # Extract ROI from full screenshot
            grid_region = screenshot[roi_y:roi_y + roi_h, roi_x:roi_x + roi_w]
            
            # Detect actual card positions dynamically (works with scrolling)
            card_positions = detect_card_positions(grid_region, config.item_card)
            # Precompute absolute screen coordinates for all detected cards
            abs_card_positions = [(roi_x + x, roi_y + y, w, h) for (x, y, w, h) in card_positions]
            
            # Extract items from visible cards
            new_items_this_capture = 0
            detected_cards = []  # Track which cards were successfully read
            
            cards_checked = 0
            cards_visible = 0
            cards_with_data = 0
            
            for idx, (x, y, w, h) in enumerate(card_positions):
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
                    clean_name = get_clean_name(ocr_name)  # Map to clean name
                    
                    # Compute thumbnail hash from the card image region between name and price
                    icfg = config.item_card
                    thumb_top = int(icfg.get('thumbnail_top', icfg.get('name_region_height', 18)))
                    thumb_h = int(icfg.get('thumbnail_height', max(0, icfg.get('price_top', 181) - thumb_top)))
                    thumb_bottom = min(card_image.shape[0], thumb_top + thumb_h)
                    thumb_img = card_image[thumb_top:thumb_bottom, 0:card_image.shape[1]] if thumb_h > 0 else card_image
                    thumb_hash = compute_thumbnail_hash(thumb_img)
                    # Persist thumbnail image for GUI (small, e.g., 96px tall) with de-duplication by hash
                    thumb_dir = os.path.join(config.snapshots_path, 'thumbs')
                    os.makedirs(thumb_dir, exist_ok=True)
                    thumb_path = ""
                    h, w = thumb_img.shape[:2]
                    chosen_hash = thumb_hash
                    if h > 0 and w > 0 and thumb_hash:
                        # If a very similar hash already exists, reuse that filename
                        existing_files = []
                        try:
                            existing_files = [f for f in os.listdir(thumb_dir) if f.lower().endswith('.png')]
                        except Exception:
                            existing_files = []
                        chosen_hash = thumb_hash
                        for fn in existing_files:
                            stem = os.path.splitext(fn)[0]
                            dist = hamming_distance_hex(thumb_hash, stem)
                            if dist is None:
                                continue
                            # If both are composite hashes (>=22 hex), compare HSV suffix (last 6 hex) to avoid cross-color reuse
                            hsv_ok = True
                            try:
                                if len(thumb_hash) >= 22 and len(stem) >= 22:
                                    hsv_a = thumb_hash[-6:]
                                    hsv_b = stem[-6:]
                                    ha, sa, va = int(hsv_a[0:2], 16), int(hsv_a[2:4], 16), int(hsv_a[4:6], 16)
                                    hb, sb, vb = int(hsv_b[0:2], 16), int(hsv_b[2:4], 16), int(hsv_b[4:6], 16)
                                    # Hue tolerance tighter; saturation must also be reasonably close
                                    hsv_ok = (abs(ha - hb) <= 15) and (abs(sa - sb) <= 40)
                            except Exception:
                                hsv_ok = True
                            # Tighten hamming threshold to reduce accidental reuse
                            if dist <= 4 and hsv_ok:
                                chosen_hash = stem
                                break
                        # Second pass: if not chosen by hash, do visual similarity against near candidates
                        if chosen_hash == thumb_hash and existing_files:
                            # Limit candidates by relaxed hash distance and similar HSV
                            candidates = []
                            for fn in existing_files:
                                stem = os.path.splitext(fn)[0]
                                dist = hamming_distance_hex(thumb_hash, stem)
                                if dist is None or dist > 12:
                                    continue
                                hsv_ok = True
                                try:
                                    if len(thumb_hash) >= 22 and len(stem) >= 22:
                                        hsv_a = thumb_hash[-6:]
                                        hsv_b = stem[-6:]
                                        ha, sa, va = int(hsv_a[0:2], 16), int(hsv_a[2:4], 16), int(hsv_a[4:6], 16)
                                        hb, sb, vb = int(hsv_b[0:2], 16), int(hsv_b[2:4], 16), int(hsv_b[4:6], 16)
                                        hsv_ok = (abs(ha - hb) <= 25) and (abs(sa - sb) <= 60)
                                except Exception:
                                    hsv_ok = True
                                if hsv_ok:
                                    candidates.append(fn)
                            # Compare RMSE with at most first 40 candidates for performance
                            for fn in candidates[:40]:
                                try:
                                    cand_img = cv2.imread(os.path.join(thumb_dir, fn))
                                    if are_images_similar(thumb_img, cand_img, rmse_threshold=10.0):
                                        chosen_hash = os.path.splitext(fn)[0]
                                        break
                                except Exception:
                                    continue
                        # Filename is the (possibly adjusted) hash
                        out_name = f"{chosen_hash}.png"
                        out_full = os.path.join(thumb_dir, out_name)
                        if not os.path.exists(out_full):
                            # Keep aspect ratio; target height 96
                            scale = 96.0 / float(h)
                            resized = cv2.resize(thumb_img, (max(1, int(w*scale)), 96), interpolation=cv2.INTER_AREA)
                            try:
                                cv2.imwrite(out_full, resized)
                            except Exception:
                                out_full = ""
                        thumb_path = out_full
                    # Use the actually chosen filename hash as the canonical thumb hash
                    thumb_hash_final = chosen_hash if chosen_hash else thumb_hash

                    # Create category-aware key with disambiguation only when needed
                    base_prefix = f"{current_category}:{clean_name}"
                    candidates = [k for k in collected_items.keys() if k.startswith(base_prefix)]
                    if not candidates:
                        item_key = base_prefix
                    else:
                        chosen = None
                        for k in candidates:
                            entry = collected_items.get(k, {})
                            same_price = float(entry.get('price', -1)) == float(item_data['price'])
                            dist = hamming_distance_hex(thumb_hash_final, entry.get('thumbHash', '')) if thumb_hash_final and entry.get('thumbHash') else None
                            # Compare hue bins to avoid merging clearly different colors
                            hue_ok = True
                            try:
                                src_bin = int(compute_color_signature(thumb_img).get('h_bin', 0))
                                dst_bin = int(entry.get('colorSig', {}).get('h_bin', 0)) if isinstance(entry.get('colorSig'), dict) else 0
                                hue_ok = hue_bin_distance(src_bin, dst_bin) <= 1
                            except Exception:
                                hue_ok = True
                            if same_price or (dist is not None and dist <= 8 and hue_ok):
                                chosen = k
                                break
                        if chosen:
                            item_key = chosen
                        else:
                            # No close match: create new key with full hash suffix
                            suffix = ("#" + (thumb_hash_final if thumb_hash_final else f"{int(time.time()) & 0xFFFFFF:06x}"))
                            item_key = base_prefix + suffix
                    
                    # Track this card for visual feedback (check by category+clean name)
                    is_new = item_key not in collected_items
                    abs_x, abs_y, aw, ah = abs_card_positions[idx]
                    detected_cards.append((abs_x, abs_y, aw, ah, is_new))
                    
                    # Add or update item (category:clean_name#hash is the unique key)
                    if is_new:
                        collected_items[item_key] = {
                            'ocrName': ocr_name,  # Store original OCR for reference
                            'price': item_data['price'],
                            'category': current_category,  # Use detected category from orange menu item
                            'thumbHash': thumb_hash_final,
                            # Snapshot persists hash only; GUI derives filename
                            'colorSig': compute_color_signature(thumb_img)
                        }
                        new_items_this_capture += 1
                        # Show both names if different
                        if ocr_name != clean_name:
                            print(f"  [{current_category}] {clean_name} (OCR: {ocr_name}) - ${item_data['price']:,}")
                        else:
                            print(f"  [{current_category}] {clean_name} - ${item_data['price']:,}")
            
            # Calculate processing time
            processing_time = time.time() - capture_start_time
            
            # Optional: Uncomment to debug OCR success rate
            # print(f"[DEBUG] Detected: {len(card_positions)}, Checked: {cards_checked}, Visible: {cards_visible}, With data: {cards_with_data}")
            
            if new_items_this_capture > 0:
                capture_count += 1
                print(f"\n[{capture_count}] Captured {new_items_this_capture} new items in {processing_time:.2f}s (Total: {len(collected_items)})")
            else:
                print(f"[✓] Processed in {processing_time:.2f}s - No new items this screen")
            
            # Draw borders around ALL detected card positions (not just those with data)
            screenshot_with_borders = screenshot.copy()
            
            # Draw borders for all detected positions (teal for detected but not fully visible)
            for (abs_x, abs_y, w, h) in abs_card_positions:
                cv2.rectangle(screenshot_with_borders, (abs_x, abs_y), (abs_x + w, abs_y + h), (255, 255, 0), 1)  # Teal thin border
            
            # Draw thicker borders for cards that were successfully read
            for (abs_x, abs_y, w, h, is_new) in detected_cards:
                # Green border for new items, light blue for already captured
                color = (0, 255, 0) if is_new else (255, 165, 0)  # Green or Light Blue
                thickness = 3 if is_new else 2
                cv2.rectangle(screenshot_with_borders, (abs_x, abs_y), (abs_x + w, abs_y + h), color, thickness)
            
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
            
            # Show current screenshot with borders
            display = cv2.resize(screenshot_with_borders, (800, 450))
            status = "CAPTURING" if capturing else "PAUSED"
            status_color = (0, 255, 0) if capturing else (0, 165, 255)
            cv2.putText(display, f"{status} | Items: {len(collected_items)} | This view: {len(detected_cards)} | Processed: {processing_time:.2f}s", 
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, status_color, 2)
            cv2.imshow('ABI Market Capture', display)
            
            # Save all border information and timestamp for time-limited display
            last_detected_cards = detected_cards.copy()
            last_card_positions = abs_card_positions
            last_category_bbox = category_bbox
            last_current_category = current_category
            last_capture_time = time.time()
    
    except KeyboardInterrupt:
        print("\n[!] Interrupted by user")
    
    finally:
        # Clean up preview window
        cv2.destroyAllWindows()
    
    # Save results
    if collected_items:
        print("\n" + "="*60)
        print(f"CAPTURE COMPLETE - {len(collected_items)} unique items")
        print("="*60)
        
        # Group items by category
        # Store clean names in snapshot (already deduplicated)
        categories = {}
        for item_key, data in collected_items.items():
            # item_key format: "category:cleanName#hash"
            category = data['category']
            clean_part = item_key.split(':', 1)[1] if ':' in item_key else item_key
            clean_name = clean_part.split('#', 1)[0]
            if category not in categories:
                categories[category] = []
            # Store clean name and thumbnail hash (GUI derives filename)
            entry = {'itemName': clean_name, 'price': data['price']}
            if data.get('thumbHash'):
                entry['thumbHash'] = data['thumbHash']
            categories[category].append(entry)
        
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
            # item_key format: "category:cleanName" - extract clean name for output
            clean_name = item_key.split(':', 1)[1] if ':' in item_key else item_key
            print(f"  ${data['price']:>8,} - [{data['category']}] {clean_name}")
        
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


