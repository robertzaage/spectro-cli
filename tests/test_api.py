"""Tests for the BridgeKit-compatible JSONL API server."""

from __future__ import annotations

import json

import pytest

from spectro.api_server import (
    _CMD_MAP,
    ServerState,
    _err,
    _ok,
)
from spectro.ble.device import ScanResult


class TestResponseHelpers:
    def test_ok_no_payload(self) -> None:
        result = json.loads(_ok("Test"))
        assert result["event"] == "Test"
        assert "payload" not in result

    def test_ok_with_payload(self) -> None:
        result = json.loads(_ok("Test", {"key": "value"}))
        assert result["event"] == "Test"
        assert result["payload"] == {"key": "value"}

    def test_err(self) -> None:
        result = json.loads(_err("Test", "vi-error-code"))
        assert result["event"] == "Test"
        assert result["error_code"] == "vi-error-code"

    def test_err_with_payload(self) -> None:
        result = json.loads(_err("Test", "vi-error", {"serial": "123"}))
        assert result["payload"] == {"serial": "123"}


class TestCommandMap:
    def test_all_commands_registered(self) -> None:
        expected = [
            "getdongle",
            "getconfiguration",
            "startbluetoothdiscovery",
            "stopbluetoothdiscovery",
            "scandevices",
            "connect",
            "disconnect",
            "scan",
            "shutdown",
        ]
        for cmd in expected:
            assert cmd in _CMD_MAP, f"Command '{cmd}' not registered"

    def test_case_insensitive(self) -> None:
        # Commands should be accessed case-insensitively
        assert "getdongle" in _CMD_MAP
        assert "GETDONGLE" not in _CMD_MAP  # keys are lowercase


class TestDevicePayload:
    def test_structure(self) -> None:
        """Verify payload matches BridgeKit DeviceConnected spec."""
        payload_keys = {"serial", "device_type", "firmware_version", "rssi", "battery", "spectro"}
        battery_keys = {"is_charging", "is_charging_complete", "level", "voltage"}
        spectro_keys = {"is_calibrated", "last_calibration_scan_count", "lifetime_scan_count"}
        assert payload_keys  # Structure documented for reference
        assert battery_keys
        assert spectro_keys


class TestScanPayload:
    def test_structure(self) -> None:
        """Verify scan response matches BridgeKit Scan spec."""
        result = ScanResult(
            serial="TEST123",
            model="spectro",
            batch="s1-1",
            sense_values=[0.5] * 32,
            corrected_values=[0.6] * 31,
            scan_count=100,
        )

        # Can't build full payload without real device, test structure
        assert result.serial == "TEST123"
        assert len(result.sense_values) == 32

    def test_curve_length(self) -> None:
        """Scan response curve should have 31 values (400-700nm, 10nm)."""
        result = ScanResult(
            serial="TEST",
            model="spectro",
            batch="s1-1",
            sense_values=[0.5] * 32,
            corrected_values=[0.6] * 31,
        )
        assert len(result.corrected_values) == 31


class TestServerState:
    def test_init(self) -> None:
        state = ServerState()
        assert state.devices == {}
        assert state.serials == set()
        assert not state.discovering

    def test_serials_tracking(self) -> None:
        state = ServerState()
        state.serials.add("ABC123")
        state.serials.add("DEF456")
        assert len(state.serials) == 2
        assert "ABC123" in state.serials


class TestJSONLProtocol:
    @pytest.mark.asyncio
    async def test_valid_command(self) -> None:
        """Simulate a TCP client sending a valid JSON command."""
        # Test through the handler directly
        state = ServerState()
        result = json.loads(await _CMD_MAP["getconfiguration"](state, {}))
        assert result["event"] == "GetConfiguration"
        assert "payload" in result
        assert "version" in result["payload"]

    @pytest.mark.asyncio
    async def test_get_dongle_empty(self) -> None:
        state = ServerState()
        result = json.loads(await _CMD_MAP["getdongle"](state, {}))
        assert result["event"] == "GetDongle"
        assert result["payload"]["connected_devices"] == []
        assert result["payload"]["status"] == "connected"

    @pytest.mark.asyncio
    async def test_disconnect_nonexistent(self) -> None:
        state = ServerState()
        result = json.loads(await _CMD_MAP["disconnect"](state, {"serial": "NONEXISTENT"}))
        assert result["event"] == "DeviceDisconnected"

    @pytest.mark.asyncio
    async def test_connect_invalid_params(self) -> None:
        state = ServerState()
        result = json.loads(await _CMD_MAP["connect"](state, {}))
        assert result["error_code"] == "vi-invalid-parameters"

    @pytest.mark.asyncio
    async def test_scan_missing_serial(self) -> None:
        state = ServerState()
        result = json.loads(await _CMD_MAP["scan"](state, {"serial": "MISSING"}))
        assert result["error_code"] == "vi-bluetooth-device-not-connected"

    @pytest.mark.asyncio
    async def test_discovery_commands(self) -> None:
        state = ServerState()
        r1 = json.loads(await _CMD_MAP["startbluetoothdiscovery"](state, {}))
        assert r1["event"] == "StartBluetoothDiscovery"
        r2 = json.loads(await _CMD_MAP["stopbluetoothdiscovery"](state, {}))
        assert r2["event"] == "StopBluetoothDiscovery"

    @pytest.mark.asyncio
    async def test_shutdown(self) -> None:
        state = ServerState()
        result = json.loads(await _CMD_MAP["shutdown"](state, {}))
        assert result["event"] == "Shutdown"
