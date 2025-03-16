from copy import deepcopy
from pprint import pformat
from typing import List

from flask import Blueprint, render_template, request, session
from loguru import logger
from werkzeug.datastructures import ImmutableMultiDict

from app.database import db
from bourso2ynab.actual import get_actual_transactions
from bourso2ynab.actual import push_to_actual as _push_to_actual
from bourso2ynab.io import read_bourso_transactions
from bourso2ynab.resolve import resolve_transactions
from bourso2ynab.transaction import Transaction, transactions_to_html
from bourso2ynab.ynab import (
    get_all_available_account_types,
    get_all_available_usernames,
    get_ynab_id,
)
from bourso2ynab.ynab import push_to_ynab as _push_to_ynab

bp = Blueprint("main", __name__, url_prefix="/")


@bp.route("/", methods=["GET"])
def main():
    logger.debug("Loading frontpage")
    return render_template(
        "submit_csv.html",
        usernames=get_all_available_usernames(),
        account_types=get_all_available_account_types(),
    )


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

    transactions_to_display = _update_transactions_based_on_db(transactions)
    html_table = transactions_to_html(
        transactions_to_display, with_table_tag=False, editable=True, with_title=True
    )

    return render_template("review_transactions.html", table=html_table)


@bp.route("/old/ynab/push", methods=["POST"])
def push_to_ynab():
    # Retrieving Transactions.
    transactions = _get_transactions_from_session()

    updated_transactions = _update_transactions_based_on_form(
        transactions, request.form
    )
    _update_db_based_on_transactions_changes(transactions, updated_transactions)

    # Retrieving YNAB credentials.
    account_type = session["account-type"]
    usernames = [session["username"]]
    if account_type == "joint":
        usernames = get_all_available_usernames()

    for username in usernames:
        kwargs = {"username": username, "account_type": account_type}
        account_id = get_ynab_id(id_type="account", **kwargs)
        budget_id = get_ynab_id(id_type="budget", **kwargs)

        logger.debug("Pushing transactions to YNAB")
        logger.debug(f"{username=}")
        logger.debug(f"{account_type=}")
        logger.debug(f"{updated_transactions=}")
        result = _push_to_ynab(updated_transactions, account_id, budget_id)

        logger.debug("Transactions pushed.")
        logger.debug(f"{result=}")

    return render_template("confirmation.html", result=result)


@bp.route("/ynab/push", methods=["POST"])
def push_to_actual():
    # Retrieving Transactions.
    transactions = _get_transactions_from_session()

    updated_transactions = _update_transactions_based_on_form(
        transactions, request.form
    )
    _update_db_based_on_transactions_changes(transactions, updated_transactions)

    # Retrieving Actual credentials.
    account_type = session["account-type"]
    username = session["username"]

    # Registering multiple usernames in case of a joint account.
    usernames = [username]  # default.
    if account_type.lower() == "joint":
        usernames = get_all_available_usernames()

    for username in usernames:
        kwargs = {"username": username, "account_type": account_type}
        account_name = get_ynab_id(id_type="account", **kwargs)
        file_uuid = get_ynab_id(id_type="budget", **kwargs)

        logger.debug("Pushing transactions to Actual")
        logger.debug(f"{username=}")
        logger.debug(f"{account_type=}")
        logger.debug(f"{updated_transactions=}")
        result = _push_to_actual(updated_transactions, file_uuid, account_name)

        logger.debug("Transactions pushed.")
        logger.debug(f"{result=}")

    # We use pprint because `result` is a list of large dictionnaries, and we want to
    # make the output digestible for the user.
    return render_template("confirmation.html", result=pformat(result))


@bp.route("/resolve", methods=["POST"])
def resolve_transactions_view():
    # Populating the session with the results from the form.
    for key in ["username", "account-type"]:
        session[key] = request.form[key]

    # Reading and saving the content of the csv file.
    csv_file = request.files["transactions-file"]
    df = read_bourso_transactions(filepath=csv_file.stream)
    local_transactions = [Transaction.from_pandas(row) for _, row in df.iterrows()]

    # Store transactions in session
    session["transactions"] = [t.__dict__ for t in local_transactions]

    return _show_resolve_view(local_transactions)


@bp.route("/resolve/refresh", methods=["POST"])
def refresh_resolve_view():
    # Get stored transactions from session using the existing helper
    local_transactions = _get_transactions_from_session()
    return _show_resolve_view(local_transactions)


def _show_resolve_view(local_transactions: List[Transaction]):
    """Helper function to show the resolve view with given local transactions."""
    # Get account details based on form selection
    username = session["username"]
    account_type = session["account-type"]
    kwargs = {"username": username, "account_type": account_type}
    account_name = get_ynab_id(id_type="account", **kwargs)
    file_uuid = get_ynab_id(id_type="budget", **kwargs)

    try:
        # Use the earliest date from local transactions as the start date
        start_date = min(t.date for t in local_transactions)
        remote_transactions = get_actual_transactions(
            file_uuid=file_uuid,
            account_name=account_name,
            start_date=start_date,
        )

        # Compare transactions
        missing_transactions = resolve_transactions(
            remote_transactions=remote_transactions,
            local_transactions=local_transactions,
        )

        return render_template(
            "resolve.html",
            missing_from_local=missing_transactions["missing_from_local"],
            missing_from_remote=missing_transactions["missing_from_remote"],
        )

    except Exception as e:
        logger.error(f"Error processing file: {str(e)}")
        return render_template("error.html", error=str(e))


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
        if old.payee == "":
            # We don't want to update the DB based on an empty field.
            # This typically happens in case of VIRs from unknown senders.
            # It wouldn't make sense to hardcode this in the db.
            continue

        if old.payee != new.payee:
            existing_entries = db.get_by_query(
                lambda data: data["original"] == old.payee
            )
            if not existing_entries:
                logger.info(
                    f"Adding a new entry in the DB: {old.payee} --> {new.payee}"
                )
                db.add({"original": old.payee, "adjusted": new.payee})
            else:
                logger.info(f"Updating an entry in the DB: {old.payee} --> {new.payee}")
                key = list(existing_entries.keys())[0]
                db.update_by_id(key, {"adjusted": new.payee})


def _update_transactions_based_on_db(transactions: List[Transaction]):
    updated_transactions = deepcopy(transactions)

    for i, transaction in enumerate(updated_transactions):
        entries = db.get_by_query(lambda data: data["original"] == transaction.payee)
        if not entries:
            continue

        key = list(entries.keys())[0]
        entry = db.get_by_id(key)
        updated_transactions[i].payee = entry["adjusted"]

    return updated_transactions
