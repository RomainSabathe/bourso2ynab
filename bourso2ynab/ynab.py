import os
import json
from pathlib import Path
from datetime import datetime
from typing import Literal, Optional

import ynab_api as ynab
from ynab_api.api.transactions_api import TransactionsApi
from ynab_api.model.save_transaction import SaveTransaction
from ynab_api.model.save_transactions_wrapper import SaveTransactionsWrapper

import pandas as pd


def get_ynab_id(
    id_type: Literal["budget", "account"],
    username: str,
    account_type: Optional[Literal["perso", "joint"]] = None,
    secrets_path: Path = Path("secrets.json")
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


def push_to_ynab(transactions: pd.DataFrame, account_id: str, budget_id: str):
    transactions = transactions.pipe(add_import_ids).replace(np.nan, None)

    configuration = ynab.Configuration()
    configuration.api_key["bearer"] = os.environ["YNAB_API_KEY"]
    configuration.api_key_prefix["bearer"] = "Bearer"
    api = TransactionsApi(ynab.ApiClient(configuration))

    ynab_transactions = SaveTransactionsWrapper(
        transactions=[
            SaveTransaction(
                account_id=account_id,
                date=datetime.strptime(transaction["Date"], "%Y-%m-%d").date(),
                amount=int(transaction["Amount"] * 1_000),
                payee_name=transaction["Payee"],
                memo=transaction["Memo"],
                approved=True,
                cleared="cleared",
                import_id=transaction["import_id"],
            )
            for _, transaction in transactions.iterrows()
        ]
    )

    try:
        return api.create_transaction(budget_id, ynab_transactions)
    except ynab.rest.ApiException as e:
        print("Exception when calling TransactionsApi->create_transaction: %s\n" % e)