import os
import json
from typing import List
from datetime import date

from ynab_api.model.save_transactions_wrapper import SaveTransactionsWrapper

from bourso2ynab.transaction import Transaction
from bourso2ynab.ynab import (
    get_all_available_account_types,
    get_ynab_id,
    push_to_ynab,
    get_all_available_usernames,
)


def test_get_ynab_id(ynab_secrets_filepath):
    kwargs = {"username": "user1", "secrets_path": ynab_secrets_filepath}
    assert get_ynab_id(id_type="budget", **kwargs) == "abcd"
    assert get_ynab_id(id_type="accounts", account_type="perso", **kwargs) == "0123"
    assert get_ynab_id(id_type="accounts", account_type="joint", **kwargs) == "4567"

    kwargs = {"username": "user2", "secrets_path": ynab_secrets_filepath}
    assert get_ynab_id(id_type="budget", **kwargs) == "7890"
    assert get_ynab_id(id_type="accounts", account_type="perso", **kwargs) == "0000"
    assert get_ynab_id(id_type="accounts", account_type="joint", **kwargs) == "1111"


def test_get_all_available_usernames(ynab_secrets_filepath):
    usernames = get_all_available_usernames(ynab_secrets_filepath)
    assert usernames == ["user1", "user2"]


def test_get_all_available_account_types(ynab_secrets_filepath):
    account_types = get_all_available_account_types(ynab_secrets_filepath)
    assert account_types == ["perso", "joint", "fancy"]


def test_push_to_ynab(mocker):
    transactions = [
        Transaction(
            type="CARTE",
            date=date(year=1971, month=1, day=1),
            amount=20.0,
            payee="TestUser2",
            memo="Test2",
        ),
        Transaction(
            type="CARTE",
            date=date(year=1971, month=1, day=1),
            amount=20.0,
            payee="TestUser3",
            memo="Test3",
        ),
        Transaction(
            type="CARTE",
            date=date(year=1970, month=1, day=1),
            amount=10.0,
            payee="TestUser1",
            memo="Test1",
        ),
    ]

    def mock_create_transaction(
        self, budget_id: str, transactions: SaveTransactionsWrapper, **kwargs
    ):
        return transactions.to_dict()["transactions"]

    os.environ["YNAB_API_KEY"] = "1234"
    mocker.patch(
        "bourso2ynab.ynab.TransactionsApi.create_transaction", mock_create_transaction
    )

    returned_transactions = push_to_ynab(
        transactions, account_id="01234", budget_id="1230"
    )

    assert returned_transactions[0]["import_id"] == "YNAB:10000:1970-01-01:1"
    assert returned_transactions[1]["import_id"] == "YNAB:20000:1971-01-01:1"
    assert returned_transactions[2]["import_id"] == "YNAB:20000:1971-01-01:2"

    assert returned_transactions[0]["approved"] == True
    assert returned_transactions[0]["cleared"] == "uncleared"
    assert returned_transactions[0]["payee_name"] == "TestUser1"


def test_push_to_ynab_filter_out_future_transactions(mocker):
    transactions = [
        Transaction(
            type="CARTE",
            date=date(year=1970, month=1, day=1),
            amount=10.0,
            payee="TestUser1",
            memo="Test1",
        ),
        Transaction(
            type="CARTE",
            date=date(year=2023, month=4, day=3),
            amount=20.0,
            payee="TestUser3",
            memo="Test3",
        ),
    ]
    today = date(year=2023, month=4, day=1)

    def mock_create_transaction(
        self, budget_id: str, transactions: SaveTransactionsWrapper, **kwargs
    ):
        return transactions.to_dict()["transactions"]

    os.environ["YNAB_API_KEY"] = "1234"
    mocker.patch(
        "bourso2ynab.ynab.TransactionsApi.create_transaction", mock_create_transaction
    )

    returned_transactions = push_to_ynab(
        transactions, account_id="01234", budget_id="1230"
    )

    assert len(returned_transactions) == 1
    assert returned_transactions[0]["import_id"] == "YNAB:10000:1970-01-01:1"
    assert returned_transactions[0]["approved"] == True
    assert returned_transactions[0]["cleared"] == "uncleared"
    assert returned_transactions[0]["payee_name"] == "TestUser1"
