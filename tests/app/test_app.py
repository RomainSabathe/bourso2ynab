from datetime import date

from flask import session

from bourso2ynab.transaction import Transaction
from app.main import _get_transactions_from_session


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


# def test_push_to_ynab(client):
#     response = client.post(
#         "/ynab/push",
#         data={
#             "payee-input-text-0": "Monsieur",
#             "memo-input-text-0": "This is a memo",
#             "payee-input-text-1": "Madame",
#             "memo-input-text-1": "",
#         },
#     )

#     import ipdb; ipdb.set_trace()
#     pass
