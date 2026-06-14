"""Tests for configuration management."""

from __future__ import annotations

import tempfile
from pathlib import Path

from spectro.config import APIConfig, Config


class TestAPIConfig:
    def test_defaults(self) -> None:
        cfg = APIConfig()
        assert cfg.base_url == "https://gdn.colourcloud.net/ss/v2"
        assert cfg.session_token == ""
        assert cfg.subscription_id == 0

    def test_custom(self) -> None:
        cfg = APIConfig(session_token="tok", subscription_id=42)
        assert cfg.session_token == "tok"
        assert cfg.subscription_id == 42


class TestConfig:
    def test_default_path(self) -> None:
        cfg = Config()
        assert cfg.path().name == "config.json"
        assert ".spectro" in str(cfg.path())

    def test_load_nonexistent(self) -> None:
        cfg = Config(data_dir=Path("/tmp/spectro_test_nonexistent"))
        loaded = cfg.load()
        assert loaded.api.session_token == ""

    def test_save_and_load(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Config(data_dir=Path(tmp))
            cfg.save(session_token="test-token", subscription_id=123)
            loaded = cfg.load()
            assert loaded.api.session_token == "test-token"
            assert loaded.api.subscription_id == 123

    def test_save_preserves_existing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Config(data_dir=Path(tmp))
            cfg.save(session_token="tok1")
            cfg.save(subscription_id=99)
            loaded = cfg.load()
            assert loaded.api.session_token == "tok1"
            assert loaded.api.subscription_id == 99

    def test_load_corrupt_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text("not json")
            cfg = Config(data_dir=Path(tmp))
            loaded = cfg.load()
            assert loaded.api.session_token == ""  # falls back to defaults

    def test_save_b2_access_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Config(data_dir=Path(tmp))
            cfg.save(b2_access_key="b2-key-123")
            loaded = cfg.load()
            assert loaded.api.b2_access_key == "b2-key-123"
