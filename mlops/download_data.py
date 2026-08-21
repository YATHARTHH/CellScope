"""
mlops/download_data.py
----------------------
Downloads BBBC039v1 from the Broad Bioimage Benchmark Collection.
License: CC0 — no registration or authentication required.
Dataset: https://bbbc.broadinstitute.org/BBBC039

BBBC039v1 contents:
  - 200 fluorescence FOVs (U2OS cells, DAPI/Hoechst stained)
  - ~23,000 manually annotated nuclei
  - Official train / validation / test partitions (CSV files)
  - Binary segmentation masks
"""

import os
import urllib.request
import zipfile
import pathlib
import hashlib
import sys

# ---------------------------------------------------------------------------
# Dataset URLs (direct links from Broad Institute, no auth required)
# ---------------------------------------------------------------------------
BBBC039_IMAGES_URL = "https://data.broadinstitute.org/bbbc/BBBC039/images.zip"
BBBC039_MASKS_URL  = "https://data.broadinstitute.org/bbbc/BBBC039/masks.zip"
BBBC039_METADATA_URL = "https://data.broadinstitute.org/bbbc/BBBC039/metadata.zip"

RAW_DIR = pathlib.Path("data/raw/bbbc039")
IMAGES_DIR  = RAW_DIR / "images"
MASKS_DIR   = RAW_DIR / "masks"
META_DIR    = RAW_DIR / "metadata"


def _progress_hook(block_num: int, block_size: int, total_size: int) -> None:
    downloaded = block_num * block_size
    if total_size > 0:
        pct = min(100, downloaded * 100 // total_size)
        mb  = downloaded / 1_048_576
        sys.stdout.write(f"\r  {pct:3d}%  {mb:.1f} MB")
        sys.stdout.flush()
    if downloaded >= total_size:
        print()


def download_and_extract(url: str, dest_dir: pathlib.Path, label: str) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    zip_path = RAW_DIR / f"{label}.zip"

    if zip_path.exists():
        print(f"  [skip] {label}.zip already downloaded.")
    else:
        print(f"  Downloading {label} from Broad Institute ...")
        urllib.request.urlretrieve(url, zip_path, reporthook=_progress_hook)
        print(f"  Saved to {zip_path}")

    print(f"  Extracting {label}.zip ...")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(dest_dir)
    print(f"  Extracted to {dest_dir}")


def main() -> None:
    print("=" * 60)
    print("CellScope — BBBC039v1 Dataset Download")
    print("License: CC0  |  No authentication required")
    print("Source:  bbbc.broadinstitute.org/BBBC039")
    print("=" * 60)

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    download_and_extract(BBBC039_IMAGES_URL,   IMAGES_DIR,  "images")
    download_and_extract(BBBC039_MASKS_URL,    MASKS_DIR,   "masks")
    download_and_extract(BBBC039_METADATA_URL, META_DIR,    "metadata")

    # Verify key files exist
    image_files = list(IMAGES_DIR.rglob("*.tif")) + list(IMAGES_DIR.rglob("*.png"))
    mask_files  = list(MASKS_DIR.rglob("*.png"))  + list(MASKS_DIR.rglob("*.tif"))
    print(f"\n  Found {len(image_files)} image files")
    print(f"  Found {len(mask_files)} mask files")

    # Look for partition CSVs
    partition_files = list(META_DIR.rglob("*.csv"))
    print(f"  Found {len(partition_files)} partition/metadata CSV files:")
    for pf in partition_files:
        print(f"    {pf.name}")

    if len(image_files) < 190:
        print("\n  WARNING: Expected ~200 images. Download may be incomplete.")
        sys.exit(1)

    print("\n  BBBC039v1 download complete.")
    print("  Run next: python mlops/preprocess.py")


if __name__ == "__main__":
    main()
