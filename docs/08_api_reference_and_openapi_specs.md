# 📡 Guide 8: Complete REST API Reference & OpenAPI Specifications

This document provides a comprehensive **REST API Reference** for CellScope, detailing every endpoint, request parameter, JSON schema, status code, and example `curl` invocation.

---

## 🌐 Base URL
- **Local Workstation**: `http://127.0.0.1:8000`
- **Interactive Swagger UI**: `http://127.0.0.1:8000/docs`
- **ReDoc Documentation**: `http://127.0.0.1:8000/redoc`
- **Raw OpenAPI JSON Spec**: `http://127.0.0.1:8000/openapi.json`

---

## 📌 Endpoint Summary

| Method | Endpoint | Description | Auth | Rate Limit |
|:---:|:---|:---|:---:|:---:|
| `GET` | `/api/v1/health` | System health, model version, & engine | None | 60 req/min |
| `POST` | `/api/v1/segment` | Single microscopy image segmentation | None | 60 req/min |
| `POST` | `/api/v1/segment_batch` | Multi-file batch segmentation queue | None | 60 req/min |
| `POST` | `/api/v1/ai/summary` | Automated AI diagnostic findings | None | 60 req/min |
| `POST` | `/api/v1/ai/chat` | Interactive AI Copilot assistant chat | None | 60 req/min |
| `GET` | `/api/v1/models` | List Model Zoo engines & benchmark stats | None | 60 req/min |
| `POST` | `/api/v1/models/switch` | Switch active inference model engine | None | 60 req/min |
| `GET` | `/api/v1/analyses` | List recent 21 CFR Part 11 audit logs | None | 60 req/min |
| `GET` | `/api/v1/analyses/{id}` | Retrieve full report by analysis ID | None | 60 req/min |
| `GET` | `/api/v1/stats` | Aggregate system database statistics | None | 60 req/min |

---

## 📖 Endpoint Details & Examples

### 1. `POST /api/v1/segment` — Single Image Segmentation
Uploads a single microscopy file (`.tif`, `.tiff`, `.png`, `.jpg`), executes StarDist 2D inference, calculates physical calibration, and returns instance masks and AI insights.

#### Request Parameters:
- **`file`** *(UploadFile, required)*: Binary image buffer (max 50 MB).
- **`pixel_size_um`** *(float, optional)*: Physical scale in $\mu\text{m}/\text{px}$ (e.g. `0.325`).

#### Example `curl`:
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/segment" \
  -F "file=@sample_nucleus.png" \
  -F "pixel_size_um=0.325"
```

#### Example Response (`200 OK`):
```json
{
  "analysis_id": "8f269675-d095-4241-aaea-0572407cddb2",
  "cell_count": 153,
  "morphology": {
    "mean_area_px": 711.2,
    "mean_area_um2": 75.1,
    "std_area_px": 84.3,
    "std_area_um2": 8.9,
    "mean_circularity": 0.82,
    "mean_intensity": 142.5,
    "density_cells_per_mm2": 1420
  },
  "calibration": {
    "source": "user_provided",
    "pixel_size_um": 0.325,
    "calibrated": true
  },
  "ai_insights": {
    "status": "Healthy & Uniform",
    "bullets": [
      "Morphology Status: Healthy & Uniform — High nuclear roundness (circularity 0.82 >= 0.80).",
      "Density & Confluence: Optimal seeding density (1,420 cells/mm²).",
      "Nuclear Footprint: Mean nuclear footprint of 75.1 µm²."
    ],
    "confidence_score": 0.94
  },
  "segmentation_mask_b64": "iVBORw0KGgoAAAANSUhEUgAA...",
  "annotated_image_b64": "iVBORw0KGgoAAAANSUhEUgAA...",
  "inference_engine": "native_tf",
  "inference_time_ms": 1580.4,
  "model_version": "CellScope-StarDist-stardist_finetuned@champion",
  "cache_hit": false
}
```

---

### 2. `POST /api/v1/ai/chat` — Interactive AI Copilot Assistant
Processes natural-language queries in context of active analysis metrics.

#### Request Body (`application/json`):
```json
{
  "prompt": "Generate a manuscript figure caption for this sample.",
  "context": {
    "cell_count": 153,
    "mean_area_um2": 75.1,
    "mean_circularity": 0.82,
    "calibrated": true
  }
}
```

#### Example Response (`200 OK`):
```json
{
  "prompt": "Generate a manuscript figure caption for this sample.",
  "response": "**Figure Caption Suggestion:**\n\n**Figure 1. Automated StarDist 2D Segmentation of Fluorescence Nuclei.** Representative single-channel fluorescence microscopy field displaying segmented nuclear instances (n = 153 nuclei detected). Mean nuclear area: 75.1 µm² (circularity score = 0.82). Segmented boundaries rendered via StarDist 2D fine-tuned model (AP50 = 0.9317)."
}
```

---

### 3. `GET /api/v1/models` — List Model Zoo Engines
Returns benchmark precision and latency metrics across available segmentation engines.

#### Example Response (`200 OK`):
```json
{
  "active_model": "stardist_finetuned",
  "active_engine": "native_tf",
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
      "status": "Production Champion"
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
      "status": "Baseline"
    }
  ]
}
```

---

### 4. `GET /api/v1/analyses` — 21 CFR Part 11 Audit History
Retrieves recent analysis runs with cryptographic SHA-256 signatures.

#### Example Response (`200 OK`):
```json
{
  "analyses": [
    {
      "id": "8f269675-d095-4241-aaea-0572407cddb2",
      "created_at": "2026-08-25T20:30:00.000Z",
      "cell_count": 153,
      "mean_area_px": 711.2,
      "mean_area_um2": 75.1,
      "mean_circularity": 0.82,
      "calibrated": 1,
      "pixel_size_um": 0.325,
      "calibration_source": "user_provided",
      "inference_engine": "native_tf",
      "inference_time_ms": 1580.4,
      "model_version": "CellScope-StarDist-stardist_finetuned@champion",
      "cache_hit": 0,
      "sha256_signature": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      "part11_verified": true
    }
  ]
}
```

---

## ⚠️ HTTP Error Status Codes

| Status Code | Meaning | Cause |
|:---:|:---|:---|
| `200 OK` | Success | Request processed successfully. |
| `400 Bad Request` | Client Error | Unsupported file format (`.exe`), payload > 50 MB, or empty batch. |
| `404 Not Found` | Resource Error | Analysis ID does not exist in SQLite database. |
| `422 Unprocessable Entity` | Schema Error | Malformed JSON request body or missing mandatory parameters. |
| `429 Too Many Requests` | Rate Exceeded | Client exceeded 60 requests / minute rate limit threshold. |
| `500 Internal Server Error` | Server Error | Deep learning inference exception or file read failure. |
