"""Collector utilities for config, OCR, image processing, computer vision, and snapshots."""
import os
import re
import json
import time
import datetime as dt
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional, Any
from pathlib import Path

import cv2
import numpy as np
import pytesseract
import yaml


# OCR name mapping cache
_ocr_mapping = None

def load_ocr_mapping() -> Dict[str, str]:
    """Load the OCR to clean name mapping from ocr_mappings.json"""
    global _ocr_mapping
    if _ocr_mapping is None:
        mapping_file = Path(__file__).parent.parent / 'mappings' / 'ocr_mappings.json'
        if mapping_file.exists():
            with open(mapping_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Filter out comment entries
                _ocr_mapping = {k: v for k, v in data.items() if not k.startswith('_')}
        else:
            _ocr_mapping = {}
    return _ocr_mapping


def get_clean_name(ocr_name: str) -> str:
    """Get the clean/deduplicated name for an OCR-extracted item name"""
    mapping = load_ocr_mapping()
    return mapping.get(ocr_name, ocr_name)


@dataclass
class CollectorConfig:
    resolution: Tuple[int, int]
    tesseract_path: str
    snapshots_path: str
    ui_regions: Dict[str, Any]
    item_card: Dict[str, Any]
    navigation: Dict[str, Any]
    preprocess: Dict[str, Any]
    ocr: Dict[str, Any]
    hotkeys: Dict[str, Any] = None


def load_config(path: str) -> CollectorConfig:
    with open(path, 'r', encoding='utf-8') as f:
        cfg = yaml.safe_load(f)
    return CollectorConfig(
        resolution=tuple(cfg.get('resolution', [1280, 720])),
        tesseract_path=cfg.get('tesseract_path', ''),
        snapshots_path=cfg.get('snapshots_path', 'snapshots'),
        ui_regions=cfg.get('ui_regions', {}),
        item_card=cfg.get('item_card', {}),
        navigation=cfg.get('navigation', {}),
        preprocess=cfg.get('preprocess', {}),
        ocr=cfg.get('ocr', {}),
        hotkeys=cfg.get('hotkeys', {
            'toggle': 'space',
            'capture': 'f8',
            'finish': 'esc',
            'quit': 'q',
        }),
    )


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def timestamp_now_epoch() -> int:
    return int(time.time())


def timestamp_to_str(ts: Optional[int] = None) -> str:
    if ts is None:
        ts = timestamp_now_epoch()
    return dt.datetime.fromtimestamp(ts).strftime('%Y-%m-%d_%H-%M')


def make_snapshot_filename(base_dir: str, ts: int) -> str:
    return os.path.join(base_dir, f"{timestamp_to_str(ts)}.json")


def write_snapshot(snapshot: Dict[str, Any], path: str) -> None:
    ensure_dir(os.path.dirname(path))
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)


# OCR helpers

def set_tesseract_path(path: str) -> None:
    if path and os.path.exists(path):
        pytesseract.pytesseract.tesseract_cmd = path


def preprocess_image(img: np.ndarray, cfg: Dict[str, Any]) -> np.ndarray:
    out = img.copy()
    if cfg.get('grayscale', True):
        out = cv2.cvtColor(out, cv2.COLOR_BGR2GRAY)
    if cfg.get('sharpen', True):
        kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
        out = cv2.filter2D(out, -1, kernel)
    alpha = float(cfg.get('contrast_alpha', 1.5))
    beta = float(cfg.get('contrast_beta', 0))
    out = cv2.convertScaleAbs(out, alpha=alpha, beta=beta)
    return out


def compute_thumbnail_hash(img_bgr: np.ndarray) -> str:
    """
    Compute a robust thumbnail fingerprint by combining:
      - aHash (8x8 luminance)  -> 16 hex
      - dHash (8x8 horizontal) -> 16 hex
      - Mean HSV signature     -> 6 hex (H,S,V each 1 byte)

    Returns a hex string (38 chars). Older snapshots may contain 16-char hashes;
    downstream code only treats this as an opaque filename/key, so longer is fine.
    """
    if img_bgr is None or img_bgr.size == 0:
        return ""

    # Guard against degenerate dims
    h, w = img_bgr.shape[:2]
    if h == 0 or w == 0:
        return ""

    # Slightly crop 1px border to reduce UI-frame influence, if possible
    if h > 4 and w > 4:
        img_bgr = img_bgr[1:h-1, 1:w-1]

    # Grayscale conversion
    try:
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    except Exception:
        gray = img_bgr if len(img_bgr.shape) == 2 else cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    # aHash (average hash) 8x8
    a_small = cv2.resize(gray, (8, 8), interpolation=cv2.INTER_AREA)
    a_avg = float(a_small.mean())
    a_bits = (a_small > a_avg).astype(np.uint8).flatten()
    a_val = 0
    for b in a_bits:
        a_val = (a_val << 1) | int(b)
    a_hex = f"{a_val:016x}"

    # dHash (difference hash) 8x8 from 9x8 resized
    d_small = cv2.resize(gray, (9, 8), interpolation=cv2.INTER_AREA)
    diff = d_small[:, 1:] > d_small[:, :-1]
    d_bits = diff.astype(np.uint8).flatten()
    d_val = 0
    for b in d_bits:
        d_val = (d_val << 1) | int(b)
    d_hex = f"{d_val:016x}"

    # Mean HSV signature, emphasizing high-saturation regions (labels/colors)
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    H, S, V = cv2.split(hsv)
    # Focus on pixels with noticeable saturation
    sat_thresh = 60
    mask = (S >= sat_thresh)
    if np.any(mask):
        h_vals = H[mask]
        s_vals = S[mask]
        v_vals = V[mask]
    else:
        h_vals = H
        s_vals = S
        v_vals = V
    h_mean = int(round(np.clip(h_vals.mean() * (255.0/180.0), 0, 255)))
    s_mean = int(round(np.clip(s_vals.mean(), 0, 255)))
    v_mean = int(round(np.clip(v_vals.mean(), 0, 255)))
    hsv_hex = f"{h_mean:02x}{s_mean:02x}{v_mean:02x}"

    return a_hex + d_hex + hsv_hex


def hamming_distance_hex(a: str, b: str) -> Optional[int]:
    """Bitwise Hamming distance between two hex strings (compare up to min length)."""
    if not a or not b:
        return None
    try:
        n = min(len(a), len(b))
        if n == 0:
            return None
        va = int(a[:n], 16)
        vb = int(b[:n], 16)
        x = va ^ vb
        return int(bin(x).count('1'))
    except Exception:
        return None


def compute_color_signature(img_bgr: np.ndarray) -> Dict[str, Any]:
    """Compute a simple color signature for disambiguation.
    Returns dict with mean HSV and a quantized hue bin (0-11).
    """
    if img_bgr is None or img_bgr.size == 0:
        return {"h_mean": 0.0, "s_mean": 0.0, "v_mean": 0.0, "h_bin": 0}
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)
    # Emphasize high-saturation pixels for color decisions
    sat_thresh = 60
    mask = (s >= sat_thresh)
    if np.any(mask):
        h_sel = h[mask]
        s_sel = s[mask]
        v_sel = v[mask]
    else:
        h_sel = h
        s_sel = s
        v_sel = v
    h_mean = float(h_sel.mean())  # 0..180 in OpenCV
    s_mean = float(s_sel.mean())  # 0..255
    v_mean = float(v_sel.mean())  # 0..255
    # Quantize hue into 12 bins (each 15 units) using mean on selected pixels
    h_bin = int(h_mean // 15) % 12
    return {"h_mean": h_mean, "s_mean": s_mean, "v_mean": v_mean, "h_bin": h_bin}


def hue_bin_distance(a: int, b: int, bins: int = 12) -> int:
    """Cyclic distance between hue bins."""
    d = abs((a % bins) - (b % bins))
    return min(d, bins - d)
    try:
        # Normalize to same length by trimming to shortest
        n = min(len(a), len(b))
        va = int(a[:n], 16)
        vb = int(b[:n], 16)
        x = va ^ vb
        # Count bits set (popcount)
        return int(bin(x).count('1'))
    except Exception:
        return None


def are_images_similar(img_a_bgr: np.ndarray, img_b_bgr: np.ndarray,
                       gray_rmse_threshold: float = 10.0,
                       hue_rmse_threshold: float = 18.0,
                       sat_mask_threshold: int = 60,
                       masked_gray_rmse_threshold: float = 14.0) -> bool:
    """Return True if two images are visually similar using multiple cues:
    - Grayscale RMSE over downscaled 64x64
    - Hue RMSE over downscaled 64x64 HSV (hue scaled to 0..255, circular)
    - If high-saturation pixels exist (S>=sat_mask_threshold), also compare grayscale RMSE
      only over that mask (to emphasize colored labels)
    """
    if img_a_bgr is None or img_b_bgr is None:
        return False
    if img_a_bgr.size == 0 or img_b_bgr.size == 0:
        return False
    try:
        # Standardize sizes
        ta = cv2.resize(img_a_bgr, (64, 64), interpolation=cv2.INTER_AREA)
        tb = cv2.resize(img_b_bgr, (64, 64), interpolation=cv2.INTER_AREA)

        # Grayscale RMSE
        ga = cv2.cvtColor(ta, cv2.COLOR_BGR2GRAY) if len(ta.shape) == 3 else ta
        gb = cv2.cvtColor(tb, cv2.COLOR_BGR2GRAY) if len(tb.shape) == 3 else tb
        diff_g = ga.astype(np.float32) - gb.astype(np.float32)
        rmse_g = float(np.sqrt(np.mean(np.square(diff_g))))
        if rmse_g > gray_rmse_threshold:
            return False

        # HSV and Hue RMSE (circular distance scaled to 0..255)
        ha, sa, va = cv2.split(cv2.cvtColor(ta, cv2.COLOR_BGR2HSV))
        hb, sb, vb = cv2.split(cv2.cvtColor(tb, cv2.COLOR_BGR2HSV))
        # Map hue 0..180 to 0..255 for distance and compute circular diff per-pixel
        ha255 = ha.astype(np.float32) * (255.0 / 180.0)
        hb255 = hb.astype(np.float32) * (255.0 / 180.0)
        d = np.abs(ha255 - hb255)
        hue_circ = np.minimum(d, 255.0 - d)
        rmse_h = float(np.sqrt(np.mean(np.square(hue_circ))))
        if rmse_h > hue_rmse_threshold:
            return False

        # High-saturation mask RMSE to emphasize colored labels
        mask = (sa >= sat_mask_threshold) | (sb >= sat_mask_threshold)
        if np.any(mask):
            gma = ga.astype(np.float32)[mask]
            gmb = gb.astype(np.float32)[mask]
            if gma.size > 0 and gmb.size > 0:
                rmse_mask = float(np.sqrt(np.mean(np.square(gma - gmb))))
                if rmse_mask > masked_gray_rmse_threshold:
                    return False

        return True
    except Exception:
        return False


def hsv_hist_similarity(img_a_bgr: np.ndarray, img_b_bgr: np.ndarray,
                        sat_mask_threshold: int = 60,
                        bins: int = 16,
                        min_cosine: float = 0.965) -> bool:
    """Compare HSV hue histograms under high-saturation mask. Returns True if cosine similarity >= min_cosine.
    Focuses on label color/pattern robustness. Uses hue (0..180) histogram with 'bins' bins.
    """
    if img_a_bgr is None or img_b_bgr is None:
        return False
    if img_a_bgr.size == 0 or img_b_bgr.size == 0:
        return False
    try:
        ta = cv2.resize(img_a_bgr, (96, 96), interpolation=cv2.INTER_AREA)
        tb = cv2.resize(img_b_bgr, (96, 96), interpolation=cv2.INTER_AREA)
        ha, sa, va = cv2.split(cv2.cvtColor(ta, cv2.COLOR_BGR2HSV))
        hb, sb, vb = cv2.split(cv2.cvtColor(tb, cv2.COLOR_BGR2HSV))
        mask_a = (sa >= sat_mask_threshold)
        mask_b = (sb >= sat_mask_threshold)
        ha = ha[mask_a]
        hb = hb[mask_b]
        if ha.size == 0 or hb.size == 0:
            return False
        hist_a, _ = np.histogram(ha, bins=bins, range=(0, 180), density=True)
        hist_b, _ = np.histogram(hb, bins=bins, range=(0, 180), density=True)
        # Cosine similarity
        num = float(np.dot(hist_a, hist_b))
        den = float(np.linalg.norm(hist_a) * np.linalg.norm(hist_b))
        if den == 0.0:
            return False
        cos = num / den
        return cos >= min_cosine
    except Exception:
        return False


# Price parsing: allow common OCR confusions (O→0, l/I→1, S→5, B→8) and mixed separators
_PRICE_RE = re.compile(r"([\-–—]|:)?\s*(?:\$\s*)?([0-9OoIiLlSsB]{1,3}(?:[\,\.\s][0-9OoIiLlSsB]{3})*|[0-9OoIiLlSsB]+)\s*$")


def _normalize_ocr_digits(token: str) -> str:
    """Normalize OCR-misread digits and strip thousand/decimal separators.
    Keeps only 0-9 by mapping common confusions.
    """
    if not token:
        return ""
    mapping = {
        'O': '0', 'o': '0',
        'l': '1', 'I': '1', 'i': '1',
        'S': '5', 's': '5',
        'B': '8',
    }
    out_chars = []
    for ch in token:
        if ch.isdigit():
            out_chars.append(ch)
        elif ch in mapping:
            out_chars.append(mapping[ch])
        elif ch in [',', '.', ' ']:
            # Skip separators entirely; we treat input as integer cents-free prices
            continue
        else:
            # Ignore any other chars
            continue
    return ''.join(out_chars)


def parse_ocr_lines(lines: List[str]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        m = _PRICE_RE.search(line)
        if not m:
            continue
        price_str = m.group(2)
        try:
            norm = _normalize_ocr_digits(price_str)
            if not norm:
                continue
            price = int(norm)
        except ValueError:
            continue
        name = line[:m.start()].strip().strip('-:').strip()
        if not name:
            continue
        items.append({'itemName': name, 'price': price})
    return items


def ocr_region_bgr(image_bgr: np.ndarray, ocr_cfg: Dict[str, Any]) -> str:
    psm = int(ocr_cfg.get('psm', 6))
    oem = int(ocr_cfg.get('oem', 3))
    custom = f"--psm {psm} --oem {oem}"
    return pytesseract.image_to_string(image_bgr, config=custom)


def screenshot_region(x: int, y: int, w: int, h: int) -> np.ndarray:
    # Use PyAutoGUI to capture screen region
    import pyautogui
    img = pyautogui.screenshot(region=(x, y, w, h))
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def capture_and_ocr(region: Tuple[int, int, int, int], preprocess_cfg: Dict[str, Any], ocr_cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    x, y, w, h = region
    bgr = screenshot_region(x, y, w, h)
    proc = preprocess_image(bgr, preprocess_cfg)
    text = ocr_region_bgr(proc, ocr_cfg)
    lines = [ln for ln in text.splitlines() if ln.strip()]
    return parse_ocr_lines(lines)


# Computer vision for UI discovery

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
    
    # Add padding to capture text, but move inward to avoid thick borders
    padding_left = 10
    padding_right = -5
    padding_vert = 5
    
    x_text = max(0, x - padding_left)
    y_text = max(0, y - padding_vert)
    w_text = min(tree_region.shape[1] - x_text, w + padding_left + padding_right)
    h_text = min(tree_region.shape[0] - y_text, h + 2*padding_vert)
    
    selected_region = tree_region[y_text:y_text+h_text, x_text:x_text+w_text]
    
    if selected_region.shape[0] < 10 or selected_region.shape[1] < 10:
        return 'Unknown', None
    
    # Save bounding box for visualization
    bbox = (x_text, y_text, w_text, h_text)
    
    # Convert to grayscale and normalize
    gray = cv2.cvtColor(selected_region, cv2.COLOR_BGR2GRAY)
    gray = cv2.normalize(gray, None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX)
    
    # Upscale for better character recognition
    gray = cv2.resize(gray, None, fx=6.0, fy=6.0, interpolation=cv2.INTER_CUBIC)
    
    # Threshold and invert
    _, gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    gray = cv2.bitwise_not(gray)
    
    # OCR with PSM 7 (single line)
    text = pytesseract.image_to_string(gray, config='--psm 7 --oem 1').strip()
    
    # Clean up
    text = text.replace('[', '').replace(']', '').replace('|', '').strip()
    
    return (text if text else 'Unknown'), bbox


def detect_card_positions(grid_image: np.ndarray, card_config: Dict[str, Any]) -> List[Tuple[int, int, int, int]]:
    """
    Detect actual item card positions using contour detection.
    Returns list of (x, y, width, height) for detected cards.
    """
    card_width = card_config['card_width']
    card_height = card_config['card_height']
    
    # Convert to grayscale and use edge detection
    gray = cv2.cvtColor(grid_image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 30, 100)
    
    # Find contours
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    cards = []
    
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        
        # Filter by size - must be close to expected card dimensions
        width_ok = abs(w - card_width) < card_width * 0.15
        height_ok = h >= card_height * 0.5 and h <= card_height * 1.15
        
        if width_ok and height_ok:
            if x >= 0 and y >= 0 and x + w <= grid_image.shape[1]:
                cards.append((x, y, w, h))
    
    # Sort by position (top to bottom, left to right)
    cards.sort(key=lambda c: (c[1], c[0]))
    
    # Remove duplicates
    filtered_cards = []
    for card in cards:
        is_duplicate = False
        for existing in filtered_cards:
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


def extract_item_from_card(card_image: np.ndarray, card_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract item name and price from a card image using known layout."""
    h, w = card_image.shape[:2]
    
    # Ensure card has minimum size
    if h < 50 or w < 50:
        return None
    
    # Extract name region (top portion)
    name_height = card_config['name_region_height']
    name_region = card_image[0:name_height, :]
    
    # Convert to grayscale and normalize
    name_gray = cv2.cvtColor(name_region, cv2.COLOR_BGR2GRAY) if len(name_region.shape) == 3 else name_region
    name_gray = cv2.normalize(name_gray, None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX)
    
    # Upscale and threshold
    scale_factor = 3.0
    name_gray = cv2.resize(name_gray, None, fx=scale_factor, fy=scale_factor, interpolation=cv2.INTER_CUBIC)
    _, name_gray = cv2.threshold(name_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    name_gray = cv2.bitwise_not(name_gray)
    
    # OCR for name
    tesseract_config = '--psm 7 --oem 1'
    best_name = pytesseract.image_to_string(name_gray, config=tesseract_config).strip()
    
    # Extract price region (bottom portion)
    price_top = card_config['price_top']
    price_left_crop = card_config.get('price_left_crop', 0)
    price_region = card_image[price_top:h, price_left_crop:]
    
    # Process price
    price_gray = cv2.cvtColor(price_region, cv2.COLOR_BGR2GRAY) if len(price_region.shape) == 3 else price_region
    price_gray = cv2.resize(price_gray, None, fx=scale_factor, fy=scale_factor, interpolation=cv2.INTER_CUBIC)
    _, price_gray = cv2.threshold(price_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    price_gray = cv2.bitwise_not(price_gray)
    
    # OCR with numeric emphasis
    price_text = pytesseract.image_to_string(price_gray, config='--psm 7 -c tessedit_char_whitelist=0123456789,$,. ').strip()
    
    # Parse price
    price_match = _PRICE_RE.search(price_text)
    if not price_match:
        return None
    
    try:
        price_token = price_match.group(2) if price_match.lastindex and price_match.lastindex >= 2 else price_match.group(0)
        norm = _normalize_ocr_digits(price_token)
        if not norm:
            return None
        price = int(norm)
    except ValueError:
        return None
    
    if not best_name or price <= 0:
        return None
    
    # Clean up name
    best_name = re.sub(r'[^\w\s\-\'\.]', ' ', best_name).strip()
    best_name = ' '.join(best_name.split())
    
    if not best_name:
        return None
    
    return {
        'itemName': best_name,
        'price': price
    }
