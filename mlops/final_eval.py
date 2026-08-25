"""
mlops/final_eval.py
-------------------
ONE-TIME evaluation of the champion model on the BBBC039 official TEST split.

This script:
  - MUST be run only ONCE after the champion model is fully frozen.
  - MUST NOT be re-run to compare models or adjust thresholds.
  - Touching the test set more than once inflates reported metrics.

Outputs:
  metrics/final_test_eval.json  (test metrics, prefixed test_*)
  MLflow run tagged eval_type: FINAL_ONE_TIME
"""

import json
import pathlib
import sys
import time
import tracemalloc

import numpy as np
import mlflow

from mlops.benchmark import (
    average_precision, count_metrics, compute_instance_metrics
)

PROC_DIR    = pathlib.Path("data/processed")
MODELS_DIR  = pathlib.Path("backend/models")
METRICS_DIR = pathlib.Path("metrics")
CHAMPION_FLAG = MODELS_DIR / "champion.json"
FINAL_EVAL_FLAG = METRICS_DIR / "final_test_eval.json"

MLFLOW_URI  = "http://127.0.0.1:5000"
EXPERIMENT  = "cellscope-final-test-evaluation"


def load_split(split: str) -> tuple[list, list]:
    split_dir = PROC_DIR / split
    X_raw = np.load(str(split_dir / "images.npy"), allow_pickle=True)
    Y_raw = np.load(str(split_dir / "masks.npy"),  allow_pickle=True)
    X = [img.astype(np.float32) for img in X_raw]
    Y = [mask.astype(np.uint16) for mask in Y_raw]
    return X, Y


def load_champion() -> dict:
    if not CHAMPION_FLAG.exists():
        print("ERROR: backend/models/champion.json not found.")
        print("Run gate.py first to select the champion model.")
        sys.exit(1)
    with open(CHAMPION_FLAG) as f:
        return json.load(f)


def main() -> None:
    # Guard: refuse to re-run if final eval already exists
    if FINAL_EVAL_FLAG.exists():
        print("=" * 60)
        print("WARNING: final_test_eval.json already exists.")
        print("The test set has already been evaluated.")
        print("Re-running would constitute test-set leakage.")
        print("If you are certain this is a fresh experiment,")
        print("manually delete metrics/final_test_eval.json first.")
        print("=" * 60)
        sys.exit(1)

    print("=" * 60)
    print("CellScope — FINAL Test-Set Evaluation (ONE-TIME)")
    print("Evaluation split: BBBC039 official TEST split")
    print("This script should run EXACTLY ONCE per champion model.")
    print("=" * 60)

    champion = load_champion()
    print(f"\n  Champion model: {champion['model']}  "
          f"(fine_tuned={champion['fine_tuned']})")

    X_test, Y_test = load_split("test")
    print(f"  Test set: {len(X_test)} images")

    # Load the champion model
    from stardist.models import StarDist2D
    if champion["fine_tuned"]:
        model = StarDist2D(None, name="stardist_finetuned",
                           basedir=str(MODELS_DIR))
    else:
        model = StarDist2D.from_pretrained("2D_versatile_fluo")

    # Run inference on test set
    preds, latencies = [], []
    tracemalloc.start()
    for img in X_test:
        t0 = time.perf_counter()
        labels, _ = model.predict_instances(img)
        latencies.append((time.perf_counter() - t0) * 1000)
        preds.append(labels)
    _, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    # Compute test metrics
    ap_m  = average_precision(preds, Y_test)
    cnt_m = count_metrics(preds, Y_test)
    per_img = [compute_instance_metrics(p, g) for p, g in zip(preds, Y_test)]
    f1s   = [m["f1"]               for m in per_img]
    mious = [m["mean_matched_iou"] for m in per_img]

    # Rename val_ prefix → test_ for final reported metrics
    def remap(d: dict) -> dict:
        return {k.replace("val_", "test_"): v for k, v in d.items()}

    results = {
        **remap(ap_m), **remap(cnt_m),
        "test_instance_F1":       round(float(np.mean(f1s)),    4),
        "test_mean_matched_iou":  round(float(np.mean(mious)),  4),
        "test_latency_ms_median": round(float(np.median(latencies)), 1),
        "test_peak_ram_mb":       round(peak_mem / 1_048_576, 1),
        "champion_model":         champion["model"],
        "fine_tuned":             champion["fine_tuned"],
        "eval_set":               "bbbc039_official_test",
    }

    # Save results
    METRICS_DIR.mkdir(parents=True, exist_ok=True)
    with open(FINAL_EVAL_FLAG, "w") as f:
        json.dump(results, f, indent=2)

    # Log to MLflow
    try:
        mlflow.set_tracking_uri(MLFLOW_URI)
        mlflow.set_experiment(EXPERIMENT)
        with mlflow.start_run(run_name=f"final_eval_{champion['model']}") as run:
            mlflow.set_tag("eval_set",     "bbbc039_official_test")
            mlflow.set_tag("eval_type",    "FINAL_ONE_TIME")
            mlflow.set_tag("champion",     champion["model"])
            mlflow.set_tag("fine_tuned",   str(champion["fine_tuned"]))
            for k, v in results.items():
                if isinstance(v, (int, float)):
                    mlflow.log_metric(k, v)
        print(f"\n  Logged to MLflow run: {run.info.run_id}")
    except Exception as e:
        print(f"\n  WARNING: MLflow logging failed ({e})")

    # Print summary
    print("\n  === FINAL TEST RESULTS ===")
    for k, v in results.items():
        print(f"    {k}: {v}")

    print("\n  Final evaluation complete.")
    print("  Run next: python mlops/benchmark_onnx.py")


if __name__ == "__main__":
    main()
