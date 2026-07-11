import sqlite3
from pathlib import Path

from kotekomi_adapters import REQUIRED_LEDGER_TABLES, SQLiteLedgerInitializer


def test_initialize_empty_ledger_creates_required_tables(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ledger" / "kotekomi.db"

    result = SQLiteLedgerInitializer(ledger_path).initialize()

    assert result.ledger_path == ledger_path
    assert result.applied_migrations == ("001",)
    with sqlite3.connect(ledger_path) as connection:
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
    assert set(REQUIRED_LEDGER_TABLES).issubset(tables)


def test_initialize_existing_ledger_is_idempotent(tmp_path: Path) -> None:
    ledger_path = tmp_path / "kotekomi.db"
    initializer = SQLiteLedgerInitializer(ledger_path)

    first = initializer.initialize()
    second = initializer.initialize()

    assert first.applied_migrations == ("001",)
    assert second.applied_migrations == ()
    with sqlite3.connect(ledger_path) as connection:
        row = connection.execute("SELECT count(*) FROM ledger_migrations").fetchone()
    assert row is not None
    migration_count = row[0]
    assert migration_count == 1
