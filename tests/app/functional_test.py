import pytest
from selenium import webdriver
from selenium.webdriver.firefox.firefox_binary import FirefoxBinary


@pytest.mark.nondestructive
def test_functional(selenium, base_url):
    selenium.get(base_url)

    header_text = selenium.find_element_by_tag_name("h1").text
    assert header_text == "Bourso2Ynab"