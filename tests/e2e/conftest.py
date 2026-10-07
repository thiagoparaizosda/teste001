import pytest

from selenium import webdriver
from selenium.webdriver.chrome.options import Options


@pytest.fixture
def download_dir(tmp_path):
    return tmp_path


@pytest.fixture
def selenium(download_dir):
    options = Options()

    prefs = {
        "download.default_directory": str(download_dir),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
    }

    options.add_experimental_option("prefs", prefs)
    options.add_argument("--window-size=1366,900")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")

    driver = webdriver.Chrome(options=options)

    try:
        yield driver
    finally:
        driver.quit()
