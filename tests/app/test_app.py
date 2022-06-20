def test_display_home_page(client):
    response = client.get("/")
    assert "<h1>Bourso2Ynab</h1>" in response.text
    assert "Select your Boursorama transactions" in response.text


def test_submit_csv_for(client, transactions_csv_filepath):
    response = client.post(
        "/csv/upload",
        data={
            "transactions-file": transactions_csv_filepath.open("rb"),
            "username": "romain",
            "account-type": "perso",
        },
    )
    assert "<table>" in response.text
    assert "<td>2022/06/13</td>" in response.text
    assert "<td>2022/06/11</td>" in response.text
    assert 'value="Ratp"' in response.text
