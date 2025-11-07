"""ABI Market Trading App - Main GUI application."""
import sys
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

# Add parent directory to path for imports (must be before importing trading_app)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import resource_path from utils
from trading_app.utils import resource_path

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

# Import utils (path already set up above)
from trading_app import utils
from trading_app import version


class TrendChart(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)  # Enable mouse tracking for hover events
        self.figure = Figure(figsize=(6, 4), facecolor='#000000')
        self.canvas = FigureCanvas(self.figure)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.canvas)
        # Store data points for hover lookup
        self._data_points = {}  # Dict mapping index to (ts, price, dt_str)
        self._scatter = None
        self._cursor = None  # mplcursors cursor object
        self._ax = None
        self._on_add_callback = None  # Store callback for manual tooltip triggering
        self._manual_annotation = None  # Store manual annotation for latest point
        self._latest_idx = None  # Track index of latest point to prevent double tooltip

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
        self._latest_idx = None  # Reset latest point tracking
        # Clear old manual annotation
        if self._manual_annotation is not None:
            try:
                self._manual_annotation.remove()
            except Exception:
                pass
            self._manual_annotation = None
        # Remove old cursor if exists
        if self._cursor is not None:
            try:
                self._cursor.remove()
            except Exception:
                pass
            self._cursor = None
        ax = self.figure.add_subplot(111, facecolor='#000000')
        self._ax = ax
        if df.empty:
            ax.set_title('No data', color='#c0c0c0')
        else:
            # Filter by itemKey to handle items with same name in different categories
            dfi = df[df['itemKey'] == item_key] if 'itemKey' in df.columns else df[df['itemName'] == item_key]
            if dfi.empty:
                ax.set_title(f'No data for {display_name or item_key}')
            else:
                # Sort by timestamp for proper plotting
                dfi = dfi.sort_values('timestamp')
                # Modern styled lines (no labels since legend is removed)
                ax.plot(dfi['timestamp'], dfi['price'], color='#00ff88', lw=2, zorder=1)  # Neon green
                if 'ma' in dfi.columns:
                    ax.plot(dfi['timestamp'], dfi['ma'], color='#ff6600', lw=1.8, linestyle='--', zorder=1)  # Orange
                # Add scatter points for hover interaction
                self._scatter = ax.scatter(dfi['timestamp'], dfi['price'], s=60, color='#00ff88', 
                                           edgecolors='#000000', linewidths=1.5, zorder=2, alpha=0.8,
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
                    chart_instance = self  # Capture self for accessing _latest_idx
                    
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
                                              facecolor='#0a0a0a', 
                                              edgecolor='#555555', 
                                              linewidth=1.5,
                                              alpha=0.98))
                            # Remove arrow if it exists (we don't want arrows anymore)
                            try:
                                if hasattr(ann, 'arrowprops') and ann.arrowprops is not None:
                                    ann.arrowprops = None
                            except Exception:
                                pass
                            
                            # Ensure tooltip is not clipped by axes
                            try:
                                ann.set_annotation_clip(False)
                            except Exception:
                                pass
                            ann.set_clip_on(False)
                            ann.set_zorder(100)
                            
                            # Show only price in tooltip (no date/time - that's on x-axis now)
                            ann.set_text(f"{price:,.0f}")
                            
                            # Style for price prominence - larger, bold
                            ann.set_fontsize(15)  # Larger font for price
                            ann.set_weight('bold')  # Bold for emphasis
                            ann.set_color('#00ff88')  # Neon green for price (consistent with chart)
                            
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
                        
                        # Ignore clicks on the latest point (already has tooltip displayed)
                        if chart_instance._latest_idx is not None and sel.index == chart_instance._latest_idx:
                            try:
                                if sel.annotation:
                                    sel.annotation.set_visible(False)
                                cursor_obj.remove_selection(sel)
                            except (AttributeError, ValueError, KeyError):
                                pass
                            canvas.draw_idle()
                            return  # Don't show the tooltip
                        
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
                    # Store callbacks for manual tooltip triggering
                    self._on_add_callback = on_add_with_tracking
                    self._on_add_simple = on_add  # Store the simple on_add too
                else:
                    # Fallback: manual hover (may not work reliably)
                    print("Warning: mplcursors not available. Hover tooltips may not work.")
                    print("Install with: pip install mplcursors")
                # Extract category and name for title if display_name not provided
                if not display_name and ':' in item_key:
                    category, name = item_key.split(':', 1)
                    title = ax.set_title(name, color='#c0c0c0', fontweight='bold', pad=15)
                else:
                    title = ax.set_title(display_name or item_key, color='#c0c0c0', fontweight='bold', pad=15)
                
                # Axes styling
                ax.set_xlabel('Time', color='#888888')
                ax.set_ylabel('')  # Remove y-axis title
                ax.tick_params(colors='#888888')
                
                # Format y-axis to show prices with commas
                from matplotlib.ticker import FuncFormatter
                def format_price(x, pos=None):
                    """Format price labels with commas"""
                    return f"{x:,.0f}"
                ax.yaxis.set_major_formatter(FuncFormatter(format_price))
                
                # Remove x-axis tick labels - just show "Time" label
                ax.set_xticklabels([])
                
                for spine in ['top', 'right', 'left', 'bottom']:
                    ax.spines[spine].set_color('#333333')
                ax.grid(True, color='#1a1a1a', alpha=0.6, linestyle='--', linewidth=0.8)
                # Legend removed for cleaner look
        self.canvas.draw_idle()
        
        # Don't automatically show tooltip here - wait for thumbnail to load first
        # Tooltip will be shown after thumbnail is loaded in _on_table_clicked
    
    def _show_latest_tooltip(self) -> None:
        """Show tooltip for the latest data point automatically."""
        if not MPLCURSORS_AVAILABLE or self._cursor is None or self._scatter is None or not self._data_points:
            return
        
        # Remove old manual annotation if it exists
        if self._manual_annotation is not None:
            try:
                self._manual_annotation.remove()
            except Exception:
                pass
            self._manual_annotation = None
        
        try:
            # Find the latest point (highest index since data is sorted chronologically)
            latest_idx = max(self._data_points.keys())
            self._latest_idx = latest_idx  # Store for click prevention
            ts, price, dt_str = self._data_points[latest_idx]
            
            # Get the actual data coordinates from the scatter plot
            # This ensures we use the same coordinate system as the plot
            scatter_offsets = self._scatter.get_offsets()
            if latest_idx < len(scatter_offsets):
                actual_x, actual_y = scatter_offsets[latest_idx]
                # Use the scatter plot's actual coordinates
                plot_x, plot_y = actual_x, actual_y
            else:
                # Fallback to our stored coordinates
                plot_x, plot_y = ts, price
            
            # Calculate position BEFORE creating annotation to use the right coordinate system
            xlim = self._ax.get_xlim()
            ylim = self._ax.get_ylim()
            
            # Calculate relative position of point within the chart
            x_range = xlim[1] - xlim[0]
            y_range = ylim[1] - ylim[0]
            x_position = (plot_x - xlim[0]) / x_range if x_range > 0 else 0.5
            y_position = (plot_y - ylim[0]) / y_range if y_range > 0 else 0.5
            
            # For bottom cases, use axes fraction coordinates to position tooltip above the point
            # This is more reliable than offset points
            use_axes_fraction = y_position < 0.4  # Use axes fraction for bottom cases
            
            # Use the callback to create the annotation
            if self._on_add_callback is not None or hasattr(self, '_on_add_simple'):
                # Use the simple on_add callback if available (it doesn't have tracking logic)
                callback_to_use = getattr(self, '_on_add_simple', None)
                if callback_to_use is None:
                    callback_to_use = self._on_add_callback
                
                # Create a fake Selection object that matches what mplcursors provides
                class FakeSelection:
                    def __init__(self, artist, idx, xdata, ydata, ax, use_axes_frac, x_pos, y_pos):
                        self.artist = artist
                        self.index = idx
                        self.target = artist
                        self.targetindex = idx
                        # Create an annotation object for the selection
                        from matplotlib.text import Annotation
                        
                        if use_axes_frac:
                            # For bottom cases: use axes fraction coordinates to position tooltip well above
                            # Calculate text position in axes fraction (0-1)
                            text_ax_x = x_pos
                            # Position well above the point - scale based on how bottom it is
                            if y_pos < 0.15:
                                text_ax_y = y_pos + 0.25  # Very bottom: move up 25% of axes height
                            elif y_pos < 0.25:
                                text_ax_y = y_pos + 0.20  # Bottom: move up 20%
                            else:
                                text_ax_y = y_pos + 0.15  # Lower: move up 15%
                            
                            # Adjust for left/right
                            if x_pos > 0.85:
                                text_ax_x = x_pos - 0.15  # Move left
                            elif x_pos < 0.2:
                                text_ax_x = x_pos + 0.15  # Move right
                            else:
                                text_ax_x = x_pos - 0.12  # Default: move left
                            
                            self.annotation = Annotation('',
                                                      (xdata, ydata),  # Point in data coordinates
                                                      xytext=(text_ax_x, text_ax_y),  # Text in axes fraction
                                                      textcoords='axes fraction',  # Use axes fraction
                                                      xycoords='data',
                                                      bbox=dict(boxstyle='round,pad=0.8',
                                                                facecolor='#0a0a0a',
                                                                edgecolor='#555555',
                                                                linewidth=1.5,
                                                                alpha=0.98),
                                                      annotation_clip=False)
                        else:
                            # For top/middle cases: use offset points as before
                            self.annotation = Annotation('',
                                                      (xdata, ydata),
                                                      xytext=(-110, -40),
                                                      textcoords='offset points',
                                                      xycoords='data',
                                                      bbox=dict(boxstyle='round,pad=0.8',
                                                                facecolor='#0a0a0a',
                                                                edgecolor='#555555',
                                                                linewidth=1.5,
                                                                alpha=0.98),
                                                      annotation_clip=False)
                        self.annotation._custom_texts = []
                        self.annotation.set_clip_on(False)
                        ax.add_artist(self.annotation)
                
                fake_sel = FakeSelection(self._scatter, latest_idx, plot_x, plot_y, self._ax, 
                                        use_axes_fraction, x_position, y_position)
                
                # Call the callback which will style and show the annotation
                callback_to_use(fake_sel)
                
                # Make absolutely sure annotation is visible
                fake_sel.annotation.set_visible(True)
                fake_sel.annotation.set_zorder(100)
                
                # Ensure clipping is disabled
                fake_sel.annotation.set_clip_on(False)
                try:
                    fake_sel.annotation.set_annotation_clip(False)
                except AttributeError:
                    pass
                
                # Force redraw with full draw
                self.canvas.draw()
                self.canvas.flush_events()
                QtCore.QCoreApplication.processEvents()  # Process events to ensure display
                
        except Exception as e:
            # Silently fail - manual tooltips still work
            pass


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
        headers = ['item', 'category', 'price', 'ma', 'ma%', 'range', 'range%']
        self.model_.setHorizontalHeaderLabels(headers)
        for _, row in df.iterrows():
            items = []
            # Show display name in GUI if available, otherwise clean name
            display_name = row.get('displayName', row.get('itemName', ''))
            name_item = QtGui.QStandardItem(str(display_name))
            # Provide a case-insensitive sort key for proper alpha sorting
            try:
                name_item.setData(str(display_name).lower(), self.sort_role)
            except Exception:
                pass
            items.append(name_item)
            # Category with case-insensitive sort key
            cat_text = str(row['category'])
            cat_item = QtGui.QStandardItem(cat_text)
            try:
                cat_item.setData(cat_text.lower(), self.sort_role)
            except Exception:
                pass
            items.append(cat_item)
            # Price (money) - display text with commas, but store numeric for sorting
            price_val = float(row['price']) if not pd.isna(row['price']) else float('nan')
            price_item = QtGui.QStandardItem(f"{price_val:,.0f}")
            price_item.setData(price_val, self.sort_role)
            items.append(price_item)
            # MA (money) - display text with commas, rounded to whole numbers, store numeric (NaN -> -1 for consistent sorting)
            ma_val = row.get('ma', np.nan)
            ma_is_nan = pd.isna(ma_val)
            ma_num = float(ma_val) if not ma_is_nan else -1.0
            ma_text = f"{ma_num:,.0f}" if not ma_is_nan else ''
            ma_item = QtGui.QStandardItem(ma_text)
            ma_item.setData(ma_num, self.sort_role)
            items.append(ma_item)
            # MA% column: percentage change from MA
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
            # Create item with percentage text
            ma_pct_item = QtGui.QStandardItem(f"{delta_pct:+.0f}%" if not pd.isna(delta_pct) else '')
            # Numeric sort key for ma% column (separate role)
            ma_pct_item.setData(float(delta_pct) if not pd.isna(delta_pct) else 0.0, self.sort_role)
            # Choose color by direction - neon colors
            if direction == 'up':
                color = QtGui.QColor(0, 255, 136)  # Neon green (#00ff88)
                ma_pct_item.setForeground(QtGui.QBrush(color))
            elif direction == 'down':
                color = QtGui.QColor(255, 68, 68)  # Neon red (#ff4444)
                ma_pct_item.setForeground(QtGui.QBrush(color))
            else:
                color = QtGui.QColor(136, 136, 136)  # Gray
                ma_pct_item.setForeground(QtGui.QBrush(color))
            items.append(ma_pct_item)
            # Price range (high - low) - absolute value with commas
            range_val = row.get('priceRange', np.nan)
            range_item = QtGui.QStandardItem(f"{float(range_val):,.0f}" if not pd.isna(range_val) else '')
            range_item.setData(float(range_val) if not pd.isna(range_val) else 0.0, self.sort_role)
            items.append(range_item)
            # Price range as percentage of current price
            range_pct = row.get('priceRangePct', np.nan) if 'priceRangePct' in row else np.nan
            range_pct_item = QtGui.QStandardItem(f"{float(range_pct):,.0f}%" if not pd.isna(range_pct) else '')
            range_pct_item.setData(float(range_pct) if not pd.isna(range_pct) else 0.0, self.sort_role)
            items.append(range_pct_item)
            # Store itemKey in user role for proper item identification when clicking (on ma% column, index 4)
            items[4].setData(row.get('itemKey', ''), QtCore.Qt.UserRole)
            self.model_.appendRow(items)
        # Set column widths: numeric columns (price, ma, ma%, range, range%) at 85% of content size
        # Text columns (item, category) share remaining space
        header = self.horizontalHeader()
        # Column indices: item=0, category=1, price=2, ma=3, ma%=4, range=5, range%=6
        numeric_cols = [2, 3, 4, 5, 6]  # price, ma, ma%, range, range%
        text_cols = [0, 1]  # item, category
        
        # First, set all columns to resize to contents to calculate natural widths
        for col in range(self.model_.columnCount()):
            header.setSectionResizeMode(col, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        
        # Calculate the width needed for each numeric column
        self.resizeColumnsToContents()
        
        # Store numeric column widths, set to 85% of content size (ma% column gets even more space)
        for col in numeric_cols:
            current_width = header.sectionSize(col)
            header.setSectionResizeMode(col, QtWidgets.QHeaderView.ResizeMode.Fixed)
            # MA% column gets 90%, others get 85%
            multiplier = 0.9 if col == 4 else 0.85
            header.resizeSection(col, max(int(current_width * multiplier), 50))  # Min 50px
        
        # Set text columns to stretch to fill remaining space
        for col in text_cols:
            header.setSectionResizeMode(col, QtWidgets.QHeaderView.ResizeMode.Stretch)
        # Default sort: biggest gainers at the top (by numeric sort role on ma% column)
        try:
            self.model_.sort(4, QtCore.Qt.SortOrder.DescendingOrder)
            # Update header to show the sort indicator
            header.setSortIndicator(4, QtCore.Qt.SortOrder.DescendingOrder)
        except Exception:
            pass


class LoadingScreen(QtWidgets.QWidget):
    """Loading screen shown while snapshots are being downloaded from S3."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(QtCore.Qt.WindowType.Window | QtCore.Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle(f'ABI Trading Platform v{version.__version__}')
        self.setFixedSize(400, 200)
        
        # Set window icon
        self._set_window_icon()
        self.setStyleSheet('''
            QWidget {
                background-color: #0a0a0a;
                color: #c0c0c0;
            }
        ''')
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setAlignment(QtCore.Qt.AlignCenter)
        layout.setSpacing(20)
        
        # Loading icon
        self.icon_label = QtWidgets.QLabel('⏳', self)
        self.icon_label.setAlignment(QtCore.Qt.AlignCenter)
        self.icon_label.setStyleSheet('font-size: 48px;')
        layout.addWidget(self.icon_label)
        
        # Status text
        self.status_label = QtWidgets.QLabel('Loading market data...', self)
        self.status_label.setAlignment(QtCore.Qt.AlignCenter)
        self.status_label.setStyleSheet('font-size: 14px; color: #888888;')
        layout.addWidget(self.status_label)
        
        # Progress bar
        self.progress_bar = QtWidgets.QProgressBar(self)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        self.progress_bar.setStyleSheet('''
            QProgressBar {
                border: 1px solid #333333;
                border-radius: 4px;
                text-align: center;
                background-color: #1a1a1a;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #00ff88;
                border-radius: 3px;
            }
        ''')
        layout.addWidget(self.progress_bar)
        
        # Center the window
        self._center_window()
    
    def _set_window_icon(self) -> None:
        """Try to load and set window icon from common locations."""
        # Possible icon locations (check .ico first on Windows, then .png)
        # In PyInstaller bundle, icon is in trading_app/ subdirectory
        # In dev mode, icon is in trading_app/ directory
        icon_paths = [
            resource_path('trading_app/icon.ico'),  # PyInstaller bundle or dev
            resource_path('trading_app/icon.png'),  # PyInstaller bundle or dev
        ]
        # Also check parent directory locations for dev mode
        if not getattr(sys, 'frozen', False):
            script_dir = Path(__file__).parent
            icon_paths.extend([
                script_dir.parent / 'icon.ico',  # abi-market-data/icon.ico
                script_dir.parent / 'icon.png',  # abi-market-data/icon.png
                script_dir.parent / 'assets' / 'icon.ico',  # abi-market-data/assets/icon.ico
                script_dir.parent / 'assets' / 'icon.png',  # abi-market-data/assets/icon.png
            ])
        
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
    
    def _center_window(self):
        """Center the loading screen on the screen."""
        screen = QtWidgets.QApplication.primaryScreen().geometry()
        size = self.geometry()
        self.move(
            (screen.width() - size.width()) // 2,
            (screen.height() - size.height()) // 2
        )
    
    def update_status(self, message: str, progress: int = None):
        """Update the status message and optionally set progress."""
        self.status_label.setText(message)
        if progress is not None:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(progress)
        QtWidgets.QApplication.processEvents()


class SnapshotLoader(QtCore.QThread):
    """Worker thread to load snapshots asynchronously."""
    progress = QtCore.Signal(str, int)  # message, progress percentage
    finished = QtCore.Signal(list)  # snapshots list
    error = QtCore.Signal(str)  # error message
    
    def __init__(self, config_path: str, snapshots_path: str, limit: int):
        super().__init__()
        self.config_path = config_path
        self.snapshots_path = snapshots_path
        self.limit = limit
    
    def run(self):
        """Load snapshots in background thread."""
        try:
            # Load config
            self.progress.emit('Loading configuration...', 5)
            cfg = utils.load_config(self.config_path)
            
            # Check if S3 is configured
            s3_config = utils.load_s3_config()
            if s3_config and s3_config.get('use_s3'):
                self.progress.emit('Connecting...', 10)
                try:
                    # List S3 snapshots (already sorted newest first)
                    s3_files = utils.list_s3_snapshots(
                        s3_config,
                        limit=self.limit,
                        raise_on_error=True,
                    )
                    total_files = len(s3_files)
                    
                    if total_files > 0:
                        self.progress.emit(f'Loading {total_files} snapshots from S3...', 15)
                        
                        snapshots = []
                        
                        for idx, filename in enumerate(s3_files):
                            # Load snapshot directly from S3 into memory (no disk caching)
                            # Remove .json extension from display
                            display_name = filename.replace('.json', '') if filename.endswith('.json') else filename
                            self.progress.emit(f'Loading {display_name}...', 15 + int((idx / total_files) * 60))
                            snap = utils.load_snapshot_from_s3(
                                s3_config,
                                filename,
                                raise_on_error=True,
                            )
                            
                            if snap and isinstance(snap.get('categories', {}), dict):
                                snapshots.append(snap)
                            
                            # Update progress
                            progress_pct = 15 + int(((idx + 1) / total_files) * 60)
                            self.progress.emit(f'Processing snapshots... ({idx + 1}/{total_files})', progress_pct)
                        
                        self.progress.emit(f'Loaded {len(snapshots)} snapshots from S3', 75)
                    else:
                        self.progress.emit('No snapshots found in S3', 50)
                        snapshots = []
                except utils.DataServiceUnavailable:
                    raise
                except Exception as e:
                    self.progress.emit(f'S3 load failed, trying local files...', 50)
                    # Fall through to local loading
                    snapshots = []
            else:
                self.progress.emit('Loading local snapshots...', 20)
                snapshots = []
            
            # Only load local snapshots if S3 is not configured
            # (When S3 is configured, we load only from S3 to protect data)
            if not (s3_config and s3_config.get('use_s3')):
                self.progress.emit('Loading local snapshots...', 80)
                local_files = utils.list_local_snapshots(self.snapshots_path, limit=self.limit)
                for fp in local_files:
                    snap = utils.load_snapshot_file(fp)
                    if snap and isinstance(snap.get('categories', {}), dict):
                        snapshots.append(snap)
            
            # Sort by timestamp, newest first, and apply limit
            self.progress.emit('Processing data...', 90)
            snapshots.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
            if self.limit and self.limit > 0:
                snapshots = snapshots[:self.limit]
            
            self.progress.emit(f'Loaded {len(snapshots)} snapshots', 100)
            self.finished.emit(snapshots)
            
        except utils.DataServiceUnavailable:
            self.error.emit('Data service not available. Please try again later.')
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, config_path: str, snapshots: list = None):
        super().__init__()
        self.setWindowTitle(f'ABI Trading Platform v{version.__version__}')
        
        # Try to load and set window icon
        self._set_window_icon()
        
        self.cfg = utils.load_config(config_path)
        self._apply_dark_theme()

        # Data - use provided snapshots or empty list
        if snapshots is None:
            snapshots = []
        
        limit = self.cfg.max_snapshots_to_load
        if snapshots:
            print(f"Loaded {len(snapshots)} snapshots (limit: {limit})")
        df = utils.snapshots_to_dataframe(snapshots)
        self.df_all = utils.add_indicators(df, self.cfg.alerts.get('ma_window', 5))

        # Debounce timer for filter changes to prevent excessive refreshes
        self._filter_debounce_timer = QtCore.QTimer(self)
        self._filter_debounce_timer.setSingleShot(True)
        self._filter_debounce_timer.timeout.connect(self.refresh_view)

        # UI
        central = QtWidgets.QWidget(self)
        self.setCentralWidget(central)
        # Root layout with top stats bar and main content row
        root_layout = QtWidgets.QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(10)
        # Top stats bar
        top_bar = QtWidgets.QWidget(self)
        top_bar.setStyleSheet('QWidget { background-color: #0a0a0a; }')
        top_bar_layout = QtWidgets.QHBoxLayout(top_bar)
        top_bar_layout.setContentsMargins(8, 8, 8, 8)
        top_bar_layout.setSpacing(12)
        top_bar_layout.setAlignment(QtCore.Qt.AlignVCenter)
        def _make_stat_label(prefix: str) -> QtWidgets.QLabel:
            lbl = QtWidgets.QLabel(f"{prefix}: 0")
            lbl.setTextFormat(QtCore.Qt.RichText)
            lbl.setStyleSheet('color: #c0c0c0; font-weight: bold;')
            lbl.setAlignment(QtCore.Qt.AlignCenter | QtCore.Qt.AlignVCenter)
            return lbl
        self.stat_expense = _make_stat_label('Total Expenses')
        self.stat_expense.setToolTip('Money put in so far')
        self.stat_income = _make_stat_label('Total Income')
        self.stat_income.setToolTip('Money made so far')
        self.stat_net = _make_stat_label('Total Net')
        self.stat_net.setToolTip('Current overall position (ahead/behind) including money tied up in active inventory')
        self.stat_gross = _make_stat_label('Total Gross')
        self.stat_gross.setToolTip('Profit from completed trades only')
        self.stat_roi = _make_stat_label('Total ROI')
        self.stat_roi.setToolTip('Return percentage on completed investments')
        for w in (self.stat_expense, self.stat_income, self.stat_net, self.stat_gross, self.stat_roi):
            top_bar_layout.addWidget(w, 1)
        root_layout.addWidget(top_bar, 0)
        # Main row container (existing columns)
        main_row = QtWidgets.QWidget(self)
        main_layout = QtWidgets.QHBoxLayout(main_row)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        root_layout.addWidget(main_row, 1)

        # Left: Filters
        left = QtWidgets.QWidget(self)
        left_layout = QtWidgets.QVBoxLayout(left)
        left_layout.setContentsMargins(10, 0, 10, 10)
        left_layout.setSpacing(8)
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

        # My Trades
        self.trades_list = QtWidgets.QListWidget(self)
        left_layout.addWidget(QtWidgets.QLabel('My Trades'))
        left_layout.addWidget(self.trades_list)

        # Right: Chart + Table + Thumbnail (thumbnail to the right of chart)
        right = QtWidgets.QWidget(self)
        right_layout = QtWidgets.QVBoxLayout(right)
        right_layout.setContentsMargins(10, 0, 10, 10)
        main_layout.addWidget(right, 3)

        # Chart + Thumbnail row (non-movable, chart takes remaining space)
        self.chart = TrendChart(self)
        
        # Thumbnail area with buttons above it
        thumb_area = QtWidgets.QWidget(self)
        thumb_layout = QtWidgets.QVBoxLayout(thumb_area)
        thumb_layout.setContentsMargins(0, 0, 0, 0)
        thumb_layout.setSpacing(4)
        
        # Button row for buy and blacklist
        button_row = QtWidgets.QWidget(self)
        button_row_layout = QtWidgets.QHBoxLayout(button_row)
        button_row_layout.setContentsMargins(0, 0, 0, 0)
        button_row_layout.setSpacing(4)
        
        # Buy button
        self.buy_btn = QtWidgets.QPushButton(self)
        self.buy_btn.setText('Buy')
        self.buy_btn.setFixedSize(46, 30)
        self.buy_btn.setStyleSheet('''
            QPushButton {
                background-color: #1a1a1a;
                border: 1px solid #333333;
                border-radius: 4px;
                font-size: 14px;
                color: #888888;
            }
            QPushButton:hover {
                background-color: #2a2a2a;
                border-color: #555555;
                color: #c0c0c0;
            }
            QPushButton:pressed {
                background-color: #0a0a0a;
            }
        ''')
        
        # Hide/blacklist button
        self.blacklist_btn = QtWidgets.QPushButton(self)
        self.blacklist_btn.setText('✕')
        self.blacklist_btn.setFixedSize(30, 30)
        self.blacklist_btn.setStyleSheet('''
            QPushButton {
                background-color: #1a1a1a;
                border: 1px solid #333333;
                border-radius: 4px;
                font-size: 16px;
                color: #888888;
            }
            QPushButton:hover {
                background-color: #2a2a2a;
                border-color: #555555;
                color: #c0c0c0;
            }
            QPushButton:pressed {
                background-color: #0a0a0a;
            }
        ''')
        
        button_row_layout.addWidget(self.buy_btn)
        button_row_layout.addWidget(self.blacklist_btn)
        button_row_layout.addStretch()
        
        self.thumb_label = QtWidgets.QLabel(self)
        self.thumb_label.setAlignment(QtCore.Qt.AlignCenter)
        self.thumb_label.setText('Thumbnail will appear here')
        self.thumb_label.setFixedWidth(140)
        self.thumb_label.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Expanding)
        
        # Add spacer to position buttons closer to thumbnail
        thumb_layout.addStretch(5)
        thumb_layout.addWidget(button_row, alignment=QtCore.Qt.AlignCenter)
        thumb_layout.addWidget(self.thumb_label, stretch=10)
        # No bottom spacer to push buttons lower
        
        self.chart.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        chart_row = QtWidgets.QWidget(self)
        row_layout = QtWidgets.QHBoxLayout(chart_row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)
        row_layout.addWidget(self.chart, stretch=1)
        row_layout.addWidget(thumb_area, stretch=0)
        right_layout.addWidget(chart_row, 3)

        self.table = DataTable(self)
        right_layout.addWidget(self.table, 2)

        # Signals
        self.category_cb.currentIndexChanged.connect(self._on_filter_changed)
        self.item_edit.textChanged.connect(self._on_filter_changed)
        self.price_min.textChanged.connect(self._on_filter_changed)
        self.price_max.textChanged.connect(self._on_filter_changed)
        self.table.clicked.connect(self._on_table_clicked)
        self.table.doubleClicked.connect(self._on_table_double_clicked)
        # Update selection via keyboard navigation as well
        # Note: selectionModel is available after model is set in DataTable
        self.table.selectionModel().currentChanged.connect(self._on_table_current_changed)
        self.alerts_list.itemClicked.connect(self._on_alert_clicked)
        # Keyboard navigation in Top Movers mirrors click behavior
        try:
            self.alerts_list.currentItemChanged.connect(self._on_alert_current_changed)
        except Exception:
            pass
        self.trades_list.itemClicked.connect(self._on_trade_widget_clicked)
        # Keyboard navigation in My Trades should mirror click behavior
        try:
            self.trades_list.currentItemChanged.connect(self._on_trade_widget_current_changed)
        except Exception:
            pass
        self.buy_btn.clicked.connect(self._on_buy_btn_clicked)
        self.blacklist_btn.clicked.connect(self._on_blacklist_btn_clicked)

        # Track current selected itemKey for button states
        self._current_item_key = None
        self._selection_guard = False
        self._pending_nav = None
        self._keyboard_nav_timer = QtCore.QTimer(self)
        self._keyboard_nav_timer.setSingleShot(True)
        self._keyboard_nav_timer.timeout.connect(self._process_pending_nav)
        QtWidgets.QApplication.instance().installEventFilter(self)

        # Right trading panel (Active / Completed)
        self._build_trading_panel(main_layout)
        # Initial load
        self.refresh_view()
        self._update_alerts()
        self._update_trades_widget()
        self._refresh_trade_panels()
        self._update_top_stats()
        # Initialize blacklist button state
        self._update_blacklist_button_state()

    def _update_top_stats(self) -> None:
        try:
            trades = utils.load_trades()
        except Exception:
            trades = []
        total_expense = 0.0
        total_income = 0.0
        completed_gross = 0.0
        completed_expense = 0.0
        for t in trades:
            try:
                expense = float(t.get('expense') or 0.0)
                income = float(t.get('income') or 0.0)
                total_expense += expense
                total_income += income
                # Calculate gross only from completed trades (status "5 - Sold")
                # This matches what users see when adding up Gross from completed trade cards
                if t.get('status') == '5 - Sold':
                    completed_gross += income - expense
                    completed_expense += expense
            except Exception:
                continue
        # Use completed_gross for Total Gross to match individual trade cards
        total_gross = completed_gross
        # Total Net: overall position including active inventory (income - expenses for all trades)
        total_net = total_income - total_expense
        # ROI based on completed trades only
        roi_pct = (total_gross / completed_expense * 100.0) if completed_expense > 0 else 0.0
        # Update labels with thousand separators, coloring only the numbers
        if hasattr(self, 'stat_expense'):
            expense_val = f"{total_expense:,.0f}"
            self.stat_expense.setText(f'Total Expenses: <span style="color: #ff4444;">{expense_val}</span>')
        if hasattr(self, 'stat_income'):
            income_val = f"{total_income:,.0f}"
            self.stat_income.setText(f'Total Income: <span style="color: #00ff88;">{income_val}</span>')
        if hasattr(self, 'stat_net'):
            net_val = f"{total_net:,.0f}"
            net_color = '#00ff88' if total_net >= 0 else '#ff4444'
            self.stat_net.setText(f'Total Net: <span style="color: {net_color};">{net_val}</span>')
        if hasattr(self, 'stat_gross'):
            gross_val = f"{total_gross:,.0f}"
            gross_color = '#00ff88' if total_gross >= 0 else '#ff4444'
            self.stat_gross.setText(f'Total Gross: <span style="color: {gross_color};">{gross_val}</span>')
        if hasattr(self, 'stat_roi'):
            roi_val = f"{roi_pct:.0f}%"
            roi_color = '#00ff88' if roi_pct >= 0 else '#ff4444'
            self.stat_roi.setText(f'Total ROI: <span style="color: {roi_color};">{roi_val}</span>')

    def _apply_dark_theme(self) -> None:
        app = QtWidgets.QApplication.instance()
        if not app:
            return
        app.setStyle('Fusion')
        palette = QtGui.QPalette()
        # Base colors - Deeper blacks like Bloomberg terminal, masculine grays
        palette.setColor(QtGui.QPalette.Window, QtGui.QColor('#000000'))  # Pure black
        palette.setColor(QtGui.QPalette.WindowText, QtGui.QColor('#c0c0c0'))  # Bright silver/gray
        palette.setColor(QtGui.QPalette.Base, QtGui.QColor('#050505'))  # Slightly off-black
        palette.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor('#0a0a0a'))  # Very dark gray
        palette.setColor(QtGui.QPalette.ToolTipBase, QtGui.QColor('#0a0a0a'))
        palette.setColor(QtGui.QPalette.ToolTipText, QtGui.QColor('#00ff00'))  # Neon green
        palette.setColor(QtGui.QPalette.Text, QtGui.QColor('#c0c0c0'))
        palette.setColor(QtGui.QPalette.Button, QtGui.QColor('#1a1a1a'))  # Dark gray button
        palette.setColor(QtGui.QPalette.ButtonText, QtGui.QColor('#c0c0c0'))
        palette.setColor(QtGui.QPalette.Highlight, QtGui.QColor('#333333'))  # Neutral gray for selection
        palette.setColor(QtGui.QPalette.HighlightedText, QtGui.QColor('#c0c0c0'))
        app.setPalette(palette)
        # Stylesheet for widgets - Tough, masculine colors
        app.setStyleSheet('''
            QMainWindow, QWidget { background-color: #000000; color: #c0c0c0; }
            QLineEdit, QComboBox, QListWidget, QTableView { 
                background-color: #0a0a0a; 
                color: #c0c0c0; 
                border: 1px solid #333333; 
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                width: 0px;
                height: 0px;
            }
            QComboBox QAbstractItemView {
                background-color: #0a0a0a;
                border: 1px solid #333333;
                padding: 0;
            }
            QComboBox QAbstractItemView::item {
                padding: 4px 6px;
                background-color: #0a0a0a;
                color: #c0c0c0;
            }
            QComboBox QAbstractItemView {
                selection-background-color: #1a1a1a;
                selection-color: #c0c0c0;
            }
            QComboBox QAbstractItemView::item:hover,
            QComboBox QAbstractItemView::item:selected {
                background-color: #1a1a1a;
                color: #c0c0c0;
            }
            QHeaderView::section { 
                background-color: #0a0a0a; 
                color: #888888; 
                padding: 4px; 
                border: 1px solid #333333; 
            }
            QTableView { 
                gridline-color: #1a1a1a; 
                selection-background-color: #1a1a1a; 
                selection-color: #c0c0c0; 
            }
            QListWidget::item { padding: 3px 4px; }
            QListWidget::item:selected { 
                background-color: #1a1a1a; 
                color: #c0c0c0; 
            }
            QLabel#thumb { 
                background-color: #0a0a0a; 
                border: 1px solid #333333; 
            }
        ''')
        # Theme applied; UI widgets not created yet here

    def _set_window_icon(self) -> None:
        """Try to load and set window icon from common locations."""
        # Possible icon locations (check .ico first on Windows, then .png)
        # In PyInstaller bundle, icon is in trading_app/ subdirectory
        # In dev mode, icon is in trading_app/ directory
        icon_paths = [
            resource_path('trading_app/icon.ico'),  # PyInstaller bundle or dev
            resource_path('trading_app/icon.png'),  # PyInstaller bundle or dev
        ]
        # Also check parent directory locations for dev mode
        if not getattr(sys, 'frozen', False):
            script_dir = Path(__file__).parent
            icon_paths.extend([
                script_dir.parent / 'icon.ico',  # abi-market-data/icon.ico
                script_dir.parent / 'icon.png',  # abi-market-data/icon.png
                script_dir.parent / 'assets' / 'icon.ico',  # abi-market-data/assets/icon.ico
                script_dir.parent / 'assets' / 'icon.png',  # abi-market-data/assets/icon.png
            ])
        
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

    def _on_filter_changed(self) -> None:
        """Handle filter changes with debouncing to prevent excessive refreshes."""
        # Restart the debounce timer - this will trigger refresh_view after 300ms of no changes
        self._filter_debounce_timer.stop()
        self._filter_debounce_timer.start(300)

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
        # Filter out blacklisted items
        blacklisted_keys = set(utils.load_blacklist())
        if blacklisted_keys:
            latest = latest[~latest['itemKey'].isin(blacklisted_keys)]
        # Keep presentation order: sort by price desc by default
        try:
            latest = latest.sort_values(['price'], ascending=[False])
        except Exception:
            pass
        return latest

    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:
        if event.type() == QtCore.QEvent.Type.KeyPress:
            if self._handle_key_press(event):
                return True
        return super().eventFilter(obj, event)

    def _handle_key_press(self, event: QtGui.QKeyEvent) -> bool:
        key = event.key()
        nav_keys = {
            QtCore.Qt.Key.Key_Up,
            QtCore.Qt.Key.Key_Down,
            QtCore.Qt.Key.Key_PageUp,
            QtCore.Qt.Key.Key_PageDown,
            QtCore.Qt.Key.Key_Home,
            QtCore.Qt.Key.Key_End,
        }
        if key not in nav_keys:
            return False
        focus = QtWidgets.QApplication.focusWidget()
        target = None
        if focus in (self.table, self.table.viewport()):
            target = 'table'
        elif focus is self.alerts_list:
            target = 'alerts'
        elif focus is self.trades_list:
            target = 'trades'
        else:
            return False
        if key == QtCore.Qt.Key.Key_Up:
            self._queue_keyboard_nav(target, 'relative', -1)
        elif key == QtCore.Qt.Key.Key_Down:
            self._queue_keyboard_nav(target, 'relative', 1)
        elif key == QtCore.Qt.Key.Key_PageUp:
            self._queue_keyboard_nav(target, 'relative', -self._page_step(target))
        elif key == QtCore.Qt.Key.Key_PageDown:
            self._queue_keyboard_nav(target, 'relative', self._page_step(target))
        elif key == QtCore.Qt.Key.Key_Home:
            self._queue_keyboard_nav(target, 'absolute', 'start')
        elif key == QtCore.Qt.Key.Key_End:
            self._queue_keyboard_nav(target, 'absolute', 'end')
        else:
            return False
        return True

    def _page_step(self, target: str) -> int:
        if target == 'table':
            try:
                viewport_height = self.table.viewport().height()
                row_height = self.table.verticalHeader().defaultSectionSize()
                step = viewport_height // max(1, row_height)
                return max(1, step)
            except Exception:
                return 10
        widget = self.alerts_list if target == 'alerts' else self.trades_list
        if widget.count() == 0:
            return 1
        try:
            item_height = widget.sizeHintForRow(0)
            step = widget.viewport().height() // max(1, item_height)
            return max(1, step)
        except Exception:
            return 10

    def _queue_keyboard_nav(self, target: str, kind: str, value: object) -> None:
        if (
            kind == 'relative'
            and self._pending_nav
            and self._pending_nav[0] == target
            and self._pending_nav[1] == 'relative'
        ):
            self._pending_nav = (target, 'relative', int(self._pending_nav[2]) + int(value))
        else:
            self._pending_nav = (target, kind, value)
        self._keyboard_nav_timer.start(30)

    def _process_pending_nav(self) -> None:
        if not self._pending_nav:
            return
        target, kind, value = self._pending_nav
        self._pending_nav = None
        if target == 'table':
            self._navigate_table(kind, value)
        elif target == 'alerts':
            self._navigate_list(self.alerts_list, 'alerts', kind, value)
        elif target == 'trades':
            self._navigate_list(self.trades_list, 'trades', kind, value)

    def _navigate_table(self, kind: str, value: object) -> None:
        model = self.table.model_
        if model is None or model.rowCount() == 0:
            return
        sel_model = self.table.selectionModel()
        current = sel_model.currentIndex() if sel_model is not None else QtCore.QModelIndex()
        if not current.isValid():
            current = model.index(0, 0)
        row = current.row() if current.isValid() else 0
        if kind == 'relative':
            row += int(value)
        elif kind == 'absolute':
            row = 0 if value == 'start' else model.rowCount() - 1
        row = max(0, min(model.rowCount() - 1, row))
        index = model.index(row, 0)
        if index.isValid():
            self._set_table_selection_for_index(index, scroll=True)

    def _navigate_list(self, widget: QtWidgets.QListWidget, source: str, kind: str, value: object) -> None:
        count = widget.count()
        if count == 0:
            return
        current_row = widget.currentRow()
        if current_row < 0:
            current_row = 0
        if kind == 'relative':
            current_row += int(value)
        elif kind == 'absolute':
            current_row = 0 if value == 'start' else count - 1
        current_row = max(0, min(count - 1, current_row))
        widget.setCurrentRow(current_row)
        item = widget.item(current_row)
        if item:
            item_key = item.data(QtCore.Qt.UserRole)
            if item_key:
                self._set_master_selection(item_key, source=source, table_index=None, scroll_table=True)

    def _apply_selection_from_table_index(
        self,
        index: QtCore.QModelIndex,
        *,
        source: str,
        scroll: bool,
    ) -> None:
        if not index.isValid():
            return
        if self._selection_guard:
            return
        model = self.table.model_
        if model is None:
            return
        item = model.item(index.row(), 4)
        if item is None:
            return
        item_key = item.data(QtCore.Qt.UserRole)
        if not item_key:
            return
        self._set_master_selection(item_key, source=source, table_index=index, scroll_table=scroll)

    def _find_table_index(self, item_key: str) -> QtCore.QModelIndex:
        model = self.table.model_
        if model is None:
            return QtCore.QModelIndex()
        for r in range(model.rowCount()):
            try:
                if model.item(r, 4).data(QtCore.Qt.UserRole) == item_key:
                    return model.index(r, 0)
            except Exception:
                continue
        return QtCore.QModelIndex()

    def _set_table_selection_for_index(self, index: QtCore.QModelIndex, *, scroll: bool) -> None:
        if not index.isValid():
            return
        sel_model = self.table.selectionModel()
        if sel_model is None:
            return
        current_idx = sel_model.currentIndex()
        if current_idx.isValid() and current_idx == index:
            if scroll:
                self.table.scrollTo(index, QtWidgets.QAbstractItemView.PositionAtCenter)
            return
        flags = QtCore.QItemSelectionModel.ClearAndSelect | QtCore.QItemSelectionModel.Rows
        sel_model.select(index, flags)
        sel_model.setCurrentIndex(index, QtCore.QItemSelectionModel.Current | QtCore.QItemSelectionModel.Rows)
        self.table.setCurrentIndex(index)
        if scroll:
            self.table.scrollTo(index, QtWidgets.QAbstractItemView.PositionAtCenter)

    def _sync_list_selection(self, widget: QtWidgets.QListWidget, item_key: str, *, active: bool) -> None:
        if widget is None or active:
            return
        blocker = QtCore.QSignalBlocker(widget)
        target_row = -1
        for i in range(widget.count()):
            try:
                if widget.item(i).data(QtCore.Qt.UserRole) == item_key:
                    target_row = i
                    break
            except Exception:
                continue
        if target_row >= 0:
            widget.setCurrentRow(target_row)
            widget.scrollToItem(widget.item(target_row), QtWidgets.QAbstractItemView.PositionAtCenter)
        else:
            widget.setCurrentRow(-1)
        del blocker

    def _update_selection_details(
        self,
        item_key: str,
        table_index: Optional[QtCore.QModelIndex],
    ) -> None:
        self._update_buy_button_state()
        self._update_blacklist_button_state()
        model = self.table.model_
        display_name = item_key or ''
        if (table_index is None or not table_index.isValid()) and item_key:
            table_index = self._find_table_index(item_key)
        if table_index is not None and table_index.isValid() and model is not None:
            row = table_index.row()
            try:
                display_name = model.item(row, 0).text()
            except Exception:
                pass
        df_full = self._filtered_df()
        if item_key:
            self.chart.plot(df_full, item_key, display_name)
        else:
            self.chart.plot(df_full, display_name, display_name)
        try:
            self.thumb_label.setText('')
            if not df_full.empty and item_key:
                if 'itemKey' in df_full.columns:
                    dfi = df_full[df_full['itemKey'] == item_key]
                else:
                    dfi = df_full[df_full['itemName'] == display_name]
                if not dfi.empty:
                    cand = []
                    if 'thumbPath' in dfi.columns:
                        for p in dfi['thumbPath']:
                            if isinstance(p, str) and p.strip():
                                cand.append(str(p))
                    seen = set()
                    cand = [x for x in cand if not (x in seen or seen.add(x))]
                    found_path = ''
                    thumb_hash = None
                    if 'thumbHash' in dfi.columns:
                        thumb_hash_values = dfi['thumbHash'].dropna().unique()
                        if len(thumb_hash_values) > 0:
                            thumb_hash = str(thumb_hash_values[0])
                    for thumb_rel in reversed(cand):
                        thumb_abs = thumb_rel
                        if not os.path.isabs(thumb_abs):
                            thumb_abs = os.path.normpath(os.path.join(self.cfg.snapshots_path, thumb_rel))
                        if os.path.exists(thumb_abs):
                            found_path = thumb_abs
                            break
                        alt_rel = thumb_rel.replace('/', os.sep).replace('\\', os.sep)
                        thumb_abs = os.path.normpath(os.path.join(self.cfg.snapshots_path, alt_rel))
                        if os.path.exists(thumb_abs):
                            found_path = thumb_abs
                            break
                    if not found_path and thumb_hash:
                        s3_config = utils.load_s3_config()
                        if s3_config and s3_config.get('use_s3'):
                            self.thumb_label.setText('⏳')
                            self.thumb_label.setStyleSheet('color: #888888; font-size: 24px;')
                            QtWidgets.QApplication.processEvents()
                            thumb_local_path = os.path.normpath(os.path.join(self.cfg.snapshots_path, 'thumbs', f"{thumb_hash}.png"))
                            if utils.download_thumbnail_from_s3(s3_config, thumb_hash, thumb_local_path):
                                if os.path.exists(thumb_local_path):
                                    found_path = thumb_local_path
                            else:
                                self.thumb_label.setStyleSheet('')
                    if found_path:
                        pix = QtGui.QPixmap(found_path)
                        if not pix.isNull():
                            self.thumb_label.setStyleSheet('')
                            target_w = self.thumb_label.width()
                            if pix.width() > target_w:
                                scaled = pix.scaledToWidth(target_w, QtCore.Qt.TransformationMode.SmoothTransformation)
                                self.thumb_label.setPixmap(scaled)
                            else:
                                self.thumb_label.setPixmap(pix)
                        else:
                            self.thumb_label.setStyleSheet('')
                            self.thumb_label.setPixmap(QtGui.QPixmap())
                    else:
                        self.thumb_label.setStyleSheet('')
                        self.thumb_label.setText('Thumbnail not found')
                else:
                    self.thumb_label.setText('')
            else:
                self.thumb_label.setText('')
        except Exception:
            self.thumb_label.setText('')
        QtCore.QCoreApplication.processEvents()
        QtCore.QTimer.singleShot(100, self.chart._show_latest_tooltip)
        self._refresh_trade_panels()

    def _set_master_selection(
        self,
        item_key: str,
        *,
        source: str,
        table_index: Optional[QtCore.QModelIndex],
        scroll_table: bool,
    ) -> None:
        if not item_key:
            return
        if self._selection_guard:
            return
        self._selection_guard = True
        try:
            self._current_item_key = item_key
            if table_index is None or not table_index.isValid():
                table_index = self._find_table_index(item_key)
            if table_index is not None and table_index.isValid() and source not in ('table', 'table-keyboard'):
                self._set_table_selection_for_index(table_index, scroll=scroll_table)
            self._sync_list_selection(self.alerts_list, item_key, active=(source == 'alerts'))
            self._sync_list_selection(self.trades_list, item_key, active=(source == 'trades'))
            self._update_selection_details(item_key, table_index)
        finally:
            self._selection_guard = False

    def _set_table_selection_for_key(self, key: str, *, scroll: bool = False) -> None:
        if not key:
            return
        index = self._find_table_index(key)
        if index.isValid():
            self._set_table_selection_for_index(index, scroll=scroll)

    def refresh_view(self, skip_auto_selection: bool = False) -> None:
        # Preserve the top-visible row's itemKey and current selection
        viewport = self.table.viewport()
        top_index = self.table.indexAt(QtCore.QPoint(0, 0))
        top_key = ''
        if top_index.isValid():
            try:
                top_key = self.table.model_.item(top_index.row(), 4).data(QtCore.Qt.UserRole)  # itemKey stored in ma% column (4)
            except Exception:
                top_key = ''
        sel_index = self.table.currentIndex()
        sel_key = self._current_item_key or ''
        if not sel_key and sel_index.isValid():
            try:
                sel_key = self.table.model_.item(sel_index.row(), 4).data(QtCore.Qt.UserRole)  # itemKey stored in ma% column (4)
            except Exception:
                sel_key = ''
        
        # Preserve sort order
        header = self.table.horizontalHeader()
        sort_column = header.sortIndicatorSection()
        sort_order = header.sortIndicatorOrder()
        # Default to column 4 (ma%) descending if no sort is set
        # Also default to ma% if sort is on item column (0) - user likely hasn't sorted yet
        if sort_column < 0 or sort_column == 0:
            sort_column = 4
            sort_order = QtCore.Qt.SortOrder.DescendingOrder

        df_full = self._filtered_df()
        df = self._latest_per_item(df_full)
        blocker = QtCore.QSignalBlocker(self.table)
        # Also block the selection model signals to prevent loops
        selection_blocker = QtCore.QSignalBlocker(self.table.selectionModel()) if self.table.selectionModel() else None
        self.table.setUpdatesEnabled(False)
        try:
            self.table.load(df)
            QtCore.QCoreApplication.processEvents()
            # Restore sort order
            try:
                self.table.model_.sort(sort_column, sort_order)
                # Update header sort indicator to match
                header.setSortIndicator(sort_column, sort_order)
            except Exception:
                pass
            # Helper to find model row by itemKey
            def _find_row_by_key(key: str) -> int:
                if not key:
                    return -1
                m = self.table.model_
                for r in range(m.rowCount()):
                    try:
                        if m.item(r, 4).data(QtCore.Qt.UserRole) == key:  # itemKey stored in ma% column (4)
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
        # Ensure a row is selected and chart/thumbnail shown (unless skipping auto-selection)
        if not skip_auto_selection:
            target_index = QtCore.QModelIndex()
            if sel_key:
                target_index = self._find_table_index(sel_key)
            if not target_index.isValid():
                current = self.table.currentIndex()
                if current.isValid():
                    target_index = current
            if not target_index.isValid() and self.table.model_.rowCount() > 0:
                target_index = self.table.model_.index(0, 0)
            if target_index.isValid():
                self._apply_selection_from_table_index(target_index, source='refresh', scroll=False)
            else:
                self.chart.plot(pd.DataFrame(), '', '')

    def _on_table_clicked(self, index: QtCore.QModelIndex) -> None:
        if self._selection_guard:
            return
        self._apply_selection_from_table_index(index, source='table', scroll=False)

    def _on_table_current_changed(self, current: QtCore.QModelIndex, prev: QtCore.QModelIndex) -> None:
        if self._selection_guard:
            return
        self._apply_selection_from_table_index(current, source='table', scroll=False)

    def _update_alerts(self) -> None:
        # Preserve current selection key
        prev_key = ''
        cur_item = self.alerts_list.currentItem()
        if cur_item is not None:
            try:
                prev_key = cur_item.data(QtCore.Qt.UserRole) or ''
            except Exception:
                prev_key = ''
        blocker = QtCore.QSignalBlocker(self.alerts_list)
        self.alerts_list.clear()
        alerts = utils.find_alerts(
            self.df_all,
            spike_pct=float(self.cfg.alerts.get('spike_threshold_pct', 20.0)),
            drop_pct=float(self.cfg.alerts.get('drop_threshold_pct', 20.0)),
        )
        # Sort: biggest losers at top, biggest gainers at bottom
        alerts.sort(key=lambda a: a.get('delta', 0.0), reverse=False)
        for a in alerts:
            raw_text = a.get('text', '')
            # Remove any leading emoji from utils, keep plain text
            display_text = raw_text[1:].strip() if raw_text[:1] in ('🔺', '🔻') else raw_text
            item = QtWidgets.QListWidgetItem(display_text)
            # Store itemKey and category for click handling
            item.setData(QtCore.Qt.UserRole, a.get('itemKey', ''))
            item.setData(QtCore.Qt.UserRole + 1, a.get('category', ''))
            # Add colored icon and text color
            t = a.get('type')
            if t in ('spike', 'drop'):
                color = QtGui.QColor(0, 255, 136) if t == 'spike' else QtGui.QColor(255, 68, 68)  # Neon green/red
                direction = 'up' if t == 'spike' else 'down'
                icon = self._make_alert_icon(color, direction)
                if icon is not None:
                    item.setIcon(icon)
                # Color the text to match the icon
                item.setForeground(QtGui.QBrush(color))
            self.alerts_list.addItem(item)
        # Restore selection without emitting signals
        if prev_key:
            for i in range(self.alerts_list.count()):
                it = self.alerts_list.item(i)
                try:
                    if it.data(QtCore.Qt.UserRole) == prev_key:
                        self.alerts_list.setCurrentItem(it)
                        break
                except Exception:
                    continue
        del blocker

    def _update_trades_widget(self) -> None:
        # Preserve current selection key
        prev_key = ''
        cur_item = self.trades_list.currentItem()
        if cur_item is not None:
            try:
                prev_key = cur_item.data(QtCore.Qt.UserRole) or ''
            except Exception:
                prev_key = ''
        blocker = QtCore.QSignalBlocker(self.trades_list)
        self.trades_list.clear()
        trade_items = utils.find_trades_items(self.df_all)
        for w in trade_items:
            item = QtWidgets.QListWidgetItem(w.get('text', ''))
            # Store itemKey and category for click handling
            item.setData(QtCore.Qt.UserRole, w.get('itemKey', ''))
            item.setData(QtCore.Qt.UserRole + 1, w.get('category', ''))
            # Add colored icon and text color like Top Movers
            t = w.get('type')
            if t in ('spike', 'drop'):
                color = QtGui.QColor(0, 255, 136) if t == 'spike' else QtGui.QColor(255, 68, 68)  # Neon green/red
                direction = 'up' if t == 'spike' else 'down'
                icon = self._make_alert_icon(color, direction)
                if icon is not None:
                    item.setIcon(icon)
                # Color the text to match the icon
                item.setForeground(QtGui.QBrush(color))
            self.trades_list.addItem(item)
        # Restore selection without emitting signals
        if prev_key:
            for i in range(self.trades_list.count()):
                it = self.trades_list.item(i)
                try:
                    if it.data(QtCore.Qt.UserRole) == prev_key:
                        self.trades_list.setCurrentItem(it)
                        break
                except Exception:
                    continue
        del blocker
    
    def _update_buy_button_state(self) -> None:
        """Enable/disable Buy button based on selection and blacklist state."""
        if not self._current_item_key:
            self.buy_btn.setEnabled(False)
            # Reset to default gray styling
            self.buy_btn.setStyleSheet('''
                QPushButton {
                    background-color: #1a1a1a;
                    border: 1px solid #333333;
                    border-radius: 4px;
                    font-size: 14px;
                    color: #888888;
                }
                QPushButton:hover {
                    background-color: #2a2a2a;
                    border-color: #555555;
                    color: #c0c0c0;
                }
                QPushButton:pressed {
                    background-color: #0a0a0a;
                }
            ''')
        else:
            self.buy_btn.setEnabled(True)
            self.buy_btn.setStyleSheet('''
                QPushButton {
                    background-color: #1a1a1a;
                    border: 1px solid #333333;
                    border-radius: 4px;
                    font-size: 14px;
                    color: #00ff88;
                }
                QPushButton:hover {
                    background-color: #2a2a2a;
                    border-color: #555555;
                    color: #00ff88;
                }
                QPushButton:pressed {
                    background-color: #0a0a0a;
                }
            ''')
    
    def _update_blacklist_button_state(self) -> None:
        """Update the blacklist button to show active state based on current item."""
        if not self._current_item_key:
            self.blacklist_btn.setText('✕')
            self.blacklist_btn.setEnabled(False)
            # Reset to default gray styling
            self.blacklist_btn.setStyleSheet('''
                QPushButton {
                    background-color: #1a1a1a;
                    border: 1px solid #333333;
                    border-radius: 4px;
                    font-size: 16px;
                    color: #888888;
                }
                QPushButton:hover {
                    background-color: #2a2a2a;
                    border-color: #555555;
                    color: #c0c0c0;
                }
                QPushButton:pressed {
                    background-color: #0a0a0a;
                }
            ''')
        else:
            self.blacklist_btn.setEnabled(True)
            if utils.is_blacklisted(self._current_item_key):
                self.blacklist_btn.setText('✕')
                # Red color for blacklisted state
                self.blacklist_btn.setStyleSheet('''
                    QPushButton {
                        background-color: #1a1a1a;
                        border: 1px solid #333333;
                        border-radius: 4px;
                        font-size: 16px;
                        color: #ff4444;
                    }
                    QPushButton:hover {
                        background-color: #2a2a2a;
                        border-color: #555555;
                        color: #ff6666;
                    }
                    QPushButton:pressed {
                        background-color: #0a0a0a;
                    }
                ''')
            else:
                self.blacklist_btn.setText('✕')
                # Reset to default gray styling
                self.blacklist_btn.setStyleSheet('''
                    QPushButton {
                        background-color: #1a1a1a;
                        border: 1px solid #333333;
                        border-radius: 4px;
                        font-size: 16px;
                        color: #888888;
                    }
                    QPushButton:hover {
                        background-color: #2a2a2a;
                        border-color: #555555;
                        color: #c0c0c0;
                    }
                    QPushButton:pressed {
                        background-color: #0a0a0a;
                    }
                ''')
    
    def _on_blacklist_btn_clicked(self) -> None:
        """Toggle current item in blacklist."""
        if not self._current_item_key:
            return
        if utils.is_blacklisted(self._current_item_key):
            utils.remove_from_blacklist(self._current_item_key)
        else:
            utils.add_to_blacklist(self._current_item_key)
        self._update_blacklist_button_state()
        self._update_buy_button_state()
        # Refresh view to hide/show the item and update widgets
        self.refresh_view()
        self._update_alerts()  # Update Top Movers
        self._update_trades_widget()  # Update My Trades
        self._refresh_trade_panels()
        self._update_top_stats()

    def _on_buy_btn_clicked(self) -> None:
        """Prompt for quantity and expense to add a trade for current item."""
        if not self._current_item_key:
            return
        qty, expense, ok = self._prompt_buy_details()
        if not ok:
            return
        # Derive display name
        display_name = ''
        try:
            display_name = self.table.model_.item(self.table.currentIndex().row(), 0).text()
        except Exception:
            display_name = self._current_item_key
        utils.add_trade(self._current_item_key, display_name, qty, expense)
        self._update_trades_widget()
        self._refresh_trade_panels()
        self._update_top_stats()

    def _handle_list_item_selection(self, item: QtWidgets.QListWidgetItem, source: str) -> None:
        if self._selection_guard:
            return
        item_key = item.data(QtCore.Qt.UserRole)
        category = item.data(QtCore.Qt.UserRole + 1)
        if not item_key:
            return
        if category and self.category_cb.currentText() != category:
            cb_blocker = QtCore.QSignalBlocker(self.category_cb)
            self.category_cb.setCurrentText(category)
            del cb_blocker
        for widget in (self.item_edit, self.price_min, self.price_max):
            blk = QtCore.QSignalBlocker(widget)
            widget.setText('')
            del blk
        self.refresh_view(skip_auto_selection=True)
        index = self._find_table_index(item_key)
        if index.isValid():
            self._apply_selection_from_table_index(index, source=source, scroll=True)
        else:
            self._set_master_selection(item_key, source=source, table_index=None, scroll_table=False)

    def _on_alert_clicked(self, item: QtWidgets.QListWidgetItem) -> None:
        self._handle_list_item_selection(item, 'alerts')

    def _on_alert_current_changed(self, current: QtWidgets.QListWidgetItem, prev: QtWidgets.QListWidgetItem) -> None:
        if current is not None:
            self._on_alert_clicked(current)

    def _on_trade_widget_clicked(self, item: QtWidgets.QListWidgetItem) -> None:
        self._handle_list_item_selection(item, 'trades')

    def _on_trade_widget_current_changed(self, current: QtWidgets.QListWidgetItem, prev: QtWidgets.QListWidgetItem) -> None:
        if current is not None:
            self._on_trade_widget_clicked(current)

    def _prompt_buy_details(self) -> tuple[int, float, bool]:
        """Show a single dialog to capture Quantity and Total Expense.
        Returns (quantity, expense, ok)."""
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle('Buy')
        layout = QtWidgets.QFormLayout(dlg)
        qty_edit = QtWidgets.QLineEdit(dlg)
        qty_edit.setPlaceholderText('e.g. 5')
        qty_edit.setText('1')
        expense_edit = QtWidgets.QLineEdit(dlg)
        expense_edit.setPlaceholderText('e.g. 12345')
        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel, parent=dlg)
        layout.addRow('Quantity', qty_edit)
        layout.addRow('Total expense', expense_edit)
        layout.addRow(btns)
        def accept() -> None:
            dlg.accept()
        def reject() -> None:
            dlg.reject()
        btns.accepted.connect(accept)
        btns.rejected.connect(reject)
        ok = dlg.exec() == QtWidgets.QDialog.Accepted
        if not ok:
            return 0, 0.0, False
        try:
            qty = int(str(qty_edit.text()).replace(',', '').strip())
        except ValueError:
            qty = 0
        try:
            expense = float(str(expense_edit.text()).replace(',', '').strip())
        except ValueError:
            expense = 0.0
        if qty <= 0:
            return 0, 0.0, False
        return qty, expense, True

    def _build_trading_panel(self, main_layout: QtWidgets.QHBoxLayout) -> None:
        # Right column: Active Trades (top) and Completed Trades (bottom)
        panel = QtWidgets.QWidget(self)
        panel_layout = QtWidgets.QVBoxLayout(panel)
        panel_layout.setContentsMargins(10, 0, 10, 10)
        panel_layout.setSpacing(8)

        panel_layout.addWidget(QtWidgets.QLabel('Active Trades'))
        self.active_scroll = QtWidgets.QScrollArea(self)
        self.active_scroll.setWidgetResizable(True)
        self.active_scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.active_scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.active_scroll.setStyleSheet(
            'QScrollArea { background-color: transparent; border: none; }'
        )
        self.active_content = QtWidgets.QWidget(self)
        self.active_content.setStyleSheet('QWidget { background-color: transparent; }')
        self.active_layout = QtWidgets.QVBoxLayout(self.active_content)
        self.active_layout.setContentsMargins(0, 0, 0, 0)
        self.active_layout.setSpacing(6)
        self.active_layout.addStretch(1)
        self.active_scroll.setWidget(self.active_content)
        self.active_scroll.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        panel_layout.addWidget(self.active_scroll, 3)

        panel_layout.addWidget(QtWidgets.QLabel('Completed Trades'))
        self.completed_scroll = QtWidgets.QScrollArea(self)
        self.completed_scroll.setWidgetResizable(True)
        self.completed_scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.completed_scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.completed_scroll.setStyleSheet(
            'QScrollArea { background-color: transparent; border: none; }'
        )
        self.completed_content = QtWidgets.QWidget(self)
        self.completed_content.setStyleSheet('QWidget { background-color: transparent; }')
        self.completed_layout = QtWidgets.QVBoxLayout(self.completed_content)
        self.completed_layout.setContentsMargins(0, 0, 0, 0)
        self.completed_layout.setSpacing(6)
        self.completed_layout.addStretch(1)
        self.completed_scroll.setWidget(self.completed_content)
        self.completed_scroll.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        panel_layout.addWidget(self.completed_scroll, 2)

        main_layout.addWidget(panel, 1)

    def _make_trade_card(self, trade: dict, completed: bool = False) -> QtWidgets.QWidget:
        card = QtWidgets.QFrame(self)
        card.setFrameShape(QtWidgets.QFrame.NoFrame)
        card.setStyleSheet('QFrame { background-color: #1a1a1a; border: none; }')
        v = QtWidgets.QVBoxLayout(card)
        v.setContentsMargins(8, 8, 8, 8)

        status = str(trade.get('status') or utils.TRADE_STATUSES[0])

        def parse_status_code(value: str) -> int:
            try:
                return int(str(value).split('-', 1)[0].strip())
            except Exception:
                return -1

        status_code = parse_status_code(status)
        if not completed:
            status_cb = QtWidgets.QComboBox(self)
            for s in utils.TRADE_STATUSES[:4]:
                status_cb.addItem(s)
            status_cb.blockSignals(True)
            status_cb.setCurrentText(status)
            status_cb.blockSignals(False)
            status_cb.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)

            def ignore_wheel_event(event: QtGui.QWheelEvent) -> None:
                event.ignore()

            status_cb.wheelEvent = ignore_wheel_event  # type: ignore
            status_cb.setStyleSheet('''
                QComboBox {
                    background-color: #0a0a0a;
                    color: #c0c0c0;
                    border: 1px solid #333333;
                    padding: 2px 4px;
                }
                QComboBox::drop-down { border: none; }
                QComboBox::down-arrow { image: none; }
            ''')
            status_cb.setItemDelegate(QtWidgets.QStyledItemDelegate(status_cb))
            view = status_cb.view()
            if isinstance(view, QtWidgets.QListView):
                view.setStyleSheet('''
                    QListView {
                        background-color: #0a0a0a;
                        border: 1px solid #333333;
                        padding: 0;
                        outline: none;
                    }
                    QListView::item {
                        padding: 4px 6px;
                        background-color: #0a0a0a;
                        color: #c0c0c0;
                    }
                    QListView::item:hover,
                    QListView::item:selected {
                        background-color: #1a1a1a;
                        color: #c0c0c0;
                    }
                ''')
            v.addWidget(status_cb)
        else:
            status_cb = None

        details_widget = QtWidgets.QWidget(self)
        rows_container = QtWidgets.QVBoxLayout(details_widget)
        rows_container.setContentsMargins(0, 2, 0, 0)
        rows_container.setSpacing(2)

        def add_row(target_layout: QtWidgets.QVBoxLayout, label_text: str, value_text: str) -> None:
            row_frame = QtWidgets.QFrame(self)
            row_frame.setFrameShape(QtWidgets.QFrame.NoFrame)
            row_frame.setStyleSheet('QFrame { border: none; background-color: transparent; } QLabel { border: none; }')
            layout = QtWidgets.QHBoxLayout(row_frame)
            layout.setContentsMargins(0, 2, 0, 2)
            layout.setSpacing(6)
            label = QtWidgets.QLabel(label_text)
            value = QtWidgets.QLabel(value_text)
            label.setStyleSheet('color: #888888;')
            value.setStyleSheet('color: #c0c0c0;')
            layout.addWidget(label, 0)
            layout.addStretch(1)
            layout.addWidget(value, 0)
            target_layout.addWidget(row_frame)

        qty = int(trade.get('quantity') or 0)
        expense = float(trade.get('expense') or 0.0)
        income = float(trade.get('income') or 0.0)
        buy = (expense / qty) if qty else 0.0
        sell = (income / qty) if qty else 0.0
        profit = income - expense
        roi_pct = ((profit / expense) * 100.0) if expense > 0 else 0.0

        if completed:
            details_widget.setVisible(False)
            header = QtWidgets.QFrame(self)
            header.setFrameShape(QtWidgets.QFrame.NoFrame)
            header_layout = QtWidgets.QHBoxLayout(header)
            header_layout.setContentsMargins(0, 0, 0, 0)
            header_layout.setSpacing(6)
            status_text = status.split('-', 1)[1].strip() if '-' in status else status
            status_label = QtWidgets.QLabel(status_text)
            status_label.setStyleSheet('color: #c0c0c0; font-weight: bold;')
            header_layout.addWidget(status_label)
            header_layout.addStretch(1)
            if status_code == 5:
                roi_color = '#00ff88' if roi_pct >= 0 else '#ff4444'
                roi_label = QtWidgets.QLabel(f'{roi_pct:.0f}%')
                roi_label.setStyleSheet(f'color: {roi_color}; font-weight: bold;')
                header_layout.addWidget(roi_label)
            toggle_btn = QtWidgets.QToolButton(self)
            toggle_btn.setText('▸')
            toggle_btn.setCheckable(True)
            toggle_btn.setChecked(False)
            toggle_btn.setAutoRaise(True)
            toggle_btn.setStyleSheet('''
                QToolButton {
                    color: #888888;
                    padding: 0px;
                }
                QToolButton:checked {
                    color: #c0c0c0;
                }
            ''')
            header_layout.addWidget(toggle_btn)
            v.addWidget(header)

            def update_details(checked: bool) -> None:
                details_widget.setVisible(checked)
                toggle_btn.setText('▾' if checked else '▸')

            toggle_btn.toggled.connect(update_details)

            if status_code == 6:
                add_row(rows_container, 'Qty', f'{qty}')
                add_row(rows_container, 'Expense', f'{expense:,.0f}')
            else:
                add_row(rows_container, 'Qty', f'{qty}')
                add_row(rows_container, 'Expense', f'{expense:,.0f}')
                add_row(rows_container, 'Income', f'{income:,.0f}')
                add_row(rows_container, 'Buy', f'{buy:,.0f}')
                add_row(rows_container, 'Sell', f'{sell:,.0f}')
                add_row(rows_container, 'ROI', f'{roi_pct:.0f}%')
                add_row(rows_container, 'Gross', f'{profit:,.0f}')
        else:
            details_widget.setVisible(True)
            add_row(rows_container, 'Qty', f'{qty}')
            add_row(rows_container, 'Expense', f'{expense:,.0f}')
            add_row(rows_container, 'Buy', f'{buy:,.0f}')

            action_row = QtWidgets.QWidget(self)
            action_layout = QtWidgets.QHBoxLayout(action_row)
            action_layout.setContentsMargins(0, 6, 0, 0)
            action_layout.setSpacing(8)
            action_layout.addStretch(1)

            lost_btn = QtWidgets.QPushButton('Lost')
            lost_btn.setFixedWidth(70)
            lost_btn.setStyleSheet('''
                QPushButton {
                    background-color: #1a1a1a;
                    border: 1px solid #333333;
                    border-radius: 4px;
                    color: #ff4444;
                }
                QPushButton:hover {
                    background-color: #2a2a2a;
                    border-color: #555555;
                    color: #ff6666;
                }
                QPushButton:pressed {
                    background-color: #0a0a0a;
                }
                QPushButton:disabled {
                    background-color: #0f0f0f;
                    border-color: #222222;
                    color: #444444;
                }
            ''')
            lost_btn.clicked.connect(lambda _=False, t=dict(trade): self._mark_trade_lost(t))
            action_layout.addWidget(lost_btn, 0)

            sell_btn = QtWidgets.QPushButton('Sold')
            sell_btn.setFixedWidth(70)
            sell_btn.setStyleSheet('''
                QPushButton {
                    background-color: #1a1a1a;
                    border: 1px solid #333333;
                    border-radius: 4px;
                    color: #00ff88;
                }
                QPushButton:hover {
                    background-color: #2a2a2a;
                    border-color: #555555;
                    color: #00ff88;
                }
                QPushButton:pressed {
                    background-color: #0a0a0a;
                }
                QPushButton:disabled {
                    background-color: #0f0f0f;
                    border-color: #222222;
                    color: #444444;
                }
            ''')
            sell_btn.clicked.connect(lambda _=False, t=dict(trade): self._mark_trade_sold(t))
            action_layout.addWidget(sell_btn, 0)

            def update_action_buttons(status_text: str) -> None:
                code = parse_status_code(status_text)
                lost_btn.setEnabled(code == 2)
                sell_btn.setEnabled(code == 4)

            update_action_buttons(status)

            if status_cb is not None:

                def on_status_changed(text: str) -> None:
                    update_action_buttons(text)
                    item_key = trade.get('itemKey')
                    if not item_key:
                        return
                    utils.update_trade(
                        item_key,
                        {'status': text},
                        trade_id=trade.get('tradeId'),
                    )
                    self._refresh_trade_panels()
                    self._update_trades_widget()
                    self._update_top_stats()

                status_cb.currentTextChanged.connect(on_status_changed)

            rows_container.addWidget(action_row)

        v.addWidget(details_widget)

        return card

    def _refresh_trade_panels(self) -> None:
        # Active trades
        # Clear active layout (except final stretch)
        while self.active_layout.count() > 1:
            item = self.active_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        key = self._current_item_key or ''
        active = [t for t in utils.list_active_trades() if key and t.get('itemKey') == key]
        # Sort by createdAt (newest first) - timestamp in milliseconds
        active.sort(key=lambda t: int(t.get('createdAt', 0) or 0), reverse=True)
        if not active:
            # Show helpful empty state
            msg = QtWidgets.QLabel('No active trades found...')
            msg.setStyleSheet('color: #888888;')
            msg.setAlignment(QtCore.Qt.AlignCenter)
            self.active_layout.insertWidget(self.active_layout.count() - 1, msg)
        else:
            for t in active:
                w = self._make_trade_card(t, completed=False)
                if w is not None:
                    w.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Maximum)
                    self.active_layout.insertWidget(self.active_layout.count() - 1, w)
        # Completed trades
        while self.completed_layout.count() > 1:
            item = self.completed_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        done = [t for t in utils.list_completed_trades() if key and t.get('itemKey') == key]
        # Sort by createdAt (newest first) - timestamp in milliseconds
        done.sort(key=lambda t: int(t.get('createdAt', 0) or 0), reverse=True)
        if not done:
            msg = QtWidgets.QLabel('No completed trades found...')
            msg.setStyleSheet('color: #888888;')
            msg.setAlignment(QtCore.Qt.AlignCenter)
            self.completed_layout.insertWidget(self.completed_layout.count() - 1, msg)
        else:
            for t in done:
                w = self._make_trade_card(t, completed=True)
                if w is not None:
                    w.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Maximum)
                    self.completed_layout.insertWidget(self.completed_layout.count() - 1, w)

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

    def _on_table_double_clicked(self, index: QtCore.QModelIndex) -> None:
        model = self.table.model_
        if not index.isValid():
            return
        row = index.row()
        item_key = model.item(row, 4).data(QtCore.Qt.UserRole)  # itemKey stored in ma% column (4)
        if not item_key:
            return
        current_display = model.item(row, 0).text()  # display name in item column (0)
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

    def _mark_trade_sold(self, trade: dict) -> None:
        if not trade:
            return
        item_key = trade.get('itemKey')
        trade_id = trade.get('tradeId')
        income_text, ok = QtWidgets.QInputDialog.getText(self, 'Sell', 'Total income:')
        if not ok:
            return
        try:
            income = float(str(income_text).replace(',', '').strip())
        except ValueError:
            income = 0.0
        if item_key:
            utils.update_trade(item_key, {'income': income, 'status': '5 - Sold'}, trade_id=trade_id)
            self._refresh_trade_panels()
            self._update_trades_widget()
            self._update_top_stats()

    def _mark_trade_lost(self, trade: dict) -> None:
        if not trade:
            return
        item_key = trade.get('itemKey')
        trade_id = trade.get('tradeId')
        if item_key:
            utils.update_trade(item_key, {'status': '6 - Lost'}, trade_id=trade_id)
            self._refresh_trade_panels()
            self._update_trades_widget()


def main() -> int:
    app = QtWidgets.QApplication(sys.argv)

    def show_critical_dialog(parent: Optional[QtWidgets.QWidget], message: str) -> None:
        dialog = QtWidgets.QMessageBox(parent)
        dialog.setIcon(QtWidgets.QMessageBox.Critical)
        dialog.setWindowTitle('Error')
        dialog.setText(message)
        icon_candidates = [
            resource_path('trading_app/icon.ico'),
            resource_path('trading_app/icon.png'),
        ]
        for candidate in icon_candidates:
            candidate_path = Path(candidate)
            if candidate_path.exists():
                icon = QtGui.QIcon(str(candidate_path))
                if not icon.isNull():
                    dialog.setWindowIcon(icon)
                    break
        dialog.exec()

    # Ensure required user data files exist before continuing
    required_files = ['trades.json', 'blacklist.json']
    missing_files = [name for name in required_files if not utils.user_data_path(name).exists()]
    if missing_files:
        show_critical_dialog(
            None,
            'User data not found. Please locate trades.json and blacklist.json and make sure they are in the same directory as ABI_Trading_Platform.exe.',
        )
        return 1

    # Load config - works in both dev and PyInstaller bundle
    config_path = resource_path('trading_app/config.yaml')
    
    # Load config to get snapshots path and limit
    cfg = utils.load_config(str(config_path))
    snapshots_path = cfg.snapshots_path
    limit = cfg.max_snapshots_to_load
    
    # Check if we need to show loading screen
    # Show loading if S3 is configured and we need to download, or if no snapshots exist locally
    s3_config = utils.load_s3_config()
    show_loading = False
    
    if s3_config and s3_config.get('use_s3'):
        # Always show loading screen when S3 is configured since we load directly from S3
        # (no disk caching, so we always need to download from S3)
        show_loading = True
    else:
        # No S3 config - check if we have local snapshots
        # If no local snapshots, loading will be fast, so skip loading screen
        local_files = utils.list_local_snapshots(snapshots_path, limit=1)
        has_local_snapshots = len(local_files) > 0
        show_loading = False  # Local loading is fast, no need for loading screen
    
    if show_loading:
        # Show loading screen
        loading_screen = LoadingScreen()
        loading_screen.show()
        app.processEvents()
        
        # Create and start snapshot loader
        loader = SnapshotLoader(str(config_path), snapshots_path, limit)
        
        def on_progress(message: str, progress: int):
            loading_screen.update_status(message, progress)
        
        main_window = [None]  # Use list to allow modification in nested functions
        
        def on_finished(snapshots: list):
            try:
                # Create main window on main thread BEFORE closing loading screen
                # This ensures the app has a window to show
                main_window[0] = MainWindow(str(config_path), snapshots)
                main_window[0].resize(1400, 700)
                main_window[0].show()
                # Close loading screen after main window is shown
                loading_screen.close()
                # Ensure the main window gets focus
                main_window[0].raise_()
                main_window[0].activateWindow()
            except Exception as e:
                print(f"[!] Error creating main window: {e}")
                import traceback
                traceback.print_exc()
                # Try to show error - but keep loading screen open so app doesn't quit
                try:
                    show_critical_dialog(
                        loading_screen,
                        f'Failed to create main window:\n{e}\n\nCheck console for details.'
                    )
                except:
                    pass
                # Don't quit - let user see the error
                loading_screen.update_status(f'Error: {str(e)}', None)
        
        def on_error(error_msg: str):
            message = error_msg or 'Unexpected error while loading data.'
            try:
                show_critical_dialog(loading_screen, message)
            finally:
                loading_screen.close()
                loader.wait(0)
                app_instance = QtWidgets.QApplication.instance()
                if app_instance is not None:
                    app_instance.exit(1)
        
        loader.progress.connect(on_progress)
        loader.finished.connect(on_finished)
        loader.error.connect(on_error)
        loader.start()
        
        # Run app - loading screen will close and main window will show when done
        return app.exec()
    else:
        # Fast path: load snapshots synchronously (they're already cached)
        try:
            snapshots = utils.load_all_snapshots(snapshots_path, limit=limit)
        except utils.DataServiceUnavailable:
            show_critical_dialog(
                None,
                'Data service not available. Please try again later.',
            )
            return 1
        except Exception as exc:
            show_critical_dialog(
                None,
                f'Failed to load data: {exc}',
            )
            return 1
        win = MainWindow(str(config_path), snapshots)
        win.resize(1400, 700)
        win.show()
        return app.exec()


if __name__ == '__main__':
    sys.exit(main())

