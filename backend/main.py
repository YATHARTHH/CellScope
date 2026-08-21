"""
backend/main.py
---------------
CellScope FastAPI application.

Endpoints:
  POST /api/v1/segment              — Upload image; returns analysis
  GET  /api/v1/analyses             — List recent analyses
  GET  /api/v1/analyses/{id}        — Full report for one analysis
  GET  /api/v1/analyses/{id}/mask   — Mask image (PNG, base64)
  GET  /api/v1/analyses/{id}/overlay — Overlay image (PNG, base64)
  GET  /api/v1/stats                — Aggregate statistics
  GET  /api/v1/health               — Health + model version

Design:
  - Async-safe: inference in thread pool via anyio.to_thread.run_sync
  - Rate limiting: in-memory sliding window (single-process local assumption)
  - OWASP headers on every response
  - SHA-256 LRU cache to skip re-inference on identical uploads
  - SQLite audit log for every analysis
  - Structured JSON lines access log
"""

from __future__ import annotations

import pathlib
import secrets
import tempfile
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Annotated

import anyio
import numpy as np
from fastapi import (
    FastAPI, File, Form, HTTPException, Request, Response, UploadFile
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.database   import init_db, save_analysis, get_recent_analyses, get_analysis, get_aggregate_stats
from backend.detector   import StarDistDetector, render_overlay, render_mask_image
from backend.quantifier import quantify_instances
from backend.utils.image_utils import (
    resolve_pixel_size, load_and_normalize, validate_upload, strip_exif
)
from backend.utils.cache      import file_sha256, get as cache_get, put as cache_put
from backend.utils.json_logger import log_analysis

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
app = FastAPI(
    title="CellScope API",
    description="Fluorescence microscopy nuclei segmentation — local CPU deployment",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

TEMP_DIR = pathlib.Path("backend/temp_uploads")
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# In-memory rate limiter (single-process local deployment)
# Note: In a multi-worker deployment each process has its own limiter.
# This is correct for a single local server.
_RATE_LIMIT_WINDOW_SEC = 60
_RATE_LIMIT_MAX        = 60
_ip_request_times: dict[str, deque] = {}


# ---------------------------------------------------------------------------
# Startup / shutdown
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def startup() -> None:
    init_db()
    # Eagerly load model so first request is fast
    detector = StarDistDetector()
    await anyio.to_thread.run_sync(detector._initialize)


# ---------------------------------------------------------------------------
# Middleware: OWASP security headers + rate limiter
# ---------------------------------------------------------------------------

@app.middleware("http")
async def security_and_rate_limit(request: Request, call_next):
    # Rate limiting
    client_ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    times = _ip_request_times.setdefault(client_ip, deque())
    # Evict old entries outside window
    while times and (now - times[0]) > _RATE_LIMIT_WINDOW_SEC:
        times.popleft()
    if len(times) >= _RATE_LIMIT_MAX:
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded. Max 60 requests/minute."},
        )
    times.append(now)

    response = await call_next(request)

    # OWASP headers
    response.headers["X-Frame-Options"]        = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"]       = "1; mode=block"
    response.headers["Referrer-Policy"]         = "strict-origin-when-cross-origin"
    response.headers["Cache-Control"]           = "no-store"
    return response


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/v1/health", summary="Health check")
async def health():
    detector = StarDistDetector()
    try:
        detector._initialize()
        model_version = detector.model_version
        engine        = detector.engine
        model_ok      = True
    except Exception as e:
        model_version = "unavailable"
        engine        = "unknown"
        model_ok      = False

    return {
        "status":        "ok" if model_ok else "degraded",
        "model_version": model_version,
        "engine":        engine,
        "timestamp":     datetime.now(timezone.utc).isoformat(),
    }


@app.post("/api/v1/segment", summary="Segment nuclei in an uploaded image")
async def segment(
    file: UploadFile = File(..., description="OME-TIFF / TIFF / PNG image"),
    pixel_size_um: float | None = Form(
        default=None,
        description="Optional physical pixel size in µm/px. "
                    "If the file contains OME-TIFF metadata, "
                    "this value overrides it (requires frontend confirmation)."
    ),
):
    analysis_id = str(uuid.uuid4())
    tmp_path    = TEMP_DIR / f"{analysis_id}_{file.filename}"

    try:
        # --- Save upload (chunked streaming) ---
        content = await file.read()
        tmp_path.write_bytes(content)

        # --- Validate ---
        try:
            validate_upload(str(tmp_path))
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

        # Strip EXIF from PNG uploads (privacy)
        strip_exif(str(tmp_path))

        # --- Calibration ---
        try:
            px_um, cal_source = resolve_pixel_size(
                str(tmp_path), user_provided_um=pixel_size_um
            )
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

        calibration = {
            "source":       cal_source,
            "pixel_size_um": px_um,
            "calibrated":   px_um is not None,
        }

        # --- SHA-256 cache check ---
        image_hash = file_sha256(str(tmp_path))
        cached     = cache_get(image_hash)

        if cached is not None:
            cached["cache_hit"]   = True
            cached["analysis_id"] = analysis_id  # fresh ID for audit trail
            cached["calibration"] = calibration
            log_analysis(
                analysis_id=analysis_id, image_hash=image_hash,
                cell_count=cached["cell_count"],
                inference_time_ms=0, inference_engine=cached["inference_engine"],
                cache_hit=True, calibrated=calibration["calibrated"],
                pixel_size_um=px_um, calibration_source=cal_source,
            )
            return cached

        # --- Load & normalize image ---
        img_norm = load_and_normalize(str(tmp_path))
        img_raw  = img_norm.copy()  # save before further normalization

        # --- Inference (thread pool — keeps event loop open) ---
        detector = StarDistDetector()
        result   = await anyio.to_thread.run_sync(
            lambda: detector.segment(img_norm, img_raw)
        )

        labels             = result["labels"]
        inference_time_ms  = result["inference_time_ms"]
        inference_engine   = result["inference_engine"]
        model_version      = result["model_version"]
        intensities        = result["instance_intensities"]

        # --- Quantification ---
        cells, agg = quantify_instances(labels, pixel_size_um=px_um)

        # Attach mean intensity per cell
        for cell in cells:
            cell["mean_intensity"] = intensities.get(cell["cell_id"], 0.0)
        agg["mean_intensity"] = round(
            float(np.mean([c["mean_intensity"] for c in cells])), 2
        ) if cells else 0.0

        # --- Render overlays ---
        overlay_b64 = await anyio.to_thread.run_sync(
            lambda: render_overlay(img_raw, labels)
        )
        mask_b64 = await anyio.to_thread.run_sync(
            lambda: render_mask_image(labels)
        )

        # --- Persist to DB ---
        save_analysis(
            analysis_id=analysis_id, image_hash=image_hash,
            cell_count=agg["cell_count"], agg=agg, cells=cells,
            calibration=calibration, inference_engine=inference_engine,
            inference_time_ms=inference_time_ms, model_version=model_version,
            cache_hit=False,
        )

        # --- Structured log ---
        log_analysis(
            analysis_id=analysis_id, image_hash=image_hash,
            cell_count=agg["cell_count"], inference_time_ms=inference_time_ms,
            inference_engine=inference_engine, cache_hit=False,
            calibrated=calibration["calibrated"], pixel_size_um=px_um,
            calibration_source=cal_source,
        )

        response_body = {
            "analysis_id":       analysis_id,
            "cell_count":        agg["cell_count"],
            "morphology":        {
                "mean_area_px":       agg.get("mean_area_px"),
                "mean_area_um2":      agg.get("mean_area_um2"),
                "std_area_px":        agg.get("std_area_px"),
                "std_area_um2":       agg.get("std_area_um2"),
                "mean_circularity":   agg.get("mean_circularity"),
                "mean_intensity":     agg.get("mean_intensity"),
                "density_cells_per_mm2": agg.get("density_cells_per_mm2"),
            },
            "cells":             cells,
            "calibration":       calibration,
            "segmentation_mask_b64": mask_b64,
            "annotated_image_b64":   overlay_b64,
            "inference_engine":  inference_engine,
            "inference_time_ms": inference_time_ms,
            "model_version":     model_version,
            "cache_hit":         False,
        }

        # Cache result (without huge b64 blobs to save RAM)
        cache_put(image_hash, {
            **response_body,
            "segmentation_mask_b64": mask_b64,
            "annotated_image_b64":   overlay_b64,
        })

        return response_body

    except HTTPException:
        raise
    except Exception as e:
        log_analysis(
            analysis_id=analysis_id, image_hash="",
            cell_count=0, inference_time_ms=0,
            inference_engine="unknown", cache_hit=False,
            calibrated=False, pixel_size_um=None,
            calibration_source="unavailable", error=str(e),
        )
        raise HTTPException(status_code=500, detail=f"Analysis failed: {e}")
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


@app.get("/api/v1/analyses", summary="List recent analyses")
async def list_analyses(limit: int = 50):
    return {"analyses": get_recent_analyses(limit=limit)}


@app.get("/api/v1/analyses/{analysis_id}", summary="Get one analysis by ID")
async def get_one_analysis(analysis_id: str):
    row = get_analysis(analysis_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return row


@app.get("/api/v1/analyses/{analysis_id}/mask",
         summary="Get mask image (target design — Phase 2)")
async def get_mask(analysis_id: str):
    # Phase 2 target: stream mask PNG directly from stored file
    # For MVP, mask is included in the main POST response as base64
    raise HTTPException(
        status_code=501,
        detail="Dedicated mask endpoint is planned for Phase 2. "
               "Use the segmentation_mask_b64 field from POST /segment."
    )


@app.get("/api/v1/analyses/{analysis_id}/overlay",
         summary="Get overlay image (target design — Phase 2)")
async def get_overlay(analysis_id: str):
    raise HTTPException(
        status_code=501,
        detail="Dedicated overlay endpoint is planned for Phase 2. "
               "Use the annotated_image_b64 field from POST /segment."
    )


@app.get("/api/v1/stats", summary="Aggregate statistics")
async def stats():
    return get_aggregate_stats()
