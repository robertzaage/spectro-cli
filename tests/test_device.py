"""Tests for BLE device parsing (no hardware required)."""

import struct

import pytest

from spectro.ble.device import (
    BatteryInfo,
    RapidScanData,
    _parse_battery,
    _parse_charging,
    _parse_correction,
    _parse_firmware,
    _parse_sense_values,
    _parse_serial,
    _parse_temperature,
    classify_error,
)


class TestParsing:
    def test_parse_serial(self) -> None:
        assert _parse_serial(b"\x1a\x2b\x3c\x4d\x5e\x6f") == "1A2B3C4D5E6F"
        assert _parse_serial(b"\xa0\xb1\xc2\xd3\xe4\xf5") == "A0B1C2D3E4F5"

    def test_parse_firmware(self) -> None:
        assert _parse_firmware(b"\x61\x64") == "v61.64"  # hex 0x61=97, 0x64=100

    def test_parse_sense_values(self) -> None:
        data = b"\xff\xff\x80\x00\x00\x00"
        vals = _parse_sense_values(data, 3)
        assert vals[0] == pytest.approx(1.0, abs=1e-4)
        assert vals[1] == pytest.approx(0.5, abs=0.01)
        assert vals[2] == pytest.approx(0.0)

    def test_parse_sense_full_32(self) -> None:
        """Spectro delivers 64 bytes = 32 uint16 BE values."""
        data = b"\x00\x00" * 32
        vals = _parse_sense_values(data, 32)
        assert len(vals) == 32

    def test_parse_sense_truncated(self) -> None:
        vals = _parse_sense_values(b"\x12\x34", 4)
        assert len(vals) == 1

    def test_parse_battery_spectro(self) -> None:
        # int32 LE value: 2000 → (2000*3300/4096)*3.364/1000 ≈ 5.4V
        data = struct.pack("<i", 2000)
        info = _parse_battery(data, "spectro")
        assert info.voltage > 0
        assert isinstance(info, BatteryInfo)

    def test_parse_charging(self) -> None:
        charging, _ = _parse_charging(b"\x00\x01")
        assert charging is True
        charging2, _ = _parse_charging(b"\x00\x00")
        assert charging2 is False

    def test_parse_correction_empty(self) -> None:
        assert _parse_correction(b"") == []

    def test_parse_correction_json(self) -> None:
        data = b'{"f78a":{"d":[1.0,0.95,0.9]}}'
        assert _parse_correction(data) == [1.0, 0.95, 0.9]

    def test_parse_correction_invalid_json(self) -> None:
        assert _parse_correction(b"not-json") == []

    def test_parse_temperature(self) -> None:
        assert _parse_temperature(b"\x01\x90") == pytest.approx(25.0, abs=0.2)  # 400/16=25


class TestDeviceTypes:
    def test_all_types_parse_battery(self) -> None:
        for kind in ("spectro", "color_muse_2"):
            info = _parse_battery(b"\x01\xf4", kind)
            assert isinstance(info, BatteryInfo)
            assert 0 <= info.level <= 100

    def test_rapid_scan_data(self) -> None:
        data = RapidScanData(light=[100, 200], dark=[10, 20])
        assert data.light == [100, 200]
        assert data.dark == [10, 20]


class TestClassifyError:
    def test_shutter_closed(self) -> None:
        assert classify_error(b"\x10") == "shutter_closed"

    def test_calibration_missing(self) -> None:
        assert classify_error(b"\x01") == "calibration_missing"
        assert classify_error(b"\x02") == "calibration_missing"

    def test_scan_error(self) -> None:
        assert classify_error(b"\x04") == "scan_error"

    def test_unknown(self) -> None:
        assert classify_error(b"\xff") == "error_0xff"

    def test_empty(self) -> None:
        assert classify_error(b"") == "unknown"
