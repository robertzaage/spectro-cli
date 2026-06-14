"""Tests for BLE scanner."""

from __future__ import annotations

import pytest

from spectro.ble.scanner import (
    DiscoveredDevice,
    Scanner,
    _guess_device_type,
    _is_variable_device,
)

# BlueZ/D-Bus is not available in CI environments — skip BLE-dependent tests.
try:
    import asyncio

    from bleak.backends.bluezdbus.manager import get_global_bluez_manager

    asyncio.new_event_loop().run_until_complete(get_global_bluez_manager())
    _HAS_BLUEZ = True
except Exception:
    _HAS_BLUEZ = False

_need_bluez = pytest.mark.skipif(not _HAS_BLUEZ, reason="BlueZ/D-Bus not available")


class TestIsVariableDevice:
    def test_spectro_name(self) -> None:
        assert _is_variable_device("SpectroSI-DEVICE123", None)

    def test_colormuse_name(self) -> None:
        assert _is_variable_device("ColorMuse-12345", None)

    def test_cm2_name(self) -> None:
        assert _is_variable_device("CM2-ABC", None)

    def test_gen3_name(self) -> None:
        assert _is_variable_device("GEN3-Device", None)

    def test_unknown_name(self) -> None:
        assert not _is_variable_device("RandomDevice", None)

    def test_by_uuid(self) -> None:
        assert _is_variable_device("", ["89504ca4-c879-446f-a10e-f6c2da131d41"])

    def test_empty_both(self) -> None:
        assert not _is_variable_device("", None)

    def test_case_insensitive_name(self) -> None:
        assert _is_variable_device("spectrosi-123", None)


class TestGuessDeviceType:
    def test_spectro(self) -> None:
        assert _guess_device_type("SpectroSI-ABC") == "spectro"

    def test_colormuse(self) -> None:
        assert _guess_device_type("ColorMuse-2-XYZ") == "color_muse_2"

    def test_cm2(self) -> None:
        assert _guess_device_type("CM2-123") == "color_muse_2"

    def test_gen3(self) -> None:
        assert _guess_device_type("GEN3-456") == "gen_3"

    def test_radius(self) -> None:
        assert _guess_device_type("Radius2-789") == "radius_2"

    def test_therma(self) -> None:
        assert _guess_device_type("Therma3-000") == "therma"

    def test_unknown_defaults_to_spectro(self) -> None:
        assert _guess_device_type("UnknownDevice") == "spectro"

    def test_empty(self) -> None:
        assert _guess_device_type("") is None


class TestDiscoveredDevice:
    def test_dataclass_fields(self) -> None:
        d = DiscoveredDevice(
            address="AA:BB:CC:DD:EE:FF",
            name="Test",
            rssi=-50,
            device_type="spectro",
            ble_device=None,  # type: ignore[arg-type]
        )
        assert d.address == "AA:BB:CC:DD:EE:FF"
        assert d.device_type == "spectro"
        assert d.rssi == -50


class TestScanner:
    @_need_bluez
    @pytest.mark.asyncio
    async def test_scan_returns_list(self) -> None:
        scanner = Scanner()
        devices = await scanner.scan(timeout=0.5)
        assert isinstance(devices, list)

    @_need_bluez
    @pytest.mark.asyncio
    async def test_find_device_nonexistent(self) -> None:
        scanner = Scanner()
        result = await scanner.find_device("00:00:00:00:00:00", timeout=0.5)
        assert result is None
