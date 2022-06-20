from flask import Blueprint, render_template, request, session

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
    return render_template("submit_csv.html")