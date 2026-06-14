"""TFLite/CoreML neural network inference for Spectro colour correction.

Models are downloaded from the public S3 bucket:
    https://gdn.colourcloud.net/s3/colorcloud.io/spectro_one/model_packages_v2/zips/ios/{serial}.zip

The pipeline matches the Android app exactly: raw sensor values →
correction factors → unification → adjustment_ca → adjustment → spectral curve.

Models are automatically downloaded and cached to ~/.spectro/models/ on first use.
"""

from __future__ import annotations

import json
import logging
import zipfile
from pathlib import Path
from typing import Any

import numpy as np

from ..config import CONFIG

logger = logging.getLogger(__name__)

_S3_BASE = "https://gdn.colourcloud.net/s3/colorcloud.io/spectro_one/model_packages_v2/zips/ios"


# =============================================================================
# Pure NumPy neural network inference
# =============================================================================


class _DenseLayer:
    def __init__(self, weights: np.ndarray, bias: np.ndarray) -> None:
        self.W = weights  # [output_dim, input_dim]
        self.b = bias  # [output_dim]

    def forward(self, x: np.ndarray) -> np.ndarray:
        # x: [batch, input_dim] → output: [batch, output_dim]
        return x @ self.W.T + self.b


def _tanh(x: np.ndarray) -> np.ndarray:
    return np.tanh(x)


def _relu(x: np.ndarray) -> np.ndarray:
    return np.maximum(0, x)


class NumpyModel:
    """A simple feed-forward neural network implemented in pure NumPy."""

    def __init__(self, layers: list[tuple[str, Any]]) -> None:
        self.layers: list[tuple[str, Any]] = []
        for layer_type, params in layers:
            self.layers.append((layer_type, params))

    def forward(self, x: np.ndarray) -> np.ndarray:
        for layer_type, params in self.layers:
            if layer_type == "dense":
                x = params.forward(x)
            elif layer_type == "relu":
                x = _relu(x)
            elif layer_type == "tanh":
                x = _tanh(x)
        return x

    def __call__(self, x: np.ndarray) -> np.ndarray:
        return self.forward(x)


# =============================================================================
# Model architectures (matching APK ann_structure)
# =============================================================================


def _build_unification(weights: dict[str, np.ndarray]) -> NumpyModel:
    return NumpyModel(
        [
            ("dense", _DenseLayer(weights["layer_0_W"], weights["layer_0_B"])),
            ("tanh", None),
            ("dense", _DenseLayer(weights["layer_2_W"], weights["layer_2_B"])),
            ("dense", _DenseLayer(weights["layer_3_W"], weights["layer_3_B"])),
        ]
    )


def _build_adjustment_ca(weights: dict[str, np.ndarray]) -> NumpyModel:
    return NumpyModel(
        [
            ("dense", _DenseLayer(weights["layer_0_W"], weights["layer_0_B"])),
            ("relu", None),
            ("dense", _DenseLayer(weights["layer_2_W"], weights["layer_2_B"])),
            ("dense", _DenseLayer(weights["layer_3_W"], weights["layer_3_B"])),
        ]
    )


def _build_adjustment(weights: dict[str, np.ndarray]) -> NumpyModel:
    return NumpyModel(
        [
            ("dense", _DenseLayer(weights["layer_0_W"], weights["layer_0_B"])),
            ("relu", None),
            ("dense", _DenseLayer(weights["layer_2_W"], weights["layer_2_B"])),
            ("relu", None),
            ("dense", _DenseLayer(weights["layer_4_W"], weights["layer_4_B"])),
        ]
    )


# =============================================================================
# Model manager
# =============================================================================


class ModelPipeline:
    """Spectro colour correction neural network pipeline."""

    def __init__(self, serial: str, cache_dir: Path | None = None) -> None:
        self.serial = serial.upper()
        self.cache_dir = cache_dir or CONFIG.data_dir / "models"
        self._unification: NumpyModel | None = None
        self._adjustment_ca: NumpyModel | None = None
        self._adjustment: NumpyModel | None = None
        self._info: dict[str, Any] = {}
        self._param_count: int = 0
        self._last_inference_ms: float = 0.0
        self._ensure_models()

    @property
    def info(self) -> dict[str, Any]:
        return self._info

    @property
    def param_count(self) -> int:
        return self._param_count

    @property
    def last_inference_ms(self) -> float:
        return self._last_inference_ms

    def _ensure_models(self) -> None:
        model_dir = self.cache_dir / self.serial
        if not (model_dir / "info_v2.json").exists():
            self._download(model_dir)
        self._load(model_dir)

    def _download(self, dest: Path) -> None:
        url = f"{_S3_BASE}/{self.serial}.zip"
        _download_model(self.serial, dest, url)

    def _load(self, model_dir: Path) -> None:
        info_path = model_dir / "info_v2.json"
        if not info_path.exists():
            raise FileNotFoundError(f"Model info not found at {info_path}")

        with open(info_path) as f:
            self._info = json.load(f)

        for name in ["unification", "adjustment_ca", "adjustment"]:
            mlmodel = model_dir / f"{name}.mlmodel"
            npy = model_dir / f"{name}_weights.npz"
            if npy.exists():
                weights = dict(np.load(npy))
            elif mlmodel.exists():
                weights = _extract_coreml_weights(mlmodel, name)
                np.savez(npy, **weights)
            else:
                raise FileNotFoundError(f"Model file not found: {mlmodel}")

            builder = {
                "unification": _build_unification,
                "adjustment_ca": _build_adjustment_ca,
                "adjustment": _build_adjustment,
            }[name]
            model = builder(weights)
            setattr(self, f"_{name}", model)

            # Count parameters
            for arr in weights.values():
                self._param_count += arr.size

    def predict(
        self,
        sensor_values: list[float],
    ) -> list[float]:
        """Run the full correction pipeline, return 31 spectral values."""
        import time

        x = np.array([sensor_values], dtype=np.float32)

        assert self._unification is not None
        assert self._adjustment_ca is not None
        assert self._adjustment is not None

        t0 = time.perf_counter()
        x = self._unification(x)
        x = self._adjustment_ca(x)
        x = self._adjustment(x)
        self._last_inference_ms = (time.perf_counter() - t0) * 1000.0

        result = x[0].tolist()
        return [max(0.0, min(1.0, float(v))) for v in result]


def _download_model(serial: str, dest: Path, url: str | None = None) -> int:
    """Download and extract a model package. Returns total bytes written."""
    import httpx

    if url is None:
        url = f"{_S3_BASE}/{serial}.zip"
    dest.mkdir(parents=True, exist_ok=True)
    zip_path = dest / "model.zip"

    logger.info("Downloading model for %s from %s", serial, url)
    with httpx.Client(timeout=httpx.Timeout(120)) as client:
        resp = client.get(url)
        resp.raise_for_status()
        zip_path.write_bytes(resp.content)

    size = zip_path.stat().st_size
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(dest)
    zip_path.unlink()
    logger.info("Model cached at %s (%d bytes)", dest, size)
    return size


def _extract_coreml_weights(mlmodel_path: str, model_name: str) -> dict[str, np.ndarray]:
    """Extract layer weights from a Core ML .mlmodel file."""
    import coremltools as ct

    model = ct.models.MLModel(mlmodel_path)
    spec = model.get_spec()
    nn = spec.neuralNetwork

    weights: dict[str, np.ndarray] = {}
    for i, layer in enumerate(nn.layers):
        if layer.HasField("innerProduct"):
            ip = layer.innerProduct
            w = np.array(ip.weights.floatValue, dtype=np.float32)
            w = w.reshape(ip.outputChannels, ip.inputChannels)
            b = np.zeros(ip.outputChannels, dtype=np.float32)
            if ip.hasBias:
                b = np.array(ip.bias.floatValue, dtype=np.float32)
            weights[f"layer_{i}_W"] = w
            weights[f"layer_{i}_B"] = b

    return weights
