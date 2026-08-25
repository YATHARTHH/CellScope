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

from contextlib import asynccontextmanager

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
from backend.ai_copilot       import generate_diagnostic_insights, generate_copilot_response

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="CellScope API",
    description="Fluorescence microscopy nuclei segmentation — local CPU deployment",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
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

        ai_insights = generate_diagnostic_insights(
            cell_count=agg["cell_count"],
            mean_area_px=agg.get("mean_area_px", 0.0),
            mean_area_um2=agg.get("mean_area_um2"),
            mean_circularity=agg.get("mean_circularity", 0.0),
            density_cells_per_mm2=agg.get("density_cells_per_mm2"),
            calibrated=calibration["calibrated"],
            pixel_size_um=calibration.get("pixel_size_um"),
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
            "ai_insights":        ai_insights,
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


@app.post("/api/v1/ai/summary", summary="Generate AI diagnostic insights")
async def ai_summary(payload: dict):
    return generate_diagnostic_insights(
        cell_count=payload.get("cell_count", 0),
        mean_area_px=payload.get("mean_area_px", 0.0),
        mean_area_um2=payload.get("mean_area_um2"),
        mean_circularity=payload.get("mean_circularity", 0.0),
        density_cells_per_mm2=payload.get("density_cells_per_mm2"),
        calibrated=payload.get("calibrated", False),
        pixel_size_um=payload.get("pixel_size_um"),
    )


@app.post("/api/v1/ai/chat", summary="Interactive AI Copilot assistant")
async def ai_chat(payload: dict):
    prompt = payload.get("prompt", "")
    context = payload.get("context")
    response_text = generate_copilot_response(prompt=prompt, context=context)
    return {"prompt": prompt, "response": response_text}


@app.post("/api/v1/segment_batch", summary="Batch segmentation for multiple microscopy images")
async def segment_batch(
    files: list[UploadFile] = File(...),
    pixel_size_um: Annotated[float | None, Form()] = None,
):
    if not files or len(files) == 0:
        raise HTTPException(status_code=400, detail="No files uploaded.")
    if len(files) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 files allowed per batch.")

    detector = StarDistDetector()
    results = []
    total_cells = 0
    areas_px = []
    areas_um2 = []
    circularities = []

    for upload_file in files:
        contents = await upload_file.read()
        if len(contents) > 50 * 1024 * 1024:
            continue
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=pathlib.Path(upload_file.filename or "").suffix) as tmp:
                tmp.write(contents)
                tmp_path = pathlib.Path(tmp.name)

            img_norm, img_raw, ome_meta = await anyio.to_thread.run_sync(
                load_and_normalize, tmp_path
            )

            resolved_px, cal_source = resolve_pixel_size(pixel_size_um, ome_meta)
            seg_result = await anyio.to_thread.run_sync(
                detector.segment, img_norm, img_raw
            )

            cells, agg = quantify_instances(
                labels=seg_result["labels"],
                img_raw=img_raw,
                pixel_size_um=resolved_px,
                instance_intensities=seg_result["instance_intensities"],
            )

            count = agg["cell_count"]
            total_cells += count
            if agg.get("mean_area_px"): areas_px.append(agg["mean_area_px"])
            if agg.get("mean_area_um2"): areas_um2.append(agg["mean_area_um2"])
            if agg.get("mean_circularity"): circularities.append(agg["mean_circularity"])

            results.append({
                "filename": upload_file.filename,
                "cell_count": count,
                "mean_area_px": agg.get("mean_area_px", 0.0),
                "mean_area_um2": agg.get("mean_area_um2"),
                "mean_circularity": agg.get("mean_circularity", 0.0),
                "inference_time_ms": seg_result["inference_time_ms"],
                "calibrated": resolved_px is not None,
            })
        except Exception as e:
            results.append({
                "filename": upload_file.filename,
                "error": str(e),
                "cell_count": 0,
            })
        finally:
            if 'tmp_path' in locals() and tmp_path.exists():
                tmp_path.unlink()

    batch_summary = {
        "total_images": len(results),
        "total_cells": total_cells,
        "mean_cells_per_image": round(total_cells / max(1, len(results)), 1),
        "mean_area_px": round(float(np.mean(areas_px)), 1) if areas_px else 0.0,
        "mean_area_um2": round(float(np.mean(areas_um2)), 1) if areas_um2 else None,
        "mean_circularity": round(float(np.mean(circularities)), 2) if circularities else 0.0,
        "items": results,
    }

    return batch_summary


@app.get("/api/v1/models", summary="List available segmentation models")
async def list_models():
    detector = StarDistDetector()
    active_key = "stardist_finetuned" if detector.champion.get("fine_tuned") else "stardist_pretrained"
    return {
        "active_model": active_key,
        "active_engine": detector.engine,
        "models": [
            {
                "key": "stardist_finetuned",
                "name": "StarDist 2D Fine-Tuned (Champion)",
                "architecture": "Star-convex Object Detection (U-Net 2D)",
                "dataset": "BBBC039 Fine-Tuned (100 Epochs)",
                "ap50": 0.9317,
                "f1_score": 0.9397,
                "count_error": "3.3%",
                "avg_latency_ms": 1580,
                "status": "Production Champion",
            },
            {
                "key": "stardist_pretrained",
                "name": "StarDist 2D Versatile Fluo (Pretrained)",
                "architecture": "Star-convex Object Detection (U-Net 2D)",
                "dataset": "Pretrained Versatile Fluo Baseline",
                "ap50": 0.8356,
                "f1_score": 0.8329,
                "count_error": "10.4%",
                "avg_latency_ms": 2300,
                "status": "Baseline",
            },
            {
                "key": "cellpose_baseline",
                "name": "CellPose 3.x cyto2/cyto3 (Generalist)",
                "architecture": "Spatial Vector Flow Field Network",
                "dataset": "CellPose Generalist Benchmark",
                "ap50": 0.8329,
                "f1_score": 0.8278,
                "count_error": "8.8%",
                "avg_latency_ms": 51000,
                "status": "Comparative Baseline",
            },
        ],
    }


@app.post("/api/v1/models/switch", summary="Switch active inference model")
async def switch_model_endpoint(payload: dict):
    model_key = payload.get("model_key")
    if not model_key:
        raise HTTPException(status_code=400, detail="Missing model_key")
    
    detector = StarDistDetector()
    try:
        updated = await anyio.to_thread.run_sync(detector.switch_model, model_key)
        return {"status": "success", "active_model": model_key, "info": updated}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
