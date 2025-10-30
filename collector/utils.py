"""Collector utilities for OCR, image processing, and snapshots."""
import os
import re
import json
import time
import datetime as dt
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional, Any

import cv2
import numpy as np
import pytesseract
import yaml


@dataclass
class CollectorConfig:
    window_title: str
    resolution: Tuple[int, int]
    tesseract_path: str
    snapshots_path: str
    ui_regions: Dict[str, Any]
    item_card: Dict[str, Any]
    navigation: Dict[str, Any]
    preprocess: Dict[str, Any]
    ocr: Dict[str, Any]


def load_config(path: str) -> CollectorConfig:
    with open(path, 'r', encoding='utf-8') as f:
        cfg = yaml.safe_load(f)
    return CollectorConfig(
        window_title=cfg.get('window_title', 'Arena Breakout: Infinite'),
        resolution=tuple(cfg.get('resolution', [1280, 720])),
        tesseract_path=cfg.get('tesseract_path', ''),
        snapshots_path=cfg.get('snapshots_path', 'snapshots'),
        ui_regions=cfg.get('ui_regions', {}),
        item_card=cfg.get('item_card', {}),
        navigation=cfg.get('navigation', {}),
        preprocess=cfg.get('preprocess', {}),
        ocr=cfg.get('ocr', {}),
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


_PRICE_RE = re.compile(r"([\-–—]|:)?\s*(\d{1,3}(?:[\,\.]\d{3})*|\d+)$")


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
            price = int(re.sub(r"[\,\.]", "", price_str))
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

