from datetime import date

import pytest
import pandas as pd

from bourso2ynab.transaction import (
    InvalidBoursoTransaction,
    UnknownTransactionType,
    Transaction,
    infer_transaction_type,
    is_valid_bourso_entry,
    make_import_ids_unique,
    format_amount,
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


@pytest.mark.parametrize(
    ("label", "expected_payee"),
    [
        ("CARTE 01/01/70 TFL TRAVEL CH CB*0000", "Tfl Travel Ch"),
        ("CARTE 01/01/70 M&S SIMPLY FOOD - CB*0000", "M&S Simply Food"),
        ("CARTE 01/01/70 ZTL*NM BURGER OPS CB*0000", "Nm Burger Ops"),
        ("CARTE 01/01/70 ZTL*Redemption Ro CB*0000", "Redemption Ro"),
        ("CARTE 01/01/70 IZ *TOSSED CB*0000", "Tossed"),
        ("CARTE 01/01/70 MARKS&SPENCER PLC CB*0000", "Marks&Spencer"),
        ("CARTE 01/01/70 FULLER SMITH & TU CB*0000", "Fuller Smith & Tu"),
        ("CARTE 01/01/70 PAYPAL *ROMAIN.S CB*0000", "Romain.S"),
        ("CARTE 01/01/70 PHARM REPUBLIQUE2 CB*0000", "Pharm Republique"),
        ("CARTE 01/01/70 VELIB METROPOLE 2 CB*0000", "Velib Metropole"),
        ("CARTE 01/01/70 FRANPRIX 5196 CB*0000", "Franprix"),
        ("CARTE 01/01/70 RELAY 340356SC 4 CB*0000", "Relay"),
        ("CARTE 01/01/70 SARL T.L.N. CB*0000", "Sarl T.L.N."),
        ("CARTE 01/01/70 FNAC SC 4 CB*0000", "Fnac"),
        ("VIR INST ALAN SA", "Alan"),
        ("CARTE 01/01/70 SC-ESSENTIEL DA CB*0000", "Sc-Essentiel Da"),
        ("CARTE 01/01/70 VIEUX CAMPEUR 4 CB*0000", "Vieux Campeur"),
        ("CARTE 01/01/70 PHIE MET M BIZOT2 CB*0000", "Phie Met M Bizot"),
        ("CARTE 01/01/70 AMAZON PAYMENTS 2 CB*0000", "Amazon Payments"),
        ("CARTE 01/01/70 SUMUP *DOCTEUR R CB*0000", "Docteur R"),
        ("CARTE 01/01/70 DOCKYARDS_TICKETS CB*0000", "Dockyards_Tickets"),
        ("CARTE 01/01/70 ECGCOSTA4017507 CB*0000", "Ecgcosta"),
        ("CARTE 01/01/70 SUMUP *MACO CB*0000", "Maco"),
    ],
)
def test_transaction_correctly_parses_label(label, expected_payee):
    transaction = Transaction.from_label(label)
    assert transaction.payee == expected_payee


@pytest.mark.parametrize(
    ("label", "expected_memo"),
    [
        ("VIR Loyer", "Loyer"),
        ("VIR Remboursement chasse aux oeufs e", "Remboursement chasse aux oeufs e"),
        # I can't manage to make this to work atm :(
        # ("VIR Remboursemnt loyer (63) electric", "Remboursment loyer (63) electric"),
        ("VIR Splurge :D", "Splurge :D"),
        ("VIR Financement pour l'Ours", "Financement pour l'Ours"),
    ],
)
def test_transaction_correctly_parses_virs(label, expected_memo):
    transaction = Transaction.from_label(label)
    assert transaction.payee is None
    assert transaction.memo == expected_memo


def test_transaction_recognizes_paypal():
    label = "CARTE 01/01/70 PAYPAL *ROMAIN.S CB*0000"
    expected_payee = "Romain.S"
    expected_memo = "(via Paypal)"

    transaction = Transaction.from_label(label)
    assert transaction.payee == expected_payee
    assert transaction.memo == expected_memo


def test_import_id():
    transaction = Transaction(
        type="CARTE", date=date(year=2022, month=6, day=14), amount=16.33
    )

    assert transaction.import_id == "YNAB:16330:2022-06-14:1"


def test_copy_with_new_index():
    transaction = Transaction(
        type="CARTE", date=date(year=2022, month=6, day=14), amount=16.33
    )
    assert transaction.type == "CARTE"
    assert transaction.date == date(year=2022, month=6, day=14)
    assert transaction.amount == 16.33
    assert transaction.index == 1

    new_transaction = transaction.copy_with_new_index(2)
    assert new_transaction.type == "CARTE"
    assert new_transaction.date == date(year=2022, month=6, day=14)
    assert new_transaction.amount == 16.33
    assert new_transaction.index == 2


def test_make_import_ids_unique():
    transactions = [
        Transaction(type="CARTE", date=date(year=1970, month=1, day=1), amount=10.0),
        Transaction(type="CARTE", date=date(year=1972, month=1, day=1), amount=20.0),
        Transaction(type="CARTE", date=date(year=1971, month=1, day=1), amount=10.0),
        Transaction(type="CARTE", date=date(year=1972, month=1, day=1), amount=20.0),
        Transaction(type="CARTE", date=date(year=1970, month=1, day=1), amount=10.0),
        Transaction(type="CARTE", date=date(year=1972, month=1, day=1), amount=20.0),
    ]
    transactions = make_import_ids_unique(transactions)
    assert transactions[0].import_id == "YNAB:10000:1970-01-01:1"
    assert transactions[1].import_id == "YNAB:10000:1970-01-01:2"
    assert transactions[2].import_id == "YNAB:10000:1971-01-01:1"
    assert transactions[3].import_id == "YNAB:20000:1972-01-01:1"
    assert transactions[4].import_id == "YNAB:20000:1972-01-01:2"
    assert transactions[5].import_id == "YNAB:20000:1972-01-01:3"


def test_transaction_to_html_non_editable():
    transaction = Transaction(
        type="CARTE",
        date=date(year=1970, month=1, day=1),
        amount=12.34,
        payee="Monsieur",
        memo="This is a test",
    )

    expected_lines = [
        "<tr>",
        "<td>1970/01/01</td>",
        "<td>12.34</td>",
        "<td>Monsieur</td>",
        "<td>This is a test</td>",
        "</tr>",
    ]

    assert "\n".join(expected_lines) == transaction.to_html()


def test_transaction_to_html_non_editable_with_title():
    transaction = Transaction(
        type="CARTE",
        date=date(year=1970, month=1, day=1),
        amount=12.34,
        payee="Monsieur",
        memo="This is a test",
    )

    expected_lines = [
        "<tr>",
        "<th>Date</th>",
        "<th>Amount</th>",
        "<th>Payee</th>",
        "<th>Memo</th>",
        "</tr>",
        "<tr>",
        "<td>1970/01/01</td>",
        "<td>12.34</td>",
        "<td>Monsieur</td>",
        "<td>This is a test</td>",
        "</tr>",
    ]

    assert "\n".join(expected_lines) == transaction.to_html(with_title=True)


def test_transaction_to_html_editable():
    transaction = Transaction(
        type="CARTE",
        date=date(year=1970, month=1, day=1),
        amount=12.34,
        payee="Monsieur",
        memo="This is a test",
    )

    expected_lines = [
        "<tr>",
        "<td>1970/01/01</td>",
        "<td>12.34</td>",
        "<td>",
        "<input ",
        'type="text"',
        'name="payee-input-text"',
        'value="Monsieur"',
        "</td>",
        "<td>",
        "<input ",
        'type="text"',
        'name="memo-input-text"',
        'value="This is a test"',
        "</td>",
        "</tr>",
    ]

    assert "\n".join(expected_lines) == transaction.to_html(editable=True)


def test_format_amount():
    assert format_amount("-2,00") == -2.00
    assert format_amount("-2") == -2.00
    assert format_amount("-2.00") == -2.00
    assert format_amount("2,12") == 2.12
