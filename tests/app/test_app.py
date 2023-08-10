import shutil
from pathlib import Path
from datetime import date

from flask import session

from bourso2ynab.ynab import get_ynab_id
from bourso2ynab.transaction import Transaction
from app.main import (
    _update_transactions_based_on_db,
    _update_transactions_based_on_form,
    _update_db_based_on_transactions_changes,
)


def test_display_home_page(client):
    response = client.get("/")
    assert "<h1>Bourso2Ynab</h1>" in response.text
    assert "Select your Boursorama transactions" in response.text


def test_home_page_shows_available_users(client, ynab_mocker):
    response = client.get("/")
    assert 'value="user1"' in response.text
    assert 'id="user1-username-radio' in response.text
    assert "User1" in response.text

    assert 'value="user2"' in response.text
    assert 'id="user2-username-radio' in response.text
    assert "User2" in response.text


def test_home_page_shows_available_accounts(client, ynab_mocker):
    response = client.get("/")
    assert 'value="perso"' in response.text
    assert 'id="perso-account-type-radio' in response.text
    assert "Perso" in response.text

    assert 'value="joint"' in response.text
    assert 'id="joint-account-type-radio' in response.text
    assert "Joint" in response.text

    assert 'value="fancy"' in response.text
    assert 'id="fancy-account-type-radio' in response.text
    assert "Fancy" in response.text


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


def test_push_to_ynab_with_perso_account_updates_one_account(
    client,
    mocker,
    ynab_secrets_filepath,
    ynab_mocker,
):
    global call_counter
    call_counter = 0

    def mock_push_to_ynab(transactions, account_id, budget_id):
        global call_counter
        call_counter += 1
        return call_counter

    mocker.patch("app.main._push_to_ynab", mock_push_to_ynab)

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

    assert call_counter == 1


def test_push_to_ynab_with_joint_account_updates_two_accounts(
    client,
    mocker,
    ynab_secrets_filepath,
    ynab_mocker,
):
    global call_counter
    call_counter = 0

    def mock_push_to_ynab(transactions, account_id, budget_id):
        global call_counter
        call_counter += 1
        return call_counter

    mocker.patch("app.main._push_to_ynab", mock_push_to_ynab)

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
        session["account-type"] = "joint"

    response = client.post(
        "/ynab/push",
        data={
            "payee-input-text-0": "Monsieur",
            "memo-input-text-0": "This is a memo",
            "payee-input-text-1": "Madame",
            "memo-input-text-1": "",
        },
    )

    assert call_counter == 2


def test_update_transactions_based_on_form():
    transactions = [
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

    form_result = {
        "payee-input-text-0": "John",  # This has changed
        "memo-input-text-0": "This is a memo",
        "payee-input-text-1": "Madame",
        "memo-input-text-1": "This is a memo that didn't exist before",  # Changed.
    }

    updated_transactions = _update_transactions_based_on_form(transactions, form_result)

    assert transactions[0].payee == "Monsieur"
    assert updated_transactions[0].payee == "John"

    assert transactions[0].memo == "This is a memo"
    assert updated_transactions[0].memo == "This is a memo"

    assert transactions[1].payee == "Madame"
    assert updated_transactions[1].payee == "Madame"

    assert transactions[1].memo is None
    assert updated_transactions[1].memo == "This is a memo that didn't exist before"


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
            "transactions-file": modified_csv_filepath.open("rb"),
            "username": "romain",
            "account-type": "perso",
        },
    )

    assert 'value="John"' in response.text
    assert 'value="Monsieur"' not in response.text


def test_update_db_based_on_transactions_changes(db):
    # The DB doesn't contain the "Monsieur" entry.
    assert len(db.get_by_query(lambda data: data["original"] == "Monsieur")) == 0

    transactions = [
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

    updated_transactions = [
        Transaction(
            type="CARTE",
            amount=-12.34,
            date=date(year=1970, month=1, day=1),
            payee="John",
            memo="This is a memo",
        ),
        Transaction(
            type="CARTE",
            amount=-2.43,
            date=date(year=1971, month=1, day=1),
            payee="Madame",
            memo="This is a memo that didn't exist before",
        ),
    ]

    _update_db_based_on_transactions_changes(transactions, updated_transactions)

    entries = db.get_by_query(lambda data: data["original"] == "Monsieur")
    assert len(entries) == 1

    key = list(entries.keys())[0]
    entry = entries[key]
    assert entry["original"] == "Monsieur"
    assert entry["adjusted"] == "John"


def test_update_db_based_on_transactions_changes_when_entry_already_exists(db):
    # The DB contains a "Sncf" entry
    assert len(db.get_all()) == 2
    entries = db.get_by_query(lambda data: data["original"] == "Sncf")
    assert len(entries) == 1

    key = list(entries.keys())[0]
    entry = entries[key]
    assert entry["original"] == "Sncf"
    assert entry["adjusted"] == "SNCF"

    transactions = [
        Transaction(
            type="CARTE",
            amount=-12.34,
            date=date(year=1970, month=1, day=1),
            payee="Sncf",
            memo="This is a memo",
        ),
        Transaction(
            type="CARTE",
            amount=-2.43,
            date=date(year=1971, month=1, day=1),
            payee="Madame",
        ),
    ]

    updated_transactions = [
        Transaction(
            type="CARTE",
            amount=-12.34,
            date=date(year=1970, month=1, day=1),
            payee="Chemin de Fer",
            memo="This is a memo",
        ),
        Transaction(
            type="CARTE",
            amount=-2.43,
            date=date(year=1971, month=1, day=1),
            payee="Madame",
            memo="This is a memo that didn't exist before",
        ),
    ]

    _update_db_based_on_transactions_changes(transactions, updated_transactions)

    assert len(db.get_all()) == 2
    entries = db.get_by_query(lambda data: data["original"] == "Sncf")
    assert len(entries) == 1

    key = list(entries.keys())[0]
    entry = entries[key]
    assert entry["original"] == "Sncf"
    assert entry["adjusted"] == "Chemin de Fer"


def test_update_transactions_based_on_db(db):
    db.add({"original": "Monsieur", "adjusted": "John"})

    transactions = [
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

    updated_transactions = _update_transactions_based_on_db(transactions)

    assert transactions[0].payee == "Monsieur"
    assert updated_transactions[0].payee == "John"

    assert transactions[0].memo == "This is a memo"
    assert updated_transactions[0].memo == "This is a memo"

    assert transactions[1].payee == "Madame"
    assert updated_transactions[1].payee == "Madame"

    assert transactions[1].memo is None
    assert updated_transactions[1].memo is None


def test_db_doesnt_get_updated_when_original_payee_is_empty(client, ynab_mocker, db):
    with client.session_transaction() as session:
        session["transactions"] = [
            Transaction(
                type="CARTE",
                amount=-12.34,
                date=date(year=1970, month=1, day=1),
                payee="",
                memo="This is a memo",
            )
        ]
        session["username"] = "user1"
        session["account-type"] = "perso"

    assert len(db.get_all()) == 2  # Initial content of the DB.

    response = client.post(
        "/ynab/push",
        data={"payee-input-text-0": "John", "memo-input-text-0": "This is a memo"},
    )

    # The result should still be a success.
    assert "All done!" in response.text
    assert "This is a memo" in response.text

    # We shouldn't have a new entry.
    assert len(db.get_all()) == 2
    entries = db.get_by_query(lambda data: data["original"] == "")
    assert len(entries) == 0


def test_db_entry_gets_updated_again_upon_new_adjustment(
    client, ynab_mocker, transactions_csv_filepath, tmpdir, db
):
    # Setting up: creating a simple transactions.csv file with only 1 line.
    header = transactions_csv_filepath.read_text("utf-8").split("\n")[0]
    line_to_add = '2022-06-09;2022-06-09;"VIR Virement de MONSIEUR";;;-10,00;;0;;0'
    csv_filepath = tmpdir / "transactions.csv"
    csv_filepath.write_text("\n".join([header, line_to_add]), encoding="utf-8")

    # At first, no "Monsieur" entry should be in the db.
    entries = db.get_by_query(lambda data: data["original"] == "Monsieur")
    assert len(entries) == 0

    # Step 1: we make a first request where we change "Monsieur" into "John".
    with client.session_transaction() as session:
        response = client.post(
            "/csv/upload",
            data={
                "username": "user1",
                "account-type": "perso",
                "transactions-file": csv_filepath.open("rb"),
            },
        )
        assert "Monsieur" in response.text

        # Changing "Monsieur" into "John".
        response = client.post(
            "/ynab/push", data={"payee-input-text-0": "John", "memo-input-text-0": ""}
        )

        # Checking the impact on the db.
        entries = db.get_by_query(lambda data: data["original"] == "Monsieur")
        assert len(entries) == 1
        key = list(entries.keys())[0]
        entry = entries[key]
        assert entry["original"] == "Monsieur"
        assert entry["adjusted"] == "John"

    # Step 2: we make a new request where we change the entry into "David"
    # Now, it's tricky:
    #  - The initial csv contains the name "Monsieur".
    #  - The HTML form should display "John" because the DB contains a Monsieur --> John rule.
    #  - However, upon changing to "David", the DB should now contain a Monsieur --> David rule.
    with client.session_transaction() as session:
        # The initial csv contains the name "Monsieur"
        response = client.post(
            "/csv/upload",
            data={
                "username": "user1",
                "account-type": "perso",
                "transactions-file": csv_filepath.open("rb"),
            },
        )
        # The HTML form should display "John" because the DB contains
        # a Monsieur --> John rule.
        assert "John" in response.text
        assert "Monsieur" not in response.text

        # Changing "Monsieur" into "David".
        response = client.post(
            "/ynab/push", data={"payee-input-text-0": "David", "memo-input-text-0": ""}
        )

        # The DB should now contain a Monsieur --> David rule.
        entries = db.get_by_query(lambda data: data["original"] == "Monsieur")
        assert len(entries) == 1
        key = list(entries.keys())[0]
        entry = entries[key]
        assert entry["original"] == "Monsieur"
        assert entry["adjusted"] == "David"

        # Moreover, we should not have a "John"-related rule.
        entries = db.get_by_query(lambda data: data["original"] == "John")
        assert len(entries) == 0


def test_db_doesnt_get_updated_with_useless_entries(
    client, ynab_mocker, transactions_csv_filepath, tmpdir, db
):
    # Setting up: creating a simple transactions.csv file with only 1 line.
    header = transactions_csv_filepath.read_text("utf-8").split("\n")[0]
    line_to_add = '2022-06-09;2022-06-09;"VIR Virement de MONSIEUR";;;-10,00;;0;;0'
    csv_filepath = tmpdir / "transactions.csv"
    csv_filepath.write_text("\n".join([header, line_to_add]), encoding="utf-8")

    # At first, no "Monsieur" entry should be in the db.
    entries = db.get_by_query(lambda data: data["original"] == "Monsieur")
    assert len(entries) == 0

    # We make a first request where we don't change the value of "Monsieur"
    with client.session_transaction() as session:
        response = client.post(
            "/csv/upload",
            data={
                "username": "user1",
                "account-type": "perso",
                "transactions-file": csv_filepath.open("rb"),
            },
        )
        assert "Monsieur" in response.text

        response = client.post(
            "/ynab/push",
            data={"payee-input-text-0": "Monsieur", "memo-input-text-0": ""},
        )

        # We still should have no "Monsieur"-related entries in the db.
        entries = db.get_by_query(lambda data: data["original"] == "Monsieur")
        assert len(entries) == 0
