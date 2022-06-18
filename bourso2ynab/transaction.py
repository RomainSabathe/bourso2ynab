import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal, Union, Optional

import pandas as pd


class UnknownTransactionType(Exception):
    pass


class InvalidBoursoTransaction(Exception):
    pass


TransactionType = Literal["VIR", "CARTE", "RETRAIT"]

TRANSACTION_LABEL_PATTERN = (
    r"^(?P<transaction_type>((CARTE)|(VIR)|(RETRAIT)))\s?"
    r"(INST\s)?"  # In case of a VIR, the format is: "VIR INST 01/01/70 Payee ..."
    r"(?P<date>\d{2}/\d{2}/\d{2})?\s?"
    r"(ZTL\*)?"
    r"(IZ \*)?"
    r"(SUMUP \*)?"
    r"(?P<is_paypal>PAYPAL \*)?"
    r"(?P<payee>.+?)\s?"
    r"(SC\s?)?"
    r"(SA\s?)?"
    r"(PLC\s?)?"
    r"(\d+(\D+)?\s?(\d\s?)?)?"  # Catches the random digits and letters after the payee name.
    r"(-\s?)?"
    r"(CB\*\d{4})?$"
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
                date=format_date_from_dateVal(row.dateVal),
                amount=format_amount(row.amount),
                payee=row.label,
            )

        tmp_formatted_transaction = Transaction.from_label(row.label)
        _date = (
            tmp_formatted_transaction.date
            if tmp_formatted_transaction.date is not None
            else format_date_from_dateVal(row.dateVal)
        )
        return Transaction(
            date=_date,
            amount=format_amount(row.amount),
            type=tmp_formatted_transaction.type,
            payee=tmp_formatted_transaction.payee,
            memo=tmp_formatted_transaction.memo,
        )

    @staticmethod
    def from_label(label: str):
        result = TRANSACTION_LABEL_PROG.match(label.strip())
        result = result.groupdict()

        is_VIR = result["transaction_type"] == "VIR"

        formatted_result = {
            "date": format_date_from_label(result.get("date")),
            "payee": format_payee_from_label(result.get("payee"), is_VIR=is_VIR),
            "type": result["transaction_type"],
        }

        # TODO: add some doc.
        if is_VIR and formatted_result["payee"] is None:
            formatted_result["memo"] = result["payee"]

        if not is_VIR and result.get("is_paypal") is not None:
            formatted_result["memo"] = "(via Paypal)"

        return Transaction(**formatted_result)


def format_payee_from_label(payee: Optional[str], is_VIR: bool) -> Optional[str]:
    if payee is None:
        return payee

    payee = payee.strip()
    # VIRs have special payee formattings
    if is_VIR:
        if payee.startswith("Virement de "):
            # E.g. "VIR INST Virement de ROMAIN S"
            payee = payee[12:]  # Removing "Virement de"
        elif payee == payee.upper():
            # When the entire payee name is capitalized, it can be assumed that it's
            # because it is the actual payee name.
            # E.g: "VIR INST 01/01/70 ALAN SA"
            pass
        else:
            # In this case, we don't have much information about the payee.
            # e.g.: "VIR Loyer"
            # e.g.: "VIR INST Remboursement pour..."
            return None

    return payee.title()


def format_date_from_label(_date: Optional[str]) -> Optional[date]:
    if _date is None:
        return _date

    return datetime.strptime(_date, "%d/%m/%y").date()


def format_date_from_dateVal(_date: Optional[str]) -> Optional[date]:
    if _date is None:
        return _date

    return datetime.strptime(_date, "%Y-%m-%d").date()


def format_amount(amount: Union[float, str]) -> float:
    return float(amount)


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
