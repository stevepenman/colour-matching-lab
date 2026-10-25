"""Offscreen regression tests using temporary storage and blocked webcam access."""

import csv
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

from color_matching import load_library
import ui


class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.paths = patch.multiple(ui, DATA_DIR=self.root, PRODUCTS_CSV=self.root / "products.csv",
                                    HISTORY_DIR=self.root / "history")
        self.paths.start()
        self.camera = patch.object(ui.cv2, "VideoCapture", side_effect=AssertionError("Camera access forbidden"))
        self.camera_mock = self.camera.start()
        self.window = ui.ColorMatcherApp(load_library(), start_preview=False)
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.app.processEvents()
        self.camera.stop()
        self.paths.stop()
        self.temp.cleanup()

    def test_start_samples_current_frame_and_records_real_result(self):
        self.window.update_video_feed(ui.VideoThread.generate_grid())
        QTest.mouseClick(self.window.start_test_button, Qt.LeftButton)
        history = self.window._history_file_for_product("demo_a")
        with history.open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["reference_name"], self.window.reference_name_label.text())
        self.assertEqual(rows[0]["user_profile"], "Demo operator")
        self.assertIn("Fictional sample A", self.window.history_log.toPlainText())
        self.camera_mock.assert_not_called()

    def test_click_mapping_and_exact_colour_match(self):
        self.window.update_video_feed(ui.VideoThread.generate_grid())
        QTest.mouseClick(self.window.video_label, Qt.LeftButton, pos=QPoint(25, 20))
        self.assertEqual(self.window.reference_name_label.text(), "Demo colour 01")
        self.assertEqual(self.window._map_click_to_frame(-1, 0), None)
        self.assertEqual(self.window._map_click_to_frame(25, 20), (25, 20))

    def test_preview_starts_offline_and_stops(self):
        self.window.start_video()
        deadline = time.monotonic() + 5
        while self.window.current_frame is None and time.monotonic() < deadline:
            self.app.processEvents()
            QTest.qWait(10)
        self.assertIsNotNone(self.window.current_frame)
        self.window.close()
        self.assertFalse(self.window.thread.isRunning())
        self.camera_mock.assert_not_called()

    def test_products_round_trip_and_history_path_stays_inside_runtime(self):
        self.window.products.append({"product_id": "001", "product_name": "Fictional sample C", "notes": "Synthetic"})
        self.window._save_products()
        self.window._load_products()
        self.assertEqual(self.window.products[-1]["product_id"], "001")
        path = self.window._history_file_for_product("../../escape")
        self.assertEqual(path.parent, self.root / "history")

    def test_history_write_failure_is_visible(self):
        self.window.update_video_feed(ui.VideoThread.generate_grid())
        with patch.object(self.window, "_history_file_for_product", return_value=self.root):
            self.window.on_start_test_clicked()
        self.assertIn("history could not be saved", self.window.status_label.text())
        self.assertNotIn("recorded locally", self.window.status_label.text())


if __name__ == "__main__":
    unittest.main()
