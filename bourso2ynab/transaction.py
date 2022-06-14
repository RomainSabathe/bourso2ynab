import re
from typing import Literal
from dataclasses import dataclass
from datetime import date, datetime

import pandas as pd


class UnknownTransactionType(Exception):
    pass


class InvalidBoursoTransaction(Exception):
    pass


TransactionType = Literal["VIR", "CARTE", "RETRAIT"]

TRANSACTION_LABEL_PATTERN = (
    r"^(?P<transaction_type>((CARTE)|(VIR)|(RETRAIT))) "
    r"(?P<date>\d{2}/\d{2}/\d{2}) "
    r"(?P<payee>.+) "
    r"CB\*\d{4}$"
).strip()
TRANSACTION_LABEL_PROG = re.compile(TRANSACTION_LABEL_PATTERN)


@dataclass
class Transaction:
    type: TransactionType
    date: date
    amount: float = None
    payee: str = None
    memo: str = None

    @staticmethod
    def from_pandas(row: pd.Series, format: bool = True):
        if not is_valid_bourso_entry(row):
            raise InvalidBoursoTransaction
        if not format:
            return Transaction(
                type=infer_transaction_type(row.label),
                date=datetime.strptime(row.dateVal, "%Y-%m-%d").date(),
                amount=float(row.amount),
                payee=row.label,
            )

    @staticmethod
    def from_label(label: str):
        result = TRANSACTION_LABEL_PROG.match(label.strip())
        result = result.groupdict()
        return Transaction(
            type=result["transaction_type"],
            payee=result["payee"].strip().title(),
            date=datetime.strptime(result["date"], "%d/%m/%y").date(),
        )


def is_valid_bourso_entry(row: pd.Series) -> bool:
    for key in ["dateVal", "label", "amount"]:
        if key not in row.keys() or pd.isnull(row[key]):
            return False
    return True


def infer_transaction_type(transaction_label: str) -> TransactionType:
    # In: "CARTE Franprix CB*"
    # Out: "CARTE"
    transaction_label = transaction_label.strip().lower()
    for transaction_type in ["VIR", "CARTE", "RETRAIT"]:
        if transaction_label.startswith(f"{transaction_type} ".lower()):
            return transaction_type
    raise UnknownTransactionType
