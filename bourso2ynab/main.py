import os
import re
import json
from pathlib import Path
from datetime import datetime
from typing import Literal, Optional, Union

import click
import numpy as np
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

from bourso2ynab.payee_formatter import PayeeFormatter
from bourso2ynab.format import format_transactions
from bourso2ynab.ynab import push_to_ynab, get_ynab_id


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


if __name__ == "__main__":
    cli()
