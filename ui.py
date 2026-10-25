import sys
import argparse
import shutil
import colorsys
import csv
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from color_matching import load_library, match_rgb, sample_region
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QFrame, QMessageBox, QPushButton, QTabWidget,
                             QInputDialog, QTextEdit, QComboBox)
from PyQt5.QtGui import QImage, QPixmap, QPainter, QPen, QFont
from PyQt5.QtCore import QThread, pyqtSignal, pyqtSlot, Qt

# Offline by default; only an explicit camera index opens a webcam.
WINDOW_WIDTH, WINDOW_HEIGHT = 1000, 760
VIDEO_WIDTH, VIDEO_HEIGHT = 400, 240
SWATCH_SIZE = 100
BASE_DIR = Path(__file__).resolve().parent
REFERENCE_CSV_FILE = BASE_DIR / "examples" / "synthetic_colours.csv"
DATA_DIR = BASE_DIR / "runtime"
PRODUCTS_CSV = DATA_DIR / "products.csv"
HISTORY_DIR = DATA_DIR / "history"
TARGET_FPS = 15
FRAME_DELAY = 1.0 / TARGET_FPS
SAMPLE_REGION_SIZE = 5


class VideoThread(QThread):
    """Emit BGR frames from a synthetic grid or an explicitly selected webcam."""
    change_pixmap_signal = pyqtSignal(np.ndarray)
    status_signal = pyqtSignal(str, bool)

    def __init__(self, camera_index=None):
        super().__init__()
        self.camera_index = camera_index
        self._run_flag = True

    @staticmethod
    def generate_grid():
        frame = np.zeros((VIDEO_HEIGHT, VIDEO_WIDTH, 3), dtype=np.uint8)
        for row in range(6):
            for col in range(8):
                rgb = tuple(int(c * 255) for c in colorsys.hsv_to_rgb(
                    col / 8, 0.4 + row * 0.1, 0.9))
                y, x = row * 40, col * 50
                frame[y:y + 40, x:x + 50] = rgb[::-1]
        return frame

    def run(self):
        cap = None
        try:
            if self.camera_index is not None:
                cap = cv2.VideoCapture(self.camera_index)
                if not cap.isOpened():
                    raise RuntimeError("Selected webcam could not be opened")
            self.status_signal.emit(
                "Synthetic grid - click a colour to match" if cap is None
                else "Webcam preview - click a colour to match", False)
            while self._run_flag:
                if cap is None:
                    frame = self.generate_grid()
                else:
                    ok, frame = cap.read()
                    if not ok:
                        raise RuntimeError("Webcam did not return a frame")
                self.change_pixmap_signal.emit(frame)
                self.msleep(round(FRAME_DELAY * 1000))
        except Exception as exc:
            self.status_signal.emit(str(exc), True)
        finally:
            if cap is not None:
                cap.release()

    def stop(self):
        self._run_flag = False
        self.wait()


# --- Main Application Window ---
class ColorMatcherApp(QMainWindow):
    def __init__(self, reference_db, camera_index=None, start_preview=True):
        super().__init__()
        self.setWindowTitle('Colour Matching Lab - Synthetic Reference Demo')
        self.camera_index = camera_index

        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)

        self.reference_db = reference_db
        self.current_frame = None
        self.last_click_pos = None  # Store last click position for visual feedback

        # Product and history management
        self.products = []
        self.current_product_id = None
        self.current_product_name = None
        self.history_log = None  # Reassigned when history tab is built
        self.product_combo = None

        self._ensure_data_paths()
        self._load_products()

        self.initUI()

        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)

        if start_preview:
            self.start_video()

    def initUI(self):
        """Sets up the user interface."""

        # Explicitly set window to normal state (not maximized/fullscreen)
        self.setWindowState(Qt.WindowNoState)

        # Set global font for the application - sleek and professional
        app_font = QFont("Segoe UI", 11)
        self.setFont(app_font)

        # Set white background for entire window
        self.setStyleSheet("QMainWindow { background-color: white; }")

        # Main layout container
        central_widget = QWidget(self)
        central_widget.setStyleSheet("background-color: white;")
        self.setCentralWidget(central_widget)

        overall_layout = QVBoxLayout(central_widget)
        overall_layout.setContentsMargins(12, 12, 12, 12)
        banner = QLabel("SYNTHETIC REFERENCE DEMO | No calibrated measurement or pass/fail decision")
        banner.setWordWrap(True)
        banner.setStyleSheet("background: #e8f0fa; color: #18334e; padding: 10px;")
        overall_layout.addWidget(banner)

        # --- Tab Widget for Multiple Pages ---
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabPosition(QTabWidget.North)
        self.tab_widget.setFont(QFont("Segoe UI", 9))
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid black;
                background-color: white;
                border-top: none;
            }
            QTabBar::tab {
                background-color: #ecf0f1;
                color: black;
                padding: 4px 10px;
                margin-right: 1px;
                border: 1px solid transparent;
                border-bottom: none;
                border-top-left-radius: 3px;
                border-top-right-radius: 3px;
                font-weight: bold;
                min-width: 60px;
            }
            QTabBar::tab:selected {
                background-color: white;
                color: black;
                border: 1px solid black;
                border-bottom: none;
            }
            QTabBar::tab:hover {
                background-color: #d5d8dc;
                color: black;
            }
        """)

        overall_layout.addWidget(self.tab_widget)

        # Create the four tabs.
        self.create_main_tab()
        self.create_history_tab()
        self.create_setup_tab()
        self.create_calibration_tab()

        self.populate_product_combo()
        self._refresh_history_view()

    def create_main_tab(self):
        main_tab = QWidget()
        layout = QVBoxLayout(main_tab)
        title = QLabel("Colour Matching Lab")
        title.setFont(QFont("Segoe UI", 22, QFont.Bold))
        layout.addWidget(title)
        controls = QHBoxLayout()
        controls.addWidget(QLabel("Demo role:"))
        self.user_profile_combo = QComboBox()
        self.user_profile_combo.addItems(["Demo operator", "Demo reviewer"])
        controls.addWidget(self.user_profile_combo)
        controls.addWidget(QLabel("Synthetic product:"))
        self.product_combo = QComboBox()
        self.product_combo.currentIndexChanged.connect(self.on_product_selected)
        controls.addWidget(self.product_combo, 1)
        layout.addLayout(controls)

        preview_row = QHBoxLayout()
        self.video_label = QLabel("Waiting for preview")
        self.video_label.setFixedSize(VIDEO_WIDTH, VIDEO_HEIGHT)
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setStyleSheet("background: #263544; color: white;")
        self.video_label.mousePressEvent = self.capture_color
        preview_row.addWidget(self.video_label)
        instructions = QLabel("Click a colour in the preview to match and record it.\n\n"
                              "Start Test samples the centre of the current frame.\n\n"
                              "Reference colours and initial products are synthetic.\n"
                              "Demo roles are labels, not authenticated accounts.")
        instructions.setWordWrap(True)
        preview_row.addWidget(instructions, 1)
        layout.addLayout(preview_row)
        self.start_test_button = QPushButton("Start Test - sample centre")
        self.start_test_button.clicked.connect(self.on_start_test_clicked)
        layout.addWidget(self.start_test_button)

        result_row = QHBoxLayout()
        for heading, prefix in [("Sampled colour", "captured"), ("Closest synthetic reference", "reference")]:
            column = QVBoxLayout()
            column.addWidget(self.create_title_label(heading))
            swatch = self.create_swatch_label()
            setattr(self, prefix + "_swatch", swatch)
            column.addWidget(swatch)
            if prefix == "captured":
                self.captured_lab_label = QLabel("L*: --  a*: --  b*: --")
                column.addWidget(self.captured_lab_label)
            else:
                self.reference_name_label = QLabel("---")
                self.reference_rgb_label = QLabel("RGB: --, --, --")
                column.addWidget(self.reference_name_label)
                column.addWidget(self.reference_rgb_label)
            result_row.addLayout(column)
        layout.addLayout(result_row)
        self.reference_delta_e_label = QLabel("Delta E 2000: --")
        self.reference_delta_e_label.setFont(QFont("Segoe UI", 18))
        layout.addWidget(self.reference_delta_e_label)
        self.status_label = QLabel("Ready")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        layout.addStretch()
        self.tab_widget.addTab(main_tab, "Match")

    def create_history_tab(self):
        """Creates the History page."""
        history_tab = QWidget()
        history_tab.setStyleSheet("background-color: white;")

        layout = QVBoxLayout(history_tab)
        layout.setContentsMargins(30, 30, 30, 30)

        title = QLabel("Test History")
        title.setFont(QFont("Segoe UI", 24, QFont.Bold))
        title.setStyleSheet("color: #2c3e50; margin-bottom: 20px;")
        layout.addWidget(title)

        self.history_log = QTextEdit()
        self.history_log.setReadOnly(True)
        self.history_log.setFont(QFont("Courier", 10))
        layout.addWidget(self.history_log)

        self.tab_widget.addTab(history_tab, "History")

    def create_setup_tab(self):
        """Creates the Setup page."""
        setup_tab = QWidget()
        setup_tab.setStyleSheet("background-color: white;")

        layout = QVBoxLayout(setup_tab)
        layout.setContentsMargins(30, 0, 30, 30)
        layout.setSpacing(12)

        title = QLabel("Setup")
        title_font = QFont("Segoe UI", 24, QFont.Bold)
        title_font.setUnderline(True)
        title.setFont(title_font)
        title.setStyleSheet("color: #2c3e50; margin-bottom: 8px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        info = QLabel("Manage local demo products. Changes are saved in the ignored runtime folder.")
        info.setFont(QFont("Segoe UI", 12))
        info.setStyleSheet("color: #7f8c8d;")
        info.setAlignment(Qt.AlignCenter)
        layout.addWidget(info)

        layout.addSpacing(15)

        product_info = QLabel("Use the buttons below to manage products for testing history.")
        product_info.setFont(QFont("Segoe UI", 11))
        product_info.setStyleSheet("color: #566573;")
        product_info.setWordWrap(True)
        product_info.setAlignment(Qt.AlignCenter)
        layout.addWidget(product_info)

        layout.addSpacing(10)

        add_product_button = QPushButton("Add Product")
        add_product_button.setFixedWidth(180)
        add_product_button.clicked.connect(self.on_add_product_clicked)
        layout.addWidget(add_product_button, alignment=Qt.AlignHCenter)

        reload_products_button = QPushButton("Reload Products from CSV")
        reload_products_button.setFixedWidth(220)
        reload_products_button.clicked.connect(self.on_reload_products_clicked)
        layout.addWidget(reload_products_button, alignment=Qt.AlignHCenter)

        remove_product_button = QPushButton("Remove Product")
        remove_product_button.setFixedWidth(180)
        remove_product_button.clicked.connect(self.on_remove_product_clicked)
        layout.addWidget(remove_product_button, alignment=Qt.AlignHCenter)

        layout.addStretch()

        self.tab_widget.addTab(setup_tab, "Setup")

    def create_calibration_tab(self):
        """Creates the Calibration page."""
        calibration_tab = QWidget()
        calibration_tab.setStyleSheet("background-color: white;")

        layout = QVBoxLayout(calibration_tab)
        layout.setContentsMargins(30, 30, 30, 30)

        title = QLabel("Calibration")
        title.setFont(QFont("Segoe UI", 24, QFont.Bold))
        title.setStyleSheet("color: #2c3e50; margin-bottom: 20px;")
        layout.addWidget(title)

        info = QLabel("Calibration is not implemented. RGB values are interpreted as sRGB under D65.\n"
                      "Camera mode requires controlled lighting, profiling and validation before real use.")
        info.setFont(QFont("Segoe UI", 12))
        info.setStyleSheet("color: #7f8c8d;")
        layout.addWidget(info)

        layout.addStretch()

        self.tab_widget.addTab(calibration_tab, "Calibration")

    # --- UI Helper Methods ---
    def create_title_label(self, text):
        label = QLabel(text)
        label.setFont(QFont("Segoe UI", 14, QFont.Bold))
        label.setStyleSheet("margin-top: 10px; color: #2c3e50; padding-left: 5px;")
        return label

    def create_swatch_label(self):
        swatch = QLabel()
        swatch.setFixedSize(SWATCH_SIZE, SWATCH_SIZE)
        swatch.setFrameShape(QFrame.Box)
        swatch.setStyleSheet("background-color: #ecf0f1; border: 2px solid #bdc3c7; border-radius: 5px;")
        swatch.setAlignment(Qt.AlignCenter)
        return swatch

    def set_swatch_color(self, swatch_label, color_rgb):
        r, g, b = int(color_rgb[0]), int(color_rgb[1]), int(color_rgb[2])
        swatch_label.setStyleSheet(f"background-color: rgb({r},{g},{b});"
                                   "border: 2px solid #bdc3c7; border-radius: 5px;")

    def update_status(self, message, is_error=False):
        color = "#e74c3c" if is_error else "#95a5a6"
        self.status_label.setText(message)
        self.status_label.setFont(QFont("Segoe UI", 10))
        self.status_label.setStyleSheet(f"color: {color}; font-style: italic;")

    def _ensure_data_paths(self):
        """Ensure the data folders and base CSV exist before use."""
        for path in (DATA_DIR, HISTORY_DIR):
            try:
                path.mkdir(parents=True, exist_ok=True)
            except Exception as exc:
                print(f"Failed to create data path {path}: {exc}")

        if not PRODUCTS_CSV.exists():
            try:
                shutil.copyfile(BASE_DIR / 'examples' / 'synthetic_products.csv', PRODUCTS_CSV)
            except Exception as exc:
                print(f"Failed to initialize products CSV: {exc}")

    def _load_products(self):
        """Load products from CSV into memory."""
        previous_id = self.current_product_id

        if not PRODUCTS_CSV.exists():
            self.products = []
            self.current_product_id = None
            self.current_product_name = None
            return

        try:
            df = pd.read_csv(PRODUCTS_CSV, dtype=str, keep_default_na=False)
        except Exception as exc:
            print(f"Error loading products CSV: {exc}")
            self.products = []
            self.current_product_id = None
            self.current_product_name = None
            return

        if df.empty:
            self.products = []
            self.current_product_id = None
            self.current_product_name = None
            return

        expected_columns = {'product_id', 'product_name'}
        missing_columns = expected_columns - set(df.columns)
        if missing_columns:
            print(f"Products CSV missing columns: {sorted(missing_columns)}")
            self.products = []
            self.current_product_id = None
            self.current_product_name = None
            return

        df = df.fillna('')
        df['product_id'] = df['product_id'].astype(str)
        df['product_name'] = df['product_name'].astype(str)
        if 'notes' not in df.columns:
            df['notes'] = ''

        self.products = df.to_dict(orient='records')

        if not self.products:
            self.current_product_id = None
            self.current_product_name = None
            return

        if previous_id and any(str(item.get('product_id')) == previous_id for item in self.products):
            self.current_product_id = previous_id
            matched = next((item for item in self.products if str(item.get('product_id')) == previous_id), None)
            self.current_product_name = matched.get('product_name') if matched else previous_id
        else:
            first_product = self.products[0]
            self.current_product_id = str(first_product.get('product_id', '')).strip() or None
            self.current_product_name = str(first_product.get('product_name', '')).strip() or self.current_product_id

    def _ensure_unique_product_id(self, base_id):
        """Return a product id that does not clash with existing entries."""
        if not base_id:
            base_id = datetime.now().strftime("product_%Y%m%d_%H%M%S")
        existing = {str(p.get('product_id', '')).strip() for p in self.products}
        candidate = base_id
        counter = 1
        while candidate in existing or not candidate:
            counter += 1
            candidate = f"{base_id}_{counter}"
        return candidate

    def _save_products(self):
        """Persist the in-memory products list to the CSV."""
        try:
            if not self.products:
                df = pd.DataFrame(columns=['product_id', 'product_name', 'notes'])
            else:
                df = pd.DataFrame(self.products)
                for column in ['product_id', 'product_name', 'notes']:
                    if column not in df.columns:
                        df[column] = ''
                df = df[['product_id', 'product_name', 'notes']]
            df.to_csv(PRODUCTS_CSV, index=False)
        except Exception as exc:
            print(f"Failed to save products CSV: {exc}")

    def populate_product_combo(self):
        """Update the product dropdown based on current data."""
        if self.product_combo is None:
            return

        self.product_combo.blockSignals(True)
        self.product_combo.clear()

        if not self.products:
            self.product_combo.addItem("No products configured", userData=None)
            self.product_combo.setEnabled(False)
            self.current_product_id = None
            self.current_product_name = None
            if self.history_log:
                self.history_log.setPlainText(
                    "No products configured.\nUse the Setup tab to add one.")
            self.product_combo.blockSignals(False)
            return

        self.product_combo.setEnabled(True)

        for product in self.products:
            product_id = str(product.get('product_id', '')).strip()
            product_name = str(product.get('product_name', '')).strip()
            if product_name and product_id and product_name.lower() != product_id.lower():
                label = f"{product_name} ({product_id})"
            else:
                label = product_name or product_id or "Untitled Product"
            self.product_combo.addItem(label, userData=product)

        target_index = 0
        if self.current_product_id:
            for idx, product in enumerate(self.products):
                if str(product.get('product_id')) == self.current_product_id:
                    target_index = idx
                    break

        self.product_combo.setCurrentIndex(target_index)
        self.product_combo.blockSignals(False)
        selected_product = self.product_combo.itemData(target_index)
        self._apply_product_selection(selected_product)

    def on_product_selected(self, index):
        if index < 0:
            return
        if self.product_combo is None:
            return
        product = self.product_combo.itemData(index)
        self._apply_product_selection(product)

    def _apply_product_selection(self, product_record):
        if not product_record:
            self.current_product_id = None
            self.current_product_name = None
            self._refresh_history_view()
            return

        self.current_product_id = str(product_record.get('product_id', '')).strip() or None
        self.current_product_name = str(product_record.get('product_name', '')).strip() or self.current_product_id
        self._refresh_history_view()

    def _refresh_history_view(self):
        if not self.history_log:
            return

        self.history_log.clear()

        if not self.current_product_id:
            self.history_log.setPlainText("Select a product to view history.")
            return

        history_file = self._history_file_for_product(self.current_product_id)
        if not history_file.exists():
            name = self.current_product_name or self.current_product_id
            self.history_log.setPlainText(f"No history recorded yet for {name}.")
            return

        try:
            with history_file.open('r', newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                entries = list(reader)
        except Exception as exc:
            self.history_log.setPlainText(f"Error reading history: {exc}")
            return

        if not entries:
            name = self.current_product_name or self.current_product_id
            self.history_log.setPlainText(f"No history recorded yet for {name}.")
            return

        rows = []
        for entry in reversed(entries):
            timestamp = entry.get('timestamp', '')
            date_str = timestamp
            time_str = ''
            if timestamp:
                try:
                    dt_obj = datetime.fromisoformat(timestamp)
                    date_str = dt_obj.strftime('%d-%m-%Y')
                    time_str = dt_obj.strftime('%H:%M')
                except ValueError:
                    date_str = timestamp
                    time_str = ''

            rows.append({
                'Date': date_str,
                'Time': time_str,
                'Product': entry.get('product_name') or self.current_product_name or self.current_product_id or '',
                'User': entry.get('user_profile', ''),
                'Reference': entry.get('reference_name', ''),
                'DeltaE': entry.get('delta_e', ''),
                'CapturedLab': entry.get('captured_lab', ''),
                'ReferenceRGB': entry.get('reference_rgb', '')
            })

        columns = ['Date', 'Time', 'Product', 'User', 'Reference', 'DeltaE', 'CapturedLab', 'ReferenceRGB']
        widths = {}
        for column in columns:
            max_len = len(column)
            for row in rows:
                max_len = max(max_len, len(str(row.get(column, '') or '')))
            widths[column] = max_len

        header = " | ".join(column.ljust(widths[column]) for column in columns)
        separator = "-+-".join('-' * widths[column] for column in columns)
        lines = [header, separator]

        for row in rows:
            line = " | ".join(str(row.get(column, '') or '').ljust(widths[column]) for column in columns)
            lines.append(line)

        self.history_log.setPlainText("\n".join(lines))

    def _history_file_for_product(self, product_id):
        safe_id = self._sanitize_filename(str(product_id))
        return HISTORY_DIR / f"{safe_id}.csv"

    def _sanitize_filename(self, value):
        sanitized = ''.join(ch if ch.isalnum() or ch in ('-', '_') else '_' for ch in value.strip())
        sanitized = sanitized.strip('_')
        return sanitized or datetime.now().strftime("product_%Y%m%d_%H%M%S")

    def _record_history_entry(self, entry):
        if not self.current_product_id:
            return False

        history_file = self._history_file_for_product(self.current_product_id)
        file_exists = history_file.exists()
        fieldnames = ['timestamp', 'user_profile', 'product_id', 'product_name',
                      'captured_lab', 'reference_name', 'reference_rgb', 'delta_e']

        try:
            with history_file.open('a', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                if not file_exists:
                    writer.writeheader()
                writer.writerow(entry)
        except Exception as exc:
            self.update_status(f"Match calculated, but history could not be saved: {exc}", True)
            return False

        self._refresh_history_view()
        return True

    def on_add_product_clicked(self):
        name, ok = QInputDialog.getText(self, "Add Product", "Product name:")
        if not ok or not name.strip():
            return

        product_name = name.strip()
        suggested_id = self._sanitize_filename(product_name).lower()
        suggested_id = self._ensure_unique_product_id(suggested_id)

        product_id, ok_id = QInputDialog.getText(
            self,
            "Add Product",
            "Product ID (leave as-is for auto-generated):",
            QLineEdit.Normal,
            suggested_id
        )
        if not ok_id:
            return

        product_id = self._sanitize_filename(product_id.strip().lower()) if product_id.strip() else suggested_id
        product_id = self._ensure_unique_product_id(product_id)

        new_product = {
            'product_id': product_id,
            'product_name': product_name,
            'notes': ''
        }

        self.products.append(new_product)
        self.current_product_id = new_product['product_id']
        self.current_product_name = new_product['product_name']
        self._save_products()
        self.populate_product_combo()
        self.update_status(f"Product '{product_name}' added.", False)

    def on_reload_products_clicked(self):
        self._load_products()
        self.populate_product_combo()
        self.update_status("Products reloaded from CSV.", False)

    def on_remove_product_clicked(self):
        if not self.products:
            QMessageBox.information(self, "No Products", "There are no products to remove.")
            return

        product_names = [f"{p.get('product_name', '')} ({p.get('product_id', '')})" for p in self.products]
        product_name, ok = QInputDialog.getItem(
            self,
            "Remove Product",
            "Select product to remove:",
            product_names,
            0,
            False
        )
        if not ok or not product_name:
            return

        # Find the product index
        try:
            index = product_names.index(product_name)
            product_to_remove = self.products[index]
        except ValueError:
            QMessageBox.warning(self, "Error", "Selected product not found.")
            return

        # Confirm removal
        reply = QMessageBox.question(
            self,
            "Confirm Removal",
            f"Are you sure you want to remove '{product_name}'?\n\n"
            "This will remove it from the product list, but history files will remain.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        # Remove the product
        removed_id = product_to_remove.get('product_id')
        self.products.pop(index)

        # If the removed product was current, reset
        if self.current_product_id == removed_id:
            self.current_product_id = None
            self.current_product_name = None

        # Save and refresh
        self._save_products()
        self.populate_product_combo()
        self.update_status(f"Product '{product_name}' removed.", False)

    def on_start_test_clicked(self):
        """Sample the centre of the latest frame without blocking the event loop."""
        if self.current_frame is None:
            self.update_status("Wait for the preview before sampling.", True)
            return
        h, w = self.current_frame.shape[:2]
        self._match_rgb(self._sample_color_region(w // 2, h // 2))

    def _match_rgb(self, rgb):
        if rgb is None:
            return
        if not self.current_product_id:
            self.update_status("Select a demo product before sampling.", True)
            return
        try:
            result = match_rgb(rgb, self.reference_db)
            lab = result["lab"]
            match_rgb_value = result["reference_rgb"]
            self.set_swatch_color(self.captured_swatch, rgb)
            self.captured_lab_label.setText(
                f"L*: {lab[0]:.2f}  a*: {lab[1]:.2f}  b*: {lab[2]:.2f}")
            self.reference_name_label.setText(result["name"])
            self.reference_rgb_label.setText("RGB: " + ", ".join(map(str, match_rgb_value)))
            self.reference_delta_e_label.setText(f"Delta E 2000: {result['delta_e']:.2f}")
            self.set_swatch_color(self.reference_swatch, match_rgb_value)
            recorded = self._record_history_entry({
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "user_profile": self.user_profile_combo.currentText(),
                "product_id": self.current_product_id,
                "product_name": self.current_product_name,
                "captured_lab": ", ".join(f"{v:.2f}" for v in lab),
                "reference_name": result["name"],
                "reference_rgb": ", ".join(map(str, match_rgb_value)),
                "delta_e": f"{result['delta_e']:.2f}",
            })
            if recorded:
                self.update_status(f"Synthetic reference: {result['name']} - result recorded locally.")
        except (ValueError, OSError) as exc:
            self.update_status(f"Sample failed: {exc}", True)

    # --- Video and Camera Logic ---
    def start_video(self):
        self.thread = VideoThread(self.camera_index)
        self.thread.change_pixmap_signal.connect(self.update_video_feed)
        self.thread.status_signal.connect(self.handle_status_message)
        self.thread.start()

    def closeEvent(self, event):
        """Shuts down the video thread when the window is closed."""
        print("Closing application...")
        if hasattr(self, 'thread') and self.thread and hasattr(self.thread, 'stop'):
            self.thread.stop()
        event.accept()

    @pyqtSlot(np.ndarray)
    def update_video_feed(self, cv_img):
        """Updates the video_label with a new frame from the VideoThread."""
        # Store the frame (as BGR) for color picking
        self.current_frame = cv_img

        # Convert OpenCV BGR image to Qt QPixmap
        qt_img = self.convert_cv_to_qt(cv_img)

        # Draw crosshair if user has clicked
        if self.last_click_pos is not None:
            pixmap = qt_img.copy()
            painter = QPainter(pixmap)
            painter.setPen(QPen(Qt.green, 2))
            x, y = self.last_click_pos
            crosshair_size = 20
            # Draw crosshair
            painter.drawLine(x - crosshair_size, y, x + crosshair_size, y)
            painter.drawLine(x, y - crosshair_size, x, y + crosshair_size)
            # Draw circle around sampling area
            painter.setPen(QPen(Qt.green, 1))
            painter.drawEllipse(x - 10, y - 10, 20, 20)
            painter.end()
            self.video_label.setPixmap(pixmap)
        else:
            self.video_label.setPixmap(qt_img)

    def convert_cv_to_qt(self, cv_img):
        """Convert from an OpenCV BGR image to QPixmap."""
        # Convert BGR to RGB
        rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)

        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w

        # Create QImage
        convert_to_Qt_format = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)

        # Scale the image to fit the label
        scaled_img = convert_to_Qt_format.scaled(VIDEO_WIDTH, VIDEO_HEIGHT, Qt.KeepAspectRatio)

        return QPixmap.fromImage(scaled_img)

    @pyqtSlot(str, bool)
    def handle_status_message(self, message, is_error):
        self.update_status(message, is_error)

    # --- Core Color Matching Logic ---
    def capture_color(self, event):
        """Called when the user clicks on the video feed."""
        if self.current_frame is None:
            return

        click_x = event.pos().x()
        click_y = event.pos().y()

        # --- Scale coordinates ---
        frame_coords = self._map_click_to_frame(click_x, click_y)
        if frame_coords is None:
            return

        frame_x, frame_y = frame_coords

        # Store click position for visual feedback (in label coordinates)
        label_w = self.video_label.width()
        label_h = self.video_label.height()
        pixmap = self.video_label.pixmap()
        if pixmap:
            pixmap_w = pixmap.width()
            pixmap_h = pixmap.height()
            offset_x = (label_w - pixmap_w) // 2
            offset_y = (label_h - pixmap_h) // 2
            self.last_click_pos = (click_x - offset_x, click_y - offset_y)

        self._match_rgb(self._sample_color_region(frame_x, frame_y))

    def _map_click_to_frame(self, click_x, click_y):
        """
        Maps click coordinates on the video label to frame coordinates.
        Returns (frame_x, frame_y) or None if click is outside the video area.
        """
        label_w = self.video_label.width()
        label_h = self.video_label.height()

        pixmap = self.video_label.pixmap()
        if not pixmap:
            return None

        pixmap_w = pixmap.width()
        pixmap_h = pixmap.height()

        offset_x = (label_w - pixmap_w) // 2
        offset_y = (label_h - pixmap_h) // 2

        # Check if click is within the pixmap bounds
        if not (offset_x <= click_x < offset_x + pixmap_w and
                offset_y <= click_y < offset_y + pixmap_h):
            return None

        pixmap_x = click_x - offset_x
        pixmap_y = click_y - offset_y

        frame_h, frame_w, _ = self.current_frame.shape
        frame_x = int(pixmap_x * (frame_w / pixmap_w))
        frame_y = int(pixmap_y * (frame_h / pixmap_h))

        # Clamp to frame boundaries
        frame_x = max(0, min(frame_w - 1, frame_x))
        frame_y = max(0, min(frame_h - 1, frame_y))

        return (frame_x, frame_y)

    def _sample_color_region(self, frame_x, frame_y):
        """
        Samples a region around the given frame coordinates and returns average RGB.
        Returns (R, G, B) tuple or None if sampling fails.
        """
        return sample_region(self.current_frame, frame_x, frame_y, SAMPLE_REGION_SIZE)


def main():
    parser = argparse.ArgumentParser(description="Offline colour matching demonstration")
    parser.add_argument("--camera-index", type=int, help="Explicitly open this local webcam; default is synthetic")
    args = parser.parse_args()
    if args.camera_index is not None and args.camera_index < 0:
        parser.error("camera index must be non-negative")
    try:
        library = load_library(REFERENCE_CSV_FILE)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Unable to load synthetic reference library: {exc}\n")
    app = QApplication([sys.argv[0]])
    window = ColorMatcherApp(library, camera_index=args.camera_index)
    window.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
