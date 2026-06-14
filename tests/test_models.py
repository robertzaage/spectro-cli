"""Tests for the ML model pipeline (pure NumPy inference)."""

import numpy as np
import pytest

from spectro.models import NumpyModel, _DenseLayer, _relu, _tanh


class TestNumpyModel:
    def test_dense_forward(self) -> None:
        w = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32)
        b = np.array([0.5, -0.5], dtype=np.float32)
        layer = _DenseLayer(w, b)
        x = np.array([[1.0, 1.0]], dtype=np.float32)
        y = layer.forward(x)
        assert y.shape == (1, 2)
        assert y[0, 0] == pytest.approx(3.5)  # 1*1 + 1*2 + 0.5
        assert y[0, 1] == pytest.approx(6.5)  # 1*3 + 1*4 - 0.5

    def test_tanh(self) -> None:
        x = np.array([[0.0, 1.0, -1.0]], dtype=np.float32)
        y = _tanh(x)
        assert y[0, 0] == pytest.approx(0.0)
        assert y[0, 1] > 0.7
        assert y[0, 2] < -0.7

    def test_relu(self) -> None:
        x = np.array([[-1.0, 0.0, 1.0]], dtype=np.float32)
        y = _relu(x)
        assert y[0, 0] == 0.0
        assert y[0, 1] == 0.0
        assert y[0, 2] == 1.0

    def test_simple_network(self) -> None:
        w1 = np.ones((4, 2), dtype=np.float32) * 0.1
        b1 = np.zeros(4, dtype=np.float32)
        w2 = np.ones((1, 4), dtype=np.float32) * 0.1
        b2 = np.zeros(1, dtype=np.float32)

        model = NumpyModel(
            [
                ("dense", _DenseLayer(w1, b1)),
                ("relu", None),
                ("dense", _DenseLayer(w2, b2)),
            ]
        )

        x = np.array([[1.0, 1.0]], dtype=np.float32)
        y = model(x)
        assert y.shape == (1, 1)
        assert y[0, 0] > 0


class TestModelVerification:
    """Verify extracted weights match expected sample outputs from info_v2.json."""

    @pytest.fixture(scope="class")
    def weights(self) -> dict[str, dict[str, np.ndarray]]:
        import os

        w = {}
        base = os.path.expanduser("~/.spectro/models")
        if not os.path.isdir(base):
            pytest.skip("No model cache directory")
        for model_dir in sorted(os.listdir(base)):
            full = os.path.join(base, model_dir)
            if not os.path.isdir(full):
                continue
            for name in ["unification", "adjustment_ca", "adjustment"]:
                npz = os.path.join(full, f"{name}_weights.npz")
                if os.path.exists(npz):
                    w[name] = dict(np.load(npz))
            if w:
                break
        if not w:
            pytest.skip("Model weights not available")
        return w

    def test_unification_0_5_input(self, weights: dict) -> None:
        if "unification" not in weights:
            pytest.skip()
        w = weights["unification"]
        # Build and run model
        x = np.full((1, 32), 0.5, dtype=np.float32)
        x = x @ w["layer_0_W"].T + w["layer_0_B"]
        x = np.tanh(x)
        x = x @ w["layer_2_W"].T + w["layer_2_B"]
        x = x @ w["layer_3_W"].T + w["layer_3_B"]
        # Check known first output value from info_v2.json
        assert x[0, 0] == pytest.approx(0.49542, abs=1e-4)

    def test_adjustment_ca_0_5_input(self, weights: dict) -> None:
        if "adjustment_ca" not in weights:
            pytest.skip()
        w = weights["adjustment_ca"]
        x = np.full((1, 32), 0.5, dtype=np.float32)
        x = x @ w["layer_0_W"].T + w["layer_0_B"]
        x = np.maximum(0, x)
        x = x @ w["layer_2_W"].T + w["layer_2_B"]
        x = x @ w["layer_3_W"].T + w["layer_3_B"]
        assert x[0, 0] == pytest.approx(0.56216, abs=1e-4)

    def test_adjustment_0_5_input(self, weights: dict) -> None:
        if "adjustment" not in weights:
            pytest.skip()
        w = weights["adjustment"]
        x = np.full((1, 31), 0.5, dtype=np.float32)
        x = x @ w["layer_0_W"].T + w["layer_0_B"]
        x = np.maximum(0, x)
        x = x @ w["layer_2_W"].T + w["layer_2_B"]
        x = np.maximum(0, x)
        x = x @ w["layer_4_W"].T + w["layer_4_B"]
        assert x[0, 0] == pytest.approx(0.40265, abs=1e-4)
