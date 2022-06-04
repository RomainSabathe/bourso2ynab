import re
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Literal, Optional

import ynab
import click
import numpy as np
import pandas as pd


@click.command()
@click.option("-i", "filepath", type=click.Path(exists=True), required=True)
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
def main(filepath, username, account_type, upload):
    df = pd.read_csv(filepath, sep=";")
    formated_df = df.apply(format_transaction, axis="columns").query("Payee != 'Test'")
    remaining_idx = df.index.difference(formated_df.index)
    df = df.loc[remaining_idx]
    assert len(df) == 0
    formated_df.to_csv(
        "C:/Users/Romain/Downloads/formated_transactions.csv", index=False
    )
    if upload:
        push_to_ynab(
            formated_df,
            account_id=get_ynab_id("account", username, account_type),
            budget_id=get_ynab_id("budget", username),
        )


def format_vir(row: pd.Series) -> pd.Series:
    pattern = r"^(?P<vir_type>(VIR)|(PRLV))( (INST)| (SEPA))? ((MLE )|(MR ))?(?P<description>[\w| |\d|\(|\)|'|:|-]+)$"
    prog = re.compile(pattern)
    result = prog.match(row["label"])
    if result is None:
        raise Exception(f"Can't parse Vir transaction: {row['label']}")
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
    if "Payee" in extra.keys():
        extra["Payee"] = extra["Payee"].replace(
            "***REMOVED*** ***REMOVED*** Ac", "***REMOVED***"
        )
    if "Payee" in extra.keys():
        extra["Payee"] = extra["Payee"].replace("Alan Sa", "Alan")

    entry = {
        "Date": row["dateVal"],
        "Amount": float(row["amount"].replace(",", ".").replace(" ", "")),
        **extra,
    }
    return pd.Series(entry)


def format_carte(row: pd.Series) -> pd.Series:
    pattern = r"^CARTE (?P<date>\d{2}/\d{2}/\d{2}) (ZTL)?\*?(?P<payee>\d?([A-Za-z]| |\_|\.|&|-|\*|')+)I?\d? ?(\([A-Za-z]+\)?)? ?(GB)?\d*(SC)? ?\d?(LTD)? ?CB\*\d{4}$"
    prog = re.compile(pattern)
    result = prog.match(row["label"])
    if result is None:
        raise Exception(f"Can't parse Carte transaction: {row['label']}")
    result = result.groupdict()
    date = datetime.strptime(result["date"], "%d/%m/%y")
    entry = {
        "Date": date.strftime("%Y-%m-%d"),
        "Payee": result["payee"].replace("_", " ").strip().title(),
        "Memo": "",
        "Amount": float(row["amount"].replace(",", ".").replace(" ", "")),
    }
    if "paypal" in entry["Payee"].lower():
        entry["Payee"] = entry["Payee"].replace("Paypal ", "")
        entry["Memo"] += " (via Paypal)"
    entry["Payee"] = (
        entry["Payee"]
        .replace("*", "")
        .replace("A. Miam Miam", "Alain Miam Miam")
        .replace("Alan Sa", "Alan")
        .replace("Amagicom", "Mullvad")
        .replace("Amazon Eu Sarl", "Amazon")
        .replace("Amazon Payments", "Amazon")
        .replace("Aylan", "La Margherita Michel Bizot")
        .replace("Camping L Estela", "Camping l'Estela")
        .replace("Carrefour Expres", "Carrefour Express")
        .replace("Concessions Gare", "Paul")
        .replace("Curb Svc Long Isa", "Curb Mobility")
        .replace("Eurostar Internat", "Eurostar")
        .replace("Fnac Sc", "Fnac")
        .replace("France Billetvad", "France Billet")
        .replace("Lattice L", "The Secret City")
        .replace("Monop", "Monoprix")
        .replace("Netflix.Com", "Netflix")
        .replace("Paddle.Co", "ProjectionLab")
        .replace("Phie Met M Bizot", "Pharmacie du Metro Michel Bizot")
        .replace("Ratp", "RATP")
        .replace("Sarl T.L.N.", "Camping Les Terrasses du Lac")
        .replace("Sc-Essentiel Da", "L'Essentiel")
        .replace("Sc-Ravitailleur", "Le Ravitailleur")
        .replace("Sc-Vieuxcamp Ec", "Au Vieux Campeur")
        .replace("Shetland Fringan", "J'peux pas J'ai poney")
        .replace("Sncf Tgv.Com", "SNCF")
        .replace("Sncf Web Mobile", "SNCF")
        .replace("Sumup Docteur R", "Dr Robert Thebault")
        .replace("Sumup Gourmandi", "Gourmandises Mexicaines")
        .replace("Tfl Travel Ch", "TFL")
        .replace("The Frog & Brit", "The Frog & British Library")
        .replace("Ugc Bornes", "UGC")
        .replace("Vieux Campeur", "Au Vieux Campeur")
        .replace("ZtlCeylon", "Pavilion Cafe")
        .replace("Railway", "Railway Tavern")
        .replace("Iz Tossed", "Tossed")
        .replace("Tfl Cycle Hire", "TFL Cycle Hire")
        .replace("Farmer J", "Farmer J")
        .replace("The Wellington Pu", "The Wellington Pub")
        .replace("Marks&Spencer Plc", "Marks & Spencer")
        .replace("Fuller Smith & Tu", "The Astronomer")
        .replace("***REMOVED***.K", "***REMOVED*** ***REMOVED***")
        .replace("Pharm Republique", "Pharmacie de la Place de la République")
        .replace("Velib Metropole", "Velib Metropole")
        # Dirty
        .replace("Au Au Vieux Campeur", "Au Vieux Campeur")
        .replace("Monoprixrix", "Monoprix")
    )

    if entry["Payee"] == "Pavilion Cafe":
        entry["Memo"] += " (in Victoria Park)"

    entry["Memo"] = entry["Memo"].strip()
    return pd.Series(entry)


def format_retrait(row: pd.Series) -> pd.Series:
    pattern = r"^RETRAIT (DAB)? (?P<date>\d{2}/\d{2}/\d{2}) \d*(?P<payee>([A-Za-z]| |\_|\.|&|-|\*|')+)I?\d? (GB)?\d* ?(LTD)? ?CB\*\d{4}$"
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


def format_transaction(row: pd.Series) -> pd.Series:
    if row["label"].startswith("CARTE"):
        return format_carte(row)
    elif row["label"].startswith("VIR") or row["label"].startswith("PRLV"):
        return format_vir(row)
    elif row["label"].startswith("RETRAIT"):
        return format_retrait(row)
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
    configuration.api_key[
        "Authorization"
    ] = "***REMOVED***"
    configuration.api_key_prefix["Authorization"] = "Bearer"
    api = ynab.TransactionsApi(ynab.ApiClient(configuration))

    ynab_transactions = ynab.BulkTransactions(
        [
            ynab.SaveTransaction(
                account_id=account_id,
                date=transaction["Date"],
                amount=int(transaction["Amount"] * 1_000),
                payee_name=transaction["Payee"],
                memo=transaction["Memo"],
                approved=True,
                import_id=transaction["import_id"],
            )
            for _, transaction in transactions.iterrows()
        ]
    )

    try:
        api_response = api.bulk_create_transactions(budget_id, ynab_transactions)
        print(api_response)
    except ynab.rest.ApiException as e:
        print("Exception when calling TransactionsApi->create_transaction: %s\n" % e)


if __name__ == "__main__":
    main()
