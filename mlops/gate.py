"""
mlops/gate.py
-------------
Reads validation metrics from benchmark.py and decides whether
fine-tuning is needed. Invokes 'dvc repro train' explicitly if the
pretrained model fails the acceptance matrix.

DESIGN NOTE:
  DVC cannot evaluate metric thresholds — it only tracks whether
  stage dependencies have changed. The gate logic lives HERE, outside
  the DVC graph. gate.py calls 'dvc repro train' as a subprocess
  only when the pretrained model is insufficient.

Champion model selection uses VALIDATION metrics only.
The BBBC039 test split is never consulted here.
"""

import json
import pathlib
import subprocess
import sys
import shutil

METRICS_DIR  = pathlib.Path("metrics")
PRETRAINED_M = METRICS_DIR / "pretrained_stardist.json"
MODELS_DIR   = pathlib.Path("backend/models")
PRETRAINED_WEIGHTS_CACHE = pathlib.Path("backend/models/pretrained_champion")

# ---------------------------------------------------------------------------
# Acceptance criteria (initial engineering targets — compare to baselines first)
# ---------------------------------------------------------------------------
GATE = {
    "val_AP50":              0.80,   # Average Precision at 50% IoU
    "val_AP75":              0.65,   # Average Precision at 75% IoU
    "val_instance_F1":       0.80,   # F1 at 0.5 IoU threshold
    "val_count_rel_error":   0.10,   # Relative count error (< = better)
    "val_mean_matched_iou":  0.75,   # Mean matched-pair IoU
}

# Metrics where lower is better
LOWER_IS_BETTER = {"val_count_rel_error"}


def load_metrics(path: pathlib.Path) -> dict:
    if not path.exists():
        print(f"[GATE] ERROR: {path} not found. Run benchmark.py first.")
        sys.exit(1)
    with open(path) as f:
        return json.load(f)


def evaluate_gate(metrics: dict) -> tuple[bool, list[str]]:
    """Returns (passes, list_of_failures)."""
    failures = []
    for key, target in GATE.items():
        value = metrics.get(key)
        if value is None:
            failures.append(f"  MISSING metric: {key}")
            continue
        if key in LOWER_IS_BETTER:
            if value > target:
                failures.append(f"  FAIL  {key}: {value:.4f} > {target} (target)")
        else:
            if value < target:
                failures.append(f"  FAIL  {key}: {value:.4f} < {target} (target)")
    return len(failures) == 0, failures


def promote_pretrained_as_champion() -> None:
    """Copy pretrained model weights to backend/models/ as the champion."""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    champion_flag = MODELS_DIR / "champion.json"
    with open(champion_flag, "w") as f:
        json.dump({"model": "stardist_2D_versatile_fluo",
                   "source": "pretrained",
                   "fine_tuned": False}, f, indent=2)
    print("  [GATE] Champion set: pretrained 2D_versatile_fluo")


def invoke_finetuning() -> None:
    """Invoke 'dvc repro train' to start fine-tuning."""
    print("  [GATE] Invoking fine-tuning: dvc repro train")
    result = subprocess.run(["dvc", "repro", "train"], check=False)
    if result.returncode != 0:
        print("  [GATE] ERROR: Fine-tuning failed. Check logs above.")
        sys.exit(result.returncode)
    # After training, compare fine-tuned val metrics vs pretrained
    compare_and_set_champion()


def compare_and_set_champion() -> None:
    """Compare pretrained vs fine-tuned (validation metrics). Set champion."""
    finetuned_m_path = METRICS_DIR / "finetuned_stardist.json"
    if not finetuned_m_path.exists():
        print("  [GATE] Fine-tuned metrics not found; using fine-tuned as champion by default.")
        with open(MODELS_DIR / "champion.json", "w") as f:
            json.dump({"model": "stardist_finetuned",
                       "source": "finetuned",
                       "fine_tuned": True}, f, indent=2)
        return

    pretrained = load_metrics(PRETRAINED_M)
    finetuned  = load_metrics(finetuned_m_path)

    # Simple comparison: use mean_AP as the tiebreaker
    if finetuned.get("val_mean_AP", 0) >= pretrained.get("val_mean_AP", 0):
        champion = "finetuned"
        print(f"  [GATE] Fine-tuned outperforms pretrained on val_mean_AP "
              f"({finetuned['val_mean_AP']:.3f} vs {pretrained['val_mean_AP']:.3f})")
    else:
        champion = "pretrained"
        print(f"  [GATE] Pretrained still outperforms fine-tuned on val_mean_AP "
              f"({pretrained['val_mean_AP']:.3f} vs {finetuned['val_mean_AP']:.3f})")

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    with open(MODELS_DIR / "champion.json", "w") as f:
        json.dump({"model": f"stardist_{champion}",
                   "source": champion,
                   "fine_tuned": champion == "finetuned"}, f, indent=2)
    print(f"  [GATE] Champion set: {champion}")


def main() -> None:
    print("=" * 60)
    print("CellScope — Benchmark Gate")
    print("Evaluating pretrained StarDist acceptance matrix")
    print("Using VALIDATION metrics only (test split untouched)")
    print("=" * 60)

    pretrained_metrics = load_metrics(PRETRAINED_M)
    passes, failures   = evaluate_gate(pretrained_metrics)

    print("\n  Pretrained model gate results:")
    for key, target in GATE.items():
        val = pretrained_metrics.get(key, "N/A")
        status = "PASS" if key not in [f.split()[1] for f in failures] else "FAIL"
        direction = "<" if key in LOWER_IS_BETTER else ">"
        print(f"    {status}  {key}: {val}  (target {direction} {target})")

    if passes:
        print("\n  [GATE] Pretrained model passes all acceptance criteria.")
        print("  [GATE] Fine-tuning is NOT required.")
        promote_pretrained_as_champion()
    else:
        print(f"\n  [GATE] Pretrained model FAILS {len(failures)} criteria:")
        for f in failures:
            print(f)
        print("\n  [GATE] Fine-tuning IS required.")
        invoke_finetuning()

    print("\n  Gate evaluation complete.")
    print("  Run next: python mlops/final_eval.py")


if __name__ == "__main__":
    main()
