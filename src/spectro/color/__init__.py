"""CIE colour science — exact tables from Variable Spectro Android APK."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum


class Illuminant(Enum):
    D50 = "D50"
    D65 = "D65"
    A = "A"
    F2 = "F2"


class Observer(Enum):
    TWO_DEGREE = "TWO_DEGREE"
    TEN_DEGREE = "TEN_DEGREE"


# ============================================================================
# CIE tables extracted from a.java — EXACTLY matching the Android app
# All SPDs: 340–830 nm, 10 nm step (50 points)
# All CMFs:  340–830 nm, 10 nm step (50 points)
# The Spectro device delivers 32 spectral sense values covering 400–700 nm
# ============================================================================

# CIE 1931 2° observer colour-matching functions (10 nm steps, index 0 = 340 nm)
_CMF2_X = [
    0.0,
    0.0,
    1.299e-4,
    4.149e-4,
    0.001368,
    0.004243,
    0.01431,
    0.04351,
    0.13438,
    0.2839,
    0.34828,
    0.3362,
    0.2908,
    0.19536,
    0.09564,
    0.03201,
    0.0049,
    0.0093,
    0.06327,
    0.1655,
    0.2904,
    0.4334499,
    0.5945,
    0.7621,
    0.9163,
    1.0263,
    1.0622,
    1.0026,
    0.8544499,
    0.6424,
    0.4479,
    0.2835,
    0.1649,
    0.0874,
    0.04677,
    0.0227,
    0.01135916,
    0.005790346,
    0.002899327,
    0.001439971,
    6.900786e-4,
    3.323011e-4,
    1.661505e-4,
    8.307527e-5,
    4.150994e-5,
    2.067383e-5,
    1.025398e-5,
    5.085868e-6,
    2.522525e-6,
    1.251141e-6,
]

_CMF2_Y = [
    0.0,
    0.0,
    3.917e-6,
    1.239e-5,
    3.9e-5,
    1.2e-4,
    3.96e-4,
    0.00121,
    0.004,
    0.0116,
    0.023,
    0.038,
    0.06,
    0.09098,
    0.13902,
    0.20802,
    0.323,
    0.503,
    0.71,
    0.862,
    0.954,
    0.9949501,
    0.995,
    0.952,
    0.87,
    0.757,
    0.631,
    0.503,
    0.381,
    0.265,
    0.175,
    0.107,
    0.061,
    0.032,
    0.017,
    0.00821,
    0.004102,
    0.002091,
    0.001047,
    5.2e-4,
    2.492e-4,
    1.2e-4,
    6.0e-5,
    3.0e-5,
    1.499e-5,
    7.4657e-6,
    3.7029e-6,
    1.8366e-6,
    9.1093e-7,
    4.5181e-7,
]

_CMF2_Z = [
    0.0,
    0.0,
    6.061e-4,
    0.001946,
    0.006450001,
    0.02005001,
    0.06785001,
    0.2074,
    0.6456,
    1.3856,
    1.74706,
    1.77211,
    1.6692,
    1.28764,
    0.8129501,
    0.46518,
    0.272,
    0.1582,
    0.07824999,
    0.04216,
    0.0203,
    0.008749999,
    0.0039,
    0.0021,
    0.001650001,
    0.0011,
    8.0e-4,
    3.4e-4,
    1.9e-4,
    4.999999e-5,
    2.0e-5,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
]

# CIE 1964 10° observer colour-matching functions (10 nm steps)
_CMF10_X = [
    0.0,
    0.0,
    1.222e-7,
    5.9586e-6,
    1.59952e-4,
    0.0023616,
    0.0191097,
    0.084736,
    0.204492,
    0.314679,
    0.383734,
    0.370702,
    0.302273,
    0.195618,
    0.080507,
    0.016172,
    0.003816,
    0.037465,
    0.117749,
    0.236491,
    0.376772,
    0.529826,
    0.705224,
    0.878655,
    1.01416,
    1.11852,
    1.12399,
    1.03048,
    0.856297,
    0.647467,
    0.431567,
    0.268329,
    0.152568,
    0.0812606,
    0.0408508,
    0.0199413,
    0.00957688,
    0.00455263,
    0.00217496,
    0.00104476,
    5.08258e-4,
    2.50969e-4,
    1.2639e-4,
    6.45258e-5,
    3.34117e-5,
    1.76115e-5,
    9.41363e-6,
    5.09347e-6,
    2.79531e-6,
    1.55314e-6,
]

_CMF10_Y = [
    0.0,
    0.0,
    1.3398e-8,
    6.511e-7,
    1.7364e-5,
    2.534e-4,
    0.0020044,
    0.008756,
    0.021391,
    0.038676,
    0.062077,
    0.089456,
    0.128201,
    0.18519,
    0.253589,
    0.339133,
    0.460777,
    0.606741,
    0.761757,
    0.875211,
    0.961988,
    0.991761,
    0.99734,
    0.955552,
    0.868934,
    0.777405,
    0.658341,
    0.527963,
    0.398057,
    0.283493,
    0.179828,
    0.107633,
    0.060281,
    0.0318004,
    0.0159051,
    0.0077488,
    0.00371774,
    0.00176847,
    8.4619e-4,
    4.0741e-4,
    1.9873e-4,
    9.8428e-5,
    4.9737e-5,
    2.5486e-5,
    1.3249e-5,
    7.0128e-6,
    3.76473e-6,
    2.04613e-6,
    1.12809e-6,
    6.297e-7,
]

_CMF10_Z = [
    0.0,
    0.0,
    5.35027e-7,
    2.61437e-5,
    7.04776e-4,
    0.0104822,
    0.0860109,
    0.389366,
    0.972542,
    1.55348,
    1.96728,
    1.9948,
    1.74537,
    1.31756,
    0.772125,
    0.415254,
    0.218502,
    0.112044,
    0.060709,
    0.030451,
    0.013676,
    0.003988,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
]

# Illuminant SPDs (340–830 nm, 10 nm step)
_SPD_D50 = [
    17.948,
    21.01,
    23.942,
    26.961,
    24.488,
    29.871,
    49.308,
    56.513,
    60.034,
    57.818,
    74.825,
    87.247,
    90.612,
    91.368,
    95.109,
    91.963,
    95.724,
    96.613,
    97.129,
    102.099,
    100.755,
    102.317,
    100.0,
    97.735,
    98.918,
    93.499,
    97.688,
    99.269,
    99.042,
    95.722,
    98.857,
    95.667,
    98.19,
    103.003,
    99.133,
    87.381,
    91.604,
    92.889,
    76.854,
    86.511,
    92.58,
    78.23,
    57.692,
    82.923,
    78.274,
    79.59,
    73.44,
    63.95,
    70.81,
    74.48,
]

_SPD_D65 = [
    39.9488,
    44.9117,
    46.6383,
    52.0891,
    49.9755,
    54.6482,
    82.7549,
    91.486,
    93.4318,
    86.6823,
    104.865,
    117.008,
    117.812,
    114.861,
    115.923,
    108.811,
    109.354,
    107.802,
    104.79,
    107.689,
    104.405,
    104.046,
    100.0,
    96.3342,
    95.788,
    88.6856,
    90.0062,
    89.5991,
    87.6987,
    83.2886,
    83.6992,
    80.0268,
    80.2146,
    82.2778,
    78.2842,
    69.7213,
    71.6091,
    74.349,
    61.604,
    69.8856,
    75.087,
    63.5927,
    46.4182,
    66.8054,
    63.3828,
    64.304,
    59.4519,
    51.959,
    57.4406,
    60.3125,
]

_SPD_A = [
    3.58968,
    4.74238,
    6.14462,
    7.82135,
    9.7951,
    12.0853,
    14.708,
    17.6753,
    20.995,
    24.6709,
    28.7027,
    33.0859,
    37.8121,
    42.8693,
    48.2423,
    53.9132,
    59.8611,
    66.0635,
    72.4959,
    79.1326,
    85.947,
    92.912,
    100.0,
    107.184,
    114.436,
    121.731,
    129.043,
    136.346,
    143.618,
    150.836,
    157.979,
    165.028,
    171.963,
    178.769,
    185.429,
    191.931,
    198.261,
    204.409,
    210.365,
    216.12,
    221.667,
    227.0,
    232.115,
    237.008,
    241.675,
    246.01,
    250.21,
    254.19,
    257.95,
    261.47,
]

_SPD_F2 = [
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    1.18,
    1.48,
    1.84,
    2.15,
    3.44,
    15.69,
    3.85,
    3.74,
    4.19,
    4.62,
    5.06,
    34.98,
    11.81,
    6.27,
    6.63,
    6.93,
    7.19,
    7.4,
    7.54,
    7.62,
    7.65,
    7.62,
    7.62,
    7.45,
    7.28,
    7.15,
    7.05,
    7.04,
    7.16,
    7.47,
    8.04,
    8.88,
    10.01,
    24.88,
    16.64,
    14.59,
    16.16,
    17.56,
    18.62,
    21.47,
    22.79,
    19.29,
]

# Column index where 400 nm starts (340 -> index 6)
_IDX_400NM = 6
# Column index where 700 nm ends (340 + 36*10 = 700, index 36 inclusive)
_IDX_700NM = 37  # exclusive

# Number of spectral sense values from the Spectro device
_SPECTRO_BANDS = 32
_SPECTRO_USABLE = _IDX_700NM - _IDX_400NM  # = 31

# White points (CIE standard — matches APK)
_WHITE_POINTS: dict[tuple[Illuminant, Observer], tuple[float, float, float]] = {
    (Illuminant.D50, Observer.TWO_DEGREE): (96.42, 100.0, 82.49),
    (Illuminant.D65, Observer.TWO_DEGREE): (95.047, 100.0, 108.883),
    (Illuminant.D65, Observer.TEN_DEGREE): (94.811, 100.0, 107.304),
    (Illuminant.A, Observer.TWO_DEGREE): (109.85, 100.0, 35.585),
    (Illuminant.F2, Observer.TWO_DEGREE): (99.187, 100.0, 67.395),
}

# Bradford adaptation matrix
_BRAD = (
    (0.8951, 0.2664, -0.1614),
    (-0.7502, 1.7135, 0.0367),
    (0.0389, -0.0685, 1.0296),
)
_BRAD_INV = (
    (0.9869929, -0.1470543, 0.1599627),
    (0.4323053, 0.5183603, 0.0492912),
    (-0.0085287, 0.0400428, 0.9684867),
)


def _m3xv3(m: tuple[tuple[float, ...], ...], v: tuple[float, float, float]) -> tuple[float, float, float]:
    return (
        m[0][0] * v[0] + m[0][1] * v[1] + m[0][2] * v[2],
        m[1][0] * v[0] + m[1][1] * v[1] + m[1][2] * v[2],
        m[2][0] * v[0] + m[2][1] * v[1] + m[2][2] * v[2],
    )


def _cmf_arrays(observer: Observer) -> tuple[list[float], list[float], list[float]]:
    if observer == Observer.TEN_DEGREE:
        return _CMF10_X, _CMF10_Y, _CMF10_Z
    return _CMF2_X, _CMF2_Y, _CMF2_Z


def _spd_array(illuminant: Illuminant) -> list[float]:
    return {
        Illuminant.D50: _SPD_D50,
        Illuminant.D65: _SPD_D65,
        Illuminant.A: _SPD_A,
        Illuminant.F2: _SPD_F2,
    }[illuminant]


def white_point(illuminant: Illuminant, observer: Observer) -> tuple[float, float, float]:
    return _WHITE_POINTS.get(
        (illuminant, observer),
        _WHITE_POINTS[(Illuminant.D50, Observer.TWO_DEGREE)],
    )


# ============================================================================
# XYZ tristimulus
# ============================================================================


@dataclass(frozen=True)
class XYZ:
    X: float
    Y: float
    Z: float

    def to_lab(
        self,
        illuminant: Illuminant = Illuminant.D50,
        observer: Observer = Observer.TWO_DEGREE,
    ) -> Lab:
        xn, yn, zn = white_point(illuminant, observer)
        return _xyz_to_lab(self.X, self.Y, self.Z, xn, yn, zn)

    def to_xyz(self, dst_illuminant: Illuminant) -> XYZ:
        """Chromatic adaptation via Bradford transform (source assumed D50)."""
        dst_wp = white_point(dst_illuminant, Observer.TWO_DEGREE)
        src_rgb = _m3xv3(_BRAD, (self.X, self.Y, self.Z))
        dst_rgb = _m3xv3(_BRAD, dst_wp)
        scale = (
            dst_rgb[0] / src_rgb[0] if src_rgb[0] else 1.0,
            dst_rgb[1] / src_rgb[1] if src_rgb[1] else 1.0,
            dst_rgb[2] / src_rgb[2] if src_rgb[2] else 1.0,
        )
        adapted = (
            src_rgb[0] * scale[0],
            src_rgb[1] * scale[1],
            src_rgb[2] * scale[2],
        )
        x, y, z = _m3xv3(_BRAD_INV, adapted)
        return XYZ(X=x, Y=y, Z=z)


def _xyz_to_lab(x: float, y: float, z: float, xn: float, yn: float, zn: float) -> Lab:
    """XYZ → Lab.  All values in [0, 100] range (matching APK SpectralCurve output)."""
    xr = x / xn  # APK white-point reference is already normalised
    yr = y / yn
    zr = z / zn

    def _f(t: float) -> float:
        if t > 0.008856451679035631:
            return t ** (1.0 / 3.0)
        return (t * 903.2962962962963 + 16.0) / 116.0

    fx = _f(xr)
    fy = _f(yr)
    fz = _f(zr)
    return Lab(
        L=116.0 * fy - 16.0,
        a=500.0 * (fx - fy),
        b=200.0 * (fy - fz),
    )


# ============================================================================
# CIE Lab
# ============================================================================


@dataclass(frozen=True)
class Lab:
    L: float
    a: float  # noqa: E741
    b: float  # noqa: E741

    def to_xyz(
        self,
        illuminant: Illuminant = Illuminant.D50,
        observer: Observer = Observer.TWO_DEGREE,
    ) -> XYZ:
        xn, yn, zn = white_point(illuminant, observer)
        return _lab_to_xyz(self.L, self.a, self.b, xn, yn, zn)

    def delta_e_76(self, other: Lab) -> float:
        return math.sqrt((self.L - other.L) ** 2 + (self.a - other.a) ** 2 + (self.b - other.b) ** 2)

    def delta_e_00(self, other: Lab) -> float:
        return _ciede2000(self.L, self.a, self.b, other.L, other.a, other.b)


def _lab_to_xyz(l_star: float, a: float, b: float, xn: float, yn: float, zn: float) -> XYZ:
    fy = (l_star + 16.0) / 116.0
    fx = a / 500.0 + fy
    fz = fy - b / 200.0

    def _f_inv(t: float) -> float:
        if t > 0.20689655172413793:  # 6/29
            return t**3
        return (t - 4.0 / 29.0) * 3.0 * (6.0 / 29.0) ** 2

    return XYZ(
        X=_f_inv(fx) * xn,
        Y=_f_inv(fy) * yn,
        Z=_f_inv(fz) * zn,
    )


# ============================================================================
# CIEDE2000
# ============================================================================


def _ciede2000(  # noqa: N803,N806 — CIE standard notation
    L1: float,
    a1: float,
    b1: float,
    L2: float,
    a2: float,
    b2: float,
) -> float:
    C1 = math.hypot(a1, b1)
    C2 = math.hypot(a2, b2)
    Cp = (C1 + C2) / 2.0
    G = 0.5 * (1.0 - math.sqrt(Cp**7 / (Cp**7 + 25**7)))
    a1p = a1 * (1.0 + G)
    a2p = a2 * (1.0 + G)
    C1p = math.hypot(a1p, b1)
    C2p = math.hypot(a2p, b2)
    h1p = math.degrees(math.atan2(b1, a1p)) % 360.0
    h2p = math.degrees(math.atan2(b2, a2p)) % 360.0
    dLp = L2 - L1
    dCp = C2p - C1p
    if C1p * C2p == 0:
        dhp = 0.0
    else:
        dh = h2p - h1p
        if abs(dh) <= 180.0:
            dhp = dh
        elif h2p <= h1p:
            dhp = dh + 360.0
        else:
            dhp = dh - 360.0
    dHp = 2.0 * math.sqrt(C1p * C2p) * math.sin(math.radians(dhp / 2.0))
    Lpp = (L1 + L2) / 2.0
    Cpp = (C1p + C2p) / 2.0
    if C1p * C2p == 0:
        hpp = h1p + h2p
    else:
        hpp = (h1p + h2p) / 2.0
        if abs(h1p - h2p) > 180.0:
            hpp += 180.0 if (h1p + h2p) < 360.0 else -180.0
    T = (
        1.0
        - 0.17 * math.cos(math.radians(hpp - 30.0))
        + 0.24 * math.cos(math.radians(2.0 * hpp))
        + 0.32 * math.cos(math.radians(3.0 * hpp + 6.0))
        - 0.20 * math.cos(math.radians(4.0 * hpp - 63.0))
    )
    dTheta = 30.0 * math.exp(-(((hpp - 275.0) / 25.0) ** 2))
    RC = 2.0 * math.sqrt(Cpp**7 / (Cpp**7 + 25**7))
    SL = 1.0 + (0.015 * (Lpp - 50.0) ** 2) / math.sqrt(20.0 + (Lpp - 50.0) ** 2)
    SC = 1.0 + 0.045 * Cpp
    SH = 1.0 + 0.015 * Cpp * T
    RT = -math.sin(math.radians(2.0 * dTheta)) * RC
    kL = kC = kH = 1.0
    return math.sqrt(
        (dLp / (kL * SL)) ** 2
        + (dCp / (kC * SC)) ** 2
        + (dHp / (kH * SH)) ** 2
        + RT * (dCp / (kC * SC)) * (dHp / (kH * SH))
    )


# ============================================================================
# SpectralCurve — matching APK exactly
# ============================================================================


class SpectralCurve:
    """Spectral reflectance curve — 32 values from Spectro device.

    The Spectro device delivers 32 uint16 values normalised to [0,1].
    The app uses 31 of them (400–700 nm, 10 nm step) for CIE integration.
    Index 0 = 400 nm, index 30 = 700 nm.  Index 31 is discarded.
    """

    def __init__(
        self,
        reflectance: list[float],
        illuminant: Illuminant = Illuminant.D65,
        observer: Observer = Observer.TEN_DEGREE,
    ) -> None:
        # Trim to exactly 31 values (400–700 nm) if > 31
        if len(reflectance) > _SPECTRO_USABLE:
            reflectance = reflectance[:_SPECTRO_USABLE]
        elif len(reflectance) < _SPECTRO_USABLE:
            reflectance = list(reflectance) + [reflectance[-1]] * (_SPECTRO_USABLE - len(reflectance))
        self.reflectance = reflectance
        self.illuminant = illuminant
        self.observer = observer

    def to_xyz(self) -> XYZ:
        """Compute CIE XYZ tristimulus values from spectral reflectance.

        Formula (matching APK exactly):
          K = 100 / Σ(S(λ) · ȳ(λ))
          X = K · Σ(R(λ) · S(λ) · x̄(λ))
          Y = K · Σ(R(λ) · S(λ) · ȳ(λ))
          Z = K · Σ(R(λ) · S(λ) · z̄(λ))
        """
        spd = _spd_array(self.illuminant)[_IDX_400NM:_IDX_700NM]
        cmf_x, cmf_y, cmf_z = _cmf_arrays(self.observer)
        cmf_x = cmf_x[_IDX_400NM:_IDX_700NM]
        cmf_y = cmf_y[_IDX_400NM:_IDX_700NM]
        cmf_z = cmf_z[_IDX_400NM:_IDX_700NM]

        R = self.reflectance
        x_sum = sum(R[i] * spd[i] * cmf_x[i] for i in range(_SPECTRO_USABLE))
        y_sum = sum(R[i] * spd[i] * cmf_y[i] for i in range(_SPECTRO_USABLE))
        z_sum = sum(R[i] * spd[i] * cmf_z[i] for i in range(_SPECTRO_USABLE))
        norm = sum(spd[i] * cmf_y[i] for i in range(_SPECTRO_USABLE))

        k = 100.0 / norm if norm > 0 else 0.0
        return XYZ(X=k * x_sum, Y=k * y_sum, Z=k * z_sum)

    def to_lab(
        self,
        illuminant: Illuminant | None = None,
        observer: Observer | None = None,
    ) -> Lab:
        xyz = self.to_xyz()
        ill = illuminant or self.illuminant
        obs = observer or self.observer
        return xyz.to_lab(ill, obs)


# ============================================================================
# XYZ → sRGB helpers
# ============================================================================

_SRGB_MAT: tuple[tuple[float, ...], ...] = (
    (3.2406, -1.5372, -0.4986),
    (-0.9689, 1.8758, 0.0415),
    (0.0557, -0.2040, 1.0570),
)


def _srgb_companding(c: float) -> float:
    if c <= 0.0031308:
        return 12.92 * c
    return 1.055 * (c ** (1.0 / 2.4)) - 0.055


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def xyz_to_srgb(x: float, y: float, z: float) -> tuple[int, int, int]:
    """CIE XYZ (0–100) → sRGB (0–255)."""
    xn, yn, zn = x / 100.0, y / 100.0, z / 100.0
    rl = _SRGB_MAT[0][0] * xn + _SRGB_MAT[0][1] * yn + _SRGB_MAT[0][2] * zn
    gl = _SRGB_MAT[1][0] * xn + _SRGB_MAT[1][1] * yn + _SRGB_MAT[1][2] * zn
    bl = _SRGB_MAT[2][0] * xn + _SRGB_MAT[2][1] * yn + _SRGB_MAT[2][2] * zn
    return (
        round(_srgb_companding(_clamp(rl)) * 255),
        round(_srgb_companding(_clamp(gl)) * 255),
        round(_srgb_companding(_clamp(bl)) * 255),
    )


def srgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{_clamp(r, 0, 255):02x}{_clamp(g, 0, 255):02x}{_clamp(b, 0, 255):02x}"


# Adobe RGB matrix (from CIE XYZ D65)
_ADOBE_MAT: tuple[tuple[float, ...], ...] = (
    (2.04159, -0.56501, -0.34473),
    (-0.96924, 1.87597, 0.04156),
    (0.01344, -0.11836, 1.01517),
)


def _adobergb_companding(c: float) -> float:
    return c ** (1.0 / (563.0 / 256.0))


def xyz_to_adobergb(x: float, y: float, z: float) -> tuple[int, int, int]:
    xn, yn, zn = x / 100.0, y / 100.0, z / 100.0
    rl = _ADOBE_MAT[0][0] * xn + _ADOBE_MAT[0][1] * yn + _ADOBE_MAT[0][2] * zn
    gl = _ADOBE_MAT[1][0] * xn + _ADOBE_MAT[1][1] * yn + _ADOBE_MAT[1][2] * zn
    bl = _ADOBE_MAT[2][0] * xn + _ADOBE_MAT[2][1] * yn + _ADOBE_MAT[2][2] * zn
    return (
        round(_adobergb_companding(_clamp(rl)) * 255),
        round(_adobergb_companding(_clamp(gl)) * 255),
        round(_adobergb_companding(_clamp(bl)) * 255),
    )


def srgb_to_hsv(r: int, g: int, b: int) -> tuple[float, float, float]:
    rn, gn, bn = r / 255.0, g / 255.0, b / 255.0
    cmax = max(rn, gn, bn)
    cmin = min(rn, gn, bn)
    delta = cmax - cmin
    if delta == 0:
        h = 0.0
    elif cmax == rn:
        h = 60.0 * (((gn - bn) / delta) % 6)
    elif cmax == gn:
        h = 60.0 * (((bn - rn) / delta) + 2)
    else:
        h = 60.0 * (((rn - gn) / delta) + 4)
    s = 0.0 if cmax == 0 else delta / cmax
    v = cmax
    return (h % 360, s * 100.0, v * 100.0)


def srgb_to_cmyk(r: int, g: int, b: int) -> tuple[float, float, float, float]:
    rn, gn, bn = r / 255.0, g / 255.0, b / 255.0
    k = 1.0 - max(rn, gn, bn)
    if k >= 1.0:
        return (0.0, 0.0, 0.0, 100.0)
    c = (1.0 - rn - k) / (1.0 - k)
    m = (1.0 - gn - k) / (1.0 - k)
    y = (1.0 - bn - k) / (1.0 - k)
    return (c * 100.0, m * 100.0, y * 100.0, k * 100.0)
