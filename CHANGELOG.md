# Changelog

## [0.2.0] — 2025-06-14

### Added
- Full measurement pipeline with neural ML correction (matching Android app output, ΔE < 0.3)
- BridgeKit-compatible JSONL API server (`spectro api`)
- Device calibration with white/green/blue tile verification (`spectro calibrate`)
- Offline product database search with 1,190 indexed products (`spectro search offline`)
- Custom Realm file parser (`realm_parser.py`) extracting products from B-tree leaf pages
- ML model download from public S3 bucket (`spectro download models`)
- Auto-download of product DB and ML models on first use (no separate download step needed)
- Auto-extraction of neural network weights from Core ML `.mlmodel` files
- Product colour database download (`spectro download products`)
- Auto-detection of nearby devices when address is omitted
- Interactive scan mode with `--keep` / `-k` flag
- All colour space outputs: Lab (D65/10° + D50/2°), XYZ, sRGB, Adobe RGB, HSV, CMYK, Hex
- Neural network pipeline: unification → adjustment_ca → adjustment (640K params, 0.6ms inference)
- CIE tables extracted from Android APK for exact colour matching
- BLE device detection by both service UUID and name prefix
- Error classification (shutter closed, calibration missing, scan error)
- Rapid scan data reading
- 116 tests across 12 test modules

### Changed
- Complete rewrite from v0.1.0 prototype
- Battery parsing now matches APK exactly (int32 LE, proper reference voltage and scaling)
- Scan counts now read as uint32 LE pairs
- Scanner detects by name prefix when service UUIDs unavailable
- Device model shown as "Spectro 1" (derived from serial + model metadata)

### Fixed
- Scan trigger requires write-with-response (device uses GATT indication, not notification)
- Since-cal now computed as lifetime − lastCal (was showing raw lastCal)
- UV scan made fully optional (not all devices have UV characteristic)
- Correction factors not double-applied with ML pipeline
