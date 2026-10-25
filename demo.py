"""Deterministic offline demonstration; no Qt window, camera or disk writes."""

import argparse
import json

from color_matching import load_library, match_rgb


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rgb", nargs=3, type=int, metavar=("R", "G", "B"), default=[128, 128, 128])
    args = parser.parse_args()
    try:
        result = match_rgb(args.rgb, load_library())
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Demo failed: {exc}\n")
    print(json.dumps({"mode": "synthetic-offline", "input_rgb": args.rgb, **result}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
