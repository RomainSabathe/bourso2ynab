import os
import json
from pathlib import Path
from datetime import datetime
from typing import Literal, Optional, List

import ynab_api as ynab
from ynab_api.api.transactions_api import TransactionsApi
from ynab_api.model.save_transaction import SaveTransaction
from ynab_api.model.save_transactions_wrapper import SaveTransactionsWrapper

from bourso2ynab.transaction import (
    Transaction,
    make_import_ids_unique,
    remove_future_transactions,
)


def get_ynab_id(
    id_type: Literal["budget", "account"],
    username: str,
    account_type: Optional[Literal["perso", "joint"]] = None,
    secrets_path: Path = Path("secrets.json"),
) -> str:
    """Utility function to retrieve YNAB IDs from within the env vars."""
    with secrets_path.open("r") as f:
        secrets = json.load(f)
    if id_type == "budget":
        return secrets["budgets"][username]
    assert (
        account_type is not None
    ), "An account type (perso/joint) is required when accessing Accounts."
    return secrets["accounts"][username][account_type]


def get_all_available_usernames(secrets_path: Path = Path("secrets.json")) -> List[str]:
    with secrets_path.open("r") as f:
        secrets = json.load(f)

    usernames = []
    for username, _ in secrets["budgets"].items():
        usernames.append(username)

    return usernames


def get_all_available_account_types(
    secrets_path: Path = Path("secrets.json"),
) -> List[str]:
    with secrets_path.open("r") as f:
        secrets = json.load(f)

    account_types = []
    usernames = get_all_available_usernames(secrets_path)
    for username in usernames:
        for account_type, _ in secrets["accounts"][username].items():
            # I don't use a `set` because I want to preserve ordering.
            if account_type not in account_types:
                account_types.append(account_type)

    return account_types


def push_to_ynab(transactions: List[Transaction], account_id: str, budget_id: str):
    configuration = ynab.Configuration(host="https://api.ynab.com/v1")
    configuration.api_key["bearer"] = os.environ["YNAB_API_KEY"]
    configuration.api_key_prefix["bearer"] = "Bearer"
    api = TransactionsApi(ynab.ApiClient(configuration))

    transactions = make_import_ids_unique(transactions)
    # The YNAB API doesn't accept transactions that are dated in the future.
    # We still want to submit all transactions that are dated in the past though,
    # so we filter the future transactions out.
    transactions = remove_future_transactions(transactions)
    ynab_transactions = SaveTransactionsWrapper(
        transactions=[
            SaveTransaction(
                account_id=account_id,
                date=transaction.date,
                amount=int(transaction.amount * 1_000),
                payee_name=transaction.payee,
                memo=transaction.memo,
                approved=True,
                cleared="uncleared",
                import_id=transaction.import_id,
            )
            for transaction in transactions
        ]
    )

    try:
        return api.create_transaction(budget_id, ynab_transactions)
    except ynab.rest.ApiException as e:
        print("Exception when calling TransactionsApi->create_transaction: %s\n" % e)
