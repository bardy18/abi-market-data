"""ABI Market Trading App - Main GUI application."""
import sys
import os
from pathlib import Path

import pandas as pd
import numpy as np
from PySide6 import QtWidgets, QtCore, QtGui
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from trading_app import utils


class TrendChart(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.figure = Figure(figsize=(6, 4))
        self.canvas = FigureCanvas(self.figure)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.canvas)

    def plot(self, df: pd.DataFrame, item_key: str, display_name: str = None) -> None:
        """
        Plot price history for an item.
        
        Args:
            df: Full dataframe
            item_key: Composite key "category:itemName" for unique item identification
            display_name: Optional display name for chart title
        """
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        if df.empty:
            ax.set_title('No data')
        else:
            # Filter by itemKey to handle items with same name in different categories
            dfi = df[df['itemKey'] == item_key] if 'itemKey' in df.columns else df[df['itemName'] == item_key]
            if dfi.empty:
                ax.set_title(f'No data for {display_name or item_key}')
            else:
                ax.plot(dfi['timestamp'], dfi['price'], label='Price', marker='o')
                if 'ma' in dfi.columns:
                    ax.plot(dfi['timestamp'], dfi['ma'], label='MA', linestyle='--')
                # Extract category and name for title if display_name not provided
                if not display_name and ':' in item_key:
                    category, name = item_key.split(':', 1)
                    ax.set_title(name)
                else:
                    ax.set_title(display_name or item_key)
                ax.set_xlabel('Time')
                ax.set_ylabel('Price')
                ax.legend()
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
        # Ensure header sorting drives model sorting by our numeric role
        try:
            header = self.horizontalHeader()
            header.setSortIndicatorShown(True)
            header.sortIndicatorChanged.connect(lambda section, order: self.model_.sort(section, order))
        except Exception:
            pass

    def load(self, df: pd.DataFrame) -> None:
        self.model_.clear()
        headers = ['move', 'category', 'itemName', 'price', 'ma', 'vol', 'vol%']
        self.model_.setHorizontalHeaderLabels(headers)
        for _, row in df.iterrows():
            items = []
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
            # Price (money) - display text, but store numeric for sorting
            price_item = QtGui.QStandardItem(f"{price_val:.0f}")
            price_item.setData(price_val, self.sort_role)
            items.append(price_item)
            # MA (money) - display text or blank, store numeric (NaN -> -1 for consistent sorting)
            ma_is_nan = pd.isna(ma_val)
            ma_num = float(ma_val) if not ma_is_nan else -1.0
            ma_text = f"{ma_num:.1f}" if not ma_is_nan else ''
            ma_item = QtGui.QStandardItem(ma_text)
            ma_item.setData(ma_num, self.sort_role)
            items.append(ma_item)
            # Volatility absolute
            vol_val = row.get('vol', np.nan)
            vol_item = QtGui.QStandardItem(f"{float(vol_val):.1f}" if not pd.isna(vol_val) else '')
            vol_item.setData(float(vol_val) if not pd.isna(vol_val) else 0.0, self.sort_role)
            items.append(vol_item)
            # Volatility percent
            vol_pct = row.get('volPct', np.nan) if 'volPct' in row else np.nan
            vol_pct_item = QtGui.QStandardItem(f"{float(vol_pct):.1f}%" if not pd.isna(vol_pct) else '')
            vol_pct_item.setData(float(vol_pct) if not pd.isna(vol_pct) else 0.0, self.sort_role)
            items.append(vol_pct_item)
            # Store itemKey in user role for proper item identification when clicking
            items[0].setData(row.get('itemKey', ''), QtCore.Qt.UserRole)
            self.model_.appendRow(items)
        self.resizeColumnsToContents()
        # Default sort: biggest gainers at the top (by numeric sort role)
        try:
            self.model_.sort(0, QtCore.Qt.SortOrder.DescendingOrder)
        except Exception:
            pass


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, config_path: str):
        super().__init__()
        self.setWindowTitle('ABI Market Trading App')
        self.cfg = utils.load_config(config_path)

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

        # Right: Chart + Table + Thumbnail
        right = QtWidgets.QWidget(self)
        right_layout = QtWidgets.QVBoxLayout(right)
        main_layout.addWidget(right, 3)

        # Thumbnail preview
        self.thumb_label = QtWidgets.QLabel(self)
        self.thumb_label.setFixedHeight(110)
        self.thumb_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        self.thumb_label.setText('Thumbnail will appear here when you select an item')
        right_layout.addWidget(self.thumb_label)

        self.chart = TrendChart(self)
        right_layout.addWidget(self.chart, 3)

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
                top_key = self.table.model_.item(top_index.row(), 0).data(QtCore.Qt.UserRole)
            except Exception:
                top_key = ''
        sel_index = self.table.currentIndex()
        sel_key = ''
        if sel_index.isValid():
            try:
                sel_key = self.table.model_.item(sel_index.row(), 0).data(QtCore.Qt.UserRole)
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
                        if m.item(r, 0).data(QtCore.Qt.UserRole) == key:
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
            # Get itemKey from stored user data
            item_key = model.item(row, 0).data(QtCore.Qt.UserRole)
            category = model.item(row, 1).text()
            display_name = model.item(row, 2).text()
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
                            self.thumb_label.setPixmap(pix)
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
                if m.item(r, 0).data(QtCore.Qt.UserRole) == item_key:
                    target_row = r
                    break
            except Exception:
                continue
        if target_row >= 0:
            idx = m.index(target_row, 0)
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
        item_key = model.item(row, 0).data(QtCore.Qt.UserRole)
        if not item_key:
            return
        current_display = model.item(row, 2).text()
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

