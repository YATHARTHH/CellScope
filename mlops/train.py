"""
mlops/train.py
--------------
Fine-tunes StarDist 2D on the BBBC039 train split.
Validates on the BBBC039 validation split.

CRITICAL: The BBBC039 official TEST split is NEVER used in this script.
Test-set evaluation is reserved exclusively for final_eval.py,
which runs ONCE after the champion model is fully frozen.

Outputs:
  backend/models/stardist_finetuned/  (model weights)
  metrics/finetuned_stardist.json     (validation metrics, prefixed val_*)
"""

import json
import pathlib
import time
import tracemalloc

import numpy as np
import mlflow
import yaml

from stardist.models import StarDist2D, Config2D

# Reuse metric functions from benchmark.py
from mlops.benchmark import (
    average_precision, count_metrics, compute_instance_metrics
)

PROC_DIR    = pathlib.Path("data/processed")
MODELS_DIR  = pathlib.Path("backend/models")
METRICS_DIR = pathlib.Path("metrics")
CONFIG_PATH = pathlib.Path("mlops/configs/stardist_config.yaml")

MLFLOW_URI  = "http://127.0.0.1:5000"
EXPERIMENT  = "cellscope-stardist-finetuning"


def load_split(split_name: str):
    """Loads normalized X and label Y from PROC_DIR/{split_name}/."""
    split_dir = PROC_DIR / split_name
    X_raw = np.load(str(split_dir / "images.npy"), allow_pickle=True)
    Y_raw = np.load(str(split_dir / "masks.npy"),  allow_pickle=True)
    # Images are already percentile-normalized (1–99.8) by preprocess.py
    X = [img.astype(np.float32) for img in X_raw]
    Y = [mask.astype(np.uint16) for mask in Y_raw]
    return X, Y


def load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return yaml.safe_load(f)
    return {}


def main() -> None:
    print("=" * 60)
    print("CellScope — StarDist Fine-Tuning")
    print("Train split: BBBC039 official train")
    print("Val split:   BBBC039 official val (for model selection only)")
    print("Test split:  NOT USED HERE — reserved for final_eval.py")
    print("=" * 60)

    X_train, Y_train = load_split("train")
    X_val,   Y_val   = load_split("val")
    print(f"  Train: {len(X_train)} images  |  Val: {len(X_val)} images")

    cfg_overrides = load_config()
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    METRICS_DIR.mkdir(parents=True, exist_ok=True)

    conf = Config2D(
        n_rays               = cfg_overrides.get("n_rays",                32),
        grid                 = tuple(cfg_overrides.get("grid",            [2, 2])),
        train_patch_size     = tuple(cfg_overrides.get("train_patch_size",[256, 256])),
        train_batch_size     = cfg_overrides.get("train_batch_size",      4),
        train_epochs         = cfg_overrides.get("train_epochs",          100),
        train_steps_per_epoch= cfg_overrides.get("train_steps_per_epoch", 100),
    )

    mlflow_run = None
    try:
        mlflow.set_tracking_uri(MLFLOW_URI)
        mlflow.set_experiment(EXPERIMENT)
        mlflow_run = mlflow.start_run(run_name="stardist_finetuned")
        mlflow.set_tag("eval_set",  "bbbc039_train_val_only")
        mlflow.set_tag("eval_type", "TRAINING_VALIDATION_ONLY")
        mlflow.log_params({
            "n_rays":                conf.n_rays,
            "grid":                  str(conf.grid),
            "train_patch_size":      str(conf.train_patch_size),
            "train_batch_size":      conf.train_batch_size,
            "train_epochs":          conf.train_epochs,
            "train_steps_per_epoch": conf.train_steps_per_epoch,
        })
    except Exception as e:
        print(f"  WARNING: MLflow server offline ({e}). Proceeding with local training.")

    model = StarDist2D(conf, name="stardist_finetuned", basedir=str(MODELS_DIR))
    model.train(X_train, Y_train, validation_data=(X_val, Y_val))
    model.optimize_thresholds(X_val, Y_val)  # threshold tuning on val only

    # Evaluate on VALIDATION split — for model selection, NOT final reporting
    print("\n  Evaluating on validation split ...")
    val_preds, latencies = [], []
    tracemalloc.start()
    for img in X_val:
        t0 = time.perf_counter()
        labels, _ = model.predict_instances(img)
        latencies.append((time.perf_counter() - t0) * 1000)
        val_preds.append(labels)
    _, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    ap_m  = average_precision(val_preds, Y_val)
    cnt_m = count_metrics(val_preds, Y_val)
    per_img = [compute_instance_metrics(p, g) for p, g in zip(val_preds, Y_val)]
    f1s   = [m["f1"]               for m in per_img]
    mious = [m["mean_matched_iou"] for m in per_img]

    val_metrics = {
        **ap_m, **cnt_m,
        "val_instance_F1":       round(float(np.mean(f1s)),    4),
        "val_mean_matched_iou":  round(float(np.mean(mious)),  4),
        "val_latency_ms_median": round(float(np.median(latencies)), 1),
        "val_peak_ram_mb":       round(peak_mem / 1_048_576, 1),
        "model": "stardist_finetuned",
        "eval_set": "bbbc039_official_val",
    }

    with open(METRICS_DIR / "finetuned_stardist.json", "w") as f:
        json.dump(val_metrics, f, indent=2)

    try:
        if mlflow_run:
            for k, v in val_metrics.items():
                if isinstance(v, (int, float)):
                    mlflow.log_metric(k, v)
            mlflow.tensorflow.log_model(model.keras_model, "stardist_model",
                                        registered_model_name="CellScope-StarDist")
            mlflow.end_run()
    except Exception as e:
        print(f"  WARNING: Failed to log metrics to MLflow ({e})")

    print(f"\n  Val AP50={val_metrics['val_AP50']:.3f}  "
          f"F1={val_metrics.get('val_instance_F1', 0):.3f}  "
          f"count_rel_err={val_metrics['val_count_rel_error']:.3f}")
    if mlflow_run:
        print(f"  MLflow run ID: {mlflow_run.info.run_id}")

    print("\n  Fine-tuning complete.")
    print("  Run next: python mlops/gate.py  (to select champion)")
    print("  Then:     python mlops/final_eval.py  (ONE-TIME test evaluation)")


if __name__ == "__main__":
    main()
