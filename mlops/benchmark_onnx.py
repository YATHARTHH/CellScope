"""
mlops/benchmark_onnx.py
-----------------------
Benchmarks native StarDist TF inference vs ONNX Runtime on the champion model.
Records: latency, peak RAM, nucleus count accuracy, AP delta.

Only runs after final_eval.py has completed (champion is frozen).

ONNX is the production path ONLY IF:
  - Equivalence tests pass (count match, mask IoU > 0.95, centroid < 2px, AP50 delta < 0.01)
  - There is a measurable latency OR RAM benefit

Output: metrics/onnx_equivalence.json
"""

import json
import pathlib
import time
import tracemalloc

import numpy as np
from scipy.optimize import linear_sum_assignment
from benchmark import compute_instance_metrics, average_precision

MODELS_DIR    = pathlib.Path("backend/models")
METRICS_DIR   = pathlib.Path("metrics")
CHAMPION_FLAG = MODELS_DIR / "champion.json"
ONNX_PATH     = MODELS_DIR / "stardist_champion.onnx"
PROC_DIR      = pathlib.Path("data/processed")

# Number of images to use for the benchmark (use val split — test already used)
N_BENCHMARK = 20


def load_champion() -> dict:
    with open(CHAMPION_FLAG) as f:
        return json.load(f)


def load_val_sample(n: int) -> tuple[list, list]:
    split_dir = PROC_DIR / "val"
    X = list(np.load(str(split_dir / "images.npy"), allow_pickle=True))[:n]
    Y = list(np.load(str(split_dir / "masks.npy"),  allow_pickle=True))[:n]
    return X, Y


def run_native(model, X: list) -> tuple[list, list[float], float]:
    """Returns (preds, latencies_ms, peak_ram_mb)."""
    preds, latencies = [], []
    tracemalloc.start()
    for img in X:
        t0 = time.perf_counter()
        labels, _ = model.predict_instances(img)
        latencies.append((time.perf_counter() - t0) * 1000)
        preds.append(labels)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return preds, latencies, peak / 1_048_576


def run_onnx(X: list) -> tuple[list, list[float], float]:
    """Runs ONNX forward pass + Python NMS. Returns (preds, latencies_ms, peak_ram_mb)."""
    import onnxruntime as ort
    from stardist.models import StarDist2D

    # Load StarDist for NMS post-processing (stays in Python always)
    sd = StarDist2D.from_pretrained("2D_versatile_fluo")

    sess = ort.InferenceSession(str(ONNX_PATH),
                                providers=["CPUExecutionProvider"])
    input_name = sess.get_inputs()[0].name

    preds, latencies = [], []
    tracemalloc.start()
    for img in X:
        img_in = img[np.newaxis, ..., np.newaxis].astype(np.float32)
        t0 = time.perf_counter()
        output = sess.run(None, {input_name: img_in})
        # output[0] = prob_map, output[1] = dist_map
        prob = output[0][0, ..., 0]
        dist = output[1][0]
        # NMS in Python via StarDist's built-in method
        labels, _ = sd._predict_instances_generator(
            prob=prob, dist=dist,
            nms_thresh=sd.thresholds.nms,
            prob_thresh=sd.thresholds.prob,
        )
        latencies.append((time.perf_counter() - t0) * 1000)
        preds.append(labels)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return preds, latencies, peak / 1_048_576


def equivalence_check(
    native_preds: list, onnx_preds: list,
    Y: list,
) -> dict:
    """Check all equivalence criteria between native and ONNX predictions."""
    # 1. Count match (exact)
    native_counts = [len(np.unique(p)) - 1 for p in native_preds]
    onnx_counts   = [len(np.unique(p)) - 1 for p in onnx_preds]
    count_diffs   = [abs(n - o) for n, o in zip(native_counts, onnx_counts)]
    count_match   = all(d == 0 for d in count_diffs)

    # 2. Mask IoU > 0.95 per matched instance (sampled on first 5 images)
    ious = []
    for n_pred, o_pred in zip(native_preds[:5], onnx_preds[:5]):
        m = compute_instance_metrics(o_pred, n_pred, iou_threshold=0.0)
        ious.append(m["mean_matched_iou"])
    mask_iou_mean = float(np.mean(ious)) if ious else 0.0

    # 3. Centroid delta < 2px
    centroid_deltas = []
    for n_pred, o_pred in zip(native_preds[:5], onnx_preds[:5]):
        for nid in np.unique(n_pred)[1:]:
            n_mask = n_pred == nid
            o_masks_ids = np.unique(o_pred[n_mask])
            if len(o_masks_ids) == 0:
                continue
            oid = o_masks_ids[np.argmax([np.sum(o_pred == i) for i in o_masks_ids])]
            o_mask = o_pred == oid
            n_cy, n_cx = np.argwhere(n_mask).mean(axis=0)
            o_cy, o_cx = np.argwhere(o_mask).mean(axis=0)
            centroid_deltas.append(np.sqrt((n_cy - o_cy)**2 + (n_cx - o_cx)**2))
    centroid_delta_mean = float(np.mean(centroid_deltas)) if centroid_deltas else 0.0

    # 4. AP50 delta < 0.01
    native_ap = average_precision(native_preds, Y)["val_AP50"]
    onnx_ap   = average_precision(onnx_preds,   Y)["val_AP50"]
    ap50_delta = abs(native_ap - onnx_ap)

    equivalence_passed = (
        count_match and
        mask_iou_mean > 0.95 and
        centroid_delta_mean < 2.0 and
        ap50_delta < 0.01
    )
    return {
        "count_match":          count_match,
        "count_difference_max": int(max(count_diffs)) if count_diffs else 0,
        "mask_iou_mean":        round(mask_iou_mean,      4),
        "centroid_delta_mean_px": round(centroid_delta_mean, 3),
        "ap50_delta":           round(ap50_delta,          4),
        "equivalence_passed":   equivalence_passed,
    }


def main() -> None:
    print("=" * 60)
    print("CellScope — ONNX Benchmark")
    print("Native StarDist TF vs ONNX Runtime")
    print("Equivalence + Latency + RAM")
    print("=" * 60)

    if not ONNX_PATH.exists():
        print(f"  ONNX model not found at {ONNX_PATH}.")
        print("  Run mlops/export_onnx.py first.")
        return

    champion = load_champion()
    print(f"  Champion: {champion['model']}")

    X_val, Y_val = load_val_sample(N_BENCHMARK)
    print(f"  Using {len(X_val)} validation images for benchmark.")

    # Load native model
    from stardist.models import StarDist2D
    if champion["fine_tuned"]:
        native_model = StarDist2D(None, name="stardist_finetuned",
                                  basedir=str(MODELS_DIR))
    else:
        native_model = StarDist2D.from_pretrained("2D_versatile_fluo")

    # Run both
    print("\n  Running native StarDist inference ...")
    native_preds, native_lat, native_ram = run_native(native_model, X_val)

    print("  Running ONNX Runtime inference ...")
    try:
        onnx_preds, onnx_lat, onnx_ram = run_onnx(X_val)
    except Exception as e:
        print(f"  ERROR: ONNX inference failed: {e}")
        return

    # Equivalence check
    equiv = equivalence_check(native_preds, onnx_preds, Y_val)

    results = {
        "native_stardist_latency_ms": round(float(np.median(native_lat)), 1),
        "onnx_cpu_latency_ms":        round(float(np.median(onnx_lat)),   1),
        "native_peak_ram_mb":         round(native_ram, 1),
        "onnx_peak_ram_mb":           round(onnx_ram,   1),
        **equiv,
        "production_recommendation":
            "onnx" if (
                equiv["equivalence_passed"] and
                (np.median(onnx_lat) < np.median(native_lat) or
                 onnx_ram < native_ram)
            ) else "native_tf",
    }

    METRICS_DIR.mkdir(parents=True, exist_ok=True)
    with open(METRICS_DIR / "onnx_equivalence.json", "w") as f:
        json.dump(results, f, indent=2)

    print("\n  === ONNX Benchmark Results ===")
    for k, v in results.items():
        print(f"    {k}: {v}")

    rec = results["production_recommendation"]
    print(f"\n  Production path: {rec.upper()}")
    if rec == "onnx":
        print("  Write 'onnx' to backend/models/inference_engine.txt")
        with open(MODELS_DIR / "inference_engine.txt", "w") as f:
            f.write("onnx")
    else:
        print("  Write 'native_tf' to backend/models/inference_engine.txt")
        with open(MODELS_DIR / "inference_engine.txt", "w") as f:
            f.write("native_tf")


if __name__ == "__main__":
    main()
