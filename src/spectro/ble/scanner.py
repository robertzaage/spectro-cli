"""BLE scanner for discovering nearby Variable Spectro devices."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass

from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from .protocol import Services

logger = logging.getLogger(__name__)

# Known device name prefixes for manufacturer detection
_VARIABLE_NAMES = [
    "SpectroSI",
    "Spectro",
    "ColorMuse",
    "CM2",
    "CM-2",
    "CM2-",
    "GEN3",
    "Radius2",
    "Therma3",
    "Therma",
]


def _is_variable_device(name: str, service_uuids: list[str] | None) -> bool:
    """Check if a BLE device is a Variable Spectro/ColorMuse device."""
    # Match by advertised service UUID (most reliable)
    if service_uuids:
        for uuid in service_uuids:
            if Services.device_type(uuid):
                return True

    # Fallback: match by name prefix
    if name:
        for prefix in _VARIABLE_NAMES:
            if name.lower().startswith(prefix.lower()):
                return True

    return False


def _guess_device_type(name: str) -> str | None:
    """Guess the device type from the advertised name."""
    if not name:
        return None
    nl = name.lower()
    if "spectro" in nl:
        return "spectro"
    if "colormuse" in nl or "cm2" in nl:
        return "color_muse_2"
    if "gen3" in nl:
        return "gen_3"
    if "radius" in nl:
        return "radius_2"
    if "therma" in nl:
        return "therma"
    return "spectro"  # default guess


@dataclass
class DiscoveredDevice:
    """A BLE device detected during scanning."""

    address: str
    name: str
    rssi: int
    device_type: str | None
    ble_device: BLEDevice

    @classmethod
    def from_bleak(cls, device: BLEDevice, adv: AdvertisementData) -> DiscoveredDevice | None:
        uuids = list(adv.service_uuids) if adv.service_uuids else None
        name = device.name or adv.local_name or ""

        if not _is_variable_device(name, uuids):
            return None

        kind = None
        if uuids:
            for u in uuids:
                k = Services.device_type(u)
                if k:
                    kind = k
                    break
        if kind is None:
            kind = _guess_device_type(name)

        return cls(
            address=device.address,
            name=name or "Unknown",
            rssi=adv.rssi or -100,
            device_type=kind,
            ble_device=device,
        )


DiscoveryCallback = Callable[[DiscoveredDevice], None]


class Scanner:
    """Scan for Variable Spectro BLE devices."""

    def __init__(self) -> None:
        self._active = False

    async def scan(
        self,
        timeout: float = 10.0,
        callback: DiscoveryCallback | None = None,
    ) -> list[DiscoveredDevice]:
        """Run a BLE scan and return discovered Variable devices."""
        found: dict[str, DiscoveredDevice] = {}
        self._active = True

        def _on_device(device: BLEDevice, adv: AdvertisementData) -> None:
            if not self._active:
                return
            info = DiscoveredDevice.from_bleak(device, adv)
            if info is None:
                return
            if info.address not in found:
                found[info.address] = info
                logger.debug("Discovered %s (%s) RSSI=%d", info.name, info.address, info.rssi)
                if callback:
                    callback(info)

        async with BleakScanner(detection_callback=_on_device):
            await asyncio.sleep(timeout)

        self._active = False
        return list(found.values())

    async def find_device(self, address: str, timeout: float = 5.0) -> DiscoveredDevice | None:
        """Find a device by MAC address, even if already connected.

        Connected devices may not appear in scans.  This method tries:
        1. Regular BLE scan
        2. BlueZ D-Bus device cache (for paired devices)
        3. Direct connection attempt (for already-connected devices)
        """
        # Try regular scan first
        devices = await self.scan(timeout=timeout)
        for d in devices:
            if d.address.lower() == address.lower():
                return d

        # Fallback: BlueZ device cache
        try:
            device = await BleakScanner.find_device_by_address(address, timeout=timeout)
            if device:
                info = DiscoveredDevice(
                    address=device.address,
                    name=device.name or "Spectro Device",
                    rssi=-100,
                    device_type=_guess_device_type(device.name or ""),
                    ble_device=device,
                )
                return info
        except Exception:
            pass

        # Last resort: try direct connection and verify it's a Variable device
        try:
            from bleak import BleakClient

            async with BleakClient(address, timeout=5.0) as client:
                if client.is_connected:
                    # Verify by reading the serial characteristic
                    try:
                        serial_uuid = "06bee248-ac7e-439a-aa35-07a6a500750a"
                        data = await client.read_gatt_char(serial_uuid)
                        if data and len(data) >= 6:
                            return DiscoveredDevice(
                                address=address,
                                name="Spectro Device",
                                rssi=-100,
                                device_type="spectro",
                                ble_device=BLEDevice(address, address, {}, -100),
                            )
                    except Exception:
                        pass
        except Exception:
            pass

        return None
