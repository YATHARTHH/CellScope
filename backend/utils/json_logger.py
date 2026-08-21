"""
backend/utils/json_logger.py
----------------------------
Structured JSON lines logger for API access events.
Writes one JSON object per line to logs/api_access.jsonl.
"""

import json
import pathlib
import time
from datetime import datetime, timezone

LOG_FILE = pathlib.Path("logs/api_access.jsonl")


def _ensure_log_dir() -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)


def log_analysis(
    analysis_id: str,
    image_hash: str,
    cell_count: int,
    inference_time_ms: float,
    inference_engine: str,
    cache_hit: bool,
    calibrated: bool,
    pixel_size_um: float | None,
    calibration_source: str,
    error: str | None = None,
) -> None:
    """Append one analysis event to the JSON lines log."""
    _ensure_log_dir()
    entry = {
        "ts":                datetime.now(timezone.utc).isoformat(),
        "analysis_id":       analysis_id,
        "image_hash":        image_hash[:16] + "...",  # partial hash for PII safety
        "cell_count":        cell_count,
        "inference_time_ms": round(inference_time_ms, 1),
        "inference_engine":  inference_engine,
        "cache_hit":         cache_hit,
        "calibrated":        calibrated,
        "calibration_source": calibration_source,
        "pixel_size_um":     pixel_size_um,
        "error":             error,
    }
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
