"""
mlops/benchmark.py
------------------
Benchmarks two models against the BBBC039v1 VALIDATION split:
  1. StarDist pretrained  — 'pretrained_versatile_fluo' (local weights)
  2. Cellpose baseline    — 'nuclei' model (Cellpose 3.x API)

IMPORTANT:
  - ONLY the VALIDATION split is used here (not the test split).
  - The test split is reserved exclusively for final_eval.py.
  - Champion selection is based on validation metrics only.

Outputs:
  metrics/pretrained_stardist.json
  metrics/cellpose_baseline.json
"""

import json
import pathlib
import time
import tracemalloc

import numpy as np
from csbdeep.utils import normalize
from scipy.optimize import linear_sum_assignment
from skimage.measure import label as sk_label
from tqdm import tqdm
import mlflow

PROC_DIR     = pathlib.Path("data/processed")
METRICS_DIR  = pathlib.Path("metrics")
METRICS_DIR.mkdir(parents=True, exist_ok=True)

MLFLOW_URI   = "http://127.0.0.1:5000"
EXPERIMENT   = "cellscope-benchmark-pretrained"

VAL_SPLIT    = "val"   # NEVER use "test" here


def load_stardist_pretrained():
    from stardist.models import StarDist2D
    local_path = pathlib.Path("backend/models/pretrained_versatile_fluo")
    if local_path.exists():
        return StarDist2D(None, name="pretrained_versatile_fluo", basedir="backend/models")
    return StarDist2D.from_pretrained("2D_versatile_fluo")


def _instance_iou_matrix(pred: np.ndarray, gt: np.ndarray) -> np.ndarray:
    """Vectorized IoU matrix using label histograms — O(H*W), not O(n^2 * H*W)."""
    pred_ids = np.unique(pred)[1:]   # skip background 0
    gt_ids   = np.unique(gt)[1:]
    n_pred, n_gt = len(pred_ids), len(gt_ids)
    if n_pred == 0 or n_gt == 0:
        return np.zeros((n_pred, n_gt), dtype=np.float32)

    # Re-index labels to 1..n so we can use them as array indices
    pred_remap = np.zeros(int(pred.max()) + 1, dtype=np.int32)
    for i, pid in enumerate(pred_ids):
        pred_remap[pid] = i + 1
    gt_remap = np.zeros(int(gt.max()) + 1, dtype=np.int32)
    for j, gid in enumerate(gt_ids):
        gt_remap[gid] = j + 1

    pred_r = pred_remap[pred]   # shape H×W, values 0..n_pred
    gt_r   = gt_remap[gt]       # shape H×W, values 0..n_gt

    # Intersection: joint histogram over (pred_label, gt_label) pairs
    # Encode pair as pred_r * (n_gt+1) + gt_r
    flat = pred_r.ravel().astype(np.int64) * (n_gt + 1) + gt_r.ravel().astype(np.int64)
    hist = np.bincount(flat, minlength=(n_pred + 1) * (n_gt + 1))
    hist = hist.reshape(n_pred + 1, n_gt + 1)
    intersection = hist[1:, 1:].astype(np.float32)  # n_pred × n_gt

    # Areas from histogram margins
    pred_area = hist[1:, :].sum(axis=1, keepdims=True)  # n_pred × 1
    gt_area   = hist[:, 1:].sum(axis=0, keepdims=True)  # 1 × n_gt
    union = pred_area + gt_area - intersection

    iou_mat = np.where(union > 0, intersection / union, 0.0).astype(np.float32)
    return iou_mat


def compute_instance_metrics(
    pred: np.ndarray,
    gt: np.ndarray,
    iou_threshold: float = 0.5,
) -> dict:
    iou_mat = _instance_iou_matrix(pred, gt)
    if iou_mat.size == 0:
        n_pred = len(np.unique(pred)) - 1
        n_gt   = len(np.unique(gt))   - 1
        return {
            "tp": 0, "fp": n_pred, "fn": n_gt,
            "precision": 0.0, "recall": 0.0, "f1": 0.0,
            "mean_matched_iou": 0.0,
        }

    row_ind, col_ind = linear_sum_assignment(-iou_mat)

    tp, matched_ious = 0, []
    for r, c in zip(row_ind, col_ind):
        if iou_mat[r, c] >= iou_threshold:
            tp += 1
            matched_ious.append(float(iou_mat[r, c]))

    n_pred = iou_mat.shape[0]
    n_gt   = iou_mat.shape[1]
    fp  = n_pred - tp
    fn  = n_gt   - tp
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1        = (2 * precision * recall / (precision + recall)
                 if (precision + recall) > 0 else 0.0)

    return {
        "tp": tp, "fp": fp, "fn": fn,
        "precision": round(precision, 4),
        "recall":    round(recall,    4),
        "f1":        round(f1,        4),
        "mean_matched_iou": round(float(np.mean(matched_ious)) if matched_ious else 0.0, 4),
    }


def average_precision(preds: list, gts: list, iou_thresholds=None) -> dict:
    if iou_thresholds is None:
        iou_thresholds = np.arange(0.5, 0.95, 0.05)

    ap_scores = []
    for thresh in iou_thresholds:
        all_tp, all_fp, all_fn = 0, 0, 0
        for pred, gt in zip(preds, gts):
            m = compute_instance_metrics(pred, gt, iou_threshold=thresh)
            all_tp += m["tp"]; all_fp += m["fp"]; all_fn += m["fn"]
        prec = all_tp / (all_tp + all_fp) if (all_tp + all_fp) > 0 else 0.0
        rec  = all_tp / (all_tp + all_fn) if (all_tp + all_fn) > 0 else 0.0
        f1   = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
        ap_scores.append(f1)

    return {
        "val_AP50":    round(ap_scores[0],  4),
        "val_AP75":    round(ap_scores[5],  4) if len(ap_scores) > 5 else 0.0,
        "val_mean_AP": round(float(np.mean(ap_scores)), 4),
    }


def count_metrics(preds: list, gts: list) -> dict:
    pred_counts = np.array([len(np.unique(p)) - 1 for p in preds], dtype=float)
    gt_counts   = np.array([len(np.unique(g)) - 1 for g in gts],   dtype=float)
    diff = np.abs(pred_counts - gt_counts)
    rel  = diff / np.maximum(gt_counts, 1)
    return {
        "val_count_mae":       round(float(np.mean(diff)),  4),
        "val_count_rmse":      round(float(np.sqrt(np.mean(diff**2))), 4),
        "val_count_rel_error": round(float(np.mean(rel)),   4),
    }


def benchmark_stardist(X_val: list, Y_val: list) -> dict:
    """Evaluate pretrained StarDist 2D on validation split."""
    print("  Loading StarDist pretrained model ...")
    model = load_stardist_pretrained()

    preds, latencies = [], []
    tracemalloc.start()

    for img in tqdm(X_val, desc="StarDist inference", unit="img"):
        t0 = time.perf_counter()
        labels, _ = model.predict_instances(img)
        latencies.append((time.perf_counter() - t0) * 1000)
        preds.append(labels)

    _, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    ap_m  = average_precision(preds, Y_val)
    cnt_m = count_metrics(preds, Y_val)

    per_img = [compute_instance_metrics(p, g) for p, g in zip(preds, Y_val)]
    f1s     = [m["f1"] for m in per_img]
    mious   = [m["mean_matched_iou"] for m in per_img]

    return {
        **ap_m, **cnt_m,
        "val_instance_F1":        round(float(np.mean(f1s)),    4),
        "val_mean_matched_iou":   round(float(np.mean(mious)),  4),
        "val_latency_ms_median":  round(float(np.median(latencies)), 1),
        "val_latency_ms_p95":     round(float(np.percentile(latencies, 95)), 1),
        "val_peak_ram_mb":        round(peak_mem / 1_048_576, 1),
        "model": "stardist_2D_versatile_fluo",
        "eval_set": "bbbc039_official_val",
    }


def benchmark_cellpose(X_val: list, Y_val: list) -> dict:
    """Evaluate Cellpose 3.x 'nuclei' model on validation split."""
    from cellpose import models as cp_models

    print("  Loading Cellpose 3.x 'nuclei' model (CPU) ...")
    cp_model = cp_models.Cellpose(gpu=False, model_type="nuclei")

    preds, latencies = [], []
    tracemalloc.start()

    for img in tqdm(X_val, desc="Cellpose inference", unit="img"):
        t0 = time.perf_counter()
        masks, _, _, _ = cp_model.eval([img], diameter=None, channels=[0, 0])
        latencies.append((time.perf_counter() - t0) * 1000)
        preds.append(masks[0].astype(np.uint16))

    _, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    ap_m  = average_precision(preds, Y_val)
    cnt_m = count_metrics(preds, Y_val)

    per_img = [compute_instance_metrics(p, g) for p, g in zip(preds, Y_val)]
    f1s     = [m["f1"] for m in per_img]
    mious   = [m["mean_matched_iou"] for m in per_img]

    return {
        **ap_m, **cnt_m,
        "val_instance_F1":        round(float(np.mean(f1s)),    4),
        "val_mean_matched_iou":   round(float(np.mean(mious)),  4),
        "val_latency_ms_median":  round(float(np.median(latencies)), 1),
        "val_latency_ms_p95":     round(float(np.percentile(latencies, 95)), 1),
        "val_peak_ram_mb":        round(peak_mem / 1_048_576, 1),
        "model": "cellpose_nuclei_3x",
        "eval_set": "bbbc039_official_val",
    }


def load_split(split: str) -> tuple[list, list]:
    split_dir = pathlib.Path("data/processed") / split
    X_raw = np.load(str(split_dir / "images.npy"), allow_pickle=True)
    Y_raw = np.load(str(split_dir / "masks.npy"),  allow_pickle=True)
    X = [img.astype(np.float32) for img in X_raw]
    Y = [mask.astype(np.uint16) for mask in Y_raw]
    return X, Y


def main() -> None:
    print("=" * 60)
    print("CellScope — Benchmark: Pretrained StarDist vs Cellpose")
    print("Evaluation split: BBBC039 official VALIDATION (not test)")
    print("=" * 60)

    X_val, Y_val = load_split(VAL_SPLIT)
    print(f"  Loaded {len(X_val)} validation images.")

    print("\n[1/2] Benchmarking StarDist pretrained ...")
    sd_metrics = benchmark_stardist(X_val, Y_val)
    with open(METRICS_DIR / "pretrained_stardist.json", "w") as f:
        json.dump(sd_metrics, f, indent=2)
    print(f"  AP50={sd_metrics['val_AP50']:.3f}  "
          f"F1={sd_metrics['val_instance_F1']:.3f}  "
          f"count_rel_err={sd_metrics['val_count_rel_error']:.3f}  "
          f"latency={sd_metrics['val_latency_ms_median']:.0f}ms")

    print("\n[2/2] Benchmarking Cellpose 3.x ...")
    cp_metrics = benchmark_cellpose(X_val, Y_val)
    with open(METRICS_DIR / "cellpose_baseline.json", "w") as f:
        json.dump(cp_metrics, f, indent=2)
    print(f"  AP50={cp_metrics['val_AP50']:.3f}  "
          f"F1={cp_metrics['val_instance_F1']:.3f}  "
          f"count_rel_err={cp_metrics['val_count_rel_error']:.3f}  "
          f"latency={cp_metrics['val_latency_ms_median']:.0f}ms")

    try:
        mlflow.set_tracking_uri(MLFLOW_URI)
        mlflow.set_experiment(EXPERIMENT)
        with mlflow.start_run(run_name="stardist_pretrained"):
            mlflow.set_tag("eval_set", "bbbc039_official_val")
            mlflow.set_tag("model",    "stardist_2D_versatile_fluo")
            for k, v in sd_metrics.items():
                if isinstance(v, (int, float)):
                    mlflow.log_metric(k, v)
        with mlflow.start_run(run_name="cellpose_baseline"):
            mlflow.set_tag("eval_set", "bbbc039_official_val")
            mlflow.set_tag("model",    "cellpose_nuclei_3x")
            for k, v in cp_metrics.items():
                if isinstance(v, (int, float)):
                    mlflow.log_metric(k, v)
        print("\n  Metrics logged to MLflow.")
    except Exception as e:
        print(f"\n  WARNING: Could not log to MLflow ({e}).")

    print("\n  Benchmark complete.")
    print("  Run next: python mlops/gate.py")


if __name__ == "__main__":
    main()
