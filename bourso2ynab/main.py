import os
import re
import json
from pathlib import Path
from datetime import datetime
from typing import Literal, Optional, Union

import click
import numpy as np
import pandas as pd
import ynab_api as ynab
from dotenv import load_dotenv
from ynab_api.api.transactions_api import TransactionsApi
from ynab_api.model.save_transaction import SaveTransaction
from ynab_api.model.save_transactions_wrapper import SaveTransactionsWrapper

load_dotenv()

from bourso2ynab.payee_formatter import PayeeFormatter
from bourso2ynab.format import format_transactions


@click.command()
@click.option(
    "-i", "--input", "input_filepath", type=click.Path(exists=True), required=True
)
@click.option("-o", "--output", "output_filepath", required=False)
@click.option(
    "-u",
    "username",
    type=click.Choice(["romain", "ginette"], case_sensitive=True),
    required=True,
)
@click.option(
    "-a",
    "account_type",
    type=click.Choice(["perso", "joint"], case_sensitive=True),
    required=True,
)
@click.option("--upload/--no-upload", default=False)
def cli(input_filepath, output_filepath, username, account_type, upload):
    df = read_bourso_transactions(input_filepath).pipe(format_transactions)
    if output_filepath is not None:
        df.to_csv(output_filepath, index=False)
    if upload:
        upload_transactions(df, username=username, account_type=account_type)


def upload_transactions(
    df: pd.DataFrame, username: str, account_type: str, affect_all_users: bool = True
):
    if account_type == "joint" and affect_all_users:
        # We want to make sure that I (me as a user) is affected last since this is
        # what will be returned to the client.
        # Here, I (me) have the username "username".
        all_users_except_me = [x for x in ["romain", "ginette"] if x != username]
        for username in [*all_users_except_me, username]:
            output = push_to_ynab(
                df,
                account_id=get_ynab_id("account", username, account_type),
                budget_id=get_ynab_id("budget", username),
            )
        return output

    return push_to_ynab(
        df,
        account_id=get_ynab_id("account", username, account_type),
        budget_id=get_ynab_id("budget", username),
    )


def convert_transaction_to_import_id(transaction: pd.Series) -> str:
    return f"YNAB:{str(int(transaction['Amount'] * 1_000))}:{transaction['Date']}"


def add_import_ids(df: pd.DataFrame) -> pd.DataFrame:
    df = df.assign(
        import_id=lambda df: df.apply(convert_transaction_to_import_id, axis="columns")
    )

    # At this stage, there could be duplicates of import_id. We need to make sure they're unique.
    for _, group in df.groupby("import_id"):
        for i, index in enumerate(group.index):
            df.loc[index, "import_id"] = df.loc[index, "import_id"] + f":{i + 1}"
            # Why i + 1? Because YNAB import IDs start counting at 1.

    return df


def get_ynab_id(
    id_type: Literal["budget", "account"],
    username: str,
    account_type: Optional[Literal["perso", "joint"]] = None,
) -> str:
    secrets = json.loads(Path("secrets.json").read_text())
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


if __name__ == "__main__":
    cli()
