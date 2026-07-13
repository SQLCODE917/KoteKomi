import sqlite3
from pathlib import Path

from kotekomi_adapters import REQUIRED_LEDGER_TABLES, SQLiteLedgerInitializer


def test_initialize_empty_ledger_creates_required_tables(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ledger" / "kotekomi.db"

    result = SQLiteLedgerInitializer(ledger_path).initialize()

    assert result.ledger_path == ledger_path
    assert result.applied_migrations == ("001", "002", "003", "004", "005", "006")
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

    assert first.applied_migrations == ("001", "002", "003", "004", "005", "006")
    assert second.applied_migrations == ()
    with sqlite3.connect(ledger_path) as connection:
        row = connection.execute("SELECT count(*) FROM ledger_migrations").fetchone()
    assert row is not None
    migration_count = row[0]
    assert migration_count == 6


def test_analysis_coverage_scope_queries_use_targeted_indexes(tmp_path: Path) -> None:
    ledger_path = tmp_path / "kotekomi.db"
    SQLiteLedgerInitializer(ledger_path).initialize()

    queries = (
        (
            "SELECT payload_json FROM planned_analysis_items WHERE analysis_run_id = ? ORDER BY id",
            ("arn_query_plan",),
        ),
        (
            "SELECT payload_json FROM analysis_item_attempts "
            "WHERE planned_item_id IN (?) ORDER BY planned_item_id, id",
            ("pai_query_plan",),
        ),
        (
            "SELECT payload_json FROM context_manifest_artifacts WHERE id IN (?) ORDER BY id",
            ("ctx_query_plan",),
        ),
        (
            "SELECT payload_json FROM extraction_tasks "
            "WHERE context_manifest_id IN (?) ORDER BY context_manifest_id, id",
            ("ctx_query_plan",),
        ),
        (
            "SELECT payload_json FROM model_runs WHERE id IN (?) ORDER BY id",
            ("mrn_query_plan",),
        ),
        (
            "SELECT proposed.payload_json FROM model_run_proposed_changes AS link "
            "JOIN proposed_changes AS proposed ON proposed.id = link.proposed_change_id "
            "WHERE link.model_run_id = ? ORDER BY link.proposed_change_id",
            ("mrn_query_plan",),
        ),
    )
    with sqlite3.connect(ledger_path) as connection:
        plans = tuple(
            tuple(
                str(row[3]) for row in connection.execute(f"EXPLAIN QUERY PLAN {query}", parameters)
            )
            for query, parameters in queries
        )

    assert all(any("SEARCH" in detail for detail in plan) for plan in plans)
    assert all(not any(detail.startswith("SCAN ") for detail in plan) for plan in plans)
