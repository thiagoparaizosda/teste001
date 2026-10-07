import os
from pathlib import Path

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


pytestmark = pytest.mark.e2e

BASE_URL = os.getenv("BASE_URL", "http://localhost:5006")
CCO_ID_TESTE = os.getenv("CCO_ID_TESTE", "AoqHEQJ8T7GwaAHFel4i1wAAAAA")


def aguardar_download_xlsx(download_dir, timeout=20):
    download_path = Path(download_dir)

    def terminou_download(_):
        arquivos_xlsx = list(download_path.glob("*.xlsx"))
        arquivos_temp = list(download_path.glob("*.crdownload"))
        return arquivos_xlsx and not arquivos_temp

    WebDriverWait(None, timeout).until(lambda _: terminou_download(None))

    return list(download_path.glob("*.xlsx"))[0]


def test_download_excel_timeline_real(selenium, download_dir):
    selenium.get(f"{BASE_URL}/cco-timeline/{CCO_ID_TESTE}")

    botao = WebDriverWait(selenium, 10).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "#btn-exportar-excel-timeline, .btn-exportar-excel-timeline"))
    )

    botao.click()

    arquivo = aguardar_download_xlsx(download_dir)

    assert arquivo.exists()
    assert arquivo.name.endswith(".xlsx")
    assert "Timeline_CCO" in arquivo.name
    assert CCO_ID_TESTE not in arquivo.name
