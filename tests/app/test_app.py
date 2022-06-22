import shutil
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
    assert "Monsieur" in response.text


def test_push_to_ynab_when_modifying_entries_modifies_the_payee_sent_to_ynab(
    client, ynab_mocker
):
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
            "payee-input-text-0": "John",  # This has changed
            "memo-input-text-0": "This is a memo",
            "payee-input-text-1": "Madame",
            "memo-input-text-1": "This is a memo that didn't exist before",  # Shouldn't have an influence.
        },
    )

    assert "John" in response.text
    assert "Monsieur" not in response.text


def test_push_to_ynab_when_modifying_entries_updates_the_db(client, ynab_mocker, db):
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

    assert len(db.get_all()) == 2  # Initial content of the DB.

    response = client.post(
        "/ynab/push",
        data={
            "payee-input-text-0": "John",
            "memo-input-text-0": "This is a memo",
            "payee-input-text-1": "Madame",
            "memo-input-text-1": "This is a memo that didn't exist before",  # Shouldn't have an influence.
        },
    )

    # The result should still be a success.
    assert "All done!" in response.text
    assert "This is a memo" in response.text

    # We should have 1 new entry: "Monsieur" became "John"
    assert len(db.get_all()) == 3
    entries = db.get_by_query(lambda data: data["original"] == "Monsieur")
    assert len(entries) == 1

    key = list(entries.keys())[0]
    entry = entries[key]
    assert entry["original"] == "Monsieur"
    assert entry["adjusted"] == "John"


def test_db_is_used_to_update_payee_name(
    client, ynab_mocker, db, transactions_csv_filepath, tmpdir
):
    # Set up: we add a "Monsieur" payee in the csv.
    line_to_add = '2022-06-09;2022-06-09;"VIR Virement de MONSIEUR";;;-10,00;;0;;0'
    modified_csv_filepath = tmpdir / "transactions.csv"
    modified_csv_filepath = shutil.copy(
        transactions_csv_filepath, modified_csv_filepath
    )
    with modified_csv_filepath.open("a", encoding="utf-8") as f:
        f.write("\n" + line_to_add)

    # First, we verify that if the DB doesn't contain the payee, then nothing happens.
    # The DB doesn't contain "Monsieur"
    assert len(db.get_by_query(lambda data: data["original"] == "Monsieur")) == 0
    # Upon making the request, "Monsieur" is in the table.
    response = client.post(
        "/csv/upload",
        data={
            "transactions-file": modified_csv_filepath.open("rb"),
            "username": "romain",
            "account-type": "perso",
        },
    )
    assert 'value="Monsieur"' in response.text

    # We update the DB to indicate that "Monsieur" should be transformed to "John"
    db.add({"original": "Monsieur", "adjusted": "John"})

    # Upon making a new request, "Monsieur" should now be gone.
    response = client.post(
        "/csv/upload",
        data={
            "transactions-file": modified_csv_filepath.open("rb"),
            "username": "romain",
            "account-type": "perso",
        },
    )
    assert 'value="John"' in response.text
    assert 'value="Monsieur"' not in response.text


def test_db_changes_are_persistent_over_multiple_requests(
    client, ynab_mocker, transactions_csv_filepath, tmpdir
):
    # Step 1: we make a first request where we change "Monsieur" into "John".
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
            "payee-input-text-0": "John",
            "memo-input-text-0": "This is a memo",
            "payee-input-text-1": "Madame",
            "memo-input-text-1": "This is a memo that didn't exist before",  # Shouldn't have an influence.
        },
    )

    # Step 2: we make a second request with original payee name "Monsieur". We expect it to be successfully
    # converted to "John".

    # (First we need to add a transaction with a Monsieur payee)
    line_to_add = '2022-06-09;2022-06-09;"VIR Virement de MONSIEUR";;;-10,00;;0;;0'
    modified_csv_filepath = tmpdir / "transactions.csv"
    modified_csv_filepath = shutil.copy(
        transactions_csv_filepath, modified_csv_filepath
    )
    with modified_csv_filepath.open("a", encoding="utf-8") as f:
        f.write("\n" + line_to_add)

    response = client.post(
        "/csv/upload",
        data={
            "transactions-file": transactions_csv_filepath.open("rb"),
            "username": "romain",
            "account-type": "perso",
        },
    )

    assert 'value="John"' in response.text
    assert 'value="Monsieur"' not in response.text
