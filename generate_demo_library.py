"""Generate fictional HSV-grid and neutral references, never commercial codes."""

import colorsys
import csv
from pathlib import Path

from color_matching import COLUMNS, rgb_to_lab


def generate_rows():
    rows = []
    for row in range(6):
        for col in range(8):
            rgb = tuple(int(v * 255) for v in colorsys.hsv_to_rgb(col / 8, 0.4 + row * 0.1, 0.9))
            rows.append([f"Demo colour {row * 8 + col + 1:02d}", *rgb_to_lab(rgb), *rgb])
    for index, level in enumerate((0, 32, 64, 96, 128, 160, 192, 255), start=1):
        rgb = (level, level, level)
        rows.append([f"Demo neutral {index:02d}", *rgb_to_lab(rgb), *rgb])
    return rows


def main():
    destination = Path(__file__).resolve().parent / "examples" / "synthetic_colours.csv"
    with destination.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(COLUMNS)
        writer.writerows(generate_rows())
    print("Generated 56 synthetic reference colours in examples/synthetic_colours.csv")


if __name__ == "__main__":
    main()
