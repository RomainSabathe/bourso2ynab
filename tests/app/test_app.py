def test_display_home_page(client):
    response = client.get("/")
    assert "<h1>Bourso2Ynab</h1>" in response.data.decode()


def test_submit_csv_for(client, transactions_csv_filepath):
    response = client.post(
        "/",
        data={
            "transactions-file": transactions_csv_filepath.open("rb"),
            "username": "romain",
            "account-type": "perso",
        },
    )
    assert "<table>" in response.data.decode()
