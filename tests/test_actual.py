from datetime import date

from actual import Actual
from actual.database import Transactions as ActualTransaction
from actual.queries import get_transactions

from bourso2ynab.actual import convert_transaction_from_actual, push_to_actual
from bourso2ynab.transaction import Transaction
def test_create_transaction():
    transactions = [
        Transaction(
            type="CARTE",
            date=date(year=2024, month=11, day=15),
            amount=10.53,
            payee="TestUser1",
            memo="Test1",
        ),
        Transaction(
            type="CARTE",
            date=date(year=2024, month=11, day=16),
            amount=20.0,
            payee="TestUser3",
            memo="Test3",
        ),
    ]

    pushed_transactions = push_to_actual(
        transactions,
        file_uuid="c4cf2015-e42f-4c60-a262-2785e3505555",
        account_name="Bourso",
    )


def test_convert_transaction_from_actual():
    # This is the reflection of a full Transaction as provided by Actual API.
    actual_transaction = ActualTransaction(
        date=20241208,
        sort_order=1733677902132.0,
        reconciled=0,
        is_child=0,
        financial_id=None,
        tombstone=0,
        is_parent=0,
        amount=-2512,
        type=None,
        cleared=0,
        acct="2eee3584-58f2-45ce-9b79-e91f22eda371",
        category_id="d4b0f075-3343-4408-91ed-fae94f74e5bf",
        location=None,
        pending=0,
        payee_id="fb42bcb7-297b-4187-b737-75019a4dbd01",
        error=None,
        parent_id=None,
        id="ee19047e-a9a9-4c8a-9e4d-2f213fc6cfc6",
        imported_description=None,
        notes="Train ticket",
        starting_balance_flag=0,
        schedule_id=None,
        transferred_id=None,
    )

    converted_transaction: Transaction = convert_transaction_from_actual(
        actual_transaction
    )

    assert converted_transaction.date == date(year=2024, month=12, day=8)
    assert converted_transaction.amount == 25.12  # Gets swapped
    assert converted_transaction.payee == "fb42bcb7-297b-4187-b737-75019a4dbd01"
    assert converted_transaction.memo == "Train ticket"
    assert converted_transaction.type is None
    assert converted_transaction.index == 1733677902132
