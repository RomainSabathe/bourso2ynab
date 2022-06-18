def test_display_home_page(client):
    response = client.get("/")
    assert "<h1>Bourso2Ynab</h1>" in response.data.decode()