import csv
from typing import Union
from pathlib import Path

import pandas as pd


def read_bourso_transactions(filepath: Union[str, Path]) -> pd.DataFrame:
    return pd.read_csv(filepath, sep=";")
