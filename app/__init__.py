import os
from flask import Flask, render_template, request
from bourso2ynab import convert_and_upload


def create_app(test_config=None):
    # create and configure the app
    app = Flask(__name__, instance_relative_config=True)

    # ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    @app.route("/", methods=["GET", "POST"])
    def main():
        if request.method == "POST":
            convert_and_upload(
                filepath=request.files["input_file"].stream,
                username=request.form["username"],
                account_type=request.form["account_type"],
                upload=True,
            )
        return render_template("base.html")

    return app
