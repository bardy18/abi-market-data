"""Trading app utilities for snapshot loading, analysis, and indicators."""
import os
import sys
import json
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from pathlib import Path

import yaml
import pandas as pd
import numpy as np


def resource_path(relative_path: str) -> Path:
    """Get absolute path to resource, works for dev and PyInstaller."""
    if getattr(sys, 'frozen', False):
        # Running as a PyInstaller bundle
        base_path = Path(sys._MEIPASS)
        return base_path / relative_path
    else:
        # Running as a script
        # If relative_path starts with a subdirectory, we need to go up from utils.py location
        base_path = Path(__file__).parent.parent
        return base_path / relative_path


# Display name mapping cache
_display_mapping = None
# Watchlist removed; trades replace it
# Trades cache
_trades_data: Optional[List[Dict[str, Any]]] = None
# Blacklist cache
_blacklist_data = None

def load_display_mapping() -> Dict[str, str]:
    """Load the display to friendly name mapping from display_mappings.json"""
    global _display_mapping
    if _display_mapping is None:
        mapping_file = resource_path('mappings/display_mappings.json')
        if mapping_file.exists():
            with open(mapping_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Filter out comment entries
                _display_mapping = {k: v for k, v in data.items() if not k.startswith('_')}
        else:
            _display_mapping = {}
    return _display_mapping


def _display_mappings_path() -> Path:
    return resource_path('mappings/display_mappings.json')


def _trades_path() -> Path:
    """Path to the trades.json file."""
    return Path(__file__).parent / 'trades.json'


# All watchlist helpers removed


# Trades management

TRADE_STATUSES = [
    "1 - Purchased",
    "2 - In Transit",
    "3 - Stored",
    "4 - For Sale",
    "5 - Sold",
    "6 - Lost",
]


def _status_sort_key(status: str) -> int:
    try:
        # expects leading number then ' - '
        num = int(str(status).split('-', 1)[0].strip())
        return num
    except Exception:
        return 999


def load_trades() -> List[Dict[str, Any]]:
    """Load trades from trades.json (list of trade dicts)."""
    global _trades_data
    if _trades_data is None:
        fp = _trades_path()
        if fp.exists():
            try:
                with open(fp, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    _trades_data = data if isinstance(data, list) else []
            except Exception:
                _trades_data = []
        else:
            _trades_data = []
    return [dict(t) for t in _trades_data]


def save_trades(trades: List[Dict[str, Any]]) -> None:
    """Persist all trades to trades.json and update cache."""
    global _trades_data
    fp = _trades_path()
    fp.parent.mkdir(parents=True, exist_ok=True)
    # Normalize/sort for stable file ordering: by status then name
    # Persist ONLY minimal fields; derived metrics are computed in the UI
    keep_keys = {'itemKey', 'quantity', 'expense', 'income', 'status'}
    norm: List[Dict[str, Any]] = []
    for t in trades:
        tc = {k: v for k, v in dict(t).items() if k in keep_keys}
        tc.setdefault('status', TRADE_STATUSES[0])
        tc.setdefault('quantity', 0)
        tc.setdefault('expense', 0.0)
        tc.setdefault('income', 0.0)
        # itemKey required for identification/display
        tc.setdefault('itemKey', '')
        norm.append(tc)
    norm.sort(key=lambda x: (_status_sort_key(x.get('status', '')), str(x.get('displayName') or x.get('itemKey') or '')))
    with open(fp, 'w', encoding='utf-8') as f:
        json.dump(norm, f, ensure_ascii=False, indent=2)
    _trades_data = norm


def add_trade(item_key: str, display_name: str, quantity: int, expense_total: float, status: str = TRADE_STATUSES[0]) -> Dict[str, Any]:
    """Add a new trade and return it."""
    trades = load_trades()
    trade = {
        'itemKey': item_key,
        'quantity': int(quantity),
        'expense': float(expense_total),
        'status': status,
        'income': 0.0,
    }
    trades.append(trade)
    save_trades(trades)
    return trade


def update_trade(item_key: str, updates: Dict[str, Any]) -> None:
    trades = load_trades()
    changed = False
    for t in trades:
        if t.get('itemKey') == item_key:
            t.update(updates)
            changed = True
            break
    if changed:
        save_trades(trades)


def list_active_trades() -> List[Dict[str, Any]]:
    statuses = set(TRADE_STATUSES[:4])
    return [t for t in load_trades() if t.get('status') in statuses]


def list_completed_trades() -> List[Dict[str, Any]]:
    statuses = set(TRADE_STATUSES[4:])
    return [t for t in load_trades() if t.get('status') in statuses]


def _blacklist_path() -> Path:
    """Get the path to the blacklist.json file."""
    return Path(__file__).parent / 'blacklist.json'


def load_blacklist() -> List[str]:
    """Load the blacklist from blacklist.json, returning list of itemKeys."""
    global _blacklist_data
    if _blacklist_data is None:
        blacklist_file = _blacklist_path()
        if blacklist_file.exists():
            try:
                with open(blacklist_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Handle both old format (list) and new format (dict with items list)
                    if isinstance(data, dict):
                        _blacklist_data = data.get('items', [])
                    else:
                        _blacklist_data = data if isinstance(data, list) else []
            except Exception:
                _blacklist_data = []
        else:
            _blacklist_data = []
    return _blacklist_data.copy()


def save_blacklist(items: List[str]) -> None:
    """Save the blacklist to blacklist.json."""
    global _blacklist_data
    blacklist_file = _blacklist_path()
    blacklist_file.parent.mkdir(parents=True, exist_ok=True)
    # Save as JSON with items list
    data = {'items': items}
    with open(blacklist_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    _blacklist_data = items.copy()


def add_to_blacklist(item_key: str) -> None:
    """Add an item to the blacklist."""
    items = load_blacklist()
    if item_key not in items:
        items.append(item_key)
        save_blacklist(items)


def remove_from_blacklist(item_key: str) -> None:
    """Remove an item from the blacklist."""
    items = load_blacklist()
    if item_key in items:
        items.remove(item_key)
        save_blacklist(items)


def is_blacklisted(item_key: str) -> bool:
    """Check if an item is in the blacklist."""
    items = load_blacklist()
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

def load_s3_config() -> Optional[Dict[str, Any]]:
    """Load S3 configuration with priority: env vars > config file > embedded defaults."""
    import os
    from pathlib import Path
    
    # Try environment variables first (for development/testing)
    bucket = os.getenv('S3_BUCKET_NAME')
    if bucket:
        config = {
            'bucket': bucket,
            'region': os.getenv('AWS_REGION', 'us-east-1'),
            'key_prefix': os.getenv('S3_KEY_PREFIX', 'snapshots/'),
            'use_s3': True,
        }
        # Add credentials if provided via env
        access_key = os.getenv('AWS_ACCESS_KEY_ID')
        secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        if access_key and secret_key:
            config['access_key'] = access_key
            config['secret_key'] = secret_key
        return config
    
    # Try config file (for users who want to override embedded credentials)
    # Check packaging folder first, then root (for backward compatibility)
    project_root = Path(__file__).parent.parent
    config_paths = [
        project_root / 'packaging' / 's3_config.json',  # Preferred location
        project_root / 's3_config.json',  # Fallback for backward compatibility
    ]
    
    for config_path in config_paths:
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    config['use_s3'] = True
                    config.setdefault('key_prefix', 'snapshots/')
                    # Normalize: map snapshots_bucket to bucket for internal use
                    if 'snapshots_bucket' in config:
                        config['bucket'] = config['snapshots_bucket']
                    return config
            except Exception:
                continue
    
    # Try embedded default credentials (for distributed executable)
    try:
        from trading_app import s3_config
        embedded_config = s3_config.get_default_s3_config()
        if embedded_config:
            return embedded_config
    except Exception:
        pass
    
    return None


def list_s3_snapshots(s3_config: Dict[str, Any], limit: Optional[int] = None) -> List[str]:
    """List snapshot files from S3, sorted by modification time (newest first)."""
    try:
        import boto3
        from botocore.exceptions import ClientError
        
        # Create S3 client - works without credentials for public buckets
        region = s3_config.get('region', 'us-east-1')
        access_key = s3_config.get('access_key')
        secret_key = s3_config.get('secret_key')
        
        if access_key and secret_key:
            s3_client = boto3.client(
                's3',
                region_name=region,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
            )
        else:
            # Try without credentials (for public buckets)
            s3_client = boto3.client('s3', region_name=region)
        
        bucket = s3_config['bucket']
        prefix = s3_config.get('key_prefix', 'snapshots/')
        
        # List objects with prefix
        paginator = s3_client.get_paginator('list_objects_v2')
        files = []
        
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            if 'Contents' in page:
                for obj in page['Contents']:
                    key = obj['Key']
                    if key.lower().endswith('.json'):
                        # Extract filename
                        filename = os.path.basename(key)
                        files.append((filename, obj['LastModified'].timestamp()))
        
        # Sort by modification time, newest first (reverse=True means newest timestamps first)
        files.sort(key=lambda x: x[1], reverse=True)
        
        # Apply limit to get only the newest N snapshots
        if limit and limit > 0:
            files = files[:limit]  # Take first N (newest) files
        
        return [f[0] for f in files]
    except Exception as e:
        print(f"[!] Error listing S3 snapshots: {e}")
        return []


def load_snapshot_from_s3(s3_config: Dict[str, Any], filename: str) -> Optional[Dict[str, Any]]:
    """Load a snapshot file directly from S3 into memory (no disk caching)."""
    try:
        import boto3
        
        # Create S3 client - works without credentials for public buckets
        region = s3_config.get('region', 'us-east-1')
        access_key = s3_config.get('access_key')
        secret_key = s3_config.get('secret_key')
        
        if access_key and secret_key:
            s3_client = boto3.client(
                's3',
                region_name=region,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
            )
        else:
            # Try without credentials (for public buckets)
            s3_client = boto3.client('s3', region_name=region)
        
        bucket = s3_config['bucket']
        prefix = s3_config.get('key_prefix', 'snapshots/')
        s3_key = f"{prefix}{filename}"
        
        # Download file content directly to memory
        response = s3_client.get_object(Bucket=bucket, Key=s3_key)
        content = response['Body'].read()
        
        # Parse JSON from memory
        return json.loads(content.decode('utf-8'))
    except Exception as e:
        print(f"[!] Error loading {filename} from S3: {e}")
        return None


def download_thumbnail_from_s3(s3_config: Dict[str, Any], thumb_hash: str, local_path: str) -> bool:
    """Download a thumbnail image from S3 to local path."""
    try:
        import boto3
        from pathlib import Path
        
        # Create S3 client - works without credentials for public buckets
        region = s3_config.get('region', 'us-east-1')
        access_key = s3_config.get('access_key')
        secret_key = s3_config.get('secret_key')
        
        if access_key and secret_key:
            s3_client = boto3.client(
                's3',
                region_name=region,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
            )
        else:
            # Try without credentials (for public buckets)
            s3_client = boto3.client('s3', region_name=region)
        
        bucket = s3_config['bucket']
        prefix = s3_config.get('key_prefix', 'snapshots/')
        # Thumbnail path in S3: snapshots/thumbs/<hash>.png
        s3_key = f"{prefix}thumbs/{thumb_hash}.png"
        
        # Ensure local directory exists
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Download file
        s3_client.download_file(bucket, s3_key, local_path)
        return True
    except Exception as e:
        # Silently fail - thumbnail might not exist for this item
        return False


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
    """Load snapshots from S3 (if configured) directly into memory, or from local files.
    
    Note: When S3 is configured, snapshots are loaded directly into memory without disk caching
    to protect data. Only thumbnails are cached to disk for performance.
    Local snapshots are only used when S3 is not configured (for development/data collection).
    """
    result: List[Dict[str, Any]] = []
    
    # Check if S3 is configured - if so, load only from S3 (no local files)
    s3_config = load_s3_config()
    if s3_config and s3_config.get('use_s3'):
        try:
            # List S3 snapshots (already sorted newest first)
            s3_files = list_s3_snapshots(s3_config, limit=limit)
            
            for filename in s3_files:
                # Load snapshot directly from S3 into memory (no disk caching)
                snap = load_snapshot_from_s3(s3_config, filename)
                if snap and isinstance(snap.get('categories', {}), dict):
                    result.append(snap)
        except Exception as e:
            print(f"[!] S3 load failed: {e}")
            # Don't fall back to local - if S3 is configured, we should use S3 only
    else:
        # S3 not configured - load from local files (for development/data collection)
        local_files = list_local_snapshots(local_path, limit=limit)
        for fp in local_files:
            snap = load_snapshot_file(fp)
            if snap and isinstance(snap.get('categories', {}), dict):
                result.append(snap)
    
    # Sort by timestamp, newest first, and apply limit
    result.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
    if limit and limit > 0:
        result = result[:limit]
    
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
    
    # Price range: highest and lowest prices across all historical data
    df['priceHigh'] = df.groupby('itemKey')['price'].transform('max')
    df['priceLow'] = df.groupby('itemKey')['price'].transform('min')
    df['priceRange'] = df['priceHigh'] - df['priceLow']
    # Price range as percentage of current price (for relative comparison)
    mask_range = df['price'] > 0
    df['priceRangePct'] = 0.0
    df.loc[mask_range, 'priceRangePct'] = (df.loc[mask_range, 'priceRange'] / df.loc[mask_range, 'price']) * 100.0
    
    return df


def find_alerts(df: pd.DataFrame, spike_pct: float, drop_pct: float) -> List[Dict[str, Any]]:
    alerts: List[Dict[str, Any]] = []
    if df.empty:
        return alerts
    # Filter out blacklisted items
    blacklisted_keys = set(load_blacklist())
    if blacklisted_keys and 'itemKey' in df.columns:
        df = df[~df['itemKey'].isin(blacklisted_keys)]
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


# find_watchlist_items removed; use find_trades_items


def find_trades_items(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Return active trades with MA delta like alerts for the left widget.
    Sorted with biggest gainers at the top (descending by delta)."""
    out: List[Dict[str, Any]] = []
    if df.empty:
        return out
    trade_keys = {t.get('itemKey') for t in list_active_trades()}
    if not trade_keys:
        return out
    # Filter out blacklisted items first
    blacklisted_keys = set(load_blacklist())
    if blacklisted_keys and 'itemKey' in df.columns:
        df = df[~df['itemKey'].isin(blacklisted_keys)]
    latest = df.groupby('itemKey').tail(1).copy()
    latest = latest[latest['itemKey'].isin(trade_keys)]
    if latest.empty:
        return out
    for _, row in latest.iterrows():
        price = row['price']
        ma = row.get('ma', np.nan)
        disp_name = row.get('displayName', row.get('itemName', ''))
        if not np.isnan(ma) and ma > 0:
            delta_pct = (price - ma) / ma * 100.0
            ttype = 'spike' if delta_pct >= 0.1 else ('drop' if delta_pct <= -0.1 else 'flat')
            out.append({
                'type': ttype,
                'text': f"{disp_name} {delta_pct:+.0f}%",
                'delta': float(delta_pct),
                'itemKey': row['itemKey'],
                'category': row['category'],
            })
        else:
            out.append({
                'type': 'flat',
                'text': disp_name,
                'delta': 0.0,
                'itemKey': row['itemKey'],
                'category': row['category'],
            })
    out.sort(key=lambda x: x.get('delta', 0.0), reverse=True)
    return out

