"""
backend/quantifier.py
---------------------
Computes per-instance morphology measurements from segmentation masks.

Design:
  - Pixel measurements are always computed.
  - Physical unit measurements (um2, cells/mm2) are ONLY computed when
    pixel_size_um is explicitly provided and > 0.
  - Never silently assumes a pixel size.
"""

from __future__ import annotations

import numpy as np
from skimage import measure


def quantify_instances(
    masks: np.ndarray,
    pixel_size_um: float | None = None,
) -> tuple[list[dict], dict]:
    """
    Compute per-cell morphology from an instance-labelled mask.

    Args:
        masks: 2D uint16 array; 0 = background, N = cell N.
        pixel_size_um: Physical pixel size in µm. None = pixel units only.

    Returns:
        (per_cell_list, aggregate_stats)
    """
    if pixel_size_um is not None and pixel_size_um <= 0:
        raise ValueError("pixel_size_um must be > 0")

    cell_ids = np.unique(masks)
    cell_ids = cell_ids[cell_ids != 0]  # exclude background

    results = []
    for cell_id in cell_ids:
        cell_mask = masks == cell_id
        area_px   = int(cell_mask.sum())

        # Physical area — only when calibrated
        area_um2  = round(area_px * (pixel_size_um ** 2), 2) if pixel_size_um else None

        # Circularity: 4π·A / P² (1 = perfect circle, < 1 = elongated)
        perimeter   = measure.perimeter(cell_mask)
        circularity = (
            round((4 * np.pi * area_px) / (perimeter ** 2), 4)
            if perimeter > 0 else 0.0
        )

        # Centroid
        props = measure.regionprops(cell_mask.astype(np.uint8))
        if props:
            cy, cx = props[0].centroid
        else:
            cy, cx = 0.0, 0.0

        # Mean intensity — requires original image; skipped here,
        # computed in detector.py where the raw image is available
        results.append({
            "cell_id":     int(cell_id),
            "area_px":     area_px,
            "area_um2":    area_um2,
            "circularity": circularity,
            "centroid_y":  round(float(cy), 1),
            "centroid_x":  round(float(cx), 1),
        })

    # Aggregate stats
    n = len(results)
    areas_px = [r["area_px"] for r in results]
    circs    = [r["circularity"] for r in results]

    agg: dict = {
        "cell_count":        n,
        "mean_area_px":      round(float(np.mean(areas_px)), 2) if n > 0 else 0.0,
        "std_area_px":       round(float(np.std(areas_px)),  2) if n > 0 else 0.0,
        "mean_circularity":  round(float(np.mean(circs)),    4) if n > 0 else 0.0,
    }

    if pixel_size_um and n > 0:
        areas_um2 = [r["area_um2"] for r in results]
        agg["mean_area_um2"] = round(float(np.mean(areas_um2)), 2)
        agg["std_area_um2"]  = round(float(np.std(areas_um2)),  2)
        # Density: cells per mm² (only when calibrated)
        image_h, image_w = masks.shape
        area_mm2 = (image_h * image_w * pixel_size_um ** 2) / 1_000_000
        agg["density_cells_per_mm2"] = round(n / area_mm2, 2) if area_mm2 > 0 else None
    else:
        agg["mean_area_um2"] = None
        agg["std_area_um2"]  = None
        agg["density_cells_per_mm2"] = None

    return results, agg
