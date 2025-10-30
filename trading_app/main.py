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
                    ax.set_title(f'[{category}] {name}')
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
        self.setSortingEnabled(True)

    def load(self, df: pd.DataFrame) -> None:
        self.model_.clear()
        headers = ['timestamp', 'category', 'itemName', 'price', 'ma', 'vol']
        self.model_.setHorizontalHeaderLabels(headers)
        for _, row in df.iterrows():
            items = []
            items.append(QtGui.QStandardItem(row['timestamp'].strftime('%Y-%m-%d %H:%M')))
            items.append(QtGui.QStandardItem(str(row['category'])))
            # Show friendly name in GUI if available, otherwise display name
            friendly_name = row.get('friendlyName', row.get('itemName', ''))
            items.append(QtGui.QStandardItem(str(friendly_name)))
            items.append(QtGui.QStandardItem(f"{row['price']:.0f}"))
            items.append(QtGui.QStandardItem(f"{row.get('ma', np.nan):.1f}" if not pd.isna(row.get('ma', np.nan)) else ''))
            items.append(QtGui.QStandardItem(f"{row.get('vol', np.nan):.1f}" if not pd.isna(row.get('vol', np.nan)) else ''))
            # Store itemKey in user role for proper item identification when clicking
            items[0].setData(row.get('itemKey', ''), QtCore.Qt.UserRole)
            self.model_.appendRow(items)
        self.resizeColumnsToContents()


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
        left_layout.addWidget(QtWidgets.QLabel('Alerts'))
        left_layout.addWidget(self.alerts_list)

        # Right: Chart + Table
        right = QtWidgets.QWidget(self)
        right_layout = QtWidgets.QVBoxLayout(right)
        main_layout.addWidget(right, 3)

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

        # Initial load
        self.refresh_view()
        self._update_alerts()

    def _filtered_df(self) -> pd.DataFrame:
        df = self.df_all
        if df.empty:
            return df
        cat = self.category_cb.currentText()
        if cat and cat != 'All':
            df = df[df['category'] == cat]
        txt = self.item_edit.text().strip().lower()
        if txt:
            # Search in itemName (display name), ocrName, and friendlyName
            search_mask = df['itemName'].str.lower().str.contains(txt) | df['ocrName'].str.lower().str.contains(txt)
            if 'friendlyName' in df.columns:
                search_mask = search_mask | df['friendlyName'].str.lower().str.contains(txt)
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

    def refresh_view(self) -> None:
        df = self._filtered_df()
        self.table.load(df)
        # Update chart to the first available item using itemKey
        if not df.empty:
            item_key = df['itemKey'].iloc[-1] if 'itemKey' in df.columns else ''
            if item_key:
                # Use friendly name for chart title
                category = df['category'].iloc[-1]
                friendly_name = df['friendlyName'].iloc[-1] if 'friendlyName' in df.columns else df['itemName'].iloc[-1]
                self.chart.plot(df, item_key, f'[{category}] {friendly_name}')
            else:
                self.chart.plot(pd.DataFrame(), '', '')
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
            friendly_name = model.item(row, 2).text()  # This is now the friendly name
            df = self._filtered_df()
            if item_key:
                # Use friendly name in chart title
                self.chart.plot(df, item_key, f'[{category}] {friendly_name}')
            else:
                # Fallback for old data without itemKey
                self.chart.plot(df, friendly_name, friendly_name)

    def _update_alerts(self) -> None:
        self.alerts_list.clear()
        alerts = utils.find_alerts(
            self.df_all,
            spike_pct=float(self.cfg.alerts.get('spike_threshold_pct', 20.0)),
            drop_pct=float(self.cfg.alerts.get('drop_threshold_pct', 20.0)),
        )
        for a in alerts:
            self.alerts_list.addItem(a)


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

