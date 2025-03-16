import decimal
import os
from datetime import date

from actual import Actual, get_ruleset
from actual.database import Transactions as ActualTransaction
from actual.queries import create_transaction, get_account, get_transactions, get_payees
from tenacity import retry, stop_after_attempt, wait_exponential

from bourso2ynab.transaction import Transaction, make_import_ids_unique


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def push_to_actual(
    transactions: list[Transaction], file_uuid: str, account_name: str
) -> list[dict[str, str]]:
    """
    file_uuid: corresponds to the "Budget" in YNAB terms. Each user is mapped to one
        file_uuid.
    account_name: corresponds to the 'account' in YNAB terms.

    Returns the list of pushed transactions as dict.

    """
    if "ACTUAL_SERVER_URL" not in os.environ:
        raise KeyError(
            "Missing a 'ACTUAL_SERVER_URL' var from your environment variables"
        )
    if "ACTUAL_PASSWORD" not in os.environ:
        raise KeyError(
            "Missing a 'ACTUAL_PASSWORD' var from your environment variables"
        )

    with Actual(
        base_url=os.environ["ACTUAL_SERVER_URL"],
        password=os.environ["ACTUAL_PASSWORD"],
        file=file_uuid,
        cert=False,  # TODO: find a proper way to do this.
    ) as actual:
        account = get_account(actual.session, account_name)
        if account is None:
            raise KeyError(f"Could not find Actual account with name {account_name}")

        # TODO: check if the transactions exist before pushing them.
        # Ideally, this should happen at the stage of the transactions upload
        # (i.e. after submitting the csv)
        transactions = make_import_ids_unique(transactions)
        pushed_transactions = [
            create_transaction(
                s=actual.session,
                date=transaction.date,
                account=account,
                payee=transaction.payee,
                notes=transaction.memo,
                amount=decimal.Decimal(transaction.amount),
                imported_id=str(transaction.index),
                cleared=True,
            )
            for transaction in transactions
        ]
        # Applying the ruleset (e.g. if payee_name == 'Tesco' then assign the category
        # 'Groceries'). The rules are defined in the frontend of Actual.
        ruleset = get_ruleset(actual.session)
        for t in pushed_transactions:
            ruleset.run(t)
        actual.commit()

        # I have no clue why, but it seems that for the "model_dump" to produce
        # non-empty dictionnaries, we must 'force' one of the entries of the transaction
        # to be computed. That's what I do in the following line.
        [transaction.amount for transaction in pushed_transactions]

        return [transaction.model_dump() for transaction in pushed_transactions]


def convert_transaction_from_actual(
    transaction: ActualTransaction,
    payee_id_to_name: dict[str | None, str | None] | None = None,
) -> Transaction:
    # Parsing the date. The Actual date is an int with 4 + 2 + 2 digits corresponding
    # to the year, month and day.
    date_str = str(transaction.date)
    year_str, month_str, day_str = date_str[:4], date_str[4:6], date_str[6:8]
    transaction_date = date(year=int(year_str), month=int(month_str), day=int(day_str))

    # Parsing the amount. It is an int, with the last 2 digits being the cents.
    transaction_amount = (
        transaction.amount / 100 if transaction.amount is not None else None
    )

    # Parsing the payee. Actual only provides the ID, not the name of the payee
    # directly. For now we will keep it as is.
    # TODO: provide support for reading the database and retrieving the payee name.
    transaction_payee = transaction.payee_id
    if (
        payee_id_to_name is not None
        and transaction.payee_id is not None
        and transaction.payee_id in payee_id_to_name.keys()
    ):
        transaction_payee = payee_id_to_name[transaction.payee_id]

    # Parsing the index. I don't have a proper way of doing this at the moment, so it'll
    # only be a best guess.
    transaction_index = (
        int(transaction.sort_order) if transaction.sort_order is not None else 1
    )

    return Transaction(
        type=None,
        date=transaction_date,
        amount=transaction_amount,
        payee=transaction_payee,
        memo=transaction.notes,
        index=transaction_index,
    )


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def get_actual_transactions(
    file_uuid: str,
    account_name: str,
    start_date: date | None = None,
) -> list[Transaction]:
    """Fetches transactions from Actual for a given account and date range.

    Args:
        file_uuid: The Actual budget file UUID
        account_name: Name of the account to fetch transactions from
        start_date: Start date for transaction fetch (inclusive). If None, all transactions
            will be fetched.

    Returns:
        List of transactions converted to the common Transaction format
    """
    if "ACTUAL_SERVER_URL" not in os.environ:
        raise KeyError("Missing a 'ACTUAL_SERVER_URL' var from your environment variables")
    if "ACTUAL_PASSWORD" not in os.environ:
        raise KeyError("Missing a 'ACTUAL_PASSWORD' var from your environment variables")

    with Actual(
        base_url=os.environ["ACTUAL_SERVER_URL"],
        password=os.environ["ACTUAL_PASSWORD"],
        file=file_uuid,
        cert=False,
    ) as actual:
        actual_transactions = get_transactions(
            actual.session,
            account=account_name,
            start_date=start_date,
        )
        
        # Get payee names for better display
        payees = get_payees(actual.session)
        payee_id_to_name = {payee.id: payee.name for payee in payees}
        
        # Convert to our transaction format
        return [
            convert_transaction_from_actual(t, payee_id_to_name)
            for t in actual_transactions
        ]
