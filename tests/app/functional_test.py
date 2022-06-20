import pytest

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait


@pytest.mark.nondestructive
def test_submit_transactions(
    selenium, base_url, transactions_csv_filepath, ynab_mocker, env_mocker
):
    selenium.get(base_url)

    # As a user, I should be able to specify who I am. There should be 2 options.
    fieldset = selenium.find_element(By.ID, "username-selection-box")
    assert fieldset.tag_name == "fieldset"

    labels = fieldset.find_elements(By.TAG_NAME, "label")
    assert len(labels) == 2
    for label in labels:
        assert label.tag_name == "label"

        username = label.get_attribute("for")
        assert label.text == username.title()

        input = label.find_element(By.TAG_NAME, "input")
        assert input.get_property("type") == "radio"
        assert input.get_property("id") == f"{username}-username-radio"
        assert input.get_property("name") == "username"
        assert input.get_property("value") == username

    browse_button = selenium.find_element(By.ID, "transactions-file-upload-button")
    browse_button.send_keys(str(transactions_csv_filepath))

    username_button = selenium.find_element(By.ID, "romain-username-radio")
    username_button.click()

    account_type_button = selenium.find_element(By.ID, "perso-account-type-radio")
    account_type_button.click()

    submit_button = selenium.find_element(By.ID, "submit-csv-button")
    submit_button.click()

    # I arrive on the next page. There is a table with the list of transactions.
    # I can validate by clicking on the button.

    el = WebDriverWait(selenium, timeout=3).until(
        lambda d: d.find_element(By.ID, "push-to-ynab-button-bottom")
    )
    el.click()

    import ipdb

    ipdb.set_trace()
    pass