"""Tests for offline product index."""

from __future__ import annotations

import tempfile
from pathlib import Path

from spectro.products import ProductIndex


class TestProductIndex:
    def test_init(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            idx = ProductIndex(db_dir=Path(tmp))
            assert not idx.is_built()
            idx.close()

    def test_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            idx = ProductIndex(db_dir=Path(tmp))
            idx._init_schema()
            # Verify tables exist
            tables = idx.conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            table_names = {t[0] for t in tables}
            assert "products" in table_names
            idx.close()

    def test_search_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            idx = ProductIndex(db_dir=Path(tmp))
            idx._init_schema()
            idx.conn.execute(
                "INSERT INTO products VALUES (?,?,?,?,?,?)",
                ("1", "Test White", "#ffffff", "Vendor", "Coll", "Paint"),
            )
            idx.conn.commit()
            rows = idx.conn.execute("SELECT * FROM products WHERE name LIKE ?", ("%White%",)).fetchall()
            assert len(rows) == 1
            assert rows[0][1] == "Test White"
            idx.close()

    def test_search_no_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            idx = ProductIndex(db_dir=Path(tmp))
            idx._init_schema()
            # Query directly without is_built check
            rows = idx.conn.execute("SELECT * FROM products WHERE name LIKE ?", ("Nope",)).fetchall()
            assert len(rows) == 0
            idx.close()

    def test_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            idx = ProductIndex(db_dir=Path(tmp))
            idx._init_schema()
            assert idx.count() == 0
            idx.conn.execute(
                "INSERT INTO products VALUES (?,?,?,?,?,?)",
                ("1", "A", "#000", "", "", ""),
            )
            idx.conn.commit()
            assert idx.count() == 1
            idx.close()

    def test_is_built(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            idx = ProductIndex(db_dir=Path(tmp))
            assert not idx.is_built()
            idx._init_schema()
            # Still 0 rows, so not "built"
            assert not idx.is_built()
            idx.conn.execute(
                "INSERT INTO products VALUES (?,?,?,?,?,?)",
                ("1", "Test", "#000", "", "", ""),
            )
            idx.conn.commit()
            assert idx.is_built()
            idx.close()
