import os
import json
import html
import logging

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from flask import Flask, render_template, request, session

logging.basicConfig(format="%(asctime)s - %(message)s", level=logging.DEBUG)
load_dotenv()


def create_app(test_config=None):
    # create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    app.secret_key = os.environ["APP_SECRET_KEY"]

    # ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    from . import main
    app.register_blueprint(main.bp)

        # if request.method == "POST":
        #     if request.form["form_type"] == "transactions_upload":
        #         return display_transactions()
        #     if request.form["form_type"] == "transactions_validation":
        #         df = load_table_and_update_payee_formatter()
        #         logging.info("Finished formatting transactions. Now sending to YNAB...")
        #         api_response = upload_transactions(
        #             df,
        #             username=session["username"],
        #             account_type=session["account_type"],
        #         )
        #         api_response = api_response.to_dict()

        #         nb_new_entries = len(api_response["data"]["transactions"])
        #         nb_duplicates = len(api_response["data"]["duplicate_import_ids"])
        #         logging.info(
        #             f"User: {session['username']}, Account type: {session['account_type']} - "
        #             f"Sent {nb_new_entries + nb_duplicates} transactions with {nb_new_entries} being new."
        #         )
        #         session.clear()
        #     return render_template(
        #         "base.html",
        #         api_response=json.dumps(api_response, indent=4, default=str),
        #     )

        # return render_template("base.html")

    return app


def display_transactions():
    df = read_bourso_transactions(filepath=request.files["input_file"].stream).pipe(
        format_transactions, format_payee=False
    )

    # We want to format the payee manually to properly update the DB.
    session["df"] = df.to_json()
    session["username"] = request.form["username"]
    session["account_type"] = request.form["account_type"]

    logging.info(
        f"User: {session['username']}, Account type: {session['account_type']} - Received {len(df)} transactions."
    )

    # Replacing the Payee entries. Instead of showing `str`, we want to
    # show text boxes that can be edited by the user.
    if "Memo" not in df.columns:
        df = df.assign(Memo=np.nan)
    with PayeeFormatter() as payee_formatter:
        df_for_form = (
            df.assign(Payee=lambda df: df.Payee.apply(payee_formatter.format))
            .assign(
                Payee=lambda df: df.apply(
                    lambda row: f'<input type="text" '
                    f'id="payee_row-{row.name}" '
                    f'name="payee_row-{row.name}" '
                    f'value="{html.escape(row.Payee) if not pd.isnull(row.Payee) else ""}" '
                    f'size="{df.Payee.str.len().max() * 1.0}">',
                    axis="columns",
                )
            )
            .assign(
                Memo=lambda df: df.apply(
                    lambda row: f'<input type="text" '
                    f'id="memo_row-{row.name}" '
                    f'name="memo_row-{row.name}" '
                    f'value="{html.escape(row.Memo) if not pd.isnull(row.Memo) else ""}" '
                    f"size=30>",
                    axis="columns",
                )
            )[["Payee", "Amount", "Date", "Memo"]]
        )

    return render_template(
        "base.html",
        dataframe=df_for_form.to_html(escape=False, index=False),
    )


def load_table_and_update_payee_formatter():
    df = pd.read_json(session["df"], convert_dates=False)
    # convert_dates=False, otherwise creates datetime items. We just want date to obtain
    # correct import ids.

    # Creating a dataframe out of the form inputs.
    updated_payee_names, updated_memos = [], []
    for key, value in request.form.items():
        if key.startswith("payee_row-"):
            index = int(key[10:])  # Removing the "payee_row-" part.
            updated_payee_names.append({"index": index, "Payee": value})
        if key.startswith("memo_row-"):
            index = int(key[9:])  # Removing the "memo_row-" part.
            updated_memos.append({"index": index, "Memo": value})

    if len(updated_payee_names) > 0:
        updated_payee_names = pd.DataFrame(updated_payee_names).set_index("index")
        df = df.assign(NewPayee=updated_payee_names.Payee)

        with PayeeFormatter() as payee_formatter:
            for old_payee, new_payee in df[["Payee", "NewPayee"]].values:
                if old_payee is None or new_payee == "":
                    continue
                is_new_rule = payee_formatter.add_formatting_rule(old_payee, new_payee)
                if is_new_rule:
                    logging.info(f"New Payee rule: {old_payee} --> {new_payee}")

            # Updating the original df with the new Payee names.
            # This should be equivalent to doing:
            # df = df.assign(Payee=updated_payee_names.Payee)
            df = df.assign(Payee=lambda df: df.Payee.apply(payee_formatter.format))

    if len(updated_memos) > 0:
        updated_memos = pd.DataFrame(updated_memos).set_index("index")
        df.loc[updated_memos.index, "Memo"] = updated_memos.Memo

    return df
