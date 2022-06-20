from flask import Blueprint, render_template, request

from bourso2ynab.transaction import Transaction
from bourso2ynab.io import read_bourso_transactions

bp = Blueprint("main", __name__, url_prefix="/")


@bp.route("/", methods=["GET"])
def main():
    return render_template("submit_csv.html")


@bp.route("/csv/upload", methods=["POST"])
def upload_csv():
    csv_file = request.files["transactions-file"]
    df = read_bourso_transactions(filepath=csv_file.stream)
    transaction = Transaction.from_pandas(df.iloc[0])

    return render_template(
        "review_transactions.html",
        table=transaction.to_html(with_title=True, editable=True),
    )
