# 🧪 Guide 3: Machine Learning Training, Benchmarking & Accuracy Metrics

This guide explains **how CellScope's AI model was trained**, **how accuracy is mathematically measured**, and **why our fine-tuned StarDist 2D champion outperformed alternative models**.

---

## 📦 1. The Dataset: Broad Institute BBBC039v1

CellScope was trained and validated on the official **Broad Institute BBBC039v1 dataset**:
- **Description**: 200 high-resolution fluorescence microscopy images ($520 \times 696$ pixels) of U2OS cell nuclei stained with Hoechst 33342.
- **Annotations**: 24,000+ hand-annotated individual nucleus polygon masks verified by expert cell biologists.
- **License**: Creative Commons CC0 (Public Domain).

---

## 🔒 2. Data Split & Scientific Leakage Protection

To prevent **data leakage** (a fatal flaw where a model accidentally memorizes test images during training), we instituted a strict 3-way split:

```
                  ┌────────────────────────────────────────┐
                  │        BBBC039 DATASET (200 IMAGES)    │
                  └───────────────────┬────────────────────┘
                                      │
          ┌───────────────────────────┼───────────────────────────┐
          ▼                           ▼                           ▼
┌───────────────────┐       ┌───────────────────┐       ┌───────────────────┐
│   TRAINING SET    │       │  VALIDATION SET   │       │   HELD-OUT TEST   │
│   (100 Images)    │       │    (50 Images)    │       │    (50 Images)    │
│  Used for gradient│       │  Used for hyper-  │       │  LOCKED UNTIL     │
│  backpropagation  │       │  parameter tuning │       │  FINAL EVALUATION │
└───────────────────┘       └───────────────────┘       └───────────────────┘
```

- **Training Set (100 images)**: Used exclusively for updating model weights during epoch backpropagation.
- **Validation Set (50 images)**: Used during fine-tuning to monitor validation loss and trigger early stopping.
- **Held-Out Test Set (50 images)**: Strictly locked and evaluated **EXACTLY ONCE** in `mlops/final_eval.py` after champion model selection.

---

## 🏋️ 3. StarDist 2D Fine-Tuning Workflow (`mlops/train.py`)

### Model Architecture
StarDist 2D replaces conventional pixel classification with **Star-Convex Polygon Regression**:
1. **Object Probabilities $P(x,y)$**: Predicts whether pixel $(x,y)$ is near a cell center.
2. **Radial Distances $R_k(x,y)$**: Predicts distances along $N=32$ radial rays extending from the center to the cell boundary.

### Training Hyperparameters
- **Base Architecture**: U-Net backbone with depth 3 and 32 initial feature channels.
- **Epochs**: 100 epochs with Keras `Adam` optimizer.
- **Learning Rate**: Initial $lr = 0.0003$ with cosine decay.
- **Patch Size**: $256 \times 256$ random crops with flip/rotate data augmentation.
- **Loss Function**: Binary Cross-Entropy (for object probability) + Mean Absolute Error (for ray distances).

---

## 📐 4. How We Measure Accuracy: Mathematical Definitions

Evaluating instance segmentation requires measuring both **bounding localization accuracy** and **instance count precision**.

### A. Intersection over Union (IoU)
For a predicted nucleus mask $A$ and ground-truth mask $B$:

$$\text{IoU}(A, B) = \frac{|A \cap B|}{|A \cup B|} = \frac{\text{Overlap Pixels}}{\text{Total Combined Pixels}}$$

- $\text{IoU} = 1.0$: Perfect match.
- $\text{IoU} \ge 0.50$: True Positive detection ($TP$).
- $\text{IoU} < 0.50$: False Positive ($FP$) or False Negative ($FN$).

---

### B. Average Precision @ IoU Threshold 0.50 ($AP_{50}$)

$$AP_{50} = \frac{TP}{TP + FP + FN}$$

- Measures how accurately the model identifies individual cell instances at a $50\%$ spatial overlap threshold.

---

### C. Instance F1 Score

$$\text{Precision} = \frac{TP}{TP + FP}, \quad \text{Recall} = \frac{TP}{TP + FN}$$

$$\text{F1 Score} = 2 \times \frac{\text{Precision} \times \text{Recall}}{\text{Precision} + \text{Recall}}$$

---

### D. Relative Count Error & Count MAE

$$\text{Count Relative Error} = \frac{|\text{Predicted Count} - \text{True Count}|}{\text{True Count}}$$

$$\text{Count MAE} = \frac{1}{N} \sum_{i=1}^{N} |\text{Predicted Count}_i - \text{True Count}_i|$$

---

## ⚡ 5. Vectorized IoU Acceleration (`mlops/benchmark.py`)

Evaluating IoU on 50 images with 200+ nuclei per image requires computing $\sim 10,000$ mask overlaps per image.

### The Optimization:
- **Naive Python Nested Loop**: Taking 45 minutes to benchmark 50 images.
- **Vectorized `np.bincount` Histogram Optimization**:
  By computing a joint histogram `np.bincount(pred_label * (max_gt + 1) + gt_label)` in $O(H \times W)$ time, we accelerated IoU evaluation from 45 minutes to **52 ms / image** ($50\times$ speedup)!

---

## 🏆 6. Official Benchmark Results

Below are the official benchmark results across all evaluated candidate models on the held-out BBBC039 test set:

| Model Architecture | Test $AP_{50}$ | Test $AP_{75}$ | Instance F1 | Count Rel. Error | Latency / Image | Status |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **StarDist 2D Fine-Tuned** | 🌟 **0.9317** | **0.8760** | **0.9397** | 🌟 **3.34%** | **1,580 ms** | 🏆 **CHAMPION** |
| **StarDist 2D Pretrained** | 0.8356 | 0.7412 | 0.8329 | 10.40% | 2,300 ms | Baseline |
| **CellPose 3.x cyto2** | 0.8329 | 0.7290 | 0.8278 | 8.80% | 51,000 ms | Baseline |

### Key Takeaways:
1. **Fine-tuning Boost**: Fine-tuning StarDist on 100 BBBC039 images boosted $AP_{50}$ from **0.8356 to 0.9317** (+9.6% absolute gain) and reduced count relative error from **10.4% down to 3.34%**.
2. **Speed Advantage**: StarDist 2D runs in **1.58 seconds** on standard CPU vs **51 seconds** for CellPose 3.x ($32\times$ faster).
