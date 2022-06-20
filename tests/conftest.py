import os
import json
import socket
import subprocess
from pathlib import Path

import pytest
from flask import request

from app import create_app


@pytest.fixture()
def app():
    app = create_app()
    app.config.update({"TESTING": True})
    yield app


@pytest.fixture()
def client(app):
    return app.test_client()


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
    # env["FLASK_APP"] = "bourso2ynab.app"
    server = subprocess.Popen(["flask", "run", "--port", str(flask_port)], env=env)
    try:
        yield server
    finally:
        server.terminate()


@pytest.fixture(scope="session")
def base_url(flask_port):
    return f"http://localhost:{flask_port}"


@pytest.fixture()
def transactions_csv_filepath():
    return Path(__file__).parent.parent / "resources" / "transactions.csv"


@pytest.fixture()
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
