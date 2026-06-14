"""Offline product database search.

Indexes the downloaded Realm product database into a local SQLite cache
for fast text and colour-based searching without cloud connectivity.
"""

from __future__ import annotations

import logging
import re
import sqlite3
import zipfile
from pathlib import Path

from .config import CONFIG

logger = logging.getLogger(__name__)


class ProductIndex:
    """Searchable offline product index built from the downloaded database."""

    def __init__(self, db_dir: Path | None = None) -> None:
        self.db_dir = db_dir or CONFIG.data_dir / "products"
        self.idx_path = self.db_dir / "search_index.db"
        self._conn: sqlite3.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.idx_path))
            self._init_schema()
        return self._conn

    def _init_schema(self) -> None:
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS products (
                uuid TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                hex_color TEXT,
                vendor TEXT DEFAULT '',
                collection TEXT DEFAULT '',
                category TEXT DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_products_name ON products(name);
            CREATE INDEX IF NOT EXISTS idx_products_hex ON products(hex_color);
            CREATE INDEX IF NOT EXISTS idx_products_vendor ON products(vendor);
            CREATE TABLE IF NOT EXISTS product_filters (
                uuid TEXT PRIMARY KEY,
                vendor TEXT,
                collection TEXT,
                category TEXT,
                brand TEXT,
                location TEXT
            );
        """)
        self.conn.commit()

    def is_built(self) -> bool:
        return self.idx_path.exists() and self.conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] > 0

    def build(self, package_id: int = 0) -> int:
        """Extract product data from the downloaded ZIP and build the index."""
        zip_path = self.db_dir / f"vp-dbs-{package_id}.zip"
        if not zip_path.exists():
            raise FileNotFoundError(
                f"Product database not found at {zip_path}. Run 'spectro download products' first."
            )

        logger.info("Building product index from %s", zip_path)

        # Clear old index
        self.conn.execute("DELETE FROM products")
        self.conn.execute("DELETE FROM product_filters")
        self.conn.commit()

        with zipfile.ZipFile(zip_path) as zf:
            filter_tmp = None
            realm_tmp = None

            for name in zf.namelist():
                if name.endswith(".db"):
                    filter_tmp = self.db_dir / name
                    zf.extract(name, self.db_dir)
                elif name.endswith(".realm"):
                    realm_tmp = self.db_dir / name
                    zf.extract(name, self.db_dir)

            # Import filter data first (UUID → vendor/collection/category)
            if filter_tmp and filter_tmp.exists():
                self._import_filters(filter_tmp)
                filter_tmp.unlink()

            # Import product names + hex colours from realm
            products: dict[str, dict[str, str]] = {}
            if realm_tmp and realm_tmp.exists():
                self._import_realm(realm_tmp, products)
                realm_tmp.unlink()

        # Bulk-insert products and link with filter data
        count = 0
        with self.conn:
            for _key, data in products.items():
                name = data.get("name", "")
                hex_val = data.get("hex_color", "")
                if not name:
                    continue

                # Try to find filter data by any known UUID
                vendor = ""
                collection = ""
                category = ""
                uid = data.get("uuid", "")
                if uid:
                    row = self.conn.execute(
                        "SELECT vendor, collection, category FROM product_filters WHERE uuid=?",
                        (uid,),
                    ).fetchone()
                    if row:
                        vendor, collection, category = row[0], row[1], row[2]

                # Use hex as the primary key (names may duplicate)
                pk = hex_val if hex_val else name
                self.conn.execute(
                    """INSERT OR REPLACE INTO products
                       (uuid, name, hex_color, vendor, collection, category)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (uid or pk, name, hex_val, vendor, collection, category),
                )
                count += 1

        logger.info("Indexed %d products", count)
        return count

    def _import_filters(self, db_path: Path) -> None:
        """Import UUID → filter data from the filter SQLite database."""
        try:
            conn = sqlite3.connect(str(db_path))
            rows = conn.execute(
                "SELECT productUUID, filterKey, translatedValue FROM product_filters"
            ).fetchall()
            conn.close()

            filters: dict[str, dict[str, str]] = {}
            for uuid_str, key, value in rows:
                if not uuid_str or not value:
                    continue
                uuid_str = str(uuid_str)
                if uuid_str not in filters:
                    filters[uuid_str] = {}
                filters[uuid_str][key] = value

            for uid, data in filters.items():
                self.conn.execute(
                    """INSERT OR REPLACE INTO product_filters
                       (uuid, vendor, collection, category, brand, location)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        uid,
                        data.get("vendor", ""),
                        data.get("collection", ""),
                        data.get("category", ""),
                        data.get("brand", ""),
                        data.get("location", ""),
                    ),
                )
            self.conn.commit()
            logger.info("Imported %d product filter entries", len(filters))
        except Exception:
            logger.debug("Failed to import filters", exc_info=True)

    def _import_realm(self, realm_path: Path, products: dict[str, dict[str, str]]) -> None:
        """Extract product names and hex colours from the Realm binary file.

        Scans for hex colour codes and matches them to nearby product
        names.  Real product names appear sporadically; metadata labels
        repeat frequently and are filtered out.

        UUIDs are extracted from numeric clusters and stored separately
        in the product_filters table (already populated from the companion
        SQLite DB).  Linking UUIDs to products requires a full Realm
        B-tree parser because name strings are stored alphabetically while
        UUIDs are in row-insertion order — the linking key lives in the
        B-tree internal nodes.
        """
        try:
            data = realm_path.read_bytes()
            text = data.decode("utf-8", errors="ignore")
            hex_matches = [(m.start(), m.group(0)) for m in re.finditer(r"#([0-9A-Fa-f]{6})", text)]

            name_re = re.compile(r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+(?:\s+\d+[A-Za-z]?)?)+)")
            name_freq: dict[str, int] = {}
            for hpos, hv in hex_matches:
                nearby = text[max(0, hpos - 400) : hpos + len(hv) + 400]
                for n in name_re.findall(nearby):
                    clean = n.strip()
                    if any(c in clean for c in "\r\n\t\x00\x01"):
                        continue
                    if clean.isupper() or not any(c.islower() for c in clean):
                        continue
                    name_freq[clean] = name_freq.get(clean, 0) + 1

            valid = {n for n, c in name_freq.items() if c <= 15}
            for hpos, hex_val in hex_matches:
                nearby = text[max(0, hpos - 400) : hpos + len(hex_val) + 400]
                for n in name_re.findall(nearby):
                    clean = n.strip()
                    if clean in valid and hex_val not in products:
                        products[hex_val] = {"name": clean, "hex_color": hex_val, "uuid": ""}
                        break

        except Exception:
            logger.debug("Failed to parse realm", exc_info=True)

    def search(
        self,
        query: str = "",
        limit: int = 50,
    ) -> list[dict[str, str]]:
        """Search products by name or hex colour."""
        if not self.is_built():
            raise RuntimeError("Product index not built. Run 'spectro download products' first.")

        if query:
            rows = self.conn.execute(
                """SELECT uuid, name, hex_color, vendor, collection, category
                   FROM products
                   WHERE name LIKE ? OR hex_color LIKE ? OR vendor LIKE ?
                   ORDER BY name
                   LIMIT ?""",
                (f"%{query}%", f"%{query}%", f"%{query}%", limit),
            ).fetchall()
        else:
            rows = self.conn.execute(
                """SELECT uuid, name, hex_color, vendor, collection, category
                   FROM products ORDER BY name LIMIT ?""",
                (limit,),
            ).fetchall()

        results = []
        for r in rows:
            results.append(
                {
                    "uuid": r[0] or "",
                    "name": r[1],
                    "hex_color": r[2] or "",
                    "vendor": r[3] or "",
                    "collection": r[4] or "",
                    "category": r[5] or "",
                }
            )
        return results

    def count(self) -> int:
        if not self.is_built():
            return 0
        return self.conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
