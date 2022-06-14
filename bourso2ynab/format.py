import re
from typing import Optional
from datetime import datetime

import pandas as pd

from .payee_formatter import PayeeFormatter


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
