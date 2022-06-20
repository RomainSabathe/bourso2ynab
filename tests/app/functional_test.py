import os
from pathlib import Path

import pytest

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.relative_locator import locate_with


@pytest.mark.nondestructive
def test_submit_transactions(selenium, base_url, transactions_csv_filepath):
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

    import ipdb; ipdb.set_trace()
    pass


# def test_functional(selenium, firefox_options):
#     selenium.get("/")


# def test_functional(browser):
#     browser.get("/")


#     def tearDown(self):
#         self.browser.quit()

# def user_enters_text_in_textbox_and_hit_enter(self, text):
#     inputbox = self.browser.find_element_by_id("id_new_item")
#     # The user types `text` into the text box as an item in a to-do list.
#     inputbox.send_keys(text)
#     inputbox.send_keys(Keys.ENTER)

# def test_can_start_a_list_and_retrieve_it_later(self):
#     # ginette has heard about a cool new online to-do ap. She goes
#     # to check out its homepage.
#     self.browser.get(self.live_server_url)

#     # She noticies the page title hand header mention to-do lists
#     self.assertIn("To-Do", self.browser.title)
#     header_text = self.browser.find_element_by_tag_name("h1").text
#     self.assertIn("To-Do", header_text)

#     # She is invited to enter a to-do item straight away
#     inputbox = self.browser.find_element_by_id("id_new_item")
#     self.assertEqual(inputbox.get_attribute("placeholder"), "Enter a to-do item")
#     form = self.browser.find_element_by_id("id_todo_form")
#     self.assertEqual(form.get_attribute("method"), "post")

#     # ginette writes text in the text box and hits enter.
#     # When she hits enter, the page updates, and now the page lists
#     # "1: Buy lettuce for snails" as an item a in a to-do list table
#     self.user_enters_text_in_textbox_and_hit_enter("Buy lettuce for snails")
#     self.wait_for_row_in_list_table("1: Buy lettuce for snails")

#     # There is still a text box inviting her to add another item. She
#     # enters "Cook salad for snails" (ginette really loves them)
#     self.user_enters_text_in_textbox_and_hit_enter("Cook salad for snails")
#     self.wait_for_row_in_list_table(
#         "1: Buy lettuce for snails"
#     )  # Checking it's still there
#     self.wait_for_row_in_list_table("2: Cook salad for snails")

# def test_multiple_users_can_start_lists_at_different_urls(self):
#     # ginette starts a new to-do list
#     self.browser.get(self.live_server_url)
#     self.user_enters_text_in_textbox_and_hit_enter("Buy lettuce for snails")
#     self.wait_for_row_in_list_table("1: Buy lettuce for snails")

#     # ginette notices that her list has a unique URL
#     ginette_list_url = self.browser.current_url
#     self.assertRegex(ginette_list_url, "/lists/.+")

#     # Now, a new user, Francis, comes along to the site

#     ## We use a new browser session to make sure that no information of ginette's
#     ## is coming through from cookies etc.
#     self.browser.quit()
#     self.browser = self._load_browser()

#     # Francis visits the home page. There is no sign of Edith's list.
#     self.browser.get(self.live_server_url)
#     page_text = self.browser.find_element_by_tag_name("body").text
#     self.assertNotIn("Buy lettuce for snails", page_text)
#     self.assertNotIn("Cook salad for snails", page_text)

#     # Francis starts a new list by entering a new item.
#     self.user_enters_text_in_textbox_and_hit_enter("Buy tea")
#     self.wait_for_row_in_list_table("1: Buy tea")

#     # Francis gets his own unique URL
#     francis_list_url = self.browser.current_url
#     self.assertRegex(francis_list_url, "/lists/.+")
#     self.assertNotEqual(ginette_list_url, francis_list_url)

#     # Still no trace of Edith's items.
#     page_text = self.browser.find_element_by_tag_name("body").text
#     self.assertNotIn("Buy lettuce for snails", page_text)
#     self.assertNotIn("Cook salad for snails", page_text)
