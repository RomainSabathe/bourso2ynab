import os
import html

import pandas as pd
from flask import Flask, render_template, request, session

from bourso2ynab import (
    read_bourso_transactions,
    format_transactions,
    upload_transactions,
    PayeeFormatter,
)


def create_app(test_config=None):
    # create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    app.secret_key = "***REMOVED***"

    # ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    @app.route("/", methods=["GET", "POST"])
    def main():
        if request.method == "POST":
            if request.form["form_type"] == "transactions_upload":
                df = read_bourso_transactions(
                    filepath=request.files["input_file"].stream
                ).pipe(format_transactions, format_payee=False)
                # We want to format the payee manually to properly update the DB.
                session["df"] = df.to_json()
                session["username"] = request.form["username"]
                session["account_type"] = request.form["account_type"]

                # Replacing the Payee entries. Instead of showing `str`, we want to
                # show text boxes that can be edited by the user.
                with PayeeFormatter() as payee_formatter:
                    df_for_form = df.assign(
                        Payee=lambda df: df.Payee.apply(payee_formatter.format)
                    ).assign(
                        Payee=lambda df: df.apply(
                            lambda row: f'<input type="text" '
                            f'id="row-{row.name}" '
                            f'name="row-{row.name}" '
                            f'value="{html.escape(row.Payee) if not pd.isnull(row.Payee) else ""}" '
                            f'size="{df.Payee.str.len().max() * 0.8}">',
                            axis="columns",
                        )
                    )[
                        ["Payee", "Amount", "Date", "Memo"]
                    ]

                return render_template(
                    "base.html",
                    dataframe=df_for_form.to_html(escape=False, index=False),
                )

            if request.form["form_type"] == "transactions_validation":
                df = pd.read_json(session["df"])

                # Creating a dataframe out of the form inputs.
                updated_payee_names = []
                for key, value in request.form.items():
                    if not key.startswith("row-"):
                        # This is not part of the table entries
                        continue
                    index = int(key[4:])  # Removing the "row-" part.
                    updated_payee_names.append({"index": index, "Payee": value})
                updated_payee_names = pd.DataFrame(updated_payee_names).set_index(
                    "index"
                )
                df = df.assign(NewPayee=updated_payee_names.Payee)

                with PayeeFormatter() as payee_formatter:
                    # for old_payee, new_payee in df[["Payee", "NewPayee"]]:
                    for old_payee, new_payee in df[["Payee", "NewPayee"]].values:
                        if old_payee is None or new_payee == "":
                            continue
                        payee_formatter.add_formatting_rule(old_payee, new_payee)

                    # Updating the original df with the new Payee names.
                    # This should be equivalent to doing:
                    # df = df.assign(Payee=updated_payee_names.Payee)
                    df = df.assign(
                        Payee=lambda df: df.Payee.apply(payee_formatter.format)
                    )

                # upload_transactions(
                #     df,
                #     username=session["username"],
                #     account_type=session["account_type"],
                # )
                session.clear()

        return render_template("base.html")

    return app
