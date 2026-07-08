"""Ledger use cases."""

from __future__ import annotations

from kotekomi_application.ports import LedgerInitializer, LedgerInitResult


def initialize_ledger(initializer: LedgerInitializer) -> LedgerInitResult:
    return initializer.initialize()
