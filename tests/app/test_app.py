from datetime import date

from flask import session

from bourso2ynab.transaction import Transaction


def test_display_home_page(client):
    response = client.get("/")
    assert "<h1>Bourso2Ynab</h1>" in response.text
    assert "Select your Boursorama transactions" in response.text


def test_submit_csv_displays_correct_info(client, transactions_csv_filepath):
    response = client.post(
        "/csv/upload",
        data={
            "transactions-file": transactions_csv_filepath.open("rb"),
            "username": "romain",
            "account-type": "perso",
        },
    )

    assert "<table>" in response.text
    assert "<td>2022/06/13</td>" in response.text
    assert "<td>2022/06/11</td>" in response.text
    assert 'value="Ratp"' in response.text


def test_submit_csv_correctly_populate_session(client, transactions_csv_filepath):
    with client:  # Why the context manager? To be able to retrieve the session.
        response = client.post(
            "/csv/upload",
            data={
                "transactions-file": transactions_csv_filepath.open("rb"),
                "username": "romain",
                "account-type": "perso",
            },
        )
        transactions = session["transactions"]
        username = session["username"]
        account_type = session["account-type"]

    assert len(transactions) == 5
    assert transactions[0].payee == "Franprix"
    assert transactions[0].amount == -11.64
    assert transactions[1].payee == "Monsieur Fromage"
    assert transactions[1].amount == -10.00

    assert username == "romain"
    assert account_type == "perso"


def test_push_to_ynab_without_modifying_entries(client, ynab_mocker):
    with client.session_transaction() as session:
        session["transactions"] = [
            Transaction(
                type="CARTE",
                amount=-12.34,
                date=date(year=1970, month=1, day=1),
                payee="Monsieur",
                memo="This is a memo",
            ),
            Transaction(
                type="CARTE",
                amount=-2.43,
                date=date(year=1971, month=1, day=1),
                payee="Madame",
            ),
        ]
        session["username"] = "user1"
        session["account-type"] = "perso"

    response = client.post(
        "/ynab/push",
        data={
            "payee-input-text-0": "Monsieur",
            "memo-input-text-0": "This is a memo",
            "payee-input-text-1": "Madame",
            "memo-input-text-1": "",
        },
    )

    assert "All done!" in response.text
    assert "This is a memo" in response.text
