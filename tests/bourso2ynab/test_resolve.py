from datetime import date

from actual.database import Transactions as ActualTransaction

from bourso2ynab.resolve import resolve_transactions
from bourso2ynab.transaction import Transaction


def test_remote_transaction_is_not_local_trivial():
    # Case where there are no local transactions.
    remote_transactions = [
        ActualTransaction(
            date=20241208,
            amount=-2512,
            type=None,
            payee_id="fb42bcb7-297b-4187-b737-75019a4dbd01",
            id="ee19047e-a9a9-4c8a-9e4d-2f213fc6cfc6",
            notes="Train ticket",
        )
    ]
    local_transactions = []

    result = resolve_transactions(
        remote_transactions=remote_transactions, local_transactions=local_transactions
    )

    assert isinstance(result, dict)
    assert "missing_from_remote" in result.keys()
    assert "missing_from_local" in result.keys()

    assert len(result["missing_from_remote"]) == 0
    assert len(result["missing_from_local"]) == 1

    missing_transaction = result["missing_from_local"][0]
    assert isinstance(missing_transaction, Transaction)
    assert missing_transaction.amount == -25.12
    assert missing_transaction.date == date(year=2024, month=12, day=8)
    assert missing_transaction.memo == "Train ticket"


def test_remote_transaction_is_not_local():
    remote_transactions = [
        ActualTransaction(
            date=20241208,
            amount=-2512,
            type=None,
            payee_id="fb42bcb7-297b-4187-b737-75019a4dbd01",
            id="ee19047e-a9a9-4c8a-9e4d-2f213fc6cfc6",
            notes="Train ticket",
        ),
        ActualTransaction(
            date=20230101,
            amount=-1015,
            type=None,
            payee_id="fb42bcb7-297b-4187-b737-75019a4dbd01",
            id="ee19047e-a9a9-4c8a-9e4d-2f213fc6cfc6",
            notes="This doesn't exist in local",
        ),
    ]
    local_transactions = [
        Transaction(
            type="CARTE",
            date=date(year=2024, month=12, day=8),
            amount=-25.12,
            payee="SNCF",
            memo="Train ticket",
        )
    ]

    result = resolve_transactions(
        remote_transactions=remote_transactions, local_transactions=local_transactions
    )

    assert isinstance(result, dict)
    assert "missing_from_remote" in result.keys()
    assert "missing_from_local" in result.keys()

    assert len(result["missing_from_remote"]) == 0
    assert len(result["missing_from_local"]) == 1

    missing_transaction = result["missing_from_local"][0]
    assert isinstance(missing_transaction, Transaction)
    assert missing_transaction.amount == -10.15
    assert missing_transaction.date == date(year=2023, month=1, day=1)
    assert missing_transaction.memo == "This doesn't exist in local"


def test_local_transaction_is_not_remote_trivial():
    # Case where there are no remote transactions.
    remote_transactions = []
    local_transactions = [
        Transaction(
            type="CARTE",
            date=date(year=2024, month=12, day=8),
            amount=12.6,
            payee="SNCF",
            memo="Train ticket",
        )
    ]

    result = resolve_transactions(
        remote_transactions=remote_transactions, local_transactions=local_transactions
    )

    assert isinstance(result, dict)
    assert "missing_from_remote" in result.keys()
    assert "missing_from_local" in result.keys()

    assert len(result["missing_from_remote"]) == 1
    assert len(result["missing_from_local"]) == 0

    missing_transaction = result["missing_from_remote"][0]
    assert isinstance(missing_transaction, Transaction)
    assert missing_transaction.amount == 12.6
    assert missing_transaction.date == date(year=2024, month=12, day=8)
    assert missing_transaction.memo == "Train ticket"


def test_local_transaction_is_not_remote():
    remote_transactions = [
        ActualTransaction(
            date=20241208,
            amount=-2512,
            type=None,
            payee_id="fb42bcb7-297b-4187-b737-75019a4dbd01",
            id="ee19047e-a9a9-4c8a-9e4d-2f213fc6cfc6",
            notes="Train ticket",
        )
    ]
    local_transactions = [
        Transaction(
            type="CARTE",
            date=date(year=2024, month=12, day=8),
            amount=-25.12,
            payee="SNCF",
            memo="Train ticket",
        ),
        Transaction(
            type="CARTE",
            date=date(year=2023, month=1, day=1),
            amount=-10.5,
            payee="Other payee",
            memo="This doesn't exist in remote",
        ),
    ]

    result = resolve_transactions(
        remote_transactions=remote_transactions, local_transactions=local_transactions
    )

    assert isinstance(result, dict)
    assert "missing_from_remote" in result.keys()
    assert "missing_from_local" in result.keys()

    assert len(result["missing_from_remote"]) == 1
    assert len(result["missing_from_local"]) == 0

    missing_transaction = result["missing_from_remote"][0]
    assert isinstance(missing_transaction, Transaction)
    assert missing_transaction.amount == -10.5
    assert missing_transaction.date == date(year=2023, month=1, day=1)
    assert missing_transaction.memo == "This doesn't exist in remote"


def test_perfect_match():
    remote_transactions = [
        ActualTransaction(
            date=20230101,
            amount=1015,
            type=None,
            payee_id="fb42bcb7-297b-4187-b737-75019a4dbd01",
            id="ee19047e-a9a9-4c8a-9e4d-2f213fc6cfc6",
            notes="A transaction",
        ),
        ActualTransaction(
            date=20241208,
            amount=2512,
            type=None,
            payee_id="fb42bcb7-297b-4187-b737-75019a4dbd01",
            id="ee19047e-a9a9-4c8a-9e4d-2f213fc6cfc6",
            notes="Train ticket",
        ),
    ]
    # Note that local transactions are ordered differently.
    local_transactions = [
        Transaction(
            type="CARTE",
            date=date(year=2024, month=12, day=8),
            amount=25.12,
            payee="SNCF",
            memo="Train ticket again (note this memo is different from remote)",
        ),
        Transaction(
            type="CARTE",
            date=date(year=2023, month=1, day=1),
            amount=10.15,
            payee="Other payee",
            memo="The memo changes again.",
        ),
    ]

    result = resolve_transactions(
        remote_transactions=remote_transactions, local_transactions=local_transactions
    )

    assert isinstance(result, dict)
    assert "missing_from_remote" in result.keys()
    assert "missing_from_local" in result.keys()

    assert len(result["missing_from_remote"]) == 0
    assert len(result["missing_from_local"]) == 0


def test_mixture():
    remote_transactions = [
        # Shared transaction
        ActualTransaction(
            date=20230101,
            amount=-1015,
            type=None,
            payee_id="fb42bcb7-297b-4187-b737-75019a4dbd01",
            id="ee19047e-a9a9-4c8a-9e4d-2f213fc6cfc6",
            notes="A transaction",
        ),
        # Not in local (same amount but different date)
        ActualTransaction(
            date=20241208,
            amount=-2512,
            type=None,
            payee_id="fb42bcb7-297b-4187-b737-75019a4dbd01",
            id="ee19047e-a9a9-4c8a-9e4d-2f213fc6cfc6",
            notes="Train ticket",
        ),
        # Not in local
        ActualTransaction(
            date=20241208,
            amount=-123,
            type=None,
            payee_id="fb42bcb7-297b-4187-b737-75019a4dbd01",
            id="ee19047e-a9a9-4c8a-9e4d-2f213fc6cfc6",
            notes="Coffee",
        ),
        # Shared transaction
        ActualTransaction(
            date=20251208,
            amount=-123,
            type=None,
            payee_id="fb42bcb7-297b-4187-b737-75019a4dbd01",
            id="ee19047e-a9a9-4c8a-9e4d-2f213fc6cfc6",
            notes="Other coffee",
        ),
    ]
    local_transactions = [
        # Not in remote (dates are different)
        Transaction(
            type="CARTE",
            date=date(year=2024, month=12, day=7),
            amount=-25.12,
            payee="SNCF",
            memo="Train ticket again (note this memo is different from remote)",
        ),
        # Shared transaction
        Transaction(
            type="CARTE",
            date=date(year=2023, month=1, day=1),
            amount=-10.15,
            payee="Other payee",
            memo="The memo changes again.",
        ),
        # Not in remote
        Transaction(
            type="CARTE",
            date=date(year=2025, month=1, day=1),
            amount=-4.56,
            payee="Yet another payee",
            memo="Something else",
        ),
        # Not in remote
        Transaction(
            type="CARTE",
            date=date(year=2022, month=1, day=1),
            amount=-4.56,
            payee="Yet yet another payee",
            memo="Something else again",
        ),
        # Shared transaction
        Transaction(
            type="CARTE",
            date=date(year=2025, month=12, day=8),
            amount=-1.23,
            payee="A coffee shop",
            memo="Other coffee but different memo",
        ),
    ]

    result = resolve_transactions(
        remote_transactions=remote_transactions, local_transactions=local_transactions
    )

    assert isinstance(result, dict)
    assert "missing_from_remote" in result.keys()
    assert "missing_from_local" in result.keys()

    assert len(result["missing_from_remote"]) == 3
    assert len(result["missing_from_local"]) == 2
