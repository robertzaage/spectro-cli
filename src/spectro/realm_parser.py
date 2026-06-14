"""Pure Python Realm file parser — extracts Product table rows.

Parses the Realm columnar B-tree format to read product UUIDs, names,
hex colours from width-17 structured data pages (0x1000000, 0x587d8,
0x1200000).  These pages store rows with marker-prefixed column values.
"""

from __future__ import annotations

import logging
import re
import struct
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Realm data markers found in width-17 structured pages
_MARKER_STRING = 0x06  # marker + varint length + data
_MARKER_INT32 = 0x05  # marker + 4 bytes LE
_MARKER_VARSTR = 0x07  # marker + varint length + string data
_MARKER_SHORTSTR = 0x09  # marker + implicit-length string


def _read_col_value(data: bytes, pos: int) -> tuple[str, int]:
    """Read one column value from a width-17 structured page.  Returns (value, next_pos)."""
    if pos >= len(data):
        return "", pos
    marker = data[pos]
    pos += 1

    if marker in (_MARKER_STRING, _MARKER_VARSTR):
        length = 0
        shift = 0
        while pos < len(data):
            b = data[pos]
            length |= (b & 0x7F) << shift
            pos += 1
            shift += 7
            if not (b & 0x80):
                break
        s = data[pos : pos + length].decode("ascii", errors="replace")
        return s, pos + length

    elif marker == _MARKER_INT32:
        val = struct.unpack_from("<i", data, pos)[0]
        return str(val), pos + 4

    elif marker in (0x00, 0x01, 0x02, 0x03):
        return "", pos  # null/skip markers

    elif marker == _MARKER_SHORTSTR:
        # Short string: next byte might be part of the value
        return "", pos

    elif marker == 0x0D:
        # Skip marker with length
        return "", pos

    return "", pos


def parse_products(realm_path: Path) -> list[dict[str, Any]]:
    """Parse the Realm file and return product rows.

    Reads width-17 structured data pages that contain product rows
    in marker-prefixed format: uuid (0x07), name (0x09), code (0x06), hex (0x07).
    Falls back to proximity-based name-hex matching for products
    without structured rows.
    """
    data = realm_path.read_bytes()
    text = data.decode("utf-8", errors="ignore")
    products: dict[str, dict[str, str]] = {}

    # --- Phase 1: structured row extraction from width-17 pages ---
    pos = 0
    while True:
        pos = data.find(b"AAAA", pos)
        if pos < 0 or pos + 8 > len(data):
            break
        hdr = data[pos + 4]
        w = hdr & 0x3F
        inner = bool(hdr & 0x40)
        nb = struct.unpack_from(">H", data, pos + 6)[0]

        # Structured product data pages: width=17, 500-50000 rows
        if w == 17 and not inner and 500 < nb < 50000:
            page = data[pos + 8 : pos + 8 + nb * 20]
            p = 0
            while p < len(page):
                values: list[str] = []
                for _ in range(16):  # read up to 16 column values
                    val, p = _read_col_value(page, p)
                    values.append(val)
                # Look for pattern: uuid (6-8 digits), name, code, hex
                uuid_candidate = ""
                name_candidate = ""
                hex_candidate = ""
                for _i, v in enumerate(values):
                    if re.match(r"^\d{6,8}$", v):
                        uuid_candidate = v
                    elif v and v[0].isupper() and any(c.islower() for c in v) and len(v) > 3:
                        name_candidate = v
                    elif re.match(r"^#[0-9A-Fa-f]{6}$", v):
                        hex_candidate = v
                if name_candidate and hex_candidate and hex_candidate not in products:
                    products[hex_candidate] = {
                        "uuid": uuid_candidate,
                        "name": name_candidate,
                        "hex_color": hex_candidate,
                        "code": "",
                    }
        pos += 1

    structured_count = len(products)

    # --- Phase 2: proximity-based fallback for remaining hexes ---
    name_re = re.compile(r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+(?:\s+\d+[A-Za-z]?)?)+)")
    hex_matches = [(m.start(), m.group(0)) for m in re.finditer(r"#([0-9A-Fa-f]{6})", text)]

    # Get names from structured products to build valid-name set
    valid = {p["name"] for p in products.values()}

    # Also extract names from null-terminated name pages (width=17, nb>1000)
    pos = 0
    while True:
        pos = data.find(b"AAAA", pos)
        if pos < 0 or pos + 8 > len(data):
            break
        hdr = data[pos + 4]
        w = hdr & 0x3F
        if w == 17:
            inner = bool(hdr & 0x40)
            nb = struct.unpack_from(">H", data, pos + 6)[0]
            if not inner and 5000 < nb < 20000:
                p = pos + 8
                while p < pos + 8 + nb * 20 and p < len(data):
                    end = data.find(b"\x00", p)
                    if end < 0 or end - p > 50:
                        break
                    s = data[p:end].decode("ascii", errors="replace")
                    if 4 < len(s) < 50 and s[0].isupper() and any(c.islower() for c in s):
                        valid.add(s)
                    p = end + 1
        pos += 1

    # Count name frequency to filter metadata
    freq: dict[str, int] = {}
    for hpos, _hv in hex_matches:
        nearby = text[max(0, hpos - 400) : hpos + 400]
        for n in name_re.findall(nearby):
            clean = n.strip()
            if clean in valid:
                freq[clean] = freq.get(clean, 0) + 1

    valid_filtered = {n for n, c in freq.items() if c <= 8}

    for hpos, hex_val in hex_matches:
        if hex_val in products:
            continue
        nearby = text[max(0, hpos - 400) : hpos + 400]
        for n in name_re.findall(nearby):
            clean = n.strip()
            if clean in valid_filtered:
                products[hex_val] = {
                    "uuid": "",
                    "name": clean,
                    "hex_color": hex_val,
                    "code": "",
                }
                break

    result: list[dict[str, Any]] = []
    for _key, info in products.items():
        result.append(
            {
                "uuid": info["uuid"],
                "name": info["name"],
                "hex_color": info["hex_color"],
                "code": info.get("code", ""),
            }
        )

    logger.info(
        "Parsed %d products (%d structured, %d fallback)",
        len(result),
        structured_count,
        len(result) - structured_count,
    )
    return result
