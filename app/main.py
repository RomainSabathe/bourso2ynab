from typing import List
from copy import deepcopy

from werkzeug.datastructures import ImmutableMultiDict
from flask import Blueprint, render_template, request, session

from app.database import db

from bourso2ynab import ynab
from bourso2ynab.io import read_bourso_transactions
from bourso2ynab.transaction import Transaction, transactions_to_html

bp = Blueprint("main", __name__, url_prefix="/")


@bp.route("/", methods=["GET"])
def main():
    return render_template("submit_csv.html")


@bp.route("/csv/upload", methods=["POST"])
def upload_csv():
    # Populating the session with the results from the form.
    for key in ["username", "account-type"]:
        session[key] = request.form[key]

    # Reading and saving the content of the csv file.
    csv_file = request.files["transactions-file"]
    df = read_bourso_transactions(filepath=csv_file.stream)
    transactions = [Transaction.from_pandas(row) for _, row in df.iterrows()]
    transactions = sorted(transactions, key=lambda x: x.date)
    session["transactions"] = transactions

    html_table = transactions_to_html(
        transactions, with_table_tag=False, editable=True, with_title=True
    )

    return render_template("review_transactions.html", table=html_table)


@bp.route("/ynab/push", methods=["POST"])
def push_to_ynab():
    # Retrieving Transactions.
    transactions = _get_transactions_from_session()

    updated_transactions = _update_transactions_based_on_form(
        transactions, request.form
    )
    _update_db_based_on_transactions_changes(transactions, updated_transactions)

    # Retrieving YNAB credentials.
    username = session["username"]
    account_type = session["account-type"]
    kwargs = {"username": username, "account_type": account_type}

    account_id = ynab.get_ynab_id(id_type="account", **kwargs)
    budget_id = ynab.get_ynab_id(id_type="budget", **kwargs)

    result = ynab.push_to_ynab(updated_transactions, account_id, budget_id)

    return render_template("confirmation.html", result=result)


def _get_transactions_from_session() -> List[Transaction]:
    # When passing transactions to a session, Flask automatically
    # convert them to dicts (because Transaction is a dataclass).
    # We need to re-convert them to a Transaction object.
    return [Transaction.from_flask_json(data) for data in session["transactions"]]


def _update_transactions_based_on_form(
    transactions: List[Transaction], form: ImmutableMultiDict
) -> List[Transaction]:
    updated_transactions = deepcopy(transactions)

    # Parsing the form. For each raw in the original table, we want to create
    # a tuple (payee, memo)
    n_rows = int(len(form) / 2)  # Why 2? Because there's always a memo and a payee

    for i in range(n_rows):
        payee = form[f"payee-input-text-{i}"]
        memo = form[f"memo-input-text-{i}"]

        updated_transactions[i].payee = payee
        updated_transactions[i].memo = memo

    return updated_transactions


def _update_db_based_on_transactions_changes(
    transactions: List[Transaction], updated_transactions: List[Transaction]
):
    for old, new in zip(transactions, updated_transactions):
        if old.payee != new.payee:
            existing_entries = db.get_by_query(
                lambda data: data["original"] == old.payee
            )
            if not existing_entries:
                db.add({"original": old.payee, "adjusted": new.payee})
            else:
                key = list(existing_entries.keys())[0]
                db.update_by_id(key, {"adjusted": new.payee})
