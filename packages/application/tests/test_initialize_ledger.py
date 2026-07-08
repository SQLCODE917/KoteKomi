from pathlib import Path

from kotekomi_application import LedgerInitResult, initialize_ledger


class FakeLedgerInitializer:
    def __init__(self) -> None:
        self.called = False

    def initialize(self) -> LedgerInitResult:
        self.called = True
        return LedgerInitResult(
            ledger_path=Path("data/kotekomi.db"),
            applied_migrations=("001",),
        )


def test_initialize_ledger_delegates_to_port() -> None:
    initializer = FakeLedgerInitializer()

    result = initialize_ledger(initializer)

    assert initializer.called
    assert result.applied_migrations == ("001",)
