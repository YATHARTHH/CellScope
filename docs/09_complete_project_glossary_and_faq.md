# 📚 Guide 9: Complete Project Glossary & FAQ

This guide provides a comprehensive **A-to-Z Glossary** of all terms used in CellScope across biology, machine learning, and web engineering, followed by **15 Frequently Asked Questions (FAQ)** for deep practical understanding.

---

## 🔤 1. Complete Project Glossary

### 🔬 Biological & Bioimaging Domain Terms
- **DAPI / Hoechst 33342**: Fluorescent blue dyes that bind to DNA in cell nuclei, causing nuclei to glow under ultraviolet light.
- **Fluorescence Microscopy**: Microscopy technique using light emission from stained samples to visualize cellular structures.
- **Nuclear Pleomorphism**: Variation in cell nucleus size, shape, and optical density. Irregular pleomorphism is a hallmark of cancerous cells.
- **Pyknosis**: Irreversible condensation of chromatin in the nucleus of a cell undergoing necrosis or apoptosis (cell death).
- **Cell Confluence**: The percentage of a culture dish surface covered by adhering cells (e.g. 80% monolayer confluence).
- **OME-TIFF**: An open-standard file format (`.ome.tif`) containing bio-microscopy images along with embedded XML physical metadata (pixel size $\mu\text{m}$).
- **Physical Scale Calibration ($\mu\text{m}/\text{px}$)**: The real-world physical distance represented by 1 pixel on the microscope camera sensor.

---

### 🧠 Machine Learning & Computer Vision Terms
- **Instance Segmentation**: Identifying every individual cell instance and delineating its exact boundary (unlike semantic segmentation which groups all cells into one blob).
- **Star-Convex Polygon**: A geometric shape where every boundary point is visible from a central origin along radial rays. StarDist uses 32 radial rays to predict cell boundaries.
- **$AP_{50}$ (Average Precision @ IoU 0.50)**: Standard benchmark metric measuring the percentage of cell instances accurately localized with at least 50% spatial overlap.
- **Held-Out Test Set**: A subset of images locked during training and evaluated **only once** to ensure true real-world accuracy without memorization (data leakage).
- **ONNX (Open Neural Network Exchange)**: An open model format allowing models trained in Keras/TensorFlow to run on lightweight C++ inference engines.

---

### ⚡ Web Engineering & Security Terms
- **FastAPI (ASGI)**: Modern Python web framework using asynchronous event loops (`uvicorn`) for high-concurrency API performance.
- **Threadpool Offloading (`anyio.to_thread.run_sync`)**: Delegation of heavy CPU operations (neural network execution) to background threads to prevent freezing the HTTP server.
- **21 CFR Part 11**: FDA regulatory standard requiring immutable, cryptographically signed audit logs for pharmaceutical electronic records.
- **SHA-256 Signature**: Cryptographic hash algorithm producing a unique 64-character fingerprint `sha256(id:hash:count:timestamp)` to verify data immutability.
- **Glassmorphic UI**: Modern visual design style featuring frosted glass panels (`backdrop-filter: blur`), subtle translucent borders, and glowing accent highlights.

---

## ❓ 2. Top 15 Frequently Asked Questions (FAQ)

### Q1: How does CellScope handle overlapping or touching cell nuclei?
CellScope uses **StarDist 2D**, which predicts star-convex radial polygon rays relative to cell centers. Because each cell is predicted from its center outward, touching cell boundaries are naturally resolved as separate objects instead of merging into one blob.

---

### Q2: Why does CellScope run 100% locally on the workstation CPU instead of the Cloud?
Pharmaceutical and clinical laboratories handle confidential patient biopsies and proprietary drug candidate data. Uploading images to cloud APIs creates privacy, HIPAA, and compliance risks. CellScope runs **100% offline on standard CPUs in 1.5 seconds**.

---

### Q3: What happens if an uploaded image has no physical scale metadata ($\mu\text{m}/\text{px}$)?
CellScope safely falls back to raw pixel measurements ($\text{px}^2$) and flags the analysis as `Uncalibrated`. This prevents making false biological assumptions while allowing users to manually enter a pixel scale if known.

---

### Q4: Can CellScope segment non-fluorescent images (e.g., Brightfield or H&E tissue stains)?
CellScope's default champion model is fine-tuned for single-channel nuclear fluorescence (DAPI / Hoechst). For H&E or brightfield tissue stains, users can switch to CellPose in the **Model Zoo** tab or fine-tune a new StarDist model via `mlops/train.py`.

---

### Q5: How fast is CellScope single-image inference?
On a standard desktop CPU without GPU acceleration, single-image inference takes **~1.58 seconds**. On GPU or via ONNX Runtime, execution takes **< 400 milliseconds**.

---

### Q6: How does the AI Copilot work without an external paid API key?
CellScope's AI Copilot runs a **100% local rule-augmented scientific reasoning engine** (`backend/ai_copilot.py`). It analyzes the per-image metrics (circularity, density, area distribution) and synthesizes publication-grade captions and insights locally without cloud API calls.

---

### Q7: What is the maximum batch size supported in Batch Processing?
Up to **50 images** per batch. Each image is processed sequentially in the background while updating real-time queue progress indicators.

---

### Q8: How does CellScope verify 21 CFR Part 11 compliance?
Every segmentation run generates a SHA-256 cryptographic signature:
`sha256(analysis_id : image_hash : cell_count : timestamp)`
Signatures are stored in SQLite and displayed with `Verified ✅` badges in the audit table, ensuring any tampering with historical data is immediately detected.

---

### Q9: What is the difference between StarDist Fine-Tuned and StarDist Pretrained?
- **StarDist Pretrained**: Default baseline model trained on generic fluorescent images ($AP_{50} = 0.8356$).
- **StarDist Fine-Tuned**: Our champion model fine-tuned for 100 epochs on Broad Institute BBBC039 images ($AP_{50} = 0.9317$).

---

### Q10: How does the interactive Canvas Overlay work?
CellScope renders raw images and segmentation masks on an HTML5 `<canvas>` element. When users move their mouse, CellScope performs point-in-polygon calculations to highlight the hovered cell boundary and display its exact area, circularity, and intensity.

---

### Q11: How do I export my analysis data for scientific publications?
1. **Single Image**: Click **"Download CSV"** in the per-cell morphology table.
2. **Batch Queue**: Click **"Export Batch CSV"** or **"Generate Printable Lab Report"** in the Batch Processing panel.
3. **Audit History**: Click **"Export Audit CSV"** in the Audit & Compliance table.

---

### Q12: How did you accelerate IoU benchmark evaluation by $50\times$?
Instead of using slow Python nested loops over label IDs ($\sim 45\text{ minutes}$), we implemented vectorized histogram binning (`pred_label * (max_gt + 1) + gt_label`) via `np.bincount`, reducing benchmark time to **52 milliseconds per image**.

---

### Q13: How can a developer retrain CellScope on a custom laboratory dataset?
1. Place annotated training images and masks in `data/processed/train/`.
2. Run `python -m mlops.train --epochs 100 --batch-size 4`.
3. Run `python -m mlops.gate` to benchmark the new model against targets.

---

### Q14: How does the FastAPI server handle high concurrent traffic?
FastAPI offloads heavy neural network inference to background worker threads using `anyio.to_thread.run_sync()`. This keeps the main ASGI event loop free to handle health probes and API requests asynchronously.

---

### Q15: How can I run CellScope in production using Docker?
Run `docker-compose up --build`. This starts the multi-stage container bundling the React Vite frontend and FastAPI backend on port `8000`.
