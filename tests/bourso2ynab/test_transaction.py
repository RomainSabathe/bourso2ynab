from datetime import date

import pytest
import pandas as pd

from bourso2ynab.transaction import (
    InvalidBoursoTransaction,
    UnknownTransactionType,
    Transaction,
    infer_transaction_type,
    is_valid_bourso_entry,
)


def test_can_create_transaction():
    transaction = Transaction(
        type="VIR",
        date=date(year=2022, month=6, day=14),
        amount=16.33,
        payee="Test",
        memo="This is a test",
    )
    transaction.payee == "Test"

    transaction = Transaction(
        type="VIR", date=date(year=2022, month=6, day=14), amount=16.33
    )
    transaction.amount == 16.33


def test_can_create_transaction_from_pandas_without_formatting():
    entry = pd.Series(
        {"dateVal": "2022-06-14", "amount": "7.5", "label": "VIR Transaction"}
    )
    transaction = Transaction.from_pandas(entry, format=False)

    assert transaction.date == date(year=2022, month=6, day=14)
    assert transaction.amount == 7.5
    assert transaction.payee == "VIR Transaction"
    assert transaction.memo is None
    assert transaction.type == "VIR"


def test_can_create_carte_transaction_from_pandas_with_formatting():
    label = "CARTE 09/06/22 SNCF INTERNET CB*5537"
    entry = pd.Series({"dateVal": "2022-06-11", "amount": "7.5", "label": label})
    transaction = Transaction.from_pandas(entry, format=True)

    assert transaction.type == "CARTE"
    assert transaction.date == date(year=2022, month=6, day=9)
    assert transaction.payee == "Sncf Internet"
    assert transaction.amount == 7.5
    assert transaction.memo is None


def test_can_create_vir_transaction_from_pandas_with_formatting_when_payee_is_available():
    label = "VIR Virement de Monsieur MACHIN"
    entry = pd.Series({"dateVal": "2022-06-11", "amount": "7.5", "label": label})
    transaction = Transaction.from_pandas(entry, format=True)

    assert transaction.type == "VIR"
    assert transaction.date == date(year=2022, month=6, day=11)
    assert transaction.payee == "Monsieur Machin"
    assert transaction.amount == 7.5
    assert transaction.memo is None


def test_can_create_vir_transaction_from_pandas_with_formatting_when_payee_is_not_available():
    label = "VIR Blabla"
    entry = pd.Series({"dateVal": "2022-06-11", "amount": "7.5", "label": label})
    transaction = Transaction.from_pandas(entry, format=True)

    assert transaction.type == "VIR"
    assert transaction.date == date(year=2022, month=6, day=11)
    assert transaction.payee is None
    assert transaction.amount == 7.5
    assert transaction.memo == "Blabla"


def test_create_transaction_from_pandas_fails():
    entry = pd.Series({"amount": "7.5", "label": "test"})
    with pytest.raises(InvalidBoursoTransaction):
        transaction = Transaction.from_pandas(entry)


def test_infer_transaction_type():
    assert infer_transaction_type("VIR Transaction I") == "VIR"
    assert infer_transaction_type("CARTE Transaction CB") == "CARTE"
    assert infer_transaction_type("RETRAIT Transaction CB") == "RETRAIT"

    assert infer_transaction_type("ViR Transaction I") == "VIR"
    assert infer_transaction_type("carte Transaction CB") == "CARTE"
    assert infer_transaction_type("reTRAIT Transaction CB") == "RETRAIT"

    assert infer_transaction_type(" ViR Transaction I") == "VIR"
    assert infer_transaction_type("carte Transaction I ") == "CARTE"

    assert infer_transaction_type("RETRAIT VIR") == "RETRAIT"


@pytest.mark.parametrize("label", ["V Transaction", "", " Cart CB", "-VIR Transaction"])
def test_infer_transaction_type_fails_on_unknown_types(label):
    with pytest.raises(UnknownTransactionType):
        infer_transaction_type(label)


def test_is_valid_bourso_entry():
    entry = pd.Series({"dateVal": "2022-06-14", "amount": "7.5", "label": "test"})
    assert is_valid_bourso_entry(entry)

    entry = pd.Series({"amount": "7.5", "label": "test"})
    assert not is_valid_bourso_entry(entry)


def test_infer_carte_transaction_from_label():
    label = "CARTE 09/06/22 SNCF INTERNET CB*5537"

    transaction = Transaction.from_label(label)
    assert transaction.type == "CARTE"
    assert transaction.date == date(year=2022, month=6, day=9)
    assert transaction.payee == "Sncf Internet"
    assert transaction.amount is None
    assert transaction.memo is None


def test_infer_vir_transaction_from_label():
    label = "VIR Virement de Monsieur MACHIN"

    transaction = Transaction.from_label(label)
    assert transaction.type == "VIR"
    assert transaction.date is None
    assert transaction.payee == "Monsieur Machin"
    assert transaction.amount is None
    assert transaction.memo is None
