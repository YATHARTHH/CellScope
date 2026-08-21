"""
backend/utils/image_utils.py
----------------------------
Image loading and physical pixel-size resolution.

Calibration priority (Option B+):
  1. OME-TIFF PhysicalSizeX metadata (auto-read)
  2. Explicit user-provided value (requires > 0; frontend must confirm override)
  3. Pixels-only fallback (None, 'unavailable')
"""

import pathlib
from xml.etree import ElementTree as ET

import numpy as np
import tifffile
from csbdeep.utils import normalize


# ---------------------------------------------------------------------------
# Pixel-size resolution
# ---------------------------------------------------------------------------

def resolve_pixel_size(
    filepath: str,
    user_provided_um: float | None = None,
) -> tuple[float | None, str]:
    """
    Returns (pixel_size_um, source).

    source is one of:
      'ome_tiff_metadata'  — read from OME-TIFF PhysicalSizeX
      'user_provided'      — caller supplied an explicit value
      'unavailable'        — no calibration available

    Priority:
      1. OME-TIFF metadata (if present and unit is um/µm/micrometer)
      2. user_provided_um (must be > 0; frontend must confirm if overriding metadata)
      3. None / 'unavailable'
    """
    if user_provided_um is not None and user_provided_um <= 0:
        raise ValueError("pixel_size_um must be > 0")

    # Step 1: try OME-TIFF metadata
    metadata_um: float | None = None
    try:
        with tifffile.TiffFile(filepath) as tif:
            if tif.ome_metadata:
                root = ET.fromstring(tif.ome_metadata)
                ns   = {"ome": "http://www.openmicroscopy.org/Schemas/OME/2016-06"}
                px   = root.find(".//ome:Pixels", ns)
                if px is not None:
                    size_x = px.get("PhysicalSizeX")
                    unit   = px.get("PhysicalSizeXUnit", "um")
                    if size_x and unit in ("um", "µm", "micrometer"):
                        metadata_um = float(size_x)
    except Exception:
        pass

    # Step 2: resolution
    if metadata_um is not None and user_provided_um is None:
        return metadata_um, "ome_tiff_metadata"
    if user_provided_um is not None:
        # Frontend must have confirmed the override when metadata was also present
        return user_provided_um, "user_provided"
    return None, "unavailable"


# ---------------------------------------------------------------------------
# Image loading
# ---------------------------------------------------------------------------

ALLOWED_EXTENSIONS = {".tif", ".tiff", ".png"}
MAX_BYTES = 50 * 1024 * 1024  # 50 MB


def validate_upload(filepath: str) -> None:
    """Raise ValueError if the file doesn't pass basic upload safety checks."""
    path = pathlib.Path(filepath)
    if path.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type '{path.suffix}'. "
            f"Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    size = path.stat().st_size
    if size > MAX_BYTES:
        raise ValueError(
            f"File too large ({size / 1_048_576:.1f} MB). Maximum is 50 MB."
        )


def load_and_normalize(filepath: str) -> np.ndarray:
    """
    Load a 2D single-channel fluorescence image and normalize it.
    - Supports OME-TIFF, TIFF, PNG.
    - Normalization: percentile 1.0–99.8 (matches StarDist training preprocessing).
    - Returns float32 2D array.
    """
    img = tifffile.imread(filepath).astype(np.float32)

    # Handle multi-dimensional arrays
    if img.ndim == 4:   # e.g. (T, Z, Y, X) — take first frame/slice
        img = img[0, 0]
    elif img.ndim == 3:
        if img.shape[0] in (1, 2, 3, 4):  # (C, H, W) — take first channel
            img = img[0]
        elif img.shape[2] in (1, 2, 3, 4):  # (H, W, C)
            img = img[..., 0]
        # else assume (Z, H, W) — take first slice
        else:
            img = img[0]

    if img.ndim != 2:
        raise ValueError(
            f"Could not reduce image to 2D. Final shape: {img.shape}. "
            "CellScope v1 supports 2D single-channel images only."
        )

    img_norm = normalize(img, 1.0, 99.8, axis=None)
    return img_norm.astype(np.float32)


def strip_exif(filepath: str) -> None:
    """
    For PNG uploads: load and re-save without EXIF/metadata to avoid
    privacy leakage. OME-TIFF metadata is retained (contains calibration).
    """
    path = pathlib.Path(filepath)
    if path.suffix.lower() == ".png":
        try:
            from PIL import Image
            img = Image.open(filepath)
            data = list(img.getdata())
            clean = Image.new(img.mode, img.size)
            clean.putdata(data)
            clean.save(filepath)
        except Exception:
            pass  # Non-critical — file is already in temp dir
