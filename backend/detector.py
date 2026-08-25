"""
backend/detector.py
-------------------
Model inference layer — selects native TF or ONNX Runtime
based on metrics/onnx_equivalence.json.

Singleton pattern: model is loaded once at startup.
Async-safe: inference runs in a thread pool via anyio.
"""

from __future__ import annotations

import base64
import io
import json
import pathlib
import time
import tracemalloc
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

from csbdeep.utils import normalize

MODELS_DIR  = pathlib.Path("backend/models")
ENGINE_FILE = MODELS_DIR / "inference_engine.txt"
CHAMPION_FILE = MODELS_DIR / "champion.json"


def _read_engine() -> str:
    """Read production engine decision from benchmark results."""
    if ENGINE_FILE.exists():
        return ENGINE_FILE.read_text().strip()
    return "native_tf"  # safe default before benchmarking


def _load_champion_info() -> dict:
    if CHAMPION_FILE.exists():
        with open(CHAMPION_FILE) as f:
            return json.load(f)
    return {"model": "stardist_2D_versatile_fluo", "fine_tuned": False, "source": "pretrained"}


class StarDistDetector:
    """Singleton inference wrapper — native TF or ONNX."""

    _instance: "StarDistDetector | None" = None

    def __new__(cls) -> "StarDistDetector":
        if cls._instance is None:
            obj = super().__new__(cls)
            obj._initialized = False
            cls._instance = obj
        return cls._instance

    def _initialize(self) -> None:
        if self._initialized:
            return
        self.engine   = _read_engine()
        self.champion = _load_champion_info()

        if self.engine == "onnx":
            self._load_onnx()
        else:
            self._load_native()

        self._initialized = True
        print(f"[Detector] Loaded {self.champion['model']} via {self.engine}")

    def _load_native(self) -> None:
        from stardist.models import StarDist2D
        if self.champion.get("fine_tuned"):
            self._model = StarDist2D(
                None, name="stardist_finetuned", basedir=str(MODELS_DIR)
            )
        else:
            local_path = MODELS_DIR / "pretrained_versatile_fluo"
            if local_path.exists():
                self._model = StarDist2D(
                    None, name="pretrained_versatile_fluo", basedir=str(MODELS_DIR)
                )
            else:
                self._model = StarDist2D.from_pretrained("2D_versatile_fluo")
        self._onnx_session = None

    def switch_model(self, model_key: str) -> dict[str, Any]:
        """Dynamically switch active model weights."""
        from stardist.models import StarDist2D
        if model_key == "stardist_finetuned":
            self.champion = {
                "model": "stardist_2D_finetuned",
                "fine_tuned": True,
                "source": "fine_tuned_bbbc039",
            }
            self._model = StarDist2D(None, name="stardist_finetuned", basedir=str(MODELS_DIR))
        elif model_key == "stardist_pretrained":
            self.champion = {
                "model": "stardist_2D_versatile_fluo",
                "fine_tuned": False,
                "source": "pretrained",
            }
            local_path = MODELS_DIR / "pretrained_versatile_fluo"
            if local_path.exists():
                self._model = StarDist2D(None, name="pretrained_versatile_fluo", basedir=str(MODELS_DIR))
            else:
                self._model = StarDist2D.from_pretrained("2D_versatile_fluo")
        else:
            raise ValueError(f"Unknown model key: {model_key}")
        
        self.engine = "native_tf"
        return self.champion

    def _load_onnx(self) -> None:
        import onnxruntime as ort
        from stardist.models import StarDist2D

        onnx_path = MODELS_DIR / "stardist_champion.onnx"
        self._onnx_session = ort.InferenceSession(
            str(onnx_path), providers=["CPUExecutionProvider"]
        )
        # StarDist still needed for NMS post-processing
        if self.champion.get("fine_tuned"):
            self._model = StarDist2D(
                None, name="stardist_finetuned", basedir=str(MODELS_DIR)
            )
        else:
            local_path = MODELS_DIR / "pretrained_versatile_fluo"
            if local_path.exists():
                self._model = StarDist2D(
                    None, name="pretrained_versatile_fluo", basedir=str(MODELS_DIR)
                )
            else:
                self._model = StarDist2D.from_pretrained("2D_versatile_fluo")

    @property
    def model_version(self) -> str:
        return f"CellScope-StarDist-{self.champion['model']}@champion"

    def segment(
        self,
        img_normalized: np.ndarray,
        img_raw: np.ndarray,
    ) -> dict[str, Any]:
        """
        Run segmentation. Returns masks + per-instance intensity.
        img_normalized: float32 2D, percentile-normalized
        img_raw:        float32 2D, original pixel values (for intensity measurement)
        """
        self._initialize()

        t0 = time.perf_counter()

        if self.engine == "onnx" and self._onnx_session is not None:
            labels = self._run_onnx(img_normalized)
        else:
            labels, _ = self._model.predict_instances(img_normalized)

        elapsed_ms = (time.perf_counter() - t0) * 1000

        # Per-instance mean intensity using raw pixel values
        instance_intensities: dict[int, float] = {}
        for cell_id in np.unique(labels):
            if cell_id == 0:
                continue
            mask = labels == cell_id
            instance_intensities[int(cell_id)] = round(float(img_raw[mask].mean()), 2)

        return {
            "labels":               labels.astype(np.uint16),
            "inference_time_ms":    round(elapsed_ms, 1),
            "inference_engine":     self.engine,
            "model_version":        self.model_version,
            "instance_intensities": instance_intensities,
        }

    def _run_onnx(self, img: np.ndarray) -> np.ndarray:
        input_name = self._onnx_session.get_inputs()[0].name
        img_in     = img[np.newaxis, ..., np.newaxis].astype(np.float32)
        output     = self._onnx_session.run(None, {input_name: img_in})
        prob = output[0][0, ..., 0]
        dist = output[1][0]
        labels, _ = self._model._predict_instances_generator(
            prob=prob, dist=dist,
            nms_thresh=self._model.thresholds.nms,
            prob_thresh=self._model.thresholds.prob,
        )
        return labels


# ---------------------------------------------------------------------------
# Overlay rendering — used by the API endpoint
# ---------------------------------------------------------------------------

_PALETTE = [
    (0x4e, 0xd7, 0x6a),  # GFP green
    (0x38, 0xbd, 0xf8),  # sky blue
    (0xf5, 0x9e, 0x0b),  # amber
    (0xe8, 0x79, 0xa8),  # pink
    (0xa7, 0x8b, 0xfa),  # violet
    (0xf8, 0x71, 0x71),  # coral
    (0x34, 0xd3, 0x99),  # emerald
    (0xfb, 0xd3, 0x8d),  # peach
]


def render_overlay(
    img_raw: np.ndarray,
    labels: np.ndarray,
    alpha: float = 0.45,
) -> str:
    img_display = img_raw - img_raw.min()
    max_val = img_display.max()
    if max_val > 0:
        img_display = (img_display / max_val * 255).astype(np.uint8)
    else:
        img_display = img_display.astype(np.uint8)

    h, w  = img_display.shape
    base  = Image.fromarray(img_display, mode="L").convert("RGBA")
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))

    instance_ids = np.unique(labels)
    instance_ids = instance_ids[instance_ids != 0]

    for idx, cell_id in enumerate(instance_ids):
        color = _PALETTE[idx % len(_PALETTE)]
        mask  = (labels == cell_id).astype(np.uint8) * int(alpha * 255)
        layer = Image.new("RGBA", (w, h), color + (0,))
        mask_img = Image.fromarray(mask, mode="L")
        layer.putalpha(mask_img)
        overlay = Image.alpha_composite(overlay, layer)

    composite = Image.alpha_composite(base, overlay)

    buf = io.BytesIO()
    composite.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def render_mask_image(labels: np.ndarray) -> str:
    h, w   = labels.shape
    canvas = Image.new("RGB", (w, h), (0, 0, 0))
    pixels = np.array(canvas)

    instance_ids = np.unique(labels)
    instance_ids = instance_ids[instance_ids != 0]

    for idx, cell_id in enumerate(instance_ids):
        color = _PALETTE[idx % len(_PALETTE)]
        mask  = labels == cell_id
        pixels[mask] = color

    img = Image.fromarray(pixels.astype(np.uint8))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")
