"""
backend/utils/cache.py
----------------------
SHA-256 LRU cache for segmentation results.
Identical uploads (same content hash) skip model inference.
"""

import hashlib
import pathlib
from collections import OrderedDict
from typing import Any

_CACHE: "OrderedDict[str, Any]" = OrderedDict()
MAX_CACHE_SIZE = 64  # entries


def file_sha256(filepath: str) -> str:
    """Compute SHA-256 hash of a file's content."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def get(image_hash: str) -> Any | None:
    """Return cached result for hash, or None if not cached."""
    if image_hash in _CACHE:
        # Move to end (LRU: recently used stays)
        _CACHE.move_to_end(image_hash)
        return _CACHE[image_hash]
    return None


def put(image_hash: str, result: Any) -> None:
    """Store result under hash. Evicts oldest entry if cache is full."""
    _CACHE[image_hash] = result
    _CACHE.move_to_end(image_hash)
    if len(_CACHE) > MAX_CACHE_SIZE:
        _CACHE.popitem(last=False)  # evict oldest
