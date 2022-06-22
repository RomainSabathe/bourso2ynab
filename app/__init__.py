import os
import logging

from flask import Flask
from dotenv import load_dotenv

from app import main

logging.basicConfig(format="%(asctime)s - %(message)s", level=logging.DEBUG)

load_dotenv()


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.secret_key = os.environ["APP_SECRET_KEY"]

    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    app.register_blueprint(main.bp)

    return app
