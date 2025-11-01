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
# Watchlist cache
_watchlist_data = None

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


def _display_mappings_path() -> Path:
    return Path(__file__).parent.parent / 'mappings' / 'display_mappings.json'


def _watchlist_path() -> Path:
    """Get the path to the watchlist.json file."""
    return Path(__file__).parent / 'watchlist.json'


def load_watchlist() -> List[str]:
    """Load the watchlist from watchlist.json, returning list of itemKeys."""
    global _watchlist_data
    if _watchlist_data is None:
        watchlist_file = _watchlist_path()
        if watchlist_file.exists():
            try:
                with open(watchlist_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Handle both old format (list) and new format (dict with items list)
                    if isinstance(data, dict):
                        _watchlist_data = data.get('items', [])
                    else:
                        _watchlist_data = data if isinstance(data, list) else []
            except Exception:
                _watchlist_data = []
        else:
            _watchlist_data = []
    return _watchlist_data.copy()


def save_watchlist(items: List[str]) -> None:
    """Save the watchlist to watchlist.json."""
    global _watchlist_data
    watchlist_file = _watchlist_path()
    watchlist_file.parent.mkdir(parents=True, exist_ok=True)
    # Save as JSON with items list
    data = {'items': items}
    with open(watchlist_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    _watchlist_data = items.copy()


def add_to_watchlist(item_key: str) -> None:
    """Add an item to the watchlist."""
    items = load_watchlist()
    if item_key not in items:
        items.append(item_key)
        save_watchlist(items)


def remove_from_watchlist(item_key: str) -> None:
    """Remove an item from the watchlist."""
    items = load_watchlist()
    if item_key in items:
        items.remove(item_key)
        save_watchlist(items)


def is_in_watchlist(item_key: str) -> bool:
    """Check if an item is in the watchlist."""
    items = load_watchlist()
    return item_key in items


def save_display_mapping(item_key: str, display_name: str) -> None:
    """Persist a display mapping update and refresh the in-memory cache."""
    global _display_mapping
    # Ensure cache is loaded
    mapping = load_display_mapping()
    mapping[item_key] = display_name
    path = _display_mappings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    # Write sorted for stability
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)
    # Refresh cache
    _display_mapping = mapping


def get_display_name(item_key: str) -> str:
    """Get the full display name for GUI from an exact item key.
    The key must match exactly what is in the mapping (including any #hash suffix).
    If no mapping is found, show the clean name portion to the user.
    """
    mapping = load_display_mapping()
    friendly = mapping.get(item_key)
    if friendly:
        return friendly
    # Fallback: return just the name portion after the category for display
    name_part = item_key.split(':', 1)[1] if ':' in item_key else item_key
    return name_part


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
                thumb_hash = item.get('thumbHash', '')
                # Derive filename from hash: thumbs/<hash>.png
                thumb_file = ''
                thumb_path = f"thumbs/{thumb_hash}.png" if thumb_hash else ''
                key_suffix = ("#" + thumb_hash) if thumb_hash else ""
                rows.append({
                    'timestamp': pd.to_datetime(ts, unit='s'),
                    'epoch': int(ts),
                    'category': category,
                    'itemName': clean_name,  # Clean name
                    'thumbHash': thumb_hash,
                    'thumbPath': thumb_path,
                    'price': float(item.get('price', 0)),
                    'itemKey': f"{category}:{clean_name}{key_suffix}",
                })
    if not rows:
        return pd.DataFrame(columns=['timestamp', 'epoch', 'category', 'itemName', 'thumbHash', 'thumbPath', 'price', 'itemKey', 'displayName'])
    df = pd.DataFrame(rows)
    # Add display names for GUI
    df['displayName'] = df['itemKey'].apply(get_display_name)
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
    # Relative volatility (% of MA). If MA == 0, set to 0 to avoid inf
    mask = df['ma'] > 0
    df['volPct'] = 0.0
    df.loc[mask, 'volPct'] = (df.loc[mask, 'vol'] / df.loc[mask, 'ma']) * 100.0
    return df


def find_alerts(df: pd.DataFrame, spike_pct: float, drop_pct: float) -> List[Dict[str, Any]]:
    alerts: List[Dict[str, Any]] = []
    if df.empty:
        return alerts
    # Group by itemKey to handle items with same name in different categories
    latest = df.groupby('itemKey').tail(1)
    for _, row in latest.iterrows():
        price = row['price']
        ma = row.get('ma', np.nan)
        if not np.isnan(ma) and ma > 0:
            delta_pct = (price - ma) / ma * 100.0
            # Prefer display name if present for cleaner alert text
            disp_name = row.get('displayName', row.get('itemName', ''))
            if delta_pct >= spike_pct:
                alerts.append({
                    'type': 'spike',
                    'text': f"{disp_name} +{delta_pct:.0f}%",
                    'delta': float(delta_pct),
                    'itemKey': row['itemKey'],
                    'category': row['category'],
                })
            elif delta_pct <= -drop_pct:
                alerts.append({
                    'type': 'drop',
                    'text': f"{disp_name} {delta_pct:.0f}%",
                    'delta': float(delta_pct),
                    'itemKey': row['itemKey'],
                    'category': row['category'],
                })
    return alerts


def find_top_volatility(df: pd.DataFrame, top_n: int = 10) -> List[Dict[str, Any]]:
    """Return top-N most volatile items using the latest row per itemKey.
    Vol is the rolling std dev over the MA window (computed in add_indicators)."""
    out: List[Dict[str, Any]] = []
    if df.empty:
        return out
    latest = df.groupby('itemKey').tail(1)
    latest = latest.copy()
    if 'vol' not in latest.columns:
        return out
    latest = latest.dropna(subset=['vol'])
    if latest.empty:
        return out
    # Prefer sorting by relative volatility if available
    sort_col = 'volPct' if 'volPct' in latest.columns else 'vol'
    latest.sort_values(sort_col, ascending=False, inplace=True)
    for _, row in latest.head(max(1, int(top_n))).iterrows():
        disp_name = row.get('displayName', row.get('itemName', ''))
        vol_val = float(row.get('vol', 0.0))
        vol_pct = float(row.get('volPct', 0.0)) if 'volPct' in row else 0.0
        out.append({
            'text': f"{disp_name} {vol_pct:.0f}%",
            'itemKey': row['itemKey'],
            'category': row['category'],
            'vol': vol_val,
            'volPct': vol_pct,
        })
    return out


def find_watchlist_items(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Return watchlist items formatted like find_alerts with delta percentage."""
    out: List[Dict[str, Any]] = []
    if df.empty:
        return out
    watchlist_keys = load_watchlist()
    if not watchlist_keys:
        return out
    # Get latest row per itemKey
    latest = df.groupby('itemKey').tail(1)
    latest = latest.copy()
    # Filter to only watchlist items
    latest = latest[latest['itemKey'].isin(watchlist_keys)]
    if latest.empty:
        return out
    # Compute delta% for each watchlist item
    for _, row in latest.iterrows():
        price = row['price']
        ma = row.get('ma', np.nan)
        disp_name = row.get('displayName', row.get('itemName', ''))
        if not np.isnan(ma) and ma > 0:
            delta_pct = (price - ma) / ma * 100.0
            # Determine type based on delta%
            item_type = 'flat'
            if delta_pct >= 0.1:
                item_type = 'spike'
            elif delta_pct <= -0.1:
                item_type = 'drop'
            out.append({
                'type': item_type,
                'text': f"{disp_name} {delta_pct:+.0f}%",
                'delta': float(delta_pct),
                'itemKey': row['itemKey'],
                'category': row['category'],
            })
        else:
            # No MA data, just show the item
            out.append({
                'type': 'flat',
                'text': disp_name,
                'delta': 0.0,
                'itemKey': row['itemKey'],
                'category': row['category'],
            })
    # Sort by delta descending to show gainers at top, losers at bottom
    out.sort(key=lambda x: x.get('delta', 0.0), reverse=True)
    return out

