# Contributing to Spectro

## Getting Started

```bash
git clone https://github.com/anomalyco/spectro.git
cd spectro
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Development Workflow

```bash
# Make your changes, then:
ruff check src/ tests/           # lint
ruff format src/ tests/ --check   # format check
pytest tests/ -v                  # 116 tests
```

### Pre-commit (recommended)

```bash
pip install pre-commit
# Add this to .git/hooks/pre-commit:
ruff check src/ tests/ && ruff format src/ tests/ --check && pytest tests/ -q
```

## Code Style

- **Line length**: 110 characters
- **Quotes**: double (`"`)
- **Imports**: `ruff` auto-sorts with `isort` rules
- **Type hints**: all public functions require type annotations
- **Docstrings**: every public function and class
- **Naming**: follow PEP 8; CIE colour science variables in `_ciede2000` use uppercase (standard notation) — suppressed via `per-file-ignores`

## Project Conventions

### Async/Await

All BLE operations are asynchronous. CLI commands use `asyncio.run()` to bridge sync ↔ async. Internal methods like `_pick_device()` and `_read_device_info()` are `async def`.

### Error Handling

- BLE operations catch `BleakError` and log at DEBUG level (these are expected with sleeping devices)
- CLI commands catch `Exception`, print user-friendly errors, and `raise typer.Exit(1)` from the caught exception
- The API server returns BridgeKit error codes (`vi-*`) for protocol errors

### Adding a New CLI Command

1. Add a function with the `@app.command()` decorator in `cli.py`
2. Use `async def _run()` pattern for async operations
3. Run `pytest tests/ -v` and `ruff check src/`

### Adding a New BLE Characteristic

1. Add the UUID constant to `Chars` in `protocol.py`
2. If it should generate notifications, add to `Chars.NOTIFY_CHARS`
3. Add a handler case in `SpectroDevice._on_notify()`
4. Add parsing function if needed
5. Add tests in `test_device.py`

## Release Process

```bash
# Update version in src/spectro/__init__.py
# Update CHANGELOG.md
pip install build twine
python -m build
twine upload dist/*
```

## Getting Help

Open an issue on GitHub with:
- Spectro version (`spectro version`)
- Device model and firmware
- Steps to reproduce
- Full command output with `-v` for verbose logging
