"""Validated sRGB/D65 colour matching, shared by the GUI and offline CLI."""

from pathlib import Path

import colour
import numpy as np
import pandas as pd

EXAMPLE_LIBRARY = Path(__file__).resolve().parent / "examples" / "synthetic_colours.csv"
COLUMNS = ["ReferenceName", "L_val", "a_val", "b_val", "R", "G", "B"]


def rgb_to_lab(rgb):
    """Interpret a three-channel 0..255 value as sRGB and convert using D65."""
    values = np.asarray(rgb, dtype=float)
    if values.shape != (3,) or not np.isfinite(values).all():
        raise ValueError("RGB must contain three finite numbers")
    if (values < 0).any() or (values > 255).any():
        raise ValueError("RGB channels must be between 0 and 255")
    return colour.XYZ_to_Lab(colour.sRGB_to_XYZ(values / 255.0))


def validate_library(frame):
    """Reject incomplete, empty, ambiguous or non-finite reference libraries."""
    if not set(COLUMNS).issubset(frame.columns) or frame.empty:
        raise ValueError("Reference library must be non-empty and contain all required columns")
    frame = frame[COLUMNS].copy()
    names = frame["ReferenceName"].fillna("").astype(str).str.strip()
    if names.eq("").any() or names.duplicated().any():
        raise ValueError("Reference names must be non-empty and unique")
    frame["ReferenceName"] = names
    try:
        frame[COLUMNS[1:]] = frame[COLUMNS[1:]].apply(pd.to_numeric, errors="raise")
    except (ValueError, TypeError) as exc:
        raise ValueError("Reference values must be numeric") from exc
    if not np.isfinite(frame[COLUMNS[1:]].to_numpy(dtype=float)).all():
        raise ValueError("Reference values must be finite")
    rgb = frame[["R", "G", "B"]].to_numpy(dtype=float)
    if (rgb < 0).any() or (rgb > 255).any() or (rgb != np.floor(rgb)).any():
        raise ValueError("Reference RGB values must be integers between 0 and 255")
    if not frame["L_val"].between(0, 100).all():
        raise ValueError("Reference lightness must be between 0 and 100")
    return frame.reset_index(drop=True)


def load_library(path=EXAMPLE_LIBRARY):
    return validate_library(pd.read_csv(path))


def match_rgb(rgb, library):
    """Rank every reference with CIEDE2000; ties use the first CSV row."""
    library = validate_library(library)
    lab = rgb_to_lab(rgb)
    distances = colour.delta_E(
        lab, library[["L_val", "a_val", "b_val"]].to_numpy(dtype=float), method="CIE 2000"
    )
    index = int(np.argmin(distances))
    row = library.iloc[index]
    return {
        "name": str(row["ReferenceName"]),
        "reference_rgb": [int(row[channel]) for channel in ("R", "G", "B")],
        "lab": [float(value) for value in lab],
        "delta_e": float(distances[index]),
    }


def sample_region(frame, x, y, size=5):
    """Spatially average a clipped odd square from a BGR frame; return RGB."""
    frame = np.asarray(frame)
    if frame.ndim != 3 or frame.shape[2] != 3 or not frame.size:
        raise ValueError("Expected a non-empty three-channel BGR frame")
    if size < 1 or size % 2 == 0:
        raise ValueError("Sample size must be a positive odd number")
    h, w = frame.shape[:2]
    if not (0 <= x < w and 0 <= y < h):
        raise ValueError("Sample coordinates must be inside the frame")
    half = size // 2
    region = frame[max(0, y - half):min(h, y + half + 1),
                   max(0, x - half):min(w, x + half + 1)]
    return tuple(float(value) for value in region.mean(axis=(0, 1))[::-1])
