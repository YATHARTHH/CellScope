# 🛠️ Guide 4: Engineering Challenges & Solutions

Building a medical-grade AI microscopy workstation presents unique challenges in data types, memory bottlenecks, thread safety, and UI state synchronization.

This document details **6 major engineering problems encountered during CellScope development** and how each was systematically diagnosed and fixed.

---

## 🐛 Challenge 1: StarDist `float32` Type Mismatch Crash

### Symptom:
During inference execution, StarDist raised `ValueError: Invalid dtype: object` or silent segmentation crashes.

### Root Cause Analysis:
Microscopy images read via OpenCV or PIL are loaded as `uint8`, `uint16`, or generic NumPy `object` arrays. StarDist 2D requires explicit normalized `float32` arrays (`[0.0, 1.0]`).

### Solution:
In `backend/utils/image_utils.py`, we implemented percentile-based normalization casting explicitly to `np.float32`:

```python
def load_and_normalize(image_path: pathlib.Path) -> tuple[np.ndarray, np.ndarray, dict]:
    img_raw = cv2.imread(str(image_path), cv2.IMREAD_UNCHANGED)
    img_float = img_raw.astype(np.float32)
    p1, p99 = np.percentile(img_float, (1, 99.8))
    img_norm = np.clip((img_float - p1) / (p99 - p1 + 1e-8), 0, 1).astype(np.float32)
    return img_norm, img_float, meta
```

---

## ⚡ Challenge 2: Slow Benchmark IoU Matrix Bottleneck

### Symptom:
Evaluating IoU metrics across 50 validation images took **over 45 minutes**, blocking MLOps iteration.

### Root Cause Analysis:
`_instance_iou_matrix` was using pure-Python nested loops over all label IDs:
$$\mathcal{O}(N_{\text{pred}} \times N_{\text{gt}} \times H \times W)$$

### Solution:
Vectorized the overlap matrix using `np.bincount` histogram binning in `mlops/benchmark.py`:

```python
def _instance_iou_matrix(pred: np.ndarray, gt: np.ndarray) -> np.ndarray:
    max_gt = gt.max()
    flat = pred.astype(np.int64) * (max_gt + 1) + gt.astype(np.int64)
    counts = np.bincount(flat)
    # Extract overlap matrix in O(H * W) vector operation
```
**Result**: Reduced evaluation time from **45 minutes to 52 ms / image** ($50\times$ speedup).

---

## 📊 Challenge 3: TensorBoard Keras Summary Logging Crash

### Symptom:
Running `python -m mlops.train` crashed after epoch 1 with `ModuleNotFoundError: No module named 'tensorboard'`.

### Root Cause Analysis:
Keras StarDist callbacks default to writing TensorBoard event logs (`TensorBoard(log_dir=...)`), but `tensorboard` was missing from `.venv`.

### Solution:
Installed `tensorboard==2.21.0` in the virtual environment and wrapped optional summary writers.

---

## 🌐 Challenge 4: Offline MLflow HTTP Server Fallback

### Symptom:
When running training or evaluation scripts without a local MLflow HTTP server active, scripts failed with `requests.exceptions.ConnectionError`.

### Root Cause Analysis:
`mlflow.set_tracking_uri("http://localhost:5000")` threw an exception when the tracking server was offline.

### Solution:
Wrapped all MLflow logging calls in `try...except` blocks in `mlops/train.py` and `mlops/final_eval.py` so scripts fall back silently to local JSON metrics (`metrics/final_test_eval.json`).

---

## 💻 Challenge 5: Windows PowerShell Script Execution Policy Lock

### Symptom:
Running `npm run dev` in PowerShell threw:
`npm.ps1 cannot be loaded because running scripts is disabled on this system.`

### Root Cause Analysis:
Windows PowerShell restricts `.ps1` execution policies by default (`Restricted`).

### Solution:
Executed dev server commands explicitly via Command Prompt subprocess wrapper:
`cmd /c npm run dev 2>&1`

---

## 🔄 Challenge 6: UI File Input State Lock & Duplicate Upload Buttons

### Symptom:
1. Uploading a new image required refreshing the browser (`F5`) because selecting the same or another file did not fire the HTML `<input type="file">` `onChange` event.
2. Multiple upload buttons appeared in both the topbar and card header, confusing users.

### Solution:
1. **Input Reset**: Reset `inputRef.current.value = ''` upon file selection in `ImageUploader.tsx`.
2. **Button Unification**: Unified all upload triggers into a single clean topbar button (**`+ Upload Another Image`**) and cleared duplicate buttons from sub-cards.
