import pytest

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


pytestmark = pytest.mark.e2e

BASE_URL = "http://localhost:5006"
CCO_ID_TESTE = "SSZF3wTAR02efqyC9d2ZXQAAAAA"


def abrir_timeline(driver):
    driver.get(f"{BASE_URL}/cco-timeline/{CCO_ID_TESTE}")

    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "btn-toggle-atributos-avancados"))
    )


def expandir_atributos(driver):
    botao_expandir = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.ID, "btn-toggle-atributos-avancados"))
    )

    botao_expandir.click()

    WebDriverWait(driver, 10).until(
        lambda d: "show" in d.find_element(By.ID, "atributos-avancados").get_attribute("class")
    )


def test_accordion_expandir_recolher(selenium):
    abrir_timeline(selenium)
    expandir_atributos(selenium)

    botao_categoria = WebDriverWait(selenium, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, '[data-bs-target="#cat-valores"]'))
    )

    selenium.execute_script(
        "arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});",
        botao_categoria
    )

    WebDriverWait(selenium, 10).until(
        EC.visibility_of(botao_categoria)
    )

    selenium.execute_script("arguments[0].click();", botao_categoria)

    categoria = WebDriverWait(selenium, 10).until(
        EC.presence_of_element_located((By.ID, "cat-valores"))
    )

    WebDriverWait(selenium, 10).until(
        lambda d: "show" in categoria.get_attribute("class")
    )

    assert "show" in categoria.get_attribute("class")

def test_busca_atributo(selenium):
    abrir_timeline(selenium)
    expandir_atributos(selenium)

    search_input = WebDriverWait(selenium, 10).until(
        EC.presence_of_element_located((By.ID, "search-atributos"))
    )

    search_input.clear()
    search_input.send_keys("valorReconhecido")

    WebDriverWait(selenium, 10).until(
        lambda d: len(d.find_elements(By.CLASS_NAME, "highlight")) > 0
    )

    highlighted = selenium.find_elements(By.CLASS_NAME, "highlight")

    assert len(highlighted) > 0


def test_busca_sem_resultado(selenium):
    abrir_timeline(selenium)
    expandir_atributos(selenium)

    search_input = WebDriverWait(selenium, 10).until(
        EC.presence_of_element_located((By.ID, "search-atributos"))
    )

    search_input.clear()
    search_input.send_keys("atributoQueNaoExiste123")

    no_results = WebDriverWait(selenium, 10).until(
        EC.visibility_of_element_located((By.ID, "no-results-msg"))
    )

    assert no_results.is_displayed()
    assert "Nenhum atributo encontrado" in no_results.text