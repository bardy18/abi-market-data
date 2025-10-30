"""Trading app utilities for snapshot loading, analysis, and indicators."""
import os
import json
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from pathlib import Path

import yaml
import pandas as pd
import numpy as np
import boto3


# Item name mapping
_name_mapping = None

def load_item_name_mapping() -> Dict[str, str]:
    """Load the manual item name mapping from item_names.json"""
    global _name_mapping
    if _name_mapping is None:
        mapping_file = Path(__file__).parent.parent / 'item_names.json'
        if mapping_file.exists():
            with open(mapping_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Filter out comment entries
                _name_mapping = {k: v for k, v in data.items() if not k.startswith('_')}
        else:
            _name_mapping = {}
    return _name_mapping


def get_display_name(ocr_name: str) -> str:
    """Get the display name for an OCR-extracted item name"""
    mapping = load_item_name_mapping()
    return mapping.get(ocr_name, ocr_name)


def get_ocr_name(display_name: str) -> Optional[str]:
    """Reverse lookup: get OCR name from display name"""
    mapping = load_item_name_mapping()
    for ocr, display in mapping.items():
        if display == display_name:
            return ocr
    return None


@dataclass
class TradingAppConfig:
    snapshots_path: str
    max_snapshots_to_load: int
    s3: Dict[str, Any]
    alerts: Dict[str, Any]


def load_config(path: str) -> TradingAppConfig:
    with open(path, 'r', encoding='utf-8') as f:
        cfg = yaml.safe_load(f)
    return TradingAppConfig(
        snapshots_path=cfg.get('snapshots_path', 'snapshots'),
        max_snapshots_to_load=int(cfg.get('max_snapshots_to_load', 100)),
        s3=cfg.get('s3', {}),
        alerts=cfg.get('alerts', {'ma_window': 5, 'spike_threshold_pct': 20.0, 'drop_threshold_pct': 20.0}),
    )


# S3 Helpers

def get_s3_client(region_name: Optional[str]) -> boto3.client:
    if region_name:
        return boto3.client('s3', region_name=region_name)
    return boto3.client('s3')


def s3_list_objects(bucket: str, prefix: str, region: Optional[str]) -> List[str]:
    s3 = get_s3_client(region)
    keys: List[str] = []
    paginator = s3.get_paginator('list_objects_v2')
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get('Contents', []):
            key = obj.get('Key')
            if key and key.lower().endswith('.json'):
                keys.append(key)
    return keys


def s3_download_file(bucket: str, key: str, local_path: str, region: Optional[str]) -> None:
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    s3 = get_s3_client(region)
    s3.download_file(bucket, key, local_path)


# Snapshot loading and analysis

def list_local_snapshots(path: str, limit: Optional[int] = None) -> List[str]:
    """List snapshot files, sorted by modification time (newest first), optionally limited."""
    if not os.path.isdir(path):
        return []
    files = [
        os.path.join(path, f)
        for f in os.listdir(path)
        if f.lower().endswith('.json')
    ]
    # Sort by modification time, newest first
    files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    if limit and limit > 0:
        files = files[:limit]
    return files


def load_snapshot_file(path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def load_all_snapshots(local_path: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Load snapshots, optionally limited to most recent N files."""
    result: List[Dict[str, Any]] = []
    for fp in list_local_snapshots(local_path, limit=limit):
        snap = load_snapshot_file(fp)
        if snap and isinstance(snap.get('categories', {}), dict):
            result.append(snap)
    return result


def snapshots_to_dataframe(snapshots: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Convert snapshots to DataFrame, grouping OCR variants by their display name.
    
    Multiple OCR names (e.g., "Aviator Helmet", "Aviotor Helmet") will be combined
    into a single item for historical tracking if they map to the same display name.
    """
    rows: List[Dict[str, Any]] = []
    for snap in snapshots:
        ts = snap.get('timestamp')
        # Format: categories is a dict mapping category name to items list
        categories_data = snap.get('categories', {})
        for category, items in categories_data.items():
            for item in items:
                ocr_name = item.get('itemName')
                display_name = get_display_name(ocr_name)
                rows.append({
                    'timestamp': pd.to_datetime(ts, unit='s'),
                    'epoch': int(ts),
                    'category': category,
                    'ocrName': ocr_name,  # Keep for reference/debugging
                    'itemName': display_name,  # Use display name as the tracking identifier
                    'displayName': display_name,  # For backward compatibility
                    'price': float(item.get('price', 0)),
                })
    if not rows:
        return pd.DataFrame(columns=['timestamp', 'epoch', 'category', 'ocrName', 'itemName', 'displayName', 'price'])
    df = pd.DataFrame(rows)
    # Sort by display name (itemName) and time for historical analysis
    df.sort_values(['itemName', 'epoch'], inplace=True)
    return df


def add_indicators(df: pd.DataFrame, ma_window: int = 5) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    df['ma'] = df.groupby('itemName')['price'].transform(lambda s: s.rolling(ma_window, min_periods=1).mean())
    df['vol'] = df.groupby('itemName')['price'].transform(lambda s: s.rolling(ma_window, min_periods=2).std().fillna(0.0))
    return df


def find_alerts(df: pd.DataFrame, spike_pct: float, drop_pct: float) -> List[str]:
    alerts: List[str] = []
    if df.empty:
        return alerts
    latest = df.groupby('itemName').tail(1)
    for _, row in latest.iterrows():
        price = row['price']
        ma = row.get('ma', np.nan)
        if not np.isnan(ma) and ma > 0:
            delta_pct = (price - ma) / ma * 100.0
            if delta_pct >= spike_pct:
                alerts.append(f"Spike: {row['itemName']} +{delta_pct:.1f}% vs MA")
            elif delta_pct <= -drop_pct:
                alerts.append(f"Drop: {row['itemName']} {delta_pct:.1f}% vs MA")
    return alerts

