"""GATT UUID constants for Variable Spectro / ColorMuse devices."""

from __future__ import annotations

from typing import Final


class Services:
    """Service UUIDs for Variable device families."""

    SPECTRO: Final = "89504ca4-c879-446f-a10e-f6c2da131d41"
    COLOR_MUSE: Final = "26db67ab-fc40-420a-b080-2ce709bfb7d0"
    COLOR_MUSE_PRO: Final = "ff5b4221-2321-4edc-8946-d53d1fc684e5"
    COLOR_MUSE_2: Final = "abf3c20a-1306-4221-82f1-d2b6706f86f1"
    RADIUS_2: Final = "13f1e628-4c7c-4563-a472-cfe1ef13eed8"
    GEN_3: Final = "146df071-5264-47e9-a436-60ab5faa21d3"
    S45: Final = "fdd2d66d-9bb4-4ed2-81c3-d1382529dc8a"
    THERMA_3: Final = "e931c127-df73-48c0-acc6-e598fc4450d3"

    ALL: Final[list[str]] = [
        COLOR_MUSE,
        COLOR_MUSE_PRO,
        COLOR_MUSE_2,
        GEN_3,
        S45,
        SPECTRO,
        RADIUS_2,
    ]

    @classmethod
    def device_type(cls, uuid: str) -> str | None:
        uuid = uuid.lower()
        return {
            cls.SPECTRO: "spectro",
            cls.COLOR_MUSE: "color_muse",
            cls.COLOR_MUSE_PRO: "color_muse_pro",
            cls.COLOR_MUSE_2: "color_muse_2",
            cls.GEN_3: "gen_3",
            cls.S45: "s45",
            cls.RADIUS_2: "radius_2",
        }.get(uuid)


class Chars:
    """Characteristic UUIDs (reverse-engineered from Android APK)."""

    # Device info --------------------------------------------------------
    SERIAL: Final = "06bee248-ac7e-439a-aa35-07a6a500750a"
    FIRMWARE: Final = "591eddc9-0ebe-4512-af25-b83ce44d24de"
    CONNECTION_CONFIRM: Final = "3a796671-b41b-4b54-a929-00f880c8833b"

    # Battery -----------------------------------------------------------
    BATTERY: Final = "4aecb80d-0f0a-45d4-a2da-4796f114b8d3"
    BATTERY_COEFF: Final = "ba77c0ef-38d8-4a32-a66c-81009ced859d"
    CHARGING_STATUS: Final = "9e60ce27-9f77-40f8-a916-2c0b5f606a68"

    # Measurement --------------------------------------------------------
    SPECTRAL_SCAN: Final = "80db9d9a-6db9-43fa-ac23-c38062ef3c9e"
    COLOR_SCAN: Final = "1a0ad4bf-7bdc-49a3-81d0-ca96ab705ed2"
    GLOSS: Final = "8acb159a-c4f2-484b-ad36-98cf214bf196"
    UV_SCAN: Final = "2857946e-162b-4e95-a332-2a3995cbc829"
    RAPID_SCAN: Final = "cabdef65-e4a0-45b1-b27f-bfa291cfd03b"
    EMISSIVE_SPECTRAL: Final = "ec4ca502-982a-4fc2-82ec-033e37ab4fe9"

    # Calibration --------------------------------------------------------
    SCAN_COUNTS: Final = "baf9126c-68d0-413a-884f-d1da34bee3fc"
    CORRECTION_FACTOR: Final = "5357adb6-c11c-4c19-8bc0-a7c146003e5a"
    CAL_GLOSS: Final = "5357adb6-c11c-4c19-8bc0-a7c146003e5b"
    CAL_UV: Final = "96b46f89-d953-48b6-9864-0d14c087dd8b"

    # Events -------------------------------------------------------------
    BUTTON: Final = "4229bdb5-8b55-4c6f-9216-d71ab06f246a"
    ERROR: Final = "8d6bfa01-c14e-4079-96f5-57a5b136fbdc"

    # Temperature --------------------------------------------------------
    TEMPERATURE: Final = "dffa1ad2-4c57-4bb7-b015-c3a388d98cc7"
    TEMPERATURE_PROBE: Final = "c5164e64-d7e3-4caf-96ff-2cdfdedba6b6"
    TEMPERATURE_SCALE: Final = "9e744af0-747a-4539-b65f-e6b9aae53394"
    PROBE_ICE_CAL: Final = "f3bb0f83-bba9-4cbe-9b81-5e4ce61832bf"

    # Misc ---------------------------------------------------------------
    OLED_CONTROL: Final = "d48193b1-911e-4b27-90d4-395b28244fdf"
    PREVIOUS_READING: Final = "7f8fbd65-f026-404f-a786-895b630edfb1"
    STREAM_REQUEST: Final = "d11e1160-6b54-4e92-ae41-d5686dff1514"
    MICRUIM_OS: Final = "69183525-7ee4-4ae7-bbf1-8b27d238e881"

    # The set of characteristics whose notifications we subscribe to.
    NOTIFY_CHARS: Final[set[str]] = {
        SPECTRAL_SCAN,
        UV_SCAN,
        BUTTON,
        ERROR,
        RAPID_SCAN,
        BATTERY,
        CHARGING_STATUS,
        TEMPERATURE,
        TEMPERATURE_PROBE,
    }


class Descriptors:
    """Standard GATT descriptors."""

    CCCD: Final = "00002902-0000-1000-8000-00805f9b34fb"
