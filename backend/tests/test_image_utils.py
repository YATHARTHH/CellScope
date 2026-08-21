import pytest
from backend.utils.image_utils import resolve_pixel_size

def test_resolve_pixel_size_unavailable(tmp_path):
    p = tmp_path / "test.tif"
    p.write_bytes(b"dummy")
    px, source = resolve_pixel_size(str(p), user_provided_um=None)
    assert px is None
    assert source == "unavailable"

def test_resolve_pixel_size_user_provided(tmp_path):
    p = tmp_path / "test.tif"
    p.write_bytes(b"dummy")
    px, source = resolve_pixel_size(str(p), user_provided_um=0.325)
    assert px == 0.325
    assert source == "user_provided"

def test_resolve_pixel_size_invalid():
    with pytest.raises(ValueError):
        resolve_pixel_size("fake.tif", user_provided_um=-0.5)
