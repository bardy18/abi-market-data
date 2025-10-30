"""Trading app utilities for snapshot loading, analysis, and indicators."""
import os
import json
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from pathlib import Path

import yaml
import pandas as pd
import numpy as np


# Display name mapping cache
_display_mapping = None

def load_display_mapping() -> Dict[str, str]:
    """Load the display to friendly name mapping from display_mappings.json"""
    global _display_mapping
    if _display_mapping is None:
        mapping_file = Path(__file__).parent.parent / 'mappings' / 'display_mappings.json'
        if mapping_file.exists():
            with open(mapping_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Filter out comment entries
                _display_mapping = {k: v for k, v in data.items() if not k.startswith('_')}
        else:
            _display_mapping = {}
    return _display_mapping


def get_display_name(item_key: str) -> str:
    """
    Get the full display name for GUI from an item key.
    
    Args:
        item_key: Composite key in format "category:cleanName"
    
    Returns:
        Full display name if mapped, otherwise returns the clean name part
    """
    mapping = load_display_mapping()
    friendly = mapping.get(item_key)
    if friendly:
        return friendly
    # Fallback: return just the display name without category prefix
    if ':' in item_key:
        return item_key.split(':', 1)[1]
    return item_key


@dataclass
class TradingAppConfig:
    snapshots_path: str
    max_snapshots_to_load: int
    alerts: Dict[str, Any]


def load_config(path: str) -> TradingAppConfig:
    with open(path, 'r', encoding='utf-8') as f:
        cfg = yaml.safe_load(f)
    return TradingAppConfig(
        snapshots_path=cfg.get('snapshots_path', 'snapshots'),
        max_snapshots_to_load=int(cfg.get('max_snapshots_to_load', 100)),
        alerts=cfg.get('alerts', {'ma_window': 5, 'spike_threshold_pct': 20.0, 'drop_threshold_pct': 20.0}),
    )


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
    
    Items are uniquely identified by category + display name to handle truncated
    names (e.g., "SH40 Tactical..." can exist in both Helmet and Body Armor categories).
    """
    rows: List[Dict[str, Any]] = []
    for snap in snapshots:
        ts = snap.get('timestamp')
        # Format: categories is a dict mapping category name to items list
        categories_data = snap.get('categories', {})
        for category, items in categories_data.items():
            for item in items:
                clean_name = item.get('itemName')  # Already clean from snapshot
                rows.append({
                    'timestamp': pd.to_datetime(ts, unit='s'),
                    'epoch': int(ts),
                    'category': category,
                    'itemName': clean_name,  # Use clean name as the tracking identifier
                    'price': float(item.get('price', 0)),
                })
    if not rows:
        return pd.DataFrame(columns=['timestamp', 'epoch', 'category', 'itemName', 'price', 'itemKey', 'friendlyName'])
    df = pd.DataFrame(rows)
    # Create composite key for unique identification (handles truncated names across categories)
    df['itemKey'] = df['category'] + ':' + df['itemName']
    # Add friendly names for GUI display
    df['friendlyName'] = df['itemKey'].apply(get_display_name)
    # Sort by item key and time for historical analysis
    df.sort_values(['itemKey', 'epoch'], inplace=True)
    return df


def add_indicators(df: pd.DataFrame, ma_window: int = 5) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    # Group by itemKey (category:itemName) to handle items with same name in different categories
    df['ma'] = df.groupby('itemKey')['price'].transform(lambda s: s.rolling(ma_window, min_periods=1).mean())
    df['vol'] = df.groupby('itemKey')['price'].transform(lambda s: s.rolling(ma_window, min_periods=2).std().fillna(0.0))
    return df


def find_alerts(df: pd.DataFrame, spike_pct: float, drop_pct: float) -> List[str]:
    alerts: List[str] = []
    if df.empty:
        return alerts
    # Group by itemKey to handle items with same name in different categories
    latest = df.groupby('itemKey').tail(1)
    for _, row in latest.iterrows():
        price = row['price']
        ma = row.get('ma', np.nan)
        if not np.isnan(ma) and ma > 0:
            delta_pct = (price - ma) / ma * 100.0
            if delta_pct >= spike_pct:
                alerts.append(f"Spike: [{row['category']}] {row['itemName']} +{delta_pct:.1f}% vs MA")
            elif delta_pct <= -drop_pct:
                alerts.append(f"Drop: [{row['category']}] {row['itemName']} {delta_pct:.1f}% vs MA")
    return alerts

