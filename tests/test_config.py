"""Tests for configuration management."""

from __future__ import annotations

from spectro.config import APIConfig, Config


class TestAPIConfig:
    def test_defaults(self) -> None:
        cfg = APIConfig()
        assert cfg.base_url == "https://gdn.colourcloud.net/ss/v2"
        assert cfg.timeout_s == 60.0

    def test_custom(self) -> None:
        cfg = APIConfig(base_url="https://example.com", timeout_s=30.0)
        assert cfg.base_url == "https://example.com"


class TestConfig:
    def test_defaults(self) -> None:
        cfg = Config()
        assert cfg.scan_timeout == 10.0
        assert cfg.connect_timeout == 15.0
        assert ".spectro" in str(cfg.data_dir)
