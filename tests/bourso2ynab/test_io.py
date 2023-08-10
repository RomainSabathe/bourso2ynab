import pandas as pd

from bourso2ynab.io import read_bourso_transactions


def test_read_bourso_transactions(tmpdir):
    lines = [
        "dateOp;dateVal;label;amount;comment",
        '1970-01-01;1970-01-01;"CARTE 13/06/22 VELIB METROPOLE 2 CB*1040";-2,00',
        '1970-01-01;1970-01-01;"CARTE 11/06/22 RATP CB*1040";-3,80',
    ]
    text = "\n".join(lines)
    filepath = tmpdir / "transactions.csv"
    filepath.write_text(text, encoding="utf-8")

    df = read_bourso_transactions(filepath)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert "dateOp" in df.columns
