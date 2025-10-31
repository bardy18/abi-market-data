"""ABI Market Trading App - Main GUI application."""
import sys
import os
from pathlib import Path
from datetime import datetime, timezone

try:
    from zoneinfo import ZoneInfo
except ImportError:
    # Fallback for Python < 3.9
    try:
        from backports.zoneinfo import ZoneInfo
    except ImportError:
        # Fallback to pytz if available
        try:
            import pytz
            ZoneInfo = lambda tz: pytz.timezone(tz)
        except ImportError:
            ZoneInfo = None

import pandas as pd
import numpy as np
from PySide6 import QtWidgets, QtCore, QtGui
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
try:
    import mplcursors
    MPLCURSORS_AVAILABLE = True
except ImportError:
    MPLCURSORS_AVAILABLE = False

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from trading_app import utils


class TrendChart(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)  # Enable mouse tracking for hover events
        self.figure = Figure(figsize=(6, 4), facecolor='#0e1116')
        self.canvas = FigureCanvas(self.figure)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.canvas)
        # Store data points for hover lookup
        self._data_points = {}  # Dict mapping index to (ts, price, dt_str)
        self._scatter = None
        self._cursor = None  # mplcursors cursor object
        self._ax = None

    def plot(self, df: pd.DataFrame, item_key: str, display_name: str = None) -> None:
        """
        Plot price history for an item.
        
        Args:
            df: Full dataframe
            item_key: Composite key "category:itemName" for unique item identification
            display_name: Optional display name for chart title
        """
        self.figure.clear()
        self._data_points = {}
        self._scatter = None
        # Remove old cursor if exists
        if self._cursor is not None:
            try:
                self._cursor.remove()
            except Exception:
                pass
            self._cursor = None
        ax = self.figure.add_subplot(111, facecolor='#0e1116')
        self._ax = ax
        if df.empty:
            ax.set_title('No data', color='#d0d4dc')
        else:
            # Filter by itemKey to handle items with same name in different categories
            dfi = df[df['itemKey'] == item_key] if 'itemKey' in df.columns else df[df['itemName'] == item_key]
            if dfi.empty:
                ax.set_title(f'No data for {display_name or item_key}')
            else:
                # Sort by timestamp for proper plotting
                dfi = dfi.sort_values('timestamp')
                # Modern styled lines (no labels since legend is removed)
                ax.plot(dfi['timestamp'], dfi['price'], color='#4cc9f0', lw=2, zorder=1)
                if 'ma' in dfi.columns:
                    ax.plot(dfi['timestamp'], dfi['ma'], color='#f72585', lw=1.8, linestyle='--', zorder=1)
                # Add scatter points for hover interaction
                self._scatter = ax.scatter(dfi['timestamp'], dfi['price'], s=60, color='#4cc9f0', 
                                           edgecolors='#0e1116', linewidths=1.5, zorder=2, alpha=0.8,
                                           picker=True, pickradius=5)
                # Store data points for hover lookup (dict mapping index to (ts, price, dt_str))
                self._data_points = {}
                # Get Eastern timezone
                eastern_tz = None
                if ZoneInfo:
                    try:
                        eastern_tz = ZoneInfo('America/New_York')
                    except Exception:
                        pass
                
                for idx, (_, row) in enumerate(dfi.iterrows()):
                    ts_raw = row['timestamp']
                    price = float(row['price'])
                    # Convert timestamp to numeric for matplotlib transforms
                    if isinstance(ts_raw, pd.Timestamp):
                        dt = ts_raw.to_pydatetime()
                        ts_num = dt.timestamp()
                        # Convert to Eastern Time and format with AM/PM
                        if eastern_tz:
                            try:
                                # If timestamp has timezone, convert it; otherwise assume UTC
                                if ts_raw.tz is not None:
                                    dt_eastern = ts_raw.tz_convert('America/New_York')
                                else:
                                    dt_eastern = ts_raw.tz_localize('UTC').tz_convert('America/New_York')
                                # Format without leading zero on hour and no seconds
                                hour = dt_eastern.hour % 12 or 12  # Convert to 12-hour, 0 becomes 12
                                minute = dt_eastern.minute
                                am_pm = dt_eastern.strftime('%p')
                                tz_abbr = dt_eastern.strftime('%Z')
                                dt_str = f"{dt_eastern.strftime('%Y-%m-%d')} {hour}:{minute:02d} {am_pm} {tz_abbr}"
                            except Exception:
                                # Fallback to original format if conversion fails
                                hour = ts_raw.hour % 12 or 12
                                minute = ts_raw.minute
                                am_pm = ts_raw.strftime('%p')
                                dt_str = f"{ts_raw.strftime('%Y-%m-%d')} {hour}:{minute:02d} {am_pm}"
                        else:
                            hour = ts_raw.hour % 12 or 12
                            minute = ts_raw.minute
                            am_pm = ts_raw.strftime('%p')
                            dt_str = f"{ts_raw.strftime('%Y-%m-%d')} {hour}:{minute:02d} {am_pm}"
                    elif isinstance(ts_raw, (int, float)):
                        ts_num = float(ts_raw)
                        dt = datetime.fromtimestamp(ts_num)
                        # Convert to Eastern Time
                        if eastern_tz:
                            try:
                                # Assume UTC if no timezone info
                                dt_utc = datetime.fromtimestamp(ts_num, tz=timezone.utc)
                                dt_eastern = dt_utc.astimezone(eastern_tz)
                                hour = dt_eastern.hour % 12 or 12
                                minute = dt_eastern.minute
                                am_pm = dt_eastern.strftime('%p')
                                tz_abbr = dt_eastern.strftime('%Z')
                                dt_str = f"{dt_eastern.strftime('%Y-%m-%d')} {hour}:{minute:02d} {am_pm} {tz_abbr}"
                            except Exception:
                                hour = dt.hour % 12 or 12
                                minute = dt.minute
                                am_pm = dt.strftime('%p')
                                dt_str = f"{dt.strftime('%Y-%m-%d')} {hour}:{minute:02d} {am_pm}"
                        else:
                            hour = dt.hour % 12 or 12
                            minute = dt.minute
                            am_pm = dt.strftime('%p')
                            dt_str = f"{dt.strftime('%Y-%m-%d')} {hour}:{minute:02d} {am_pm}"
                    elif isinstance(ts_raw, datetime):
                        ts_num = ts_raw.timestamp()
                        if eastern_tz and ts_raw.tzinfo is not None:
                            try:
                                dt_eastern = ts_raw.astimezone(eastern_tz)
                                hour = dt_eastern.hour % 12 or 12
                                minute = dt_eastern.minute
                                am_pm = dt_eastern.strftime('%p')
                                tz_abbr = dt_eastern.strftime('%Z')
                                dt_str = f"{dt_eastern.strftime('%Y-%m-%d')} {hour}:{minute:02d} {am_pm} {tz_abbr}"
                            except Exception:
                                hour = ts_raw.hour % 12 or 12
                                minute = ts_raw.minute
                                am_pm = ts_raw.strftime('%p')
                                dt_str = f"{ts_raw.strftime('%Y-%m-%d')} {hour}:{minute:02d} {am_pm}"
                        else:
                            hour = ts_raw.hour % 12 or 12
                            minute = ts_raw.minute
                            am_pm = ts_raw.strftime('%p')
                            dt_str = f"{ts_raw.strftime('%Y-%m-%d')} {hour}:{minute:02d} {am_pm}"
                    else:
                        try:
                            # Try to convert to numeric
                            ts_num = float(ts_raw)
                            dt = datetime.fromtimestamp(ts_num)
                            if eastern_tz:
                                try:
                                    dt_utc = datetime.fromtimestamp(ts_num, tz=timezone.utc)
                                    dt_eastern = dt_utc.astimezone(eastern_tz)
                                    hour = dt_eastern.hour % 12 or 12
                                    minute = dt_eastern.minute
                                    am_pm = dt_eastern.strftime('%p')
                                    tz_abbr = dt_eastern.strftime('%Z')
                                    dt_str = f"{dt_eastern.strftime('%Y-%m-%d')} {hour}:{minute:02d} {am_pm} {tz_abbr}"
                                except Exception:
                                    hour = dt.hour % 12 or 12
                                    minute = dt.minute
                                    am_pm = dt.strftime('%p')
                                    dt_str = f"{dt.strftime('%Y-%m-%d')} {hour}:{minute:02d} {am_pm}"
                            else:
                                hour = dt.hour % 12 or 12
                                minute = dt.minute
                                am_pm = dt.strftime('%p')
                                dt_str = f"{dt.strftime('%Y-%m-%d')} {hour}:{minute:02d} {am_pm}"
                        except (ValueError, TypeError):
                            ts_num = 0.0
                            dt_str = str(ts_raw)
                    self._data_points[idx] = (ts_num, price, dt_str)
                
                # Set up hover tooltips using mplcursors if available
                if MPLCURSORS_AVAILABLE:
                    # Disconnect old cursor if exists
                    if self._cursor is not None:
                        self._cursor.remove()
                    
                    # Create cursor for scatter plot with custom tooltip
                    # Use click mode - tooltips appear on click and can be toggled
                    self._cursor = mplcursors.cursor(
                        self._scatter,
                        hover=False,  # Use click mode instead
                        highlight=True,
                        multiple=False  # Only show one tooltip at a time
                    )
                    
                    # Custom formatter for tooltips - need to capture self in closure
                    data_points = self._data_points  # Capture for closure
                    canvas = self.canvas  # Capture for redraw
                    
                    def on_add(sel):
                        idx = sel.index
                        if idx in data_points:
                            ts, price, dt_str = data_points[idx]
                            ann = sel.annotation
                            
                            # Store custom text elements on annotation for cleanup
                            if not hasattr(ann, '_custom_texts'):
                                ann._custom_texts = []
                            # Remove old custom texts if they exist
                            for txt in ann._custom_texts:
                                try:
                                    txt.remove()
                                except:
                                    pass
                            ann._custom_texts.clear()
                            
                            # Clear default annotation text
                            ann.set_text('')
                            
                            # Style the annotation box first
                            ann.set_bbox(dict(boxstyle='round,pad=0.8', 
                                              facecolor='#121621', 
                                              edgecolor='#4a5568', 
                                              linewidth=1.5,
                                              alpha=0.98))
                            # Update arrow props if they exist
                            try:
                                ann.arrowprops.update(dict(arrowstyle='->', 
                                                           connectionstyle='arc3,rad=0',
                                                           color='#4a5568', 
                                                           linewidth=1.5))
                            except AttributeError:
                                pass
                            
                            # Show only price in tooltip (no date/time - that's on x-axis now)
                            ann.set_text(f"${price:,.0f}")
                            
                            # Style for price prominence - larger, bold
                            ann.set_fontsize(15)  # Larger font for price
                            ann.set_weight('bold')  # Bold for emphasis
                            ann.set_color('#d0d4dc')  # Bright color
                            
                            canvas.draw_idle()
                    
                    def on_remove(sel):
                        # Clean up custom text elements if they exist
                        if hasattr(sel.annotation, '_custom_texts'):
                            for txt in sel.annotation._custom_texts:
                                try:
                                    txt.remove()
                                except:
                                    pass
                            sel.annotation._custom_texts.clear()
                        # Force redraw when tooltip is removed to ensure it disappears
                        canvas.draw_idle()
                    
                    # Track current selection to allow toggling
                    current_selection = None
                    current_selection_idx = None  # Track the index separately
                    cursor_obj = self._cursor  # Capture cursor for removal
                    
                    def on_add_with_tracking(sel):
                        nonlocal current_selection, current_selection_idx  # Allow modifying the outer variable
                        
                        # If clicking the same point that already has a tooltip, toggle it off
                        if current_selection_idx is not None and current_selection_idx == sel.index:
                            # Toggle off - hide both the old and new selection
                            try:
                                # Hide the old selection if it still exists
                                if current_selection and current_selection.annotation:
                                    current_selection.annotation.set_visible(False)
                                    cursor_obj.remove_selection(current_selection)
                            except (AttributeError, ValueError, KeyError):
                                pass
                            
                            # Hide the new selection too (since mplcursors already created it)
                            try:
                                if sel.annotation:
                                    sel.annotation.set_visible(False)
                                cursor_obj.remove_selection(sel)
                            except (AttributeError, ValueError, KeyError):
                                try:
                                    if sel.annotation:
                                        sel.annotation.set_visible(False)
                                except AttributeError:
                                    pass
                            
                            current_selection = None
                            current_selection_idx = None
                            canvas.draw_idle()
                            return  # Don't show the tooltip
                        
                        # Track the selection and show it
                        if current_selection:
                            # Hide previous selection first
                            try:
                                prev_ann = current_selection.annotation
                                if prev_ann:
                                    prev_ann.set_visible(False)
                                cursor_obj.remove_selection(current_selection)
                            except (AttributeError, ValueError, KeyError):
                                # Fallback: just hide annotation
                                try:
                                    if current_selection.annotation:
                                        current_selection.annotation.set_visible(False)
                                except AttributeError:
                                    pass
                        
                        current_selection = sel
                        current_selection_idx = sel.index
                        on_add(sel)
                    
                    def on_remove_with_tracking(sel):
                        nonlocal current_selection, current_selection_idx  # Allow modifying the outer variable
                        # Remove from tracking when selection is removed
                        if current_selection == sel:
                            current_selection = None
                            current_selection_idx = None
                        on_remove(sel)
                    
                    self._cursor.connect("add", on_add_with_tracking)
                    self._cursor.connect("remove", on_remove_with_tracking)
                else:
                    # Fallback: manual hover (may not work reliably)
                    print("Warning: mplcursors not available. Hover tooltips may not work.")
                    print("Install with: pip install mplcursors")
                # Extract category and name for title if display_name not provided
                if not display_name and ':' in item_key:
                    category, name = item_key.split(':', 1)
                    title = ax.set_title(name, color='#d0d4dc', fontweight='bold', pad=15)
                else:
                    title = ax.set_title(display_name or item_key, color='#d0d4dc', fontweight='bold', pad=15)
                
                # Axes styling
                ax.set_xlabel('Time', color='#9aa4b2')
                ax.set_ylabel('')  # Remove y-axis title
                ax.tick_params(colors='#9aa4b2')
                
                # Format y-axis to show prices with commas
                from matplotlib.ticker import FuncFormatter
                def format_price(x, pos=None):
                    """Format price labels with commas"""
                    return f"{x:,.0f}"
                ax.yaxis.set_major_formatter(FuncFormatter(format_price))
                
                # Remove x-axis tick labels - just show "Time" label
                ax.set_xticklabels([])
                
                for spine in ['top', 'right', 'left', 'bottom']:
                    ax.spines[spine].set_color('#2a2f3a')
                ax.grid(True, color='#2a2f3a', alpha=0.6, linestyle='--', linewidth=0.8)
                # Legend removed for cleaner look
        self.canvas.draw_idle()


class DataTable(QtWidgets.QTableView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.model_ = QtGui.QStandardItemModel(self)
        self.setModel(self.model_)
        # Use a dedicated numeric sort role to avoid display text interference
        self.sort_role = int(QtCore.Qt.UserRole) + 5
        self.model_.setSortRole(self.sort_role)
        self.setSortingEnabled(True)
        # Icons are not used in the move column; rely on text color only
        # Disable in-place editing; changes must go through mapping dialog
        self.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        # Select whole rows only; single selection
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        # Ensure header sorting drives model sorting by our numeric role
        try:
            header = self.horizontalHeader()
            header.setSortIndicatorShown(True)
            header.sortIndicatorChanged.connect(lambda section, order: self.model_.sort(section, order))
        except Exception:
            pass

    def load(self, df: pd.DataFrame) -> None:
        self.model_.clear()
        headers = ['category', 'item', 'move', 'price', 'ma', 'vol', 'vol%']
        self.model_.setHorizontalHeaderLabels(headers)
        for _, row in df.iterrows():
            items = []
            # Category with case-insensitive sort key
            cat_text = str(row['category'])
            cat_item = QtGui.QStandardItem(cat_text)
            try:
                cat_item.setData(cat_text.lower(), self.sort_role)
            except Exception:
                pass
            items.append(cat_item)
            # Show display name in GUI if available, otherwise clean name
            display_name = row.get('displayName', row.get('itemName', ''))
            name_item = QtGui.QStandardItem(str(display_name))
            # Provide a case-insensitive sort key for proper alpha sorting
            try:
                name_item.setData(str(display_name).lower(), self.sort_role)
            except Exception:
                pass
            items.append(name_item)
            # Status/move column: icon + delta text
            price_val = float(row['price']) if not pd.isna(row['price']) else float('nan')
            ma_val = row.get('ma', np.nan)
            delta_pct = float('nan')
            if not pd.isna(ma_val) and ma_val != 0:
                delta_pct = (price_val - float(ma_val)) / float(ma_val) * 100.0
            # Determine direction
            direction = 'flat'
            if not pd.isna(delta_pct):
                if delta_pct >= 0.1:
                    direction = 'up'
                elif delta_pct <= -0.1:
                    direction = 'down'
            # Create item with icon and text
            move_item = QtGui.QStandardItem(f"{delta_pct:+.1f}%" if not pd.isna(delta_pct) else '')
            # Numeric sort key for move column (separate role)
            move_item.setData(float(delta_pct) if not pd.isna(delta_pct) else 0.0, self.sort_role)
            # Choose color by direction
            if direction == 'up':
                color = QtGui.QColor(0, 150, 0)
                move_item.setForeground(QtGui.QBrush(color))
            elif direction == 'down':
                color = QtGui.QColor(180, 0, 0)
                move_item.setForeground(QtGui.QBrush(color))
            else:
                color = QtGui.QColor(128, 128, 128)
                move_item.setForeground(QtGui.QBrush(color))
            items.append(move_item)
            # Price (money) - display text with commas, but store numeric for sorting
            price_item = QtGui.QStandardItem(f"{price_val:,.0f}")
            price_item.setData(price_val, self.sort_role)
            items.append(price_item)
            # MA (money) - display text with commas, rounded to whole numbers, store numeric (NaN -> -1 for consistent sorting)
            ma_is_nan = pd.isna(ma_val)
            ma_num = float(ma_val) if not ma_is_nan else -1.0
            ma_text = f"{ma_num:,.0f}" if not ma_is_nan else ''
            ma_item = QtGui.QStandardItem(ma_text)
            ma_item.setData(ma_num, self.sort_role)
            items.append(ma_item)
            # Volatility absolute - rounded to whole numbers with commas
            vol_val = row.get('vol', np.nan)
            vol_item = QtGui.QStandardItem(f"{float(vol_val):,.0f}" if not pd.isna(vol_val) else '')
            vol_item.setData(float(vol_val) if not pd.isna(vol_val) else 0.0, self.sort_role)
            items.append(vol_item)
            # Volatility percent - rounded to whole numbers (commas only if >= 1000)
            vol_pct = row.get('volPct', np.nan) if 'volPct' in row else np.nan
            vol_pct_item = QtGui.QStandardItem(f"{float(vol_pct):,.0f}%" if not pd.isna(vol_pct) else '')
            vol_pct_item.setData(float(vol_pct) if not pd.isna(vol_pct) else 0.0, self.sort_role)
            items.append(vol_pct_item)
            # Store itemKey in user role for proper item identification when clicking (on move column)
            items[2].setData(row.get('itemKey', ''), QtCore.Qt.UserRole)
            self.model_.appendRow(items)
        # Set column widths: numeric columns (move, price, ma, vol, vol%) at 85% of content size
        # Text columns (category, item) share remaining space
        header = self.horizontalHeader()
        # Column indices: category=0, item=1, move=2, price=3, ma=4, vol=5, vol%=6
        numeric_cols = [2, 3, 4, 5, 6]  # move, price, ma, vol, vol%
        text_cols = [0, 1]  # category, item
        
        # First, set all columns to resize to contents to calculate natural widths
        for col in range(self.model_.columnCount()):
            header.setSectionResizeMode(col, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        
        # Calculate the width needed for each numeric column
        self.resizeColumnsToContents()
        
        # Store numeric column widths, set to 85% of content size (move column gets even more space)
        for col in numeric_cols:
            current_width = header.sectionSize(col)
            header.setSectionResizeMode(col, QtWidgets.QHeaderView.ResizeMode.Fixed)
            # Move column gets 90%, others get 85%
            multiplier = 0.9 if col == 2 else 0.85
            header.resizeSection(col, max(int(current_width * multiplier), 50))  # Min 50px
        
        # Set text columns to stretch to fill remaining space
        for col in text_cols:
            header.setSectionResizeMode(col, QtWidgets.QHeaderView.ResizeMode.Stretch)
        # Default sort: biggest gainers at the top (by numeric sort role on move column)
        try:
            self.model_.sort(2, QtCore.Qt.SortOrder.DescendingOrder)
        except Exception:
            pass


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, config_path: str):
        super().__init__()
        self.setWindowTitle('ABI Market Trading App')
        
        # Try to load and set window icon
        self._set_window_icon()
        
        self.cfg = utils.load_config(config_path)
        self._apply_dark_theme()

        # Data - load limited number of recent snapshots
        limit = self.cfg.max_snapshots_to_load
        snapshots = utils.load_all_snapshots(self.cfg.snapshots_path, limit=limit)
        print(f"Loaded {len(snapshots)} snapshots (limit: {limit})")
        df = utils.snapshots_to_dataframe(snapshots)
        self.df_all = utils.add_indicators(df, self.cfg.alerts.get('ma_window', 5))

        # UI
        central = QtWidgets.QWidget(self)
        self.setCentralWidget(central)
        main_layout = QtWidgets.QHBoxLayout(central)

        # Left: Filters
        left = QtWidgets.QWidget(self)
        left_layout = QtWidgets.QVBoxLayout(left)
        main_layout.addWidget(left, 1)

        self.category_cb = QtWidgets.QComboBox(self)
        cats = sorted(list(set(self.df_all['category'].unique()))) if not self.df_all.empty else []
        self.category_cb.addItem('All')
        for c in cats:
            self.category_cb.addItem(c)
        left_layout.addWidget(QtWidgets.QLabel('Category'))
        left_layout.addWidget(self.category_cb)

        self.item_edit = QtWidgets.QLineEdit(self)
        left_layout.addWidget(QtWidgets.QLabel('Item name contains'))
        left_layout.addWidget(self.item_edit)

        self.price_min = QtWidgets.QLineEdit(self)
        self.price_max = QtWidgets.QLineEdit(self)
        self.price_min.setPlaceholderText('Min')
        self.price_max.setPlaceholderText('Max')
        price_box = QtWidgets.QHBoxLayout()
        price_box.addWidget(self.price_min)
        price_box.addWidget(self.price_max)
        left_layout.addWidget(QtWidgets.QLabel('Price range'))
        left_layout.addLayout(price_box)

        self.alerts_list = QtWidgets.QListWidget(self)
        left_layout.addWidget(QtWidgets.QLabel('Top Movers'))
        left_layout.addWidget(self.alerts_list)

        # Top Volatility
        self.vol_list = QtWidgets.QListWidget(self)
        left_layout.addWidget(QtWidgets.QLabel('Top Volatility'))
        left_layout.addWidget(self.vol_list)

        # Right: Chart + Table + Thumbnail (thumbnail to the right of chart)
        right = QtWidgets.QWidget(self)
        right_layout = QtWidgets.QVBoxLayout(right)
        main_layout.addWidget(right, 3)

        # Chart + Thumbnail row (non-movable, chart takes remaining space)
        self.chart = TrendChart(self)
        self.thumb_label = QtWidgets.QLabel(self)
        self.thumb_label.setAlignment(QtCore.Qt.AlignCenter)
        self.thumb_label.setText('Thumbnail will appear here')
        self.thumb_label.setFixedWidth(140)
        self.thumb_label.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Expanding)
        self.chart.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        chart_row = QtWidgets.QWidget(self)
        row_layout = QtWidgets.QHBoxLayout(chart_row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)
        row_layout.addWidget(self.chart, stretch=1)
        row_layout.addWidget(self.thumb_label, stretch=0)
        right_layout.addWidget(chart_row, 3)

        self.table = DataTable(self)
        right_layout.addWidget(self.table, 2)

        # Signals
        self.category_cb.currentIndexChanged.connect(self.refresh_view)
        self.item_edit.textChanged.connect(self.refresh_view)
        self.price_min.textChanged.connect(self.refresh_view)
        self.price_max.textChanged.connect(self.refresh_view)
        self.table.clicked.connect(self._on_table_clicked)
        self.table.doubleClicked.connect(self._on_table_double_clicked)
        # Update selection via keyboard navigation as well
        # Note: selectionModel is available after model is set in DataTable
        self.table.selectionModel().currentChanged.connect(self._on_table_current_changed)
        self.alerts_list.itemClicked.connect(self._on_alert_clicked)
        self.vol_list.itemClicked.connect(self._on_vol_clicked)

        # Initial load
        self.refresh_view()
        self._update_alerts()
        self._update_volatility()

    def _apply_dark_theme(self) -> None:
        app = QtWidgets.QApplication.instance()
        if not app:
            return
        app.setStyle('Fusion')
        palette = QtGui.QPalette()
        # Base colors
        palette.setColor(QtGui.QPalette.Window, QtGui.QColor('#0e1116'))
        palette.setColor(QtGui.QPalette.WindowText, QtGui.QColor('#d0d4dc'))
        palette.setColor(QtGui.QPalette.Base, QtGui.QColor('#0e1116'))
        palette.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor('#121621'))
        palette.setColor(QtGui.QPalette.ToolTipBase, QtGui.QColor('#0e1116'))
        palette.setColor(QtGui.QPalette.ToolTipText, QtGui.QColor('#d0d4dc'))
        palette.setColor(QtGui.QPalette.Text, QtGui.QColor('#d0d4dc'))
        palette.setColor(QtGui.QPalette.Button, QtGui.QColor('#121621'))
        palette.setColor(QtGui.QPalette.ButtonText, QtGui.QColor('#d0d4dc'))
        palette.setColor(QtGui.QPalette.Highlight, QtGui.QColor('#1f6feb'))
        palette.setColor(QtGui.QPalette.HighlightedText, QtGui.QColor('#ffffff'))
        app.setPalette(palette)
        # Stylesheet for widgets
        app.setStyleSheet('''
            QMainWindow, QWidget { background-color: #0e1116; color: #d0d4dc; }
            QLineEdit, QComboBox, QListWidget, QTableView { background-color: #121621; color: #d0d4dc; border: 1px solid #2a2f3a; }
            QHeaderView::section { background-color: #121621; color: #9aa4b2; padding: 4px; border: 1px solid #2a2f3a; }
            QTableView { gridline-color: #2a2f3a; selection-background-color: #163a72; selection-color: #ffffff; }
            QListWidget::item { padding: 3px 4px; }
            QListWidget::item:selected { background-color: #163a72; }
            QLabel#thumb { background-color: #121621; border: 1px solid #2a2f3a; }
        ''')
        # Theme applied; UI widgets not created yet here

    def _set_window_icon(self) -> None:
        """Try to load and set window icon from common locations."""
        # Get the directory where this script is located
        script_dir = Path(__file__).parent
        # Possible icon locations (check .ico first on Windows, then .png)
        icon_paths = [
            script_dir / 'icon.ico',  # trading_app/icon.ico
            script_dir / 'icon.png',  # trading_app/icon.png
            script_dir.parent / 'icon.ico',  # abi-market-data/icon.ico
            script_dir.parent / 'icon.png',  # abi-market-data/icon.png
            script_dir.parent / 'assets' / 'icon.ico',  # abi-market-data/assets/icon.ico
            script_dir.parent / 'assets' / 'icon.png',  # abi-market-data/assets/icon.png
        ]
        
        for icon_path in icon_paths:
            if icon_path.exists():
                try:
                    icon = QtGui.QIcon(str(icon_path))
                    if not icon.isNull():
                        self.setWindowIcon(icon)
                        return
                except Exception:
                    # If loading fails, try next path
                    continue

    def _filtered_df(self) -> pd.DataFrame:
        df = self.df_all
        if df.empty:
            return df
        cat = self.category_cb.currentText()
        if cat and cat != 'All':
            df = df[df['category'] == cat]
        txt = self.item_edit.text().strip().lower()
        if txt:
            # Search in itemName (clean name), displayName (if present), and itemKey
            search_mask = df['itemName'].astype(str).str.contains(txt, case=False, na=False)
            if 'displayName' in df.columns:
                search_mask = search_mask | df['displayName'].astype(str).str.contains(txt, case=False, na=False)
            if 'itemKey' in df.columns:
                search_mask = search_mask | df['itemKey'].astype(str).str.contains(txt, case=False, na=False)
            df = df[search_mask]
        mn, mx = self.price_min.text().strip(), self.price_max.text().strip()
        if mn:
            try:
                df = df[df['price'] >= float(mn)]
            except ValueError:
                pass
        if mx:
            try:
                df = df[df['price'] <= float(mx)]
            except ValueError:
                pass
        return df

    def _latest_per_item(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        # Ensure sorted by time, then take last per itemKey
        if 'epoch' in df.columns:
            df_sorted = df.sort_values(['itemKey', 'epoch'])
        else:
            df_sorted = df.copy()
        latest = df_sorted.groupby('itemKey', as_index=False).tail(1)
        # Keep presentation order: sort by price desc by default
        try:
            latest = latest.sort_values(['price'], ascending=[False])
        except Exception:
            pass
        return latest

    def refresh_view(self) -> None:
        # Preserve the top-visible row's itemKey and current selection
        viewport = self.table.viewport()
        top_index = self.table.indexAt(QtCore.QPoint(0, 0))
        top_key = ''
        if top_index.isValid():
            try:
                top_key = self.table.model_.item(top_index.row(), 2).data(QtCore.Qt.UserRole)  # itemKey stored in move column (2)
            except Exception:
                top_key = ''
        sel_index = self.table.currentIndex()
        sel_key = ''
        if sel_index.isValid():
            try:
                sel_key = self.table.model_.item(sel_index.row(), 2).data(QtCore.Qt.UserRole)  # itemKey stored in move column (2)
            except Exception:
                sel_key = ''

        df_full = self._filtered_df()
        df = self._latest_per_item(df_full)
        blocker = QtCore.QSignalBlocker(self.table)
        self.table.setUpdatesEnabled(False)
        try:
            self.table.load(df)
            QtCore.QCoreApplication.processEvents()
            # Helper to find model row by itemKey
            def _find_row_by_key(key: str) -> int:
                if not key:
                    return -1
                m = self.table.model_
                for r in range(m.rowCount()):
                    try:
                        if m.item(r, 2).data(QtCore.Qt.UserRole) == key:  # itemKey stored in move column (2)
                            return r
                    except Exception:
                        continue
                return -1

            # Restore top-visible row
            r_top = _find_row_by_key(top_key)
            if r_top >= 0:
                idx_top = self.table.model_.index(r_top, 0)
                if idx_top.isValid():
                    self.table.scrollTo(idx_top, QtWidgets.QAbstractItemView.PositionAtTop)
            # Restore selection
            r_sel = _find_row_by_key(sel_key)
            if r_sel >= 0:
                idx_sel = self.table.model_.index(r_sel, 0)
                if idx_sel.isValid():
                    self.table.setCurrentIndex(idx_sel)
        finally:
            self.table.setUpdatesEnabled(True)
        # Ensure a row is selected and chart/thumbnail shown
        if not df.empty:
            current = self.table.currentIndex()
            if not current.isValid():
                # Select first row
                idx0 = self.table.model_.index(0, 0)
                if idx0.isValid():
                    self.table.setCurrentIndex(idx0)
                    self._on_table_clicked(idx0)
            else:
                self._on_table_clicked(current)
        else:
            self.chart.plot(pd.DataFrame(), '', '')

    def _on_table_clicked(self, index: QtCore.QModelIndex) -> None:
        # Chart the clicked row's item using itemKey
        model = self.table.model_
        if index.isValid():
            row = index.row()
            # Get itemKey from stored user data (stored in move column, index 2)
            item_key = model.item(row, 2).data(QtCore.Qt.UserRole)
            category = model.item(row, 0).text()  # category column
            display_name = model.item(row, 1).text()  # item column
            df_full = self._filtered_df()
            if item_key:
                # Use display name in chart title
                self.chart.plot(df_full, item_key, display_name)
            else:
                # Fallback for old data without itemKey
                self.chart.plot(df_full, display_name, display_name)

            # Update thumbnail preview
            try:
                self.thumb_label.setText('')
                # Find rows for this item
                if not df_full.empty and 'thumbPath' in df_full.columns:
                    dfi = df_full[df_full['itemKey'] == item_key] if 'itemKey' in df_full.columns else df_full[df_full['itemName'] == display_name]
                    if not dfi.empty:
                        # Gather candidate paths (skip NaN and empty strings)
                        # Build candidate paths using derived thumbPath only
                        cand = []
                        if 'thumbPath' in dfi.columns:
                            for p in dfi['thumbPath']:
                                if isinstance(p, str) and p.strip():
                                    cand.append(str(p))
                        # De-duplicate preserving order
                        seen = set()
                        cand = [x for x in cand if not (x in seen or seen.add(x))]
                        found_path = ''
                        for thumb_rel in reversed(cand):
                            # Try absolute first
                            thumb_abs = thumb_rel
                            if not os.path.isabs(thumb_abs):
                                thumb_abs = os.path.normpath(os.path.join(self.cfg.snapshots_path, thumb_rel))
                            if os.path.exists(thumb_abs):
                                found_path = thumb_abs
                                break
                            # Try replacing slashes just in case
                            alt_rel = thumb_rel.replace('/', os.sep).replace('\\', os.sep)
                            thumb_abs = os.path.normpath(os.path.join(self.cfg.snapshots_path, alt_rel))
                            if os.path.exists(thumb_abs):
                                found_path = thumb_abs
                                break
                        if found_path:
                            pix = QtGui.QPixmap(found_path)
                            if not pix.isNull():
                                target_w = self.thumb_label.width()
                                if pix.width() > target_w:
                                    scaled = pix.scaledToWidth(target_w, QtCore.Qt.TransformationMode.SmoothTransformation)
                                    self.thumb_label.setPixmap(scaled)
                                else:
                                    # Do not upscale small thumbnails to avoid fuzziness
                                    self.thumb_label.setPixmap(pix)
                            else:
                                self.thumb_label.setPixmap(QtGui.QPixmap())
                        else:
                            self.thumb_label.setText('Thumbnail not found')
                else:
                    self.thumb_label.setText('')
            except Exception:
                self.thumb_label.setText('')

    def _on_table_current_changed(self, current: QtCore.QModelIndex, prev: QtCore.QModelIndex) -> None:
        # Mirror click handling for keyboard selection changes
        self._on_table_clicked(current)

    def _update_alerts(self) -> None:
        self.alerts_list.clear()
        alerts = utils.find_alerts(
            self.df_all,
            spike_pct=float(self.cfg.alerts.get('spike_threshold_pct', 20.0)),
            drop_pct=float(self.cfg.alerts.get('drop_threshold_pct', 20.0)),
        )
        # Sort: biggest gainers at top, biggest losers at bottom
        alerts.sort(key=lambda a: a.get('delta', 0.0), reverse=True)
        for a in alerts:
            raw_text = a.get('text', '')
            # Remove any leading emoji from utils, keep plain text
            display_text = raw_text[1:].strip() if raw_text[:1] in ('🔺', '🔻') else raw_text
            item = QtWidgets.QListWidgetItem(display_text)
            # Store itemKey and category for click handling
            item.setData(QtCore.Qt.UserRole, a.get('itemKey', ''))
            item.setData(QtCore.Qt.UserRole + 1, a.get('category', ''))
            # Add colored icon only; leave text default color
            t = a.get('type')
            if t in ('spike', 'drop'):
                color = QtGui.QColor(0, 150, 0) if t == 'spike' else QtGui.QColor(180, 0, 0)
                direction = 'up' if t == 'spike' else 'down'
                icon = self._make_alert_icon(color, direction)
                if icon is not None:
                    item.setIcon(icon)
            self.alerts_list.addItem(item)

    def _update_volatility(self) -> None:
        self.vol_list.clear()
        tops = utils.find_top_volatility(self.df_all, top_n=10)
        for v in tops:
            item = QtWidgets.QListWidgetItem(v.get('text', ''))
            item.setData(QtCore.Qt.UserRole, v.get('itemKey', ''))
            item.setData(QtCore.Qt.UserRole + 1, v.get('category', ''))
            # Add an exclamation icon to indicate volatility
            try:
                icon = self._make_vol_icon(QtGui.QColor(255, 140, 0))  # orange
                if icon is not None:
                    item.setIcon(icon)
            except Exception:
                pass
            self.vol_list.addItem(item)

    def _on_alert_clicked(self, item: QtWidgets.QListWidgetItem) -> None:
        # Select the corresponding row in the table and update chart/thumbnail
        item_key = item.data(QtCore.Qt.UserRole)
        category = item.data(QtCore.Qt.UserRole + 1)
        if not item_key:
            return
        # Make sure filters show the item: set category to alert's category and clear name/price filters
        if category and self.category_cb.currentText() != category:
            blocker = QtCore.QSignalBlocker(self.category_cb)
            self.category_cb.setCurrentText(category)
            del blocker
        for w in (self.item_edit, self.price_min, self.price_max):
            blk = QtCore.QSignalBlocker(w)
            w.setText('')
            del blk
        # Refresh view then find and select the row with this itemKey
        self.refresh_view()
        m = self.table.model_
        target_row = -1
        for r in range(m.rowCount()):
            try:
                if m.item(r, 2).data(QtCore.Qt.UserRole) == item_key:  # itemKey stored in move column (2)
                    target_row = r
                    break
            except Exception:
                continue
        if target_row >= 0:
            idx = m.index(target_row, 0)  # Use column 0 for selection index
            if idx.isValid():
                self.table.setCurrentIndex(idx)
                self.table.scrollTo(idx, QtWidgets.QAbstractItemView.PositionAtCenter)
                self._on_table_clicked(idx)

    def _on_vol_clicked(self, item: QtWidgets.QListWidgetItem) -> None:
        # Reuse the same behavior as alert click for volatility items
        self._on_alert_clicked(item)

    def _make_alert_icon(self, color: QtGui.QColor, direction: str = 'up') -> QtGui.QIcon:
        # Create a small triangle icon with the given color and orientation
        size = 12
        pm = QtGui.QPixmap(size, size)
        pm.fill(QtCore.Qt.GlobalColor.transparent)
        painter = QtGui.QPainter(pm)
        try:
            painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
            brush = QtGui.QBrush(color)
            pen = QtGui.QPen(color)
            pen.setWidth(1)
            painter.setPen(pen)
            painter.setBrush(brush)
            if direction == 'down':
                # Downward triangle
                points = [
                    QtCore.QPointF(2.0, 2.0),
                    QtCore.QPointF(size-2.0, 2.0),
                    QtCore.QPointF(size/2.0, size-2.0),
                ]
            else:
                # Upward triangle
                points = [
                    QtCore.QPointF(size/2.0, 2.0),
                    QtCore.QPointF(2.0, size-2.0),
                    QtCore.QPointF(size-2.0, size-2.0),
                ]
            painter.drawPolygon(QtGui.QPolygonF(points))
        finally:
            painter.end()
        return QtGui.QIcon(pm)

    def _make_vol_icon(self, color: QtGui.QColor) -> QtGui.QIcon:
        # Draw a small exclamation mark icon
        size = 12
        pm = QtGui.QPixmap(size, size)
        pm.fill(QtCore.Qt.GlobalColor.transparent)
        painter = QtGui.QPainter(pm)
        try:
            painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
            pen = QtGui.QPen(color)
            pen.setWidth(2)
            pen.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.setBrush(color)
            # Draw vertical line
            x = size / 2.0
            # Shorten line so it doesn't touch the dot
            painter.drawLine(int(x), 2, int(x), size - 6)
            # Draw dot
            painter.drawEllipse(QtCore.QPointF(x, size - 2), 1.2, 1.2)
        finally:
            painter.end()
        return QtGui.QIcon(pm)

    def _on_table_double_clicked(self, index: QtCore.QModelIndex) -> None:
        model = self.table.model_
        if not index.isValid():
            return
        row = index.row()
        item_key = model.item(row, 2).data(QtCore.Qt.UserRole)  # itemKey stored in move column (2)
        if not item_key:
            return
        current_display = model.item(row, 1).text()  # display name in item column (1)
        # Pre-fill with the key's name portion before any #hash
        base_name = current_display
        if ':' in item_key:
            base_name = item_key.split(':', 1)[1]
        if '#' in base_name:
            base_name = base_name.split('#', 1)[0]
        text, ok = QtWidgets.QInputDialog.getText(
            self,
            'Add Display Mapping',
            f'Enter display name for:\n{item_key}',
            QtWidgets.QLineEdit.Normal,
            base_name,
        )
        if not ok:
            return
        new_name = str(text).strip()
        if not new_name:
            return
        try:
            from trading_app.utils import save_display_mapping, get_display_name
            save_display_mapping(item_key, new_name)
            if not self.df_all.empty:
                self.df_all['displayName'] = self.df_all['itemKey'].apply(get_display_name)
            self.refresh_view()
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, 'Error', f'Failed to save mapping:\n{e}')


def main() -> int:
    app = QtWidgets.QApplication(sys.argv)
    # Load config relative to this script's location
    config_path = Path(__file__).parent / 'config.yaml'
    win = MainWindow(str(config_path))
    win.resize(1100, 700)
    win.show()
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())

