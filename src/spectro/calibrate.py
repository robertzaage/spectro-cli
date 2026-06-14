"""Device calibration — matching the Android app flow.

Spectro 1 requires 3 scans: white tile, green tile, blue tile.
Results are written back to the device via BLE characteristics.
"""

from __future__ import annotations

import asyncio
import logging
import struct
from typing import Any

from .ble.device import SpectroDevice
from .ble.protocol import Chars
from .color import Illuminant, Observer, SpectralCurve

logger = logging.getLogger(__name__)

# Manufacturer verification data — hardcoded from the APK info_v2.json
_VERIFICATION_WHITE = [
    0.70146,
    0.70848,
    0.70733,
    0.71855,
    0.71798,
    0.72063,
    0.73252,
    0.73093,
    0.72969,
    0.72758,
    0.74091,
    0.74797,
    0.74853,
    0.74410,
    0.74912,
    0.75943,
    0.76227,
    0.75762,
    0.75324,
    0.75019,
    0.75533,
    0.75119,
    0.75821,
    0.75017,
    0.75300,
    0.75528,
    0.74571,
    0.74797,
    0.74370,
    0.75320,
    0.74265,
]

_VERIFICATION_GREEN = [
    0.13810,
    0.13248,
    0.14109,
    0.14472,
    0.15482,
    0.16299,
    0.18065,
    0.20340,
    0.23282,
    0.26168,
    0.29923,
    0.32446,
    0.33668,
    0.32420,
    0.31224,
    0.29859,
    0.27418,
    0.25451,
    0.24483,
    0.22591,
    0.21493,
    0.20795,
    0.20987,
    0.20449,
    0.20173,
    0.19850,
    0.19996,
    0.20837,
    0.21704,
    0.23256,
    0.24642,
]

_VERIFICATION_BLUE = [
    0.63080,
    0.64955,
    0.65432,
    0.67343,
    0.68495,
    0.68569,
    0.69543,
    0.70086,
    0.69669,
    0.68575,
    0.68616,
    0.69006,
    0.65870,
    0.61089,
    0.58544,
    0.57179,
    0.54130,
    0.52312,
    0.49576,
    0.45639,
    0.44837,
    0.44250,
    0.43408,
    0.42238,
    0.41907,
    0.43452,
    0.41773,
    0.43531,
    0.44181,
    0.45173,
    0.47345,
]

_VERIFICATION_TOLERANCE = 1.0  # ΔE2000 pass threshold


def _to_spectral(values: list[float], serial: str = "") -> list[float]:
    """Convert 32 sensor values → 31 spectral values using ML pipeline if available."""
    if serial:
        try:
            from .models import ModelPipeline

            pipeline = ModelPipeline(serial)
            return pipeline.predict(values)
        except Exception:
            pass

    # Fallback: use raw correction factors
    if len(values) > 31:
        values = values[:31]
    return values


def _delta_e_2000(lab1: tuple[float, float, float], lab2: tuple[float, float, float]) -> float:
    """Compute CIEDE2000 between two Lab tuples."""
    from .color import Lab

    return Lab(*lab1).delta_e_00(Lab(*lab2))


def _lab_from_spectral(spectral: list[float]) -> tuple[float, float, float]:
    curve = SpectralCurve(spectral, illuminant=Illuminant.D65, observer=Observer.TEN_DEGREE)
    lab = curve.to_lab()
    return (lab.L, lab.a, lab.b)


async def calibrate_spectro_1(
    dev: SpectroDevice,
    on_prompt: Any = print,
) -> dict[str, Any]:
    """Run the Spectro 1 calibration flow.

    Returns {"success": True} on success, {"success": False, "error": ...} on failure.
    """
    scans: dict[str, Any] = {}

    tiles = [
        ("white", "Place the device on the WHITE calibration tile and press Enter..."),
        ("green", "Place the device on the GREEN verification tile and press Enter..."),
        ("blue", "Place the device on the BLUE verification tile and press Enter..."),
    ]

    for tile_name, prompt in tiles:
        on_prompt(f"\n{prompt}")
        input()
        try:
            result = await dev.scan()
            scans[tile_name] = result
            on_prompt(f"  {tile_name} tile scan complete (scan #{result.scan_count})")
        except Exception as e:
            return {"success": False, "error": f"{tile_name} tile scan failed: {e}"}

    # Verify the calibration using manufacturer reference data
    white_spectral = _to_spectral(scans["white"].corrected_values or scans["white"].sense_values, dev.serial)
    green_spectral = _to_spectral(scans["green"].corrected_values or scans["green"].sense_values, dev.serial)
    blue_spectral = _to_spectral(scans["blue"].corrected_values or scans["blue"].sense_values, dev.serial)

    white_lab = _lab_from_spectral(white_spectral)
    green_lab = _lab_from_spectral(green_spectral)
    blue_lab = _lab_from_spectral(blue_spectral)

    ref_white_lab = _lab_from_spectral(_VERIFICATION_WHITE)
    ref_green_lab = _lab_from_spectral(_VERIFICATION_GREEN)
    ref_blue_lab = _lab_from_spectral(_VERIFICATION_BLUE)

    de_white = _delta_e_2000(white_lab, ref_white_lab)
    de_green = _delta_e_2000(green_lab, ref_green_lab)
    de_blue = _delta_e_2000(blue_lab, ref_blue_lab)

    on_prompt("\nVerification results:")
    on_prompt(f"  White: ΔE={de_white:.2f} {'✓' if de_white <= _VERIFICATION_TOLERANCE else '✗'}")
    on_prompt(f"  Green: ΔE={de_green:.2f} {'✓' if de_green <= _VERIFICATION_TOLERANCE else '✗'}")
    on_prompt(f"  Blue:  ΔE={de_blue:.2f} {'✓' if de_blue <= _VERIFICATION_TOLERANCE else '✗'}")

    if de_white > _VERIFICATION_TOLERANCE:
        return {"success": False, "error": f"White tile verification failed (ΔE={de_white:.2f} > 1.0)"}
    if de_green > _VERIFICATION_TOLERANCE:
        return {"success": False, "error": f"Green tile verification failed (ΔE={de_green:.2f} > 1.0)"}
    if de_blue > _VERIFICATION_TOLERANCE:
        return {"success": False, "error": f"Blue tile verification failed (ΔE={de_blue:.2f} > 1.0)"}

    # Write calibration data to device
    await _write_calibration(dev, scans)

    return {
        "success": True,
        "verification": {
            "white_de": round(de_white, 2),
            "green_de": round(de_green, 2),
            "blue_de": round(de_blue, 2),
        },
    }


async def _write_calibration(dev: SpectroDevice, scans: dict[str, Any]) -> None:
    """Write calibration data back to the device via BLE characteristics.

    Encodes sense values as (value - 0.2) * 65535 → uint16 BE.
    """
    for tile_name, result in scans.items():
        values = result.sense_values[:32]
        buf = bytearray()
        for v in values:
            encoded = max(0, min(65535, int(round((v - 0.2) * 65535))))
            buf.extend(struct.pack(">H", encoded))

        # Write to correction factor characteristic
        if dev._client:
            await dev._client.write_gatt_char(Chars.CORRECTION_FACTOR, bytes(buf), response=True)
            logger.info("Wrote %s tile calibration (%d bytes)", tile_name, len(buf))
            await asyncio.sleep(0.5)
