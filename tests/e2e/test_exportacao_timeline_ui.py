import os

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


pytestmark = pytest.mark.e2e

BASE_URL = os.getenv("BASE_URL", "http://localhost:5006")
CCO_ID_TESTE = os.getenv("CCO_ID_TESTE", "AoqHEQJ8T7GwaAHFel4i1wAAAAA")


def abrir_timeline(driver):
    driver.get(f"{BASE_URL}/cco-timeline/{CCO_ID_TESTE}")

    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, ".card-header"))
    )


def test_timeline_exibe_botao_exportar_excel(selenium):
    abrir_timeline(selenium)

    botao = WebDriverWait(selenium, 10).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, "#btn-exportar-excel-timeline, .btn-exportar-excel-timeline"))
    )

    assert botao.is_displayed()
    assert "Exportar Excel" in botao.text

    icone = botao.find_element(By.CSS_SELECTOR, "i")
    assert "fa-file-excel" in icone.get_attribute("class")


def test_timeline_clique_exportar_excel_chama_endpoint(selenium):
    abrir_timeline(selenium)

    # Captura a URL enviada para window.open sem precisar baixar o arquivo
    selenium.execute_script("""
        window.__lastExportUrl = null;
        window.open = function(url) {
            window.__lastExportUrl = url;
        };
    """)

    botao = WebDriverWait(selenium, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "#btn-exportar-excel-timeline, .btn-exportar-excel-timeline"))
    )

    selenium.execute_script(
        "arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});",
        botao
    )

    selenium.execute_script("arguments[0].click();", botao)

    WebDriverWait(selenium, 10).until(
        lambda driver: driver.execute_script("return window.__lastExportUrl") is not None
    )

    url_exportacao = selenium.execute_script("return window.__lastExportUrl")

    assert f"/api/cco-timeline/{CCO_ID_TESTE}/export" in url_exportacao
    assert "format=xlsx" in url_exportacao