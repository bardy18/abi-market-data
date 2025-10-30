"""Computer vision utilities for dynamic UI discovery."""
import re
from typing import List, Tuple, Dict, Any, Optional

import cv2
import numpy as np
import pytesseract


def detect_selected_category(tree_region: np.ndarray, tesseract_path: str = None) -> Tuple[str, Optional[Tuple[int, int, int, int]]]:
    """
    Detect the currently selected category by finding the orange-highlighted menu item.
    Returns tuple of (category_name, bounding_box) where bounding_box is (x, y, w, h) or None.
    """
    if tesseract_path:
        pytesseract.pytesseract.tesseract_cmd = tesseract_path
    
    # Convert to HSV for color detection
    hsv = cv2.cvtColor(tree_region, cv2.COLOR_BGR2HSV)
    
    # Orange color range in HSV
    # Orange is roughly: H=10-25, S=100-255, V=100-255
    lower_orange = np.array([5, 100, 100])
    upper_orange = np.array([25, 255, 255])
    
    # Create mask for orange regions
    orange_mask = cv2.inRange(hsv, lower_orange, upper_orange)
    
    # Find contours in the orange mask
    contours, _ = cv2.findContours(orange_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        return 'Unknown', None
    
    # Find the largest orange region (should be the selected menu item)
    largest_contour = max(contours, key=cv2.contourArea)
    x, y, w, h = cv2.boundingRect(largest_contour)
    
    # Add padding to capture just the text, but move inward to avoid the thick borders
    padding_left = 10   # Move inward from left border
    padding_right = -5   # Move inward from right (negative = shrink)
    padding_vert = 5
    
    x_text = max(0, x - padding_left)
    y_text = max(0, y - padding_vert)
    w_text = min(tree_region.shape[1] - x_text, w + padding_left + padding_right)
    h_text = min(tree_region.shape[0] - y_text, h + 2*padding_vert)
    
    selected_region = tree_region[y_text:y_text+h_text, x_text:x_text+w_text]
    
    if selected_region.shape[0] < 10 or selected_region.shape[1] < 10:
        return 'Unknown', None
    
    # Save the bounding box for visualization
    bbox = (x_text, y_text, w_text, h_text)
    
    # Convert to grayscale
    gray = cv2.cvtColor(selected_region, cv2.COLOR_BGR2GRAY)
    
    # Normalize
    gray = cv2.normalize(gray, None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX)
    
    # Upscale significantly for better character recognition
    gray = cv2.resize(gray, None, fx=6.0, fy=6.0, interpolation=cv2.INTER_CUBIC)
    
    # Use Otsu threshold
    _, gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # Invert
    gray = cv2.bitwise_not(gray)
    
    # Use PSM 7 (single line) which works best for category names
    text = pytesseract.image_to_string(gray, config='--psm 7 --oem 1').strip()
    
    # Clean up
    text = text.replace('[', '').replace(']', '').replace('|', '').strip()
    
    return (text if text else 'Unknown'), bbox


def detect_tree_items(tree_image: np.ndarray, line_height: int, indent_x: int) -> List[Dict[str, Any]]:
    """
    Detect tree navigation items using OCR.
    Returns list of {text, y_pos, indent_level, click_x, click_y}
    """
    # OCR the tree navigation area
    text = pytesseract.image_to_string(tree_image)
    
    # Get detailed bounding boxes
    data = pytesseract.image_to_data(tree_image, output_type=pytesseract.Output.DICT)
    
    items = []
    for i, text_val in enumerate(data['text']):
        if not text_val.strip():
            continue
        
        conf = int(data['conf'][i])
        if conf < 30:  # Low confidence, skip
            continue
        
        x = data['left'][i]
        y = data['top'][i]
        
        # Determine indent level based on x position
        indent_level = 0
        if x > indent_x * 1.5:
            indent_level = 1
        
        items.append({
            'text': text_val.strip(),
            'y_pos': y,
            'x_pos': x,
            'indent_level': indent_level,
            'click_x': x + 10,  # Click slightly right of text start
            'click_y': y + 10,  # Click middle of text
        })
    
    # Group nearby items into single lines
    items.sort(key=lambda it: it['y_pos'])
    grouped = []
    current_line = None
    
    for item in items:
        if current_line is None:
            current_line = item
        elif abs(item['y_pos'] - current_line['y_pos']) < line_height // 2:
            # Same line, concatenate text
            current_line['text'] += ' ' + item['text']
        else:
            grouped.append(current_line)
            current_line = item
    
    if current_line:
        grouped.append(current_line)
    
    return grouped


def generate_grid_positions(card_config: Dict[str, Any], grid_height: int) -> List[Tuple[int, int, int, int]]:
    """
    Generate item card positions based on known grid layout.
    Returns list of (x, y, width, height) for each potential card position.
    """
    columns = card_config['columns']
    card_width = card_config['card_width']
    card_height = card_config['card_height']
    gap_h = card_config['gap_horizontal']
    gap_v = card_config['gap_vertical']
    
    # Calculate how many rows fit in the visible area
    max_rows = (grid_height + gap_v) // (card_height + gap_v)
    
    cards = []
    for row in range(max_rows + 1):  # +1 for partially visible row
        for col in range(columns):
            x = col * (card_width + gap_h)
            y = row * (card_height + gap_v)
            cards.append((x, y, card_width, card_height))
    
    return cards


def detect_card_positions(grid_image: np.ndarray, card_config: Dict[str, Any]) -> List[Tuple[int, int, int, int]]:
    """
    Detect actual item card positions using contour detection.
    Finds rectangles that match expected card dimensions.
    Returns list of (x, y, width, height) for detected cards.
    """
    card_width = card_config['card_width']
    card_height = card_config['card_height']
    
    # Convert to grayscale
    gray = cv2.cvtColor(grid_image, cv2.COLOR_BGR2GRAY)
    
    # Use edge detection
    edges = cv2.Canny(gray, 30, 100)
    
    # Find contours
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    cards = []
    
    for contour in contours:
        # Get bounding rectangle
        x, y, w, h = cv2.boundingRect(contour)
        
        # Filter by size - must be close to expected card dimensions
        # Width must match closely (±15%)
        width_ok = abs(w - card_width) < card_width * 0.15
        
        # Height can be shorter for bottom row (as low as 50% for partially visible cards)
        height_ok = h >= card_height * 0.5 and h <= card_height * 1.15
        
        if width_ok and height_ok:
            # Check that the card is mostly within bounds
            if x >= 0 and y >= 0 and x + w <= grid_image.shape[1]:
                cards.append((x, y, w, h))
    
    # Sort by position (top to bottom, left to right)
    cards.sort(key=lambda c: (c[1], c[0]))
    
    # Remove duplicates (cards detected multiple times)
    filtered_cards = []
    for card in cards:
        # Check if this card overlaps significantly with any already added card
        is_duplicate = False
        for existing in filtered_cards:
            # Calculate overlap
            x_overlap = max(0, min(card[0] + card[2], existing[0] + existing[2]) - max(card[0], existing[0]))
            y_overlap = max(0, min(card[1] + card[3], existing[1] + existing[3]) - max(card[1], existing[1]))
            overlap_area = x_overlap * y_overlap
            card_area = card[2] * card[3]
            
            if overlap_area > card_area * 0.5:  # More than 50% overlap
                is_duplicate = True
                break
        
        if not is_duplicate:
            filtered_cards.append(card)
    
    return filtered_cards


def is_price_region(price_image: np.ndarray, debug: bool = False) -> bool:
    """Check if image region looks like a price (white text on dark background)"""
    if price_image.shape[0] < 10 or price_image.shape[1] < 10:
        return False
    
    # Convert to grayscale
    gray = cv2.cvtColor(price_image, cv2.COLOR_BGR2GRAY) if len(price_image.shape) == 3 else price_image
    
    # Price regions have dark background with bright text
    mean_intensity = np.mean(gray)
    max_intensity = np.max(gray)
    std_dev = np.std(gray)
    
    # Relaxed thresholds - price regions are darker than average but have bright text
    has_bright_text = max_intensity > 180  # Lowered from 200
    has_dark_background = mean_intensity < 120  # Raised from 100 to be more lenient
    has_variance = std_dev > 20  # Lowered from 30
    
    if debug:
        print(f"    mean={mean_intensity:.1f}, max={max_intensity:.1f}, std={std_dev:.1f} -> "
              f"bright={has_bright_text}, dark={has_dark_background}, var={has_variance}")
    
    return has_bright_text and has_dark_background and has_variance


def extract_item_from_card(card_image: np.ndarray, card_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Extract item name and price from a card image using known layout.
    """
    h, w = card_image.shape[:2]
    
    # Ensure card has minimum size
    if h < 50 or w < 50:
        return None
    
    # Extract name region (top portion)
    name_height = card_config['name_region_height']
    name_region = card_image[0:name_height, :]
    
    # Convert to grayscale
    name_gray = cv2.cvtColor(name_region, cv2.COLOR_BGR2GRAY) if len(name_region.shape) == 3 else name_region
    
    # Normalize for consistency across different captures
    name_gray = cv2.normalize(name_gray, None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX)
    
    # Upscale for better OCR
    scale_factor = 3.0
    name_gray = cv2.resize(name_gray, None, fx=scale_factor, fy=scale_factor, interpolation=cv2.INTER_CUBIC)
    
    # Use Otsu threshold (works better than fixed threshold for varying text)
    _, name_gray = cv2.threshold(name_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # Invert to black text on white (Tesseract standard)
    name_gray = cv2.bitwise_not(name_gray)
    
    # Use single config for consistency (not multiple attempts)
    # PSM 7 = single line, OEM 1 = LSTM (most consistent)
    tesseract_config = '--psm 7 --oem 1'
    best_name = pytesseract.image_to_string(name_gray, config=tesseract_config).strip()
    
    # Extract price region (bottom portion)
    price_top = card_config['price_top']
    price_left_crop = card_config.get('price_left_crop', 0)  # Optional left crop to remove currency icon
    price_region = card_image[price_top:h, price_left_crop:]
    
    # Simpler preprocessing for price (numbers need less aggressive processing)
    price_gray = cv2.cvtColor(price_region, cv2.COLOR_BGR2GRAY) if len(price_region.shape) == 3 else price_region
    
    # Upscale
    price_gray = cv2.resize(price_gray, None, fx=scale_factor, fy=scale_factor, interpolation=cv2.INTER_CUBIC)
    
    # Simple Otsu threshold (no denoising to preserve number shapes)
    _, price_gray = cv2.threshold(price_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # CRITICAL: Invert so we have black text on white background (tesseract standard)
    price_gray = cv2.bitwise_not(price_gray)
    
    # OCR with numeric emphasis
    price_text = pytesseract.image_to_string(price_gray, config='--psm 7 -c tessedit_char_whitelist=0123456789,$,. ').strip()
    
    # Parse price (look for numbers)
    price_match = re.search(r'(\d{1,3}(?:[\,\.]\d{3})*|\d+)', price_text)
    if not price_match:
        return None
    
    try:
        price = int(re.sub(r'[\,\.]', '', price_match.group(1)))
    except ValueError:
        return None
    
    if not best_name or price <= 0:
        return None
    
    # Clean up name (remove common OCR artifacts but keep most characters)
    best_name = re.sub(r'[^\w\s\-\'\.]', ' ', best_name).strip()
    best_name = ' '.join(best_name.split())  # Normalize whitespace
    
    if not best_name:
        return None
    
    return {
        'itemName': best_name,
        'price': price
    }


def check_scrollbar_at_bottom(scrollbar_image: np.ndarray) -> bool:
    """
    Check if scrollbar indicates we're at the bottom.
    Uses simple heuristic: if bottom portion is darker/different, we're not at bottom.
    """
    h, w = scrollbar_image.shape[:2]
    
    if h < 50:
        return True  # Too small to determine
    
    # Convert to grayscale
    gray = cv2.cvtColor(scrollbar_image, cv2.COLOR_BGR2GRAY) if len(scrollbar_image.shape) == 3 else scrollbar_image
    
    # Compare top and bottom thirds
    top_third = gray[0:h//3, :]
    bottom_third = gray[2*h//3:h, :]
    
    top_mean = np.mean(top_third)
    bottom_mean = np.mean(bottom_third)
    
    # If bottom is significantly darker, we're likely not at bottom
    # This is a heuristic - may need tuning
    return abs(top_mean - bottom_mean) < 20
