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

#  TODO: this import doesn't work :(
# from .payee_formatter import PayeeFormatter
class PayeeFormatter:
    def __init__(self):
        self._db_filepath = Path("bourso2ynab/payee_name_fix.json")
        self._load_db()

    def format(self, payee: str) -> str:
        return self.db.get(payee, payee)

    def add_formatting_rule(self, unformatted_payee: str, formatted_payee: str) -> bool:
        """Return True if it's a new rule. False otherwise."""
        is_known_rule = self.db.get(unformatted_payee) == formatted_payee
        if not is_known_rule:
            self.db[unformatted_payee] = formatted_payee
        return is_known_rule

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self._db_filepath.write_text(
            json.dumps(self.db, indent=4, sort_keys=True, ensure_ascii=False),
            encoding="utf-8",
        )

    def _load_db(self):
        # TODO: find a better way to handle resources
        # TODO: even better: put this into an actual database.
        self.db = json.loads(self._db_filepath.read_text(encoding="utf-8"))


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


def read_bourso_transactions(filepath: Union[str, Path]) -> pd.DataFrame:
    return pd.read_csv(filepath, sep=";")


def format_transactions(df: pd.DataFrame, format_payee: bool = True) -> pd.DataFrame:
    formated_df = df.apply(
        format_transaction,
        payee_formatter=PayeeFormatter() if format_payee else None,
        axis="columns",
    )
    remaining_idx = df.index.difference(formated_df.index)
    df = df.loc[remaining_idx]
    assert len(df) == 0
    return formated_df.sort_values(["Date", "Payee", "Amount"], ascending=False)


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


def format_vir(row: pd.Series, payee_formatter: Optional[PayeeFormatter]) -> pd.Series:
    pattern = r"^(?P<vir_type>(VIR)|(PRLV))( (INST)| (SEPA))? ((MLE )|(MR ))?(?P<description>[\w| |\d|\(|\)|'|:|-]+)$"
    prog = re.compile(pattern)
    result = prog.match(row["label"])
    if result is None:
        # We try with a simpler, less capable pattern
        pattern = r"^(?P<vir_type>(VIR)|(PRLV)) (?P<description>.+)$"
        prog = re.compile(pattern)
        result = prog.match(row["label"])
        if result is None:
            raise Exception(f"Can't parse Carte transaction: {row['label']}")
    description = result.group("description")
    # Boursorama indicates the sender or receiver of the transfer when the description
    # is all uppercase.
    description_is_payee = (
        description == description.upper() or result.group("vir_type") == "PRLV"
    )
    if description_is_payee:
        extra = {"Payee": description.title()}
    else:
        extra = {"Memo": description}
        if description in ["Energie", "Loyer"]:
            extra.update({"Payee": "ginette Georges"})
    if "Payee" in extra.keys() and payee_formatter is not None:
        extra["Payee"] = payee_formatter.format(extra["Payee"])

    entry = {
        "Date": row["dateVal"],
        "Amount": float(row["amount"].replace(",", ".").replace(" ", "")),
        **extra,
    }
    return pd.Series(entry)


def format_carte(
    row: pd.Series, payee_formatter: Optional[PayeeFormatter]
) -> pd.Series:
    pattern = r"^CARTE (?P<date>\d{2}/\d{2}/\d{2}) (ZTL)?\*?(?P<payee>\d?([A-Za-z]| |\_|\.|&|-|\*|')+)I?\d? ?(\([A-Za-z]+\)?)? ?(GB)?\d*(SC)? ?\d?(LTD)? ?CB\*\d{4}$"
    prog = re.compile(pattern)
    result = prog.match(row["label"])
    if result is None:
        # We try with a simpler, less capable pattern
        pattern = r"^CARTE (?P<date>\d{2}/\d{2}/\d{2}) (?P<payee>.+) CB\*\d{4}$"
        prog = re.compile(pattern)
        result = prog.match(row["label"])
        if result is None:
            raise Exception(f"Can't parse Carte transaction: {row['label']}")
    result = result.groupdict()
    date = datetime.strptime(result["date"], "%d/%m/%y")
    entry = {
        "Date": date.strftime("%Y-%m-%d"),
        "Payee": result["payee"].replace("_", " ").replace("*", "").strip().title(),
        "Memo": "",
        "Amount": float(row["amount"].replace(",", ".").replace(" ", "")),
    }
    if "paypal" in entry["Payee"].lower():
        entry["Payee"] = entry["Payee"].replace("Paypal ", "")
        entry["Memo"] += " (via Paypal)"
    if payee_formatter is not None:
        entry["Payee"] = payee_formatter.format(entry["Payee"])

    if entry["Payee"] == "Pavilion Cafe":
        entry["Memo"] += " (in Victoria Park)"

    entry["Memo"] = entry["Memo"].strip()
    return pd.Series(entry)


def format_retrait(
    row: pd.Series, payee_formatter: Optional[PayeeFormatter]
) -> pd.Series:
    pattern = r"^RETRAIT (DAB)? (?P<date>\d{2}/\d{2}/\d{2}) \d*(?P<payee>([A-Za-z]| |\_|\.|&|-|\*|')+)I?\d? (GB)?\d* ?(LTD)? ?CB\*\d{4}$"
    prog = re.compile(pattern)
    result = prog.match(row["label"])
    if result is None:
        # We try with a simpler, less capable pattern
        pattern = (
            r"^RETRAIT (DAB)? (?P<date>\d{2}/\d{2}/\d{2}) (?P<payee>.+) CB\*\d{4}$"
        )
        prog = re.compile(pattern)
        result = prog.match(row["label"])
        if result is None:
            raise Exception(f"Can't parse Retrait transaction: {row['label']}")
    result = result.groupdict()
    date = datetime.strptime(result["date"], "%d/%m/%y")
    entry = {
        "Date": date.strftime("%Y-%m-%d"),
        "Payee": "ATM",
        "Memo": "",
        "Amount": float(row["amount"].replace(",", ".").replace(" ", "")),
    }
    return pd.Series(entry)


def format_transaction(
    row: pd.Series, payee_formatter: Optional[PayeeFormatter]
) -> pd.Series:
    kwargs = {"payee_formatter": payee_formatter}

    if row["label"].startswith("CARTE"):
        return format_carte(row, **kwargs)
    elif row["label"].startswith("VIR") or row["label"].startswith("PRLV"):
        return format_vir(row, **kwargs)
    elif row["label"].startswith("RETRAIT"):
        return format_retrait(row, **kwargs)
    raise Exception("Unknown transaction type")


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

    df = (
        pd.DataFrame(
            api.get_transactions_by_account(budget_id, account_id).to_dict()["data"][
                "transactions"
            ]
        )
        .assign(
            is_faulty_import=lambda df: df.import_id.apply(
                lambda x: False if pd.isnull(x) else "00:00:00" in x
            )
        )
        .query("is_faulty_import == True")
    )

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
