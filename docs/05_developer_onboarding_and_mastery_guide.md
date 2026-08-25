# 🎓 Guide 5: Developer Onboarding & Mastery Guide

This document is a complete walkthrough for developers, bioinformaticians, and engineers who want to **master the CellScope codebase** and build new features.

---

## 📂 1. Directory Tree & Codebase Map

```
cellscope/
├── backend/                        # FastAPI REST Server
│   ├── main.py                     # API route definitions & middleware
│   ├── detector.py                 # StarDist 2D inference singleton & ONNX wrapper
│   ├── quantifier.py               # Instance morphology & calibration engine
│   ├── ai_copilot.py               # AI findings & chat assistant engine
│   ├── database.py                 # SQLite audit log & SHA-256 Part 11 signatures
│   ├── models/                     # Trained weights & champion.json
│   ├── tests/                      # Pytest backend test suite (9/9 passed)
│   └── utils/                      # Caching, OME-TIFF metadata & JSON logging
│
├── frontend/                       # React 18 + Vite SPA Dashboard
│   ├── src/
│   │   ├── App.tsx                 # Main layout & activeTab navigation controller
│   │   ├── index.css               # Glassmorphic design tokens & CSS system
│   │   ├── types.ts                # Shared TypeScript interface definitions
│   │   └── components/
│   │       ├── ImageUploader.tsx   # Drag-and-drop image uploader
│   │       ├── CellMetricsPanel.tsx# Primary stat tiles & per-cell inspector
│   │       ├── AICard.tsx          # Automated AI Diagnostic Findings summary
│   │       ├── AICopilotDrawer.tsx # Interactive AI Copilot assistant chat
│   │       ├── BatchProcessingPanel.tsx # Multi-file batch queue & CSV export
│   │       ├── ModelZooPanel.tsx   # Model comparison cards & engine switcher
│   │       ├── AuditLogTable.tsx   # 21 CFR Part 11 SHA-256 audit table
│   │       ├── SegmentationOverlay.tsx # Interactive HTML5 Canvas overlay
│   │       ├── SplitViewer.tsx     # Before/after slider viewer
│   │       ├── HistogramPanel.tsx  # Cell area frequency histogram
│   │       └── ModelInfoBar.tsx    # Live system health status bar
│   └── package.json
│
├── mlops/                          # Training, Benchmarking & Held-Out Eval
│   ├── train.py                    # 100-epoch StarDist 2D fine-tuning script
│   ├── benchmark.py                # Vectorized IoU & AP50 evaluation engine
│   ├── final_eval.py               # ONE-TIME held-out test evaluation script
│   ├── benchmark_onnx.py           # ONNX vs TF equivalence verifier
│   └── gate.py                     # Automated model champion acceptance gate
│
├── docs/                           # Documentation Suite
│   ├── 01_project_vision_and_usecases.md
│   ├── 02_architecture_and_tech_stack_justification.md
│   ├── 03_ml_training_benchmarking_and_accuracy.md
│   ├── 04_engineering_challenges_and_solutions.md
│   └── 05_developer_onboarding_and_mastery_guide.md
│
└── README.md                       # Master index & quickstart guide
```

---

## 📑 2. Main Files Brief & Purpose Reference

Below is a detailed reference guide for all key files in the codebase, summarizing their role, key responsibilities, and main functions:

### 🐍 Backend Core Modules (`backend/`)

- **[`backend/main.py`](file:///d:/cellscope/backend/main.py)**: The FastAPI application entrypoint. Configures database lifespan initialization, CORS middleware, OWASP security headers, and sliding-window rate limiting. Exposes REST endpoints:
  - `POST /api/v1/segment`: Upload & segment single microscopy image.
  - `POST /api/v1/segment_batch`: Process up to 50 images in parallel batch queue.
  - `POST /api/v1/ai/summary`: Generate automated diagnostic findings.
  - `POST /api/v1/ai/chat`: Interactive AI Microscopy Copilot assistant chat.
  - `GET /api/v1/models` & `POST /api/v1/models/switch`: Model Zoo switcher.
  - `GET /api/v1/analyses`: Retrieve 21 CFR Part 11 audit history.
- **[`backend/detector.py`](file:///d:/cellscope/backend/detector.py)**: StarDist 2D inference singleton wrapper. Loads Keras TensorFlow weights (`stardist_finetuned` vs `pretrained_versatile_fluo`) or ONNX Runtime sessions, runs prediction generators, computes per-instance mean intensities, renders RGBA overlay images in base64, and supports dynamic runtime engine switching (`switch_model`).
- **[`backend/quantifier.py`](file:///d:/cellscope/backend/quantifier.py)**: Quantitative morphology engine. Receives StarDist label matrices and computes per-cell geometry (area, perimeter, centroid $X/Y$, circularity $4\pi A / P^2$). Applies Option B+ physical scale calibration ($\mu\text{m}/\text{px}$) and calculates summary statistics (mean area, nuclear density per $\text{mm}^2$).
- **[`backend/ai_copilot.py`](file:///d:/cellscope/backend/ai_copilot.py)**: 100% offline local AI reasoning engine. Converts morphology metrics into natural-language diagnostic findings (`generate_diagnostic_insights`) and handles interactive user queries (`generate_copilot_response`) for manuscript captions, circularity explanations, and statistical advice.
- **[`backend/database.py`](file:///d:/cellscope/backend/database.py)**: SQLite database interface (`backend/analyses.db`). Handles database creation, saving analysis runs with JSON morphology blobs, querying audit history, and generating cryptographic SHA-256 signatures `sha256(id:hash:count:timestamp)` for 21 CFR Part 11 compliance verification.

---

### ⚛️ Frontend React Components (`frontend/src/`)

- **[`frontend/src/App.tsx`](file:///d:/cellscope/frontend/src/App.tsx)**: Main React application controller. Manages tab navigation state (`activeTab: 'analysis' | 'copilot' | 'batch' | 'zoo' | 'history'`), global analysis result state, system health polling, and topbar layout.
- **[`frontend/src/index.css`](file:///d:/cellscope/frontend/src/index.css)**: Central design system stylesheet. Defines custom CSS design tokens for dark scientific glassmorphism (`backdrop-filter: blur(16px)`), neon fluorescence accents (`#4ade80`, `#38bdf8`, `#a78bfa`), stat tile grids, tables, and micro-animations.
- **[`frontend/src/types.ts`](file:///d:/cellscope/frontend/src/types.ts)**: Shared TypeScript interface definitions (`AnalysisResult`, `CellInstance`, `Morphology`, `CalibrationInfo`, `AIInsights`, `AuditRow`, `HealthStatus`).
- **[`frontend/src/components/ImageUploader.tsx`](file:///d:/cellscope/frontend/src/components/ImageUploader.tsx)**: Drag-and-drop file uploader supporting `.tif`, `.tiff`, `.png`, and `.jpg` images. Implements file input clearing (`inputRef.current.value = ''`) for instant consecutive uploads and optional pixel size ($\mu\text{m}/\text{px}$) scale input.
- **[`frontend/src/components/CellMetricsPanel.tsx`](file:///d:/cellscope/frontend/src/components/CellMetricsPanel.tsx)**: Displays primary quantitative stat tiles (Nuclei Count, Mean Area, Circularity, Density) and renders an interactive single-nucleus inspection card when a cell is hovered or clicked on the overlay.
- **[`frontend/src/components/AICard.tsx`](file:///d:/cellscope/frontend/src/components/AICard.tsx)**: Renders the automated AI Diagnostic Findings summary card at the top of the results grid with confidence scores and biological health bullet points.
- **[`frontend/src/components/AICopilotDrawer.tsx`](file:///d:/cellscope/frontend/src/components/AICopilotDrawer.tsx)**: Interactive AI Microscopy Copilot chat drawer with 1-click quick presets (*Manuscript Caption*, *Circularity Score*, *Statistical Advice*) and copy-to-clipboard tools.
- **[`frontend/src/components/BatchProcessingPanel.tsx`](file:///d:/cellscope/frontend/src/components/BatchProcessingPanel.tsx)**: Multi-file batch segmentation panel. Renders batch queue progress, summary stat tiles, per-file summary table, **Batch CSV Export**, and **Printable Lab Report Generator**.
- **[`frontend/src/components/ModelZooPanel.tsx`](file:///d:/cellscope/frontend/src/components/ModelZooPanel.tsx)**: Model Zoo management panel displaying comparative benchmark metrics ($AP_{50}$, $F1$, latency, count error) for StarDist Fine-Tuned, StarDist Pretrained, and CellPose 3.x, with 1-click active engine switching.
- **[`frontend/src/components/AuditLogTable.tsx`](file:///d:/cellscope/frontend/src/components/AuditLogTable.tsx)**: 21 CFR Part 11 audit history component displaying SHA-256 cryptographic signatures, `Verified ✅` badges, hash copy buttons, and CSV log export.
- **[`frontend/src/components/SegmentationOverlay.tsx`](file:///d:/cellscope/frontend/src/components/SegmentationOverlay.tsx)**: Interactive HTML5 Canvas overlay component rendering segmented nuclear instances with color-coded boundaries, hover tooltips, and cell selection click events.
- **[`frontend/src/components/SplitViewer.tsx`](file:///d:/cellscope/frontend/src/components/SplitViewer.tsx)**: Interactive clip-path before/after slider comparing raw fluorescence image against annotated segmentation overlay.
- **[`frontend/src/components/HistogramPanel.tsx`](file:///d:/cellscope/frontend/src/components/HistogramPanel.tsx)**: Recharts frequency histogram plotting the size distribution of cell nuclear areas ($\text{px}^2$ or $\mu\text{m}^2$).

---

### 🚀 MLOps & Benchmark Scripts (`mlops/`)

- **[`mlops/train.py`](file:///d:/cellscope/mlops/train.py)**: StarDist 2D fine-tuning script. Trains Keras StarDist model for 100 epochs on 100 BBBC039 training images with Adam optimizer and cosine learning rate decay.
- **[`mlops/benchmark.py`](file:///d:/cellscope/mlops/benchmark.py)**: Model evaluation benchmark script. Features vectorized $O(H \times W)$ `np.bincount` IoU matrix calculation for high-speed $AP_{50}$, $AP_{75}$, and F1 evaluation across validation images.
- **[`mlops/final_eval.py`](file:///d:/cellscope/mlops/final_eval.py)**: ONE-TIME evaluation script executed exclusively on the 50 held-out BBBC039 test set images after champion model selection.
- **[`mlops/gate.py`](file:///d:/cellscope/mlops/gate.py)**: Model acceptance gate script verifying candidate performance against benchmark targets (`AP50 >= 0.85`, `count_rel_error <= 0.10`) before promoting weights to `backend/models/champion.json`.

---

## 💻 2. How to Run CellScope Locally

### Prerequisites
- Python 3.10+ (Python 3.13 recommended)
- Node.js 18+ (Node.js 20 recommended)

### Step 1: Clone & Setup Python Virtual Environment
```bash
cd cellscope
python -m venv .venv

# On Windows PowerShell / CMD:
.venv\Scripts\activate

# On Linux / macOS:
source .venv/bin/activate

pip install -r backend/requirements.txt
```

### Step 2: Launch FastAPI Backend Server
```bash
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```
- API Swagger Docs available at: `http://127.0.0.1:8000/docs`

### Step 3: Launch React Vite Frontend Server
In a second terminal tab:
```bash
cd frontend
npm install

# On Windows:
cmd /c npm run dev

# On Linux / macOS:
npm run dev
```
- Dashboard live at: `http://localhost:3000`

---

## 🛠️ 3. How to Extend CellScope: Developer Recipes

### Recipe A: Adding a New AI Copilot Quick Prompt
1. Open `frontend/src/components/AICopilotDrawer.tsx`.
2. Add your new prompt to `quickPrompts` array:
   ```ts
   { label: 'Apoptosis Risk', prompt: 'Assess nuclear fragmentation and apoptosis risk for this field.', icon: AlertTriangle }
   ```
3. Open `backend/ai_copilot.py` and add keyword handler in `generate_copilot_response()`:
   ```python
   if "apoptosis" in p or "fragmentation" in p:
       return "Apoptosis Risk Assessment: Circularity > 0.80 indicates 0% nuclear blebbing."
   ```

### Recipe B: Running Backend Automated Tests
```bash
python -m pytest backend/tests/ -v
```

### Recipe C: Triggering Model Fine-Tuning
```bash
python -m mlops.train --epochs 100 --batch-size 4
```
- Automatically saves new weights to `backend/models/stardist_finetuned` and updates `backend/models/champion.json`.
