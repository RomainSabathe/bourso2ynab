import os
import json
import socket
import functools
import subprocess
from pathlib import Path

import pytest
from flask import request
from pysondb import PysonDB
import flask.json as flask_json
from dotenv import load_dotenv

from app import create_app
from bourso2ynab.ynab import get_ynab_id


@pytest.fixture()
def app(tmpdir):
    app = create_app()

    app.config.update({"TESTING": True})
    yield app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture
def db(tmpdir, mocker):
    _db = PysonDB(tmpdir / "db.json")

    # Setting up initial data.
    _db.add_many(
        [
            {"original": "Sncf", "adjusted": "SNCF"},
            {"original": "Redemption Ro", "adjusted": "Redemption Roasters"},
        ]
    )

    mocker.patch("app.main.db", _db)

    return _db


@pytest.fixture
def firefox_options(firefox_options):
    firefox_options.binary = r"C:\Program Files\WindowsApps\Mozilla.Firefox_101.0.1.0_x64__n80bbvh6b1yt2\VFS\ProgramFiles\Firefox Package Root\firefox.exe"
    firefox_options.add_argument("-foreground")
    # firefox_options.add_argument("--headless")
    firefox_options.set_preference("browser.anchor_color", "#FF0000")
    return firefox_options


@pytest.fixture(scope="session")
def flask_port():
    ## Ask OS for a free port.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        addr = s.getsockname()
        port = addr[1]
        return port


@pytest.fixture(scope="session", autouse=True)
def live_server(flask_port):
    env = os.environ.copy()

    # Preventing from pushing to the live server.
    if env.get("YNAB_API_KEY") is not None:
        env.pop("YNAB_API_KEY")

    server = subprocess.Popen(["flask", "run", "--port", str(flask_port)], env=env)
    try:
        yield server
    finally:
        server.terminate()


@pytest.fixture(scope="session")
def base_url(flask_port):
    return f"http://localhost:{flask_port}"


@pytest.fixture
def transactions_csv_filepath():
    return Path(__file__).parent / "resources" / "transactions.csv"


@pytest.fixture
def ynab_secrets_filepath(tmpdir):
    secrets = {
        "budgets": {
            "user1": "abcd",
            "user2": "7890",
        },
        "accounts": {
            "user1": {"perso": "0123", "joint": "4567"},
            "user2": {"perso": "0000", "joint": "1111"},
        },
    }
    with (tmpdir / "secrets.json").open("w") as f:
        json.dump(secrets, f)

    yield tmpdir / "secrets.json"


@pytest.fixture
def ynab_mocker(mocker, ynab_secrets_filepath):
    mocker.patch(
        "app.main.ynab.get_ynab_id",
        functools.partial(get_ynab_id, secrets_path=ynab_secrets_filepath),
    )
    mocker.patch(
        "app.main.ynab.push_to_ynab",
        lambda transactions, account_id, budget_id: flask_json.dumps(transactions),
    )

    yield


@pytest.fixture
def env_mocker(mocker):
    def mocked_load_dotenv():
        load_dotenv()
        if os.environ.get("YNAB_API_KEY") is not None:
            os.environ.pop("YNAB_API_KEY")

    mocker.patch("bourso2ynab.main.load_dotenv", mocked_load_dotenv)
    mocker.patch("app.main.load_dotenv", mocked_load_dotenv)

    yield
