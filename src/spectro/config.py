"""Application configuration (file-backed)."""

from __future__ import annotations

import contextlib
import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class APIConfig:
    """Variable Cloud API credentials."""

    base_url: str = "https://gdn.colourcloud.net/ss/v2"
    auth_url: str = "https://gdn.colourcloud.net/cas/"
    timeout_s: float = 60.0
    session_token: str = ""
    subscription_id: int = 0
    b2_access_key: str = ""


@dataclass
class Config:
    """Top-level application configuration."""

    data_dir: Path = field(default_factory=lambda: Path.home() / ".spectro")
    api: APIConfig = field(default_factory=APIConfig)
    scan_timeout: float = 10.0
    connect_timeout: float = 15.0

    # ------------------------------------------------------------------
    def path(self) -> Path:
        return self.data_dir / "config.json"

    def load(self) -> Config:
        path = self.path()
        if not path.exists():
            return self
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return self

        api_kw: dict[str, object] = {}
        for key in ("session_token", "b2_access_key"):
            if key in data:
                api_kw[key] = str(data[key])
        for key in ("subscription_id",):
            if key in data:
                api_kw[key] = int(data[key])
        if "base_url" in data:
            api_kw["base_url"] = str(data["base_url"])
        if api_kw:
            return Config(api=APIConfig(**api_kw))  # type: ignore[arg-type]
        return self

    def save(self, **kwargs: object) -> None:
        path = self.path()
        path.parent.mkdir(parents=True, exist_ok=True)
        existing: dict[str, object] = {}
        if path.exists():
            with contextlib.suppress(json.JSONDecodeError, OSError):
                existing = json.loads(path.read_text())
        for k, v in kwargs.items():
            if v not in (None, "", 0):
                existing[k] = v
        path.write_text(json.dumps(existing, indent=2))


# Singleton – load once at import time.
CONFIG = Config().load()
