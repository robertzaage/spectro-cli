"""Tests for BLE protocol constants."""

from spectro.ble.protocol import Chars, Descriptors, Services


class TestServices:
    def test_spectro_uuid(self) -> None:
        assert len(Services.SPECTRO) == 36
        assert Services.device_type(Services.SPECTRO) == "spectro"

    def test_color_muse_uuid(self) -> None:
        assert Services.device_type(Services.COLOR_MUSE) == "color_muse"

    def test_scan_filters_covers_all(self) -> None:
        for svc in Services.ALL:
            assert Services.device_type(svc) is not None, f"No device type for {svc}"

    def test_unknown_returns_none(self) -> None:
        assert Services.device_type("00000000-0000-0000-0000-000000000000") is None


class TestCharacteristics:
    def test_critical_uuids(self) -> None:
        assert len(Chars.SPECTRAL_SCAN) == 36
        assert len(Chars.SERIAL) == 36
        assert len(Chars.BATTERY) == 36

    def test_descriptor(self) -> None:
        assert Descriptors.CCCD == "00002902-0000-1000-8000-00805f9b34fb"

    def test_notify_chars_not_empty(self) -> None:
        assert len(Chars.NOTIFY_CHARS) > 0
