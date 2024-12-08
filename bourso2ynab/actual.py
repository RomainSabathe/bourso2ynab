import decimal
import os

from actual import Actual
from actual.queries import create_transaction, get_account

from bourso2ynab.transaction import Transaction, make_import_ids_unique


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
        actual.commit()

        # I have no clue why, but it seems that for the "model_dump" to produce
        # non-empty dictionnaries, we must 'force' one of the entries of the transaction
        # to be computed. That's what I do in the following line.
        [transaction.amount for transaction in pushed_transactions]

        return [transaction.model_dump() for transaction in pushed_transactions]
