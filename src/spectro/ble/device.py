"""BLE device interaction — connect, query info, measure colour."""

from __future__ import annotations

import asyncio
import dataclasses
import json
import logging
import struct
from dataclasses import dataclass

from bleak import BleakClient
from bleak.backends.device import BLEDevice
from bleak.exc import BleakError

from ..config import CONFIG
from .protocol import Chars

logger = logging.getLogger(__name__)

# Number of spectral sense values from the Spectro device
_SPECTRO_BANDS = 32

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class BatteryInfo:
    level: int
    voltage: float
    is_charging: bool = False
    is_charged: bool = False
    temperature: float | None = None


@dataclass
class DeviceIdent:
    serial: str
    firmware: str
    model: str
    batch: str
    battery: BatteryInfo | None = None
    scan_count: int = 0
    cal_scan_count: int = 0
    is_calibrated: bool = False
    temperature: float | None = None


@dataclass
class ScanResult:
    serial: str
    model: str
    batch: str
    sense_values: list[float]
    uv_values: list[float] | None = None
    gloss_values: list[float] | None = None
    raw_gloss: float | None = None
    ambient_values: list[float] | None = None
    temperature: float | None = None
    scan_count: int = 0
    cal_scan_count: int = 0
    is_calibrated: bool = False
    corrected_values: list[float] | None = None
    correction_factors: list[float] | None = None
    ml_inference_ms: float = 0.0


@dataclass
class RapidScanData:
    light: list[int] = dataclasses.field(default_factory=list)
    dark: list[int] = dataclasses.field(default_factory=list)


# ---------------------------------------------------------------------------
# Error classification
# ---------------------------------------------------------------------------

_SHUTTER_CLOSED = 0x10
_CAL_MISSING = {1, 2, 3}
_SCAN_ERRORS = {4, 8}


def classify_error(data: bytes) -> str:
    if not data:
        return "unknown"
    code = data[0]
    if code == _SHUTTER_CLOSED:
        return "shutter_closed"
    if code in _CAL_MISSING:
        return "calibration_missing"
    if code in _SCAN_ERRORS:
        return "scan_error"
    return f"error_0x{code:02x}"


# ---------------------------------------------------------------------------
# Parsing helpers (matching APK logic)
# ---------------------------------------------------------------------------


def _parse_uint16_be(data: bytes, offset: int = 0) -> int:
    return struct.unpack_from(">H", data, offset)[0]


def _parse_serial(data: bytes) -> str:
    """APK SerialReadEvent — hex of 6 raw bytes."""
    return data[:6].hex().upper()


def _parse_firmware(data: bytes) -> str:
    """APK FirmwareReadEvent — v%01X.%02X."""
    if len(data) < 2:
        return "?"
    return f"v{data[0] & 0xFF:X}.{data[1] & 0xFF:02X}"


def _parse_battery(
    data: bytes,
    device_type: str = "spectro",
    battery_coeff: float | None = None,
) -> BatteryInfo:
    """APK BatteryVoltageReadEvent — matches Java exactly.

    Formula: voltage = ((raw_int32_le * ref_mv) / 4096) * scale / 1000

    The scaling factor can be overridden by the BATTERY_COEFF characteristic.
    Default: 3.364 for Spectro, 2.0 for others.
    """
    if len(data) < 4:
        return BatteryInfo(level=0, voltage=0.0)

    raw = struct.unpack_from("<i", data, 0)[0]

    if device_type == "color_muse_2":
        ref_mv = 1210.0
        scale = battery_coeff if battery_coeff else 2.0
    else:
        ref_mv = 3300.0
        scale = battery_coeff if battery_coeff else 3.364

    voltage = ((raw * ref_mv) / 4096.0) * scale / 1000.0

    threshold = 3.5 if device_type == "color_muse_2" else 3.6
    level = 0 if voltage < threshold else int((voltage - threshold) / (4.0 - threshold) * 100)
    level = max(0, min(100, level))

    return BatteryInfo(level=level, voltage=round(voltage, 3))


def _parse_charging(data: bytes) -> tuple[bool, bool]:
    return (data[1] == 1 if len(data) > 1 else False, False)


def _parse_sense_values(data: bytes, count: int = 32) -> list[float]:
    """Convert raw uint16 BE pairs → normalised [0.0 … 1.0].

    The Spectro device returns 32 uint16 BE values (64 bytes).
    The app uses indices 0–30 (31 values, 400–700 nm, 10 nm step).
    Index 31 is not used for CIE integration.
    """
    values: list[float] = []
    for i in range(min(count, len(data) // 2)):
        values.append(_parse_uint16_be(data, i * 2) / 65535.0)
    return values


def _parse_correction(data: bytes) -> list[float]:
    """Parse correction factors from device.

    May be JSON (APK d.java format) or raw uint16 BE values.
    The device stores 32 uint16 BE correction values (64 bytes).
    Formula: correction[i] = (raw[i] / 65535.0) + 0.2
    """
    # Try JSON first (newer devices / factory calibration)
    try:
        text = data.decode("utf-8").rstrip("\x00")
        if text.startswith("{"):
            obj = json.loads(text)
            for key in ("f78a", "f79b"):
                if key in obj and "d" in obj[key]:
                    return [float(x) for x in obj[key]["d"]]
    except (json.JSONDecodeError, UnicodeDecodeError, KeyError, ValueError):
        pass

    # Fallback: raw uint16 BE binary (64 bytes = 32 values)
    if len(data) >= 64:
        factors = []
        for i in range(32):
            raw = _parse_uint16_be(data, i * 2)
            factors.append(round(raw / 65535.0 + 0.2, 6))
        return factors

    return []


def _parse_correction_batch(data: bytes) -> str | None:
    """Extract batch name from device correction factor JSON metadata."""
    try:
        text = data.decode("utf-8").rstrip("\x00")
        if not text.startswith("{"):
            return None
        obj = json.loads(text)
        for key in ("f78a", "f79b"):
            if key in obj:
                inner = obj[key]
                if isinstance(inner, dict):
                    for bk in ("batch", "native_batch", "model", "name"):
                        if bk in inner:
                            return str(inner[bk])
    except Exception:
        pass
    return None


def _parse_temperature(data: bytes) -> float | None:
    if len(data) < 2:
        return None
    raw = _parse_uint16_be(data, 0)
    return round(raw / 16.0, 1)


# ---------------------------------------------------------------------------
# BLE device handle
# ---------------------------------------------------------------------------


class SpectroDevice:
    """Represents a connected Variable Spectro / ColorMuse device."""

    def __init__(self, ble_device: BLEDevice, device_type: str = "spectro") -> None:
        self._ble = ble_device
        self._device_type = device_type
        self._client: BleakClient | None = None
        self._serial: str = ""
        self._firmware: str = ""
        self._model: str = ""
        self._batch: str = ""
        self._scan_count: int = 0
        self._cal_scan_count: int = 0
        self._correction_factors: list[float] = []
        self._battery: BatteryInfo | None = None
        self._temperature: float | None = None
        self._scan_rx: asyncio.Queue[bytearray] = asyncio.Queue()
        self._uv_rx: asyncio.Queue[bytearray] = asyncio.Queue()
        self._rapid_rx: asyncio.Queue[bytearray] = asyncio.Queue()
        self._last_error: str = ""

    @property
    def is_connected(self) -> bool:
        return self._client is not None and self._client.is_connected

    @property
    def serial(self) -> str:
        return self._serial

    @property
    def firmware(self) -> str:
        return self._firmware

    @property
    def model(self) -> str:
        return self._model

    @property
    def batch(self) -> str:
        return self._batch

    @property
    def scan_count(self) -> int:
        return self._scan_count

    @property
    def cal_scan_count(self) -> int:
        return self._cal_scan_count

    @property
    def last_error(self) -> str:
        return self._last_error

    async def connect(self) -> None:
        self._client = BleakClient(self._ble, timeout=CONFIG.connect_timeout)
        await self._client.connect()
        await self._enable_notifications()
        await self._read_device_info()

    async def disconnect(self) -> None:
        if self._client:
            await self._client.disconnect()
            self._client = None

    async def get_device_info(self) -> DeviceIdent:
        return DeviceIdent(
            serial=self._serial,
            firmware=self._firmware,
            model=self._model,
            batch=self._batch,
            battery=self._battery,
            scan_count=self._scan_count,
            cal_scan_count=self._cal_scan_count,
            is_calibrated=self._cal_scan_count >= 0 and self._scan_count > 0,
            temperature=self._temperature,
        )

    async def get_battery(self) -> BatteryInfo:
        return (await self._read_battery()) or BatteryInfo(level=0, voltage=0.0)

    async def scan(self) -> ScanResult:
        """Perform a full spectral scan, matching APK flow."""
        self._scan_rx = asyncio.Queue()
        self._uv_rx = asyncio.Queue()

        await self._write(Chars.SPECTRAL_SCAN, b"\x20", response=True)

        sense_raw = await asyncio.wait_for(self._scan_rx.get(), timeout=CONFIG.connect_timeout)
        sense = _parse_sense_values(bytes(sense_raw), _SPECTRO_BANDS)

        # Re-read scan counts after measurement (device increments on trigger)
        counts = await self._read(Chars.SCAN_COUNTS)
        if counts and len(counts) >= 8:
            lifetime = struct.unpack_from("<I", counts, 0)[0]
            last_cal = struct.unpack_from("<I", counts, 4)[0]
            self._scan_count = lifetime
            self._cal_scan_count = lifetime - last_cal

        gloss_buf: list[float] = []
        raw_gloss: float | None = None
        gloss_data = await self._read(Chars.GLOSS)
        if gloss_data and len(gloss_data) >= 2:
            gloss_buf = _parse_sense_values(gloss_data, len(gloss_data) // 2)
            if gloss_buf:
                raw_gloss = gloss_buf[0]

        # UV scan (optional — not all devices have UV)
        uv_list: list[float] | None = None
        try:
            await self._write(Chars.UV_SCAN, b"\x20", response=True)
            uv_raw = await asyncio.wait_for(self._uv_rx.get(), timeout=3.0)
            uv_list = [
                float(_parse_uint16_be(bytes(uv_raw), i * 2)) / 65535.0 for i in range(len(uv_raw) // 2)
            ]
        except Exception:
            pass

        is_cal = self._cal_scan_count >= 0 and self._scan_count > 0
        result = ScanResult(
            serial=self._serial,
            model=self._model,
            batch=self._batch,
            sense_values=sense,
            gloss_values=gloss_buf if gloss_buf else None,
            raw_gloss=raw_gloss,
            uv_values=uv_list,
            scan_count=self._scan_count,
            cal_scan_count=self._cal_scan_count,
            is_calibrated=is_cal,
            temperature=self._temperature,
        )

        # Run ML pipeline if model available for this device.
        # The ML models handle correction internally — do NOT pre-apply
        # the device correction factors when using the ML pipeline.
        if self._serial and len(sense) >= 31:
            try:
                from ..models import ModelPipeline

                pipeline = ModelPipeline(self._serial)
                ml_output = pipeline.predict(sense)
                result.corrected_values = ml_output
                result.ml_inference_ms = pipeline.last_inference_ms
            except Exception:
                logger.debug("ML pipeline unavailable for %s", self._serial, exc_info=True)

        # Fallback: apply device correction factors directly (no ML)
        factors_ok = (
            result.corrected_values is None
            and self._correction_factors
            and len(self._correction_factors) == len(sense)
        )
        if factors_ok:
            result.corrected_values = [s * c for s, c in zip(sense, self._correction_factors, strict=False)]
            result.correction_factors = list(self._correction_factors)

        return result

    async def get_rapid_scan(self) -> RapidScanData:
        """Read the latest rapid-scan data if available."""
        self._rapid_rx = asyncio.Queue()
        data = await self._read(Chars.RAPID_SCAN)
        if data:
            light = [_parse_uint16_be(data, i * 2) for i in range(len(data) // 4)]
            dark = [_parse_uint16_be(data, i * 2 + 2) for i in range(len(data) // 4)]
            return RapidScanData(light=light, dark=dark)
        return RapidScanData()

    # -- private helpers --------------------------------------------------

    async def _enable_notifications(self) -> None:
        if not self._client:
            return
        for uuid in Chars.NOTIFY_CHARS:
            try:
                await self._client.start_notify(uuid, self._on_notify)
            except BleakError:
                logger.debug("Cannot enable notify for %s", uuid)

    def _on_notify(self, char_handle: object, data: bytearray) -> None:
        uuid = getattr(char_handle, "uuid", str(char_handle)).lower() if char_handle else ""
        data_bytes = bytes(data)

        if uuid == Chars.SPECTRAL_SCAN.lower():
            self._scan_rx.put_nowait(data)
        elif uuid == Chars.UV_SCAN.lower():
            self._uv_rx.put_nowait(data)
        elif uuid == Chars.BATTERY.lower():
            self._battery = _parse_battery(data_bytes, self._device_type)
        elif uuid == Chars.CHARGING_STATUS.lower():
            if self._battery:
                charging, _ = _parse_charging(data_bytes)
                self._battery.is_charging = charging
        elif uuid == Chars.TEMPERATURE.lower():
            self._temperature = _parse_temperature(data_bytes)
        elif uuid == Chars.ERROR.lower():
            self._last_error = classify_error(data_bytes)
            logger.warning("Device error: %s", self._last_error)
        elif uuid == Chars.RAPID_SCAN.lower():
            self._rapid_rx.put_nowait(data)

    async def _read(self, uuid: str) -> bytes | None:
        if not self._client:
            return None
        try:
            data = await self._client.read_gatt_char(uuid)
            return bytes(data) if data else None
        except BleakError:
            return None

    async def _read_battery(self) -> BatteryInfo | None:
        data = await self._read(Chars.BATTERY)
        if not data:
            return None
        return _parse_battery(data, self._device_type)

    async def _write(self, uuid: str, data: bytes, response: bool = False) -> None:
        if self._client:
            await self._client.write_gatt_char(uuid, data, response=response)

    async def _read_device_info(self) -> None:
        if not self._client:
            return
        data = await self._read(Chars.SERIAL)
        if data:
            self._serial = _parse_serial(data)
        data = await self._read(Chars.FIRMWARE)
        if data:
            self._firmware = _parse_firmware(data)
        self._model = self._device_type
        self._batch = "?"
        if self._serial and self._serial.isalnum():
            self._model = "Spectro 1" if not self._serial[0].isalpha() else self._device_type

        # Batch from correction factor JSON or model info
        corr = await self._read(Chars.CORRECTION_FACTOR)
        if corr:
            self._correction_factors = _parse_correction(corr)
            # Try to extract batch from JSON metadata
            batch = _parse_correction_batch(corr)
            if batch:
                self._batch = batch

        # Fallback: try model info for batch
        if self._batch == "?" and self._serial:
            try:
                from ..models import ModelPipeline

                pipeline = ModelPipeline(self._serial)
                info = pipeline.info
                if info and "native_batch" in info:
                    self._batch = info["native_batch"]
                elif info:
                    for os_info in info.get("output_spaces", []):
                        if os_info.get("is_native"):
                            self._batch = os_info.get("batch", self._batch)
            except Exception:
                pass

        # Last resort fallback
        if self._batch == "?" and self._serial:
            import re as _re

            m = _re.match(r"\d?([A-Z]?\d+)", self._serial)
            if m:
                prefix = self._serial[0] if self._serial[0].isalpha() else "s"
                self._batch = f"{prefix}{m.group(1).lstrip('0') or '0'}"

        # Scan counts — uint32 little-endian pairs
        counts = await self._read(Chars.SCAN_COUNTS)
        if counts and len(counts) >= 8:
            self._scan_count = struct.unpack_from("<I", counts, 0)[0]
            self._cal_scan_count = struct.unpack_from("<I", counts, 4)[0]

        # Battery coefficient (overrides default scaling factor)
        battery_coeff = None
        coeff_data = await self._read(Chars.BATTERY_COEFF)
        if coeff_data and len(coeff_data) >= 4:
            battery_coeff = struct.unpack_from("<f", coeff_data, 0)[0]

        bat = await self._read(Chars.BATTERY)
        if bat:
            self._battery = _parse_battery(bat, self._device_type, battery_coeff)
        chg = await self._read(Chars.CHARGING_STATUS)
        if chg and self._battery:
            charging, _ = _parse_charging(chg)
            self._battery.is_charging = charging
        # Scan counts — uint32 little-endian pairs.
        # offset 0 = lifetime, offset 4 = last calibration scan number.
        counts = await self._read(Chars.SCAN_COUNTS)
        if counts and len(counts) >= 8:
            lifetime = struct.unpack_from("<I", counts, 0)[0]
            last_cal = struct.unpack_from("<I", counts, 4)[0]
            self._scan_count = lifetime
            self._cal_scan_count = lifetime - last_cal

        # Battery coefficient (overrides default scaling factor)
        battery_coeff = None
        coeff_data = await self._read(Chars.BATTERY_COEFF)
        if coeff_data and len(coeff_data) >= 4:
            battery_coeff = struct.unpack_from("<f", coeff_data, 0)[0]

        bat = await self._read(Chars.BATTERY)
        if bat:
            self._battery = _parse_battery(bat, self._device_type, battery_coeff)
        chg = await self._read(Chars.CHARGING_STATUS)
        if chg and self._battery:
            charging, _ = _parse_charging(chg)
            self._battery.is_charging = charging
        if self._serial and self._serial.isalnum():
            self._model = "Spectro 1" if not self._serial[0].isalpha() else self._device_type

        # Batch from correction factor JSON or model info
        corr = await self._read(Chars.CORRECTION_FACTOR)
        if corr:
            self._correction_factors = _parse_correction(corr)
            batch = _parse_correction_batch(corr)
            if batch:
                self._batch = batch

        # Fallback: try model info for batch
        if self._batch == "?" and self._serial:
            try:
                from ..models import ModelPipeline

                pipeline = ModelPipeline(self._serial)
                info = pipeline.info
                if info and "native_batch" in info:
                    self._batch = info["native_batch"]
                elif info:
                    for os_info in info.get("output_spaces", []):
                        if os_info.get("is_native"):
                            self._batch = os_info.get("batch", self._batch)
            except Exception:
                pass

        temp = await self._read(Chars.TEMPERATURE)
        if temp:
            self._temperature = _parse_temperature(temp)
