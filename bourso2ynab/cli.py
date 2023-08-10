import os
from pathlib import Path

import click

from bourso2ynab.ynab import push_to_ynab
from bourso2ynab.transaction import Transaction
from bourso2ynab.io import read_bourso_transactions


@click.command()
@click.argument("filepath", type=click.Path(exists=True))
@click.option(
    "--budget-id",
    help="Budget ID used to send the Transaction to. "
    "Can also be provided with the YNAB_BUDGET_ID environment variable.",
)
@click.option(
    "--account-id",
    help="Account ID used to send the Transaction to. "
    "Can also be provided with the YNAB_BUDGET_ID environment variable.",
)
def push(filepath: Path, budget_id: str, account_id: str):
    """Reads FILEPATH which contains Boursorama transactions and pushes them to a YNAB account.
    Note: this script does not use the database of updated payee names.
    """
    filepath = Path(filepath)

    if budget_id is None:
        assert (
            os.environ.get("YNAB_BUDGET_ID") is not None
        ), "You need to provide a Budget ID."
        budget_id = os.environ["YNAB_BUDGET_ID"]
    if account_id is None:
        assert (
            os.environ.get("YNAB_ACCOUNT_ID") is not None
        ), "You need to provide an Account ID."
        account_id = os.environ["YNAB_ACCOUNT_ID"]

    df = read_bourso_transactions(filepath)
    transactions = [Transaction.from_pandas(row) for _, row in df.iterrows()]
    result = push_to_ynab(transactions, account_id=account_id, budget_id=budget_id)
    print(result)


if __name__ == "__main__":
    push()
