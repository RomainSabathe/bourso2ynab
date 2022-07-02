import click
import numpy as np
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

from bourso2ynab.ynab import push_to_ynab, get_ynab_id


@click.command()
@click.option(
    "-i", "--input", "input_filepath", type=click.Path(exists=True), required=True
)
@click.option("-o", "--output", "output_filepath", required=False)
@click.option(
    "-u",
    "username",
    type=click.Choice(["romain", "marianne"], case_sensitive=True),
    required=True,
)
@click.option(
    "-a",
    "account_type",
    type=click.Choice(["perso", "joint"], case_sensitive=True),
    required=True,
)
@click.option("--upload/--no-upload", default=False)
def cli(input_filepath, output_filepath, username, account_type, upload):
    raise NotImplementedError


if __name__ == "__main__":
    cli()
