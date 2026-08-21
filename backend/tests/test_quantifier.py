import pytest
import numpy as np
from backend.quantifier import quantify_instances

def test_quantify_pixel_units_only():
    masks = np.zeros((100, 100), dtype=np.uint16)
    masks[10:20, 10:20] = 1
    masks[30:50, 30:50] = 2

    cells, agg = quantify_instances(masks, pixel_size_um=None)

    assert agg["cell_count"] == 2
    assert agg["mean_area_um2"] is None
    assert agg["density_cells_per_mm2"] is None
    assert cells[0]["area_px"] == 100
    assert cells[0]["area_um2"] is None
    assert cells[1]["area_px"] == 400

def test_quantify_calibrated():
    masks = np.zeros((100, 100), dtype=np.uint16)
    masks[10:20, 10:20] = 1

    cells, agg = quantify_instances(masks, pixel_size_um=0.5)

    assert agg["cell_count"] == 1
    assert agg["mean_area_um2"] == 25.0  # 100 * (0.5^2)
    assert cells[0]["area_um2"] == 25.0

def test_quantify_invalid_pixel_size():
    masks = np.zeros((10, 10), dtype=np.uint16)
    with pytest.raises(ValueError):
        quantify_instances(masks, pixel_size_um=-1.0)
