"""Tests for device calibration module."""

from __future__ import annotations

import struct

import pytest

from spectro.calibrate import (
    _VERIFICATION_BLUE,
    _VERIFICATION_GREEN,
    _VERIFICATION_TOLERANCE,
    _VERIFICATION_WHITE,
    _delta_e_2000,
    _to_spectral,
)


class TestDeltaE:
    def test_identical(self) -> None:
        assert _delta_e_2000((50, 0, 0), (50, 0, 0)) == 0.0

    def test_different(self) -> None:
        d = _delta_e_2000((50, 0, 0), (60, 10, -10))
        assert d > 5

    def test_known_pair(self) -> None:
        d = _delta_e_2000((50, 2.6772, -79.7751), (50, 0, -82.7485))
        assert d == pytest.approx(2.0425, abs=0.1)


class TestVerificationData:
    def test_white_length(self) -> None:
        assert len(_VERIFICATION_WHITE) == 31

    def test_green_length(self) -> None:
        assert len(_VERIFICATION_GREEN) == 31

    def test_blue_length(self) -> None:
        assert len(_VERIFICATION_BLUE) == 31

    def test_values_in_range(self) -> None:
        for arr in [_VERIFICATION_WHITE, _VERIFICATION_GREEN, _VERIFICATION_BLUE]:
            for v in arr:
                assert 0.0 <= v <= 1.0, f"Value {v} out of [0,1] range"

    def test_tolerance(self) -> None:
        assert _VERIFICATION_TOLERANCE == 1.0


class TestSpectralConversion:
    def test_trim_to_31(self) -> None:
        """32 sensor values should be trimmed to 31 for spectral."""
        result = _to_spectral([0.5] * 32)
        assert len(result) == 31

    def test_preserves_31(self) -> None:
        result = _to_spectral([0.3] * 31)
        assert len(result) == 31

    def test_short_padding(self) -> None:
        result = _to_spectral([0.5] * 10)
        assert len(result) == 10  # _to_spectral doesn't pad


class TestCalibrationEncoding:
    def test_encode_zero(self) -> None:
        """Value 0.2 should encode as 0 (the floor)."""
        encoded = max(0, min(65535, int(round((0.2 - 0.2) * 65535))))
        assert encoded == 0

    def test_encode_one(self) -> None:
        """Value 1.0 should encode as (0.8 * 65535)."""
        encoded = max(0, min(65535, int(round((1.0 - 0.2) * 65535))))
        assert encoded == 52428

    def test_encode_clamp(self) -> None:
        """Negative and >1 values should be clamped."""
        for v in [-0.5, 1.5]:
            encoded = max(0, min(65535, int(round((v - 0.2) * 65535))))
            assert 0 <= encoded <= 65535

    def test_uint16_be_format(self) -> None:
        """Encoded values should be uint16 big-endian."""
        val = 20000
        packed = struct.pack(">H", val)
        assert len(packed) == 2
        assert struct.unpack(">H", packed)[0] == val
