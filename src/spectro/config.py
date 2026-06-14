"""Application configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class APIConfig:
    """Variable Cloud API settings (URLs, timeouts)."""

    base_url: str = "https://gdn.colourcloud.net/ss/v2"
    auth_url: str = "https://gdn.colourcloud.net/cas/"
    timeout_s: float = 60.0


@dataclass
class Config:
    """Top-level application configuration."""

    data_dir: Path = field(default_factory=lambda: Path.home() / ".spectro")
    api: APIConfig = field(default_factory=APIConfig)
    scan_timeout: float = 10.0
    connect_timeout: float = 15.0


CONFIG = Config()
