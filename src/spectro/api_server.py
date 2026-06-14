"""BridgeKit-compatible JSONL API server for Spectro devices.

Implements the Bridge by Variable protocol over TCP (localhost:9100),
using direct BLE connections (no dongle required).  License commands
are stubbed out — this is a device-control API only.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from .ble.device import ScanResult, SpectroDevice
from .ble.scanner import Scanner
from .color import Illuminant, Observer, SpectralCurve, srgb_to_hex, xyz_to_srgb

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Server state
# ---------------------------------------------------------------------------


class ServerState:
    def __init__(self) -> None:
        self.devices: dict[str, SpectroDevice] = {}  # serial → device
        self.serials: set[str] = set()  # licensed serials (all discovered)
        self.scan_results: dict[str, ScanResult] = {}  # serial → last scan
        self.discovering = False
        self._scanner = Scanner()

    async def scan(self) -> list[dict[str, Any]]:
        devices = await self._scanner.scan(timeout=5.0)
        results = []
        for d in devices:
            dev = SpectroDevice(d.ble_device, device_type=d.device_type or "spectro")
            await dev.connect()
            info = await dev.get_device_info()
            self.devices[info.serial] = dev
            self.serials.add(info.serial)
            await dev.disconnect()
            results.append(_device_payload(dev, info, d.rssi))
        return results


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------


def _ok(event: str, payload: dict[str, Any] | None = None) -> str:
    obj: dict[str, Any] = {"event": event}
    if payload:
        obj["payload"] = payload
    return json.dumps(obj)


def _err(event: str, code: str, payload: dict[str, Any] | None = None) -> str:
    obj: dict[str, Any] = {"event": event, "error_code": code}
    if payload:
        obj["payload"] = payload
    return json.dumps(obj)


def _device_payload(dev: SpectroDevice, info: Any = None, rssi: int = 0) -> dict[str, Any]:
    """Build the BridgeKit DeviceConnected payload."""
    if info is None:
        import asyncio as _asyncio

        info = _asyncio.run(dev.get_device_info())

    bat = info.battery
    battery = {
        "is_charging": bat.is_charging if bat else False,
        "is_charging_complete": bat.is_charged if bat else False,
        "level": bat.level if bat else 0,
        "voltage": bat.voltage if bat else 0.0,
    }
    payload: dict[str, Any] = {
        "serial": dev.serial,
        "device_type": "spectro",
        "firmware_version": dev.firmware,
        "rssi": rssi,
        "battery": battery,
        "spectro": {
            "is_calibrated": info.is_calibrated,
            "last_calibration_scan_count": dev.cal_scan_count,
            "lifetime_scan_count": dev.scan_count,
        },
    }
    return payload


def _scan_payload(result: ScanResult, dev: SpectroDevice) -> dict[str, Any]:
    """Build the BridgeKit Scan response payload."""
    data = result.corrected_values or result.sense_values
    curve = SpectralCurve(data, illuminant=Illuminant.D65, observer=Observer.TEN_DEGREE)
    xyz = curve.to_xyz()
    lab = xyz.to_lab(Illuminant.D65, Observer.TEN_DEGREE)
    r, g, b = xyz_to_srgb(xyz.X, xyz.Y, xyz.Z)
    hex_c = srgb_to_hex(r, g, b)

    payload: dict[str, Any] = {
        "serial": result.serial,
        "device_type": "spectro",
        "batch": result.batch,
        "model": "11.0",
        "scan_count": result.scan_count,
        "created_at": int(time.time()),
        "start": 400,
        "step": 10,
        "curve": data,
        "sense_values": result.sense_values,
        "hex": hex_c,
        "lab": {
            "L": round(lab.L, 5),
            "a": round(lab.a, 5),
            "b": round(lab.b, 5),
            "illuminant": "d65",
            "observer": "10°",
        },
    }
    if result.gloss_values:
        payload["gloss"] = {
            "id": "gloss_v5",
            "ambient_sense_values": [],
            "raw_value": result.raw_gloss or 0.0,
            "gloss": result.gloss_values[0] if result.gloss_values else 0.0,
        }
    if result.uv_values:
        payload["uv"] = {"sense_values": result.uv_values}
    return payload


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------


async def handle_get_dongle(state: ServerState, _params: dict[str, Any]) -> str:
    devices = []
    for _serial, dev in state.devices.items():
        devices.append(_device_payload(dev, rssi=-50))
    return _ok(
        "GetDongle",
        {
            "status": "connected",
            "connected_devices": devices,
            "dongle_id": "ble",
            "firmware_version": "0.2.0",
        },
    )


async def handle_get_config(state: ServerState, _params: dict[str, Any]) -> str:
    return _ok(
        "GetConfiguration",
        {
            "address": "localhost",
            "port": 9100,
            "verbose": False,
            "version": "0.2.0",
            "keep_alive": False,
            "serials": list(state.serials),
            "devices": {s: {"device_type": "spectro", "batches": []} for s in state.serials},
        },
    )


async def handle_start_discovery(state: ServerState, _params: dict[str, Any]) -> str:
    state.discovering = True
    return _ok("StartBluetoothDiscovery")


async def handle_stop_discovery(state: ServerState, _params: dict[str, Any]) -> str:
    state.discovering = False
    return _ok("StopBluetoothDiscovery")


async def handle_scan_devices(state: ServerState, _params: dict[str, Any]) -> str:
    devices = await state.scan()
    return _ok("DiscoveredPeripheral", {"devices": devices})


async def handle_connect(state: ServerState, params: dict[str, Any]) -> str:
    serial = params.get("serial", "")
    if not serial:
        return _err("Connect", "vi-invalid-parameters", {"serial": serial})

    # Find device by scanning
    scanner = Scanner()
    devices = await scanner.scan(timeout=5.0)
    for d in devices:
        dev = SpectroDevice(d.ble_device, device_type=d.device_type or "spectro")
        await dev.connect()
        if dev.serial == serial:
            state.devices[serial] = dev
            state.serials.add(serial)
            info = await dev.get_device_info()
            return _ok("DeviceConnected", _device_payload(dev, info, d.rssi))
        await dev.disconnect()

    return _err("DeviceDisconnected", "vi-connection-timed-out", {"serial": serial})


async def handle_disconnect(state: ServerState, params: dict[str, Any]) -> str:
    serial = params.get("serial", "")
    dev = state.devices.pop(serial, None)
    if dev:
        await dev.disconnect()
    return _ok("DeviceDisconnected", {"serial": serial})


async def handle_scan(state: ServerState, params: dict[str, Any]) -> str:
    serial = params.get("serial", "")
    dev = state.devices.get(serial)
    if not dev or not dev.is_connected:
        return _err("Scan", "vi-bluetooth-device-not-connected", {"serial": serial})

    try:
        result = await dev.scan()
        state.scan_results[serial] = result
        return _ok("Scan", _scan_payload(result, dev))
    except Exception as e:
        return _err("Scan", "vi-scan-failed", {"serial": serial, "message": str(e)})


async def handle_shutdown(_state: ServerState, _params: dict[str, Any]) -> str:
    return _ok("Shutdown")


# ---------------------------------------------------------------------------
# TCP server
# ---------------------------------------------------------------------------


_CMD_MAP: dict[str, Any] = {
    "getdongle": handle_get_dongle,
    "getconfiguration": handle_get_config,
    "startbluetoothdiscovery": handle_start_discovery,
    "stopbluetoothdiscovery": handle_stop_discovery,
    "scandevices": handle_scan_devices,
    "connect": handle_connect,
    "disconnect": handle_disconnect,
    "scan": handle_scan,
    "shutdown": handle_shutdown,
}


async def _handle_client(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    state: ServerState,
) -> None:
    addr = writer.get_extra_info("peername")
    logger.info("API client connected: %s", addr)
    buf = b""
    try:
        while True:
            data = await reader.read(4096)
            if not data:
                break
            buf += data
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                line = line.strip()
                if not line:
                    continue
                try:
                    cmd = json.loads(line)
                except json.JSONDecodeError:
                    writer.write(b'{"event":"error","error_code":"vi-invalid-json"}\n')
                    await writer.drain()
                    continue

                command = cmd.get("command", "").lower()
                params = cmd.get("parameters", {})
                handler = _CMD_MAP.get(command)
                if handler:
                    try:
                        resp = await handler(state, params)
                    except Exception as e:
                        resp = _err(command, "vi-internal-error", {"message": str(e)})
                    writer.write(resp.encode() + b"\n")
                    await writer.drain()

                    if command == "shutdown":
                        writer.close()
                        return
                else:
                    writer.write(_err(command, "vi-unknown-command", {}).encode() + b"\n")
                    await writer.drain()
    except Exception:
        logger.debug("Client disconnected: %s", addr, exc_info=True)
    finally:
        writer.close()


async def run_api_server(host: str = "localhost", port: int = 9100) -> None:
    state = ServerState()
    server = await asyncio.start_server(lambda r, w: _handle_client(r, w, state), host, port)
    logger.info("BridgeKit API server listening on %s:%d", host, port)
    async with server:
        await server.serve_forever()
