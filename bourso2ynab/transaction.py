import re
import json
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal, Union, Optional, List

import pandas as pd


class UnknownTransactionType(Exception):
    pass


class InvalidBoursoTransaction(Exception):
    pass


TransactionType = Literal["VIR", "CARTE", "RETRAIT"]

TRANSACTION_LABEL_PATTERN = (
    r"^(?P<transaction_type>((CARTE)|(VIR)|(RETRAIT)|(PRLV)))\s"
    r"(INST\s)?"  # In case of a VIR, the format is: "VIR INST 01/01/70 Payee ..."
    r"(SEPA\s)?"  # In case of a PRLV, the format is: "PRLV SEPA Payee ..."
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
    index: int = 1  # Used to avoid importing duplicated transactions

    @staticmethod
    def from_pandas(row: pd.Series, format: bool = True):
        row = populate_dates(row)
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
    def from_label(label: str, errors: Literal["coerce", "raise"] = "coerce"):
        result = TRANSACTION_LABEL_PROG.match(label.strip())

        if result is None:
            # Unhappy path: parsing has failed.
            if errors == "raise":
                raise ValueError(f"Can't parse Transaction from label: {label}")
            return Transaction(type=None, date=None, payee=label)

        # Happy path: parsing has succedeed.
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

    @staticmethod
    def from_flask_json(entry: str):
        # Only the date has a special formating. So it's the only field we need
        # to carefully parse.
        # e.g. entry["date"] = "Thu, 01 Jan 1970 00:00:00 GMT"
        _date = datetime.strptime(entry.pop("date"), "%a, %d %b %Y %H:%M:%S %Z").date()
        return Transaction(date=_date, **entry)

    def to_html(
        self,
        with_title: bool = False,
        editable: bool = False,
        position: int = 0,
    ) -> str:
        safe_str = lambda x: x if x is not None else ""
        formatted_date = safe_str(
            self.date.strftime("%Y/%m/%d") if self.date is not None else None
        )
        formatted_amount = safe_str(
            f"{self.amount:.2f}" if self.amount is not None else None
        )
        formatted_memo = safe_str(self.memo)
        formatted_payee = safe_str(self.payee)

        lines = []

        if with_title:
            lines.extend(
                [
                    "<tr>",
                    "<th class='date'>Date</th>",
                    "<th class='amount'>Amount</th>",
                    "<th class='payee'>Payee</th>",
                    "<th class='memo'>Memo</th>",
                    "</tr>",
                ]
            )

        def maybe_to_editable(html_row: str, name: str) -> List[str]:
            if not editable:
                return [html_row]

            re_match = re.match(
                r"^<td class='(?P<klass>.*)'>(?P<content>.*?)</td>$", html_row
            )
            content = re_match.group("content")
            klass = re_match.group("klass")

            to_return = [f"<td class='{klass}'>"]
            # The "payee" field is editable with a simple input field.
            # The "memo" field can be longer, so we use a textarea.
            if name == "payee":
                to_return.extend(
                    [
                        "<input type='text'",
                        f'name="{name}-input-text-{position}"',
                        f'value="{content}"',
                        ">",
                    ]
                )
            elif name == "memo":
                to_return.extend(
                    [
                        "<textarea ",
                        f'name="{name}-input-text-{position}">',
                        content,
                        "</textarea>",
                    ]
                )

            to_return.append("</td>")
            return to_return

        lines.extend(
            [
                "<tr>",
                f"<td class='date'>{formatted_date}</td>",
                f"<td class='amount'>{formatted_amount} €</td>",
                *maybe_to_editable(
                    f"<td class='payee'>{formatted_payee}</td>", name="payee"
                ),
                *maybe_to_editable(
                    f"<td class='memo'>{formatted_memo}</td>", name="memo"
                ),
                "</tr>",
            ]
        )

        return "\n".join(lines)

    def copy_with_new_index(self, new_index: int):
        return Transaction(
            type=self.type,
            date=self.date,
            amount=self.amount,
            payee=self.payee,
            memo=self.memo,
            index=new_index,
        )

    @property
    def import_id(self) -> str:
        amount_in_mili_currency = int(round(self.amount * 1_000))
        amount_in_mili_currency_str = str(amount_in_mili_currency)
        formated_date = self.date.strftime("%Y-%m-%d")

        return f"YNAB:{amount_in_mili_currency_str}:{formated_date}:{self.index}"


def populate_dates(row: pd.Series) -> pd.Series:
    """For some transactions, the `dateVal` is set to NaN whilst the `dateOp` is valid.
    bourso2ynab primarily uses `dateVal`. As a quick bypass, we populate the `dateVal`
    field with the content of `dateOp`."""
    if "dateOp" in row.keys() and "dateVal" in row.keys():
        if pd.isnull(row["dateVal"]) and not pd.isnull(row["dateOp"]):
            row["dateVal"] = row["dateOp"]
    return row


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
    if isinstance(amount, float):
        return amount

    amount = amount.replace(",", ".")  # French uses a comma
    amount = amount.replace(" ", "")  # A space is used for separating thousands
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


def make_import_ids_unique(transactions: List[Transaction]) -> List[Transaction]:
    transactions = sorted(transactions, key=lambda t: t.import_id)
    new_transactions = [transactions[0]]

    for left, right in zip(transactions[:-1], transactions[1:]):
        if left.import_id != right.import_id:
            # The original transactions were different. Nothing to do.
            new_transactions.append(right)
            continue

        new_index = new_transactions[-1].index + 1
        new_transaction = right.copy_with_new_index(new_index)
        new_transactions.append(new_transaction)

    return new_transactions


def remove_future_transactions(transactions: List[Transaction]) -> List[Transaction]:
    today = datetime.today().date()
    return [transaction for transaction in transactions if transaction.date <= today]


def transactions_to_html(
    transactions: List[Transaction],
    with_table_tag: bool = False,
    with_title: bool = False,
    **kwargs,
) -> str:
    lines = [
        transaction.to_html(position=i, with_title=(i == 0 and with_title), **kwargs)
        for (i, transaction) in enumerate(transactions)
    ]

    if with_table_tag:
        lines = ["<table>", *lines, "</table>"]

    return "\n".join(lines)
