"""Tests for colour science module — using APK-exact CIE tables."""

import pytest

from spectro.color import (
    XYZ,
    Illuminant,
    Lab,
    Observer,
    SpectralCurve,
    srgb_to_hex,
    white_point,
    xyz_to_srgb,
)


class TestWhitePoint:
    def test_d50_2deg(self) -> None:
        wp = white_point(Illuminant.D50, Observer.TWO_DEGREE)
        assert wp == pytest.approx((96.42, 100.0, 82.49), rel=1e-3)

    def test_d65_2deg(self) -> None:
        wp = white_point(Illuminant.D65, Observer.TWO_DEGREE)
        assert wp == pytest.approx((95.047, 100.0, 108.883), rel=1e-3)

    def test_d65_10deg(self) -> None:
        wp = white_point(Illuminant.D65, Observer.TEN_DEGREE)
        assert wp == pytest.approx((94.811, 100.0, 107.304), rel=1e-3)


class TestXYZ:
    def test_to_lab_d50(self) -> None:
        xyz = XYZ(X=50.0, Y=50.0, Z=50.0)
        lab = xyz.to_lab(Illuminant.D50, Observer.TWO_DEGREE)
        assert lab.L > 0

    def test_to_lab_d65_white_is_neutral(self) -> None:
        """D65 white point should produce near-zero a*, b*."""
        xyz = XYZ(X=95.047, Y=100.0, Z=108.883)
        lab = xyz.to_lab(Illuminant.D65, Observer.TWO_DEGREE)
        assert pytest.approx(100.0, abs=0.1) == lab.L
        assert abs(lab.a) < 1.0
        assert abs(lab.b) < 1.0

    def test_chromatic_adaptation(self) -> None:
        xyz = XYZ(X=96.42, Y=100.0, Z=82.49)
        adapted = xyz.to_xyz(Illuminant.D65)
        assert adapted.X > 0 and adapted.Y > 0


class TestLab:
    def test_roundtrip(self) -> None:
        original = Lab(L=50, a=10, b=-20)
        xyz = original.to_xyz()
        back = xyz.to_lab()
        assert pytest.approx(original.L, abs=0.1) == back.L
        assert back.a == pytest.approx(original.a, abs=0.1)
        assert back.b == pytest.approx(original.b, abs=0.1)

    def test_delta_e76(self) -> None:
        assert Lab(50, 0, 0).delta_e_76(Lab(50, 0, 0)) == 0.0
        assert Lab(50, 0, 0).delta_e_76(Lab(60, 0, 0)) > 0

    def test_delta_e00_identity(self) -> None:
        assert Lab(50, 0, 0).delta_e_00(Lab(50, 0, 0)) == 0.0

    def test_delta_e00_known(self) -> None:
        d = Lab(50, 0, 0).delta_e_00(Lab(52, 5, 5))
        assert 3 < d < 10


class TestSpectralCurve:
    def test_create_31_values(self) -> None:
        """Spectro delivers 32 values; SpectralCurve uses first 31 (400-700nm)."""
        curve = SpectralCurve([0.5] * 32)
        assert len(curve.reflectance) == 31

    def test_white_spectrum_gives_white_xyz(self) -> None:
        """Perfect reflector (1.0 at all wavelengths) → D65 white point."""
        curve = SpectralCurve([1.0] * 32, illuminant=Illuminant.D65, observer=Observer.TEN_DEGREE)
        xyz = curve.to_xyz()
        assert pytest.approx(100.0, rel=0.05) == xyz.Y

    def test_black_spectrum(self) -> None:
        curve = SpectralCurve([0.0] * 32)
        xyz = curve.to_xyz()
        assert xyz.Y < 1.0

    def test_mid_grey_to_lab(self) -> None:
        curve = SpectralCurve([0.5] * 32)
        lab = curve.to_lab()
        assert 30 < lab.L < 80

    def test_d50_illuminant(self) -> None:
        curve = SpectralCurve([1.0] * 32, illuminant=Illuminant.D50, observer=Observer.TWO_DEGREE)
        xyz = curve.to_xyz()
        assert pytest.approx(100.0, rel=0.05) == xyz.Y


class TestXYZtoSRGB:
    def test_white(self) -> None:
        r, g, b = xyz_to_srgb(95.047, 100.0, 108.883)
        assert r == pytest.approx(255, abs=3)
        assert g == pytest.approx(255, abs=3)
        assert b == pytest.approx(255, abs=3)

    def test_black(self) -> None:
        assert xyz_to_srgb(0, 0, 0) == (0, 0, 0)

    def test_hex(self) -> None:
        assert srgb_to_hex(255, 0, 0) == "#ff0000"
        assert srgb_to_hex(0, 0, 0) == "#000000"
        assert srgb_to_hex(300, -10, 300) == "#ff00ff"  # clamping
