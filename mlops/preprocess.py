"""
mlops/preprocess.py
-------------------
Loads the BBBC039v1 official train/validation/test partitions and
normalizes images for StarDist training and evaluation.

Key design decisions:
  - Uses the OFFICIAL BBBC039 partitions (not a custom split) so results
    are comparable across studies.
  - Normalization: percentile 1.0–99.8 per image (matches StarDist 2D_versatile_fluo).
  - Saves processed numpy arrays as compressed .npz files per split.
  - Mask labels are uint16 instance IDs (each nucleus = unique integer).
"""

import pathlib
import json
import numpy as np
import tifffile
from skimage import io as skio
from skimage.measure import label as sk_label
from csbdeep.utils import normalize

RAW_DIR   = pathlib.Path("data/raw/bbbc039")
PROC_DIR  = pathlib.Path("data/processed")
META_DIR  = RAW_DIR / "metadata"
IMG_DIR   = RAW_DIR / "images"
MASK_DIR  = RAW_DIR / "masks"


def load_official_partitions() -> dict[str, list[str]]:
    """
    Load the official BBBC039 train/val/test partition CSV files.
    Returns a dict: {"train": [...], "val": [...], "test": [...]}
    """
    partitions: dict[str, list[str]] = {}

    # BBBC039 provides partition CSVs in the metadata folder
    # File names may vary: train.txt, validation.txt, test.txt or similar
    for split_name, possible_names in [
        ("train",      ["train.txt", "training.txt", "train.csv"]),
        ("val",        ["validation.txt", "val.txt", "validation.csv"]),
        ("test",       ["test.txt", "testing.txt", "test.csv"]),
    ]:
        for fname in possible_names:
            fpath = META_DIR / fname
            if fpath.exists():
                with open(fpath) as f:
                    names = [line.strip() for line in f if line.strip()]
                partitions[split_name] = names
                print(f"  [{split_name}] {len(names)} FOVs from {fname}")
                break
        else:
            # Fallback: scan metadata directory for any matching file
            found = list(META_DIR.glob(f"*{split_name}*"))
            if found:
                with open(found[0]) as f:
                    names = [line.strip() for line in f if line.strip()]
                partitions[split_name] = names
                print(f"  [{split_name}] {len(names)} FOVs from {found[0].name}")
            else:
                print(f"  WARNING: No partition file found for '{split_name}'. "
                      f"Files in metadata/: {[f.name for f in META_DIR.iterdir()]}")
                partitions[split_name] = []

    return partitions


def find_image(stem: str) -> pathlib.Path | None:
    """Find an image file by stem (without extension) in IMG_DIR."""
    for ext in [".tif", ".tiff", ".png"]:
        p = IMG_DIR / (stem + ext)
        if p.exists():
            return p
    # Recursive search if not in root
    for ext in [".tif", ".tiff", ".png"]:
        matches = list(IMG_DIR.rglob(stem + ext))
        if matches:
            return matches[0]
    return None


def find_mask(stem: str) -> pathlib.Path | None:
    """Find a mask file by stem in MASK_DIR."""
    for ext in [".png", ".tif", ".tiff"]:
        p = MASK_DIR / (stem + ext)
        if p.exists():
            return p
    for ext in [".png", ".tif", ".tiff"]:
        matches = list(MASK_DIR.rglob(stem + ext))
        if matches:
            return matches[0]
    return None


def load_image(path: pathlib.Path) -> np.ndarray:
    """Load a single-channel fluorescence image as float32."""
    img = tifffile.imread(str(path)).astype(np.float32)
    if img.ndim == 3:
        # Take first channel if multi-channel (should not happen for BBBC039)
        img = img[0]
    return img


def load_mask(path: pathlib.Path) -> np.ndarray:
    """
    Load segmentation mask as uint16 instance labels.
    BBBC039 masks are binary PNG files; we label connected components
    to produce unique integer IDs per nucleus.
    """
    mask = skio.imread(str(path))
    if mask.ndim == 3:
        mask = mask[..., 0]  # take first channel
    mask = (mask > 0).astype(np.uint8)
    labeled = sk_label(mask).astype(np.uint16)
    return labeled


def process_split(split_name: str, file_stems: list[str]) -> None:
    """Normalize images and save processed split as .npz."""
    if not file_stems:
        print(f"  [{split_name}] Skipping — no files listed.")
        return

    out_dir = PROC_DIR / split_name
    out_dir.mkdir(parents=True, exist_ok=True)

    loaded_images, loaded_masks, loaded_names = [], [], []
    missing = []

    for stem in file_stems:
        # Strip extension if present in partition file
        stem = pathlib.Path(stem).stem

        img_path  = find_image(stem)
        mask_path = find_mask(stem)

        if img_path is None or mask_path is None:
            missing.append(stem)
            continue

        img  = load_image(img_path)
        mask = load_mask(mask_path)

        # Normalize: percentile 1.0–99.8 (matches StarDist 2D_versatile_fluo training)
        img_norm = normalize(img, 1.0, 99.8, axis=None)

        loaded_images.append(img_norm)
        loaded_masks.append(mask)
        loaded_names.append(stem)

    if missing:
        print(f"  [{split_name}] WARNING: {len(missing)} files not found: {missing[:5]}")

    if not loaded_images:
        print(f"  [{split_name}] No images loaded — skipping save.")
        return

    # Save as object arrays (images may have different sizes)
    np.save(str(out_dir / "images.npy"),  np.array(loaded_images, dtype=object), allow_pickle=True)
    np.save(str(out_dir / "masks.npy"),   np.array(loaded_masks,  dtype=object), allow_pickle=True)
    np.save(str(out_dir / "names.npy"),   np.array(loaded_names,  dtype=object), allow_pickle=True)

    print(f"  [{split_name}] Saved {len(loaded_images)} images to {out_dir}")


def main() -> None:
    print("=" * 60)
    print("CellScope — BBBC039 Preprocessing")
    print("Using OFFICIAL BBBC039 train/val/test partitions")
    print("=" * 60)

    PROC_DIR.mkdir(parents=True, exist_ok=True)

    partitions = load_official_partitions()

    for split in ["train", "val", "test"]:
        stems = partitions.get(split, [])
        process_split(split, stems)

    # Save partition summary for reproducibility
    summary = {k: len(v) for k, v in partitions.items()}
    with open(PROC_DIR / "partition_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\n  Partition summary: {summary}")
    print("  Preprocessing complete.")
    print("  Run next: python mlops/benchmark.py")


if __name__ == "__main__":
    main()
