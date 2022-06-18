import json

from bourso2ynab.ynab import get_ynab_id


def test_get_ynab_id(tmpdir):
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

    kwargs = {"username": "user1", "secrets_path": tmpdir / "secrets.json"}
    assert get_ynab_id(id_type="budget", **kwargs) == "abcd"
    assert get_ynab_id(id_type="accounts", account_type="perso", **kwargs) == "0123"
    assert get_ynab_id(id_type="accounts", account_type="joint", **kwargs) == "4567"

    kwargs = {"username": "user2", "secrets_path": tmpdir / "secrets.json"}
    assert get_ynab_id(id_type="budget", **kwargs) == "7890"
    assert get_ynab_id(id_type="accounts", account_type="perso", **kwargs) == "0000"
    assert get_ynab_id(id_type="accounts", account_type="joint", **kwargs) == "1111"
