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
        
        # Automatically show tooltip for the latest data point after chart is rendered
        if MPLCURSORS_AVAILABLE and self._cursor is not None and self._data_points:
            # Process events to ensure canvas is drawn, then show tooltip
            QtCore.QCoreApplication.processEvents()
            QtCore.QTimer.singleShot(200, self._show_latest_tooltip)
    
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
        headers = ['item', 'category', 'price', 'ma', 'ma%', 'vol', 'vol%']
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
            # Store itemKey in user role for proper item identification when clicking (on ma% column, index 4)
            items[4].setData(row.get('itemKey', ''), QtCore.Qt.UserRole)
            self.model_.appendRow(items)
        # Set column widths: numeric columns (price, ma, ma%, vol, vol%) at 85% of content size
        # Text columns (item, category) share remaining space
        header = self.horizontalHeader()
        # Column indices: item=0, category=1, price=2, ma=3, ma%=4, vol=5, vol%=6
        numeric_cols = [2, 3, 4, 5, 6]  # price, ma, ma%, vol, vol%
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

        # Debounce timer for filter changes to prevent excessive refreshes
        self._filter_debounce_timer = QtCore.QTimer(self)
        self._filter_debounce_timer.setSingleShot(True)
        self._filter_debounce_timer.timeout.connect(self.refresh_view)

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

        # My Watchlist
        self.watchlist_list = QtWidgets.QListWidget(self)
        left_layout.addWidget(QtWidgets.QLabel('My Watchlist'))
        left_layout.addWidget(self.watchlist_list)

        # Right: Chart + Table + Thumbnail (thumbnail to the right of chart)
        right = QtWidgets.QWidget(self)
        right_layout = QtWidgets.QVBoxLayout(right)
        main_layout.addWidget(right, 3)

        # Chart + Thumbnail row (non-movable, chart takes remaining space)
        self.chart = TrendChart(self)
        
        # Thumbnail area with buttons above it
        thumb_area = QtWidgets.QWidget(self)
        thumb_layout = QtWidgets.QVBoxLayout(thumb_area)
        thumb_layout.setContentsMargins(0, 0, 0, 0)
        thumb_layout.setSpacing(4)
        
        # Button row for watchlist and blacklist
        button_row = QtWidgets.QWidget(self)
        button_row_layout = QtWidgets.QHBoxLayout(button_row)
        button_row_layout.setContentsMargins(0, 0, 0, 0)
        button_row_layout.setSpacing(4)
        
        # Star button for watchlist
        self.watchlist_btn = QtWidgets.QPushButton(self)
        self.watchlist_btn.setText('☆')
        self.watchlist_btn.setFixedSize(30, 30)
        self.watchlist_btn.setStyleSheet('''
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
        
        button_row_layout.addWidget(self.watchlist_btn)
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
        self.watchlist_list.itemClicked.connect(self._on_watchlist_clicked)
        self.watchlist_btn.clicked.connect(self._on_watchlist_btn_clicked)
        self.blacklist_btn.clicked.connect(self._on_blacklist_btn_clicked)

        # Track current selected itemKey for button states
        self._current_item_key = None

        # Initial load
        self.refresh_view()
        self._update_alerts()
        self._update_watchlist()
        # Initialize blacklist button state
        self._update_blacklist_button_state()

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
        sel_key = ''
        if sel_index.isValid():
            try:
                sel_key = self.table.model_.item(sel_index.row(), 4).data(QtCore.Qt.UserRole)  # itemKey stored in ma% column (4)
            except Exception:
                sel_key = ''

        df_full = self._filtered_df()
        df = self._latest_per_item(df_full)
        blocker = QtCore.QSignalBlocker(self.table)
        # Also block the selection model signals to prevent loops
        selection_blocker = QtCore.QSignalBlocker(self.table.selectionModel()) if self.table.selectionModel() else None
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
            # Get itemKey from stored user data (stored in ma% column, index 4)
            item_key = model.item(row, 4).data(QtCore.Qt.UserRole)
            display_name = model.item(row, 0).text()  # item column
            category = model.item(row, 1).text()  # category column
            
            # Store current item key for button states
            self._current_item_key = item_key
            self._update_watchlist_button_state()
            self._update_blacklist_button_state()
            
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
                                    # IMPORTANT: This line must be indented inside the else block above
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

    def _update_watchlist(self) -> None:
        self.watchlist_list.clear()
        watchlist_items = utils.find_watchlist_items(self.df_all)
        for w in watchlist_items:
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
            self.watchlist_list.addItem(item)
    
    def _update_watchlist_button_state(self) -> None:
        """Update the watchlist button to show star or filled star based on current item."""
        if not self._current_item_key:
            self.watchlist_btn.setText('☆')
            self.watchlist_btn.setEnabled(False)
            # Reset to default gray styling
            self.watchlist_btn.setStyleSheet('''
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
            self.watchlist_btn.setEnabled(True)
            if utils.is_in_watchlist(self._current_item_key):
                self.watchlist_btn.setText('★')
                # Neon green for activated state
                self.watchlist_btn.setStyleSheet('''
                    QPushButton {
                        background-color: #1a1a1a;
                        border: 1px solid #333333;
                        border-radius: 4px;
                        font-size: 16px;
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
            else:
                self.watchlist_btn.setText('☆')
                # Reset to default gray styling
                self.watchlist_btn.setStyleSheet('''
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
            # Remove from watchlist if it's there (can't watch blacklisted items)
            if utils.is_in_watchlist(self._current_item_key):
                utils.remove_from_watchlist(self._current_item_key)
        self._update_blacklist_button_state()
        self._update_watchlist_button_state()  # Update watchlist button state too
        # Refresh view to hide/show the item and update widgets
        self.refresh_view()
        self._update_alerts()  # Update Top Movers
        self._update_watchlist()  # Update My Watchlist
    
    def _on_watchlist_btn_clicked(self) -> None:
        """Toggle current item in watchlist."""
        if not self._current_item_key:
            return
        if utils.is_in_watchlist(self._current_item_key):
            utils.remove_from_watchlist(self._current_item_key)
        else:
            utils.add_to_watchlist(self._current_item_key)
        self._update_watchlist_button_state()
        self._update_watchlist()

    def _on_alert_clicked(self, item: QtWidgets.QListWidgetItem) -> None:
        # Select the corresponding row in the table and update chart/thumbnail
        item_key = item.data(QtCore.Qt.UserRole)
        category = item.data(QtCore.Qt.UserRole + 1)
        if not item_key:
            return
        
        # Block ALL signals from table and selection model to prevent cascading triggers
        table_blocker = QtCore.QSignalBlocker(self.table)
        sel_model = self.table.selectionModel()
        sel_blocker = QtCore.QSignalBlocker(sel_model) if sel_model else None
        
        target_row = -1
        target_idx = None
        
        try:
            # Make sure filters show the item: set category to alert's category and clear name/price filters
            if category and self.category_cb.currentText() != category:
                cb_blocker = QtCore.QSignalBlocker(self.category_cb)
                self.category_cb.setCurrentText(category)
                del cb_blocker
            for w in (self.item_edit, self.price_min, self.price_max):
                blk = QtCore.QSignalBlocker(w)
                w.setText('')
                del blk
            
            # Refresh view but skip auto-selection since we'll select the target row manually
            self.refresh_view(skip_auto_selection=True)
            
            # Now find and select the row with this itemKey (signals still blocked)
            m = self.table.model_
            for r in range(m.rowCount()):
                try:
                    if m.item(r, 4).data(QtCore.Qt.UserRole) == item_key:  # itemKey stored in ma% column (4)
                        target_row = r
                        break
                except Exception:
                    continue
            
            if target_row >= 0:
                idx = m.index(target_row, 0)  # Use column 0 for selection index
                if idx.isValid():
                    target_idx = idx
                    # Select the row and scroll to it (signals still blocked)
                    self.table.setCurrentIndex(idx)
                    self.table.scrollTo(idx, QtWidgets.QAbstractItemView.PositionAtCenter)
        finally:
            # Unblock signals
            del table_blocker
            if sel_blocker:
                del sel_blocker
        
        # Now manually update chart and thumbnail ONCE (signals are unblocked now)
        if target_idx is not None:
            self._on_table_clicked(target_idx)

    def _on_watchlist_clicked(self, item: QtWidgets.QListWidgetItem) -> None:
        # Reuse the same behavior as alert click for watchlist items
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

