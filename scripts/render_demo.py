"""Render a synthetic application screenshot offscreen using temporary storage."""

import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QFontDatabase, QFont
import ui
from color_matching import load_library


def main():
    app = QApplication([])
    # Some Windows offscreen sessions do not discover installed system fonts.
    if not QFontDatabase().families():
        system_font = Path(os.environ.get("WINDIR", "")) / "Fonts" / "arial.ttf"
        if not system_font.is_file() or QFontDatabase.addApplicationFont(str(system_font)) < 0:
            raise RuntimeError("Qt cannot find fonts; run this renderer in a desktop environment")
        app.setFont(QFont("Arial", 11))
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        with patch.multiple(ui, DATA_DIR=root, PRODUCTS_CSV=root / "products.csv", HISTORY_DIR=root / "history"):
            window = ui.ColorMatcherApp(load_library(), start_preview=False)
            window.show()
            app.processEvents()
            window.update_video_feed(ui.VideoThread.generate_grid())
            window._match_rgb(window._sample_color_region(25, 20))
            app.processEvents()
            image = window.grab()
            if not image.save(str(ROOT / "docs" / "demo.png")):
                raise RuntimeError("Unable to save screenshot")
            window.close()
    print("Rendered docs/demo.png using synthetic input and temporary history")


if __name__ == "__main__":
    main()
