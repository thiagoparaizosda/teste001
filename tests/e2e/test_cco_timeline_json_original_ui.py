import os

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


pytestmark = pytest.mark.e2e

BASE_URL = os.getenv("BASE_URL", "http://localhost:5006")
CCO_ID_TESTE = os.getenv("CCO_ID_TESTE", "TnzgaDKeQXG4wcBxSSoA3wAAAAA")


def abrir_timeline(selenium):
    selenium.get(f"{BASE_URL}/cco-timeline/{CCO_ID_TESTE}")

    WebDriverWait(selenium, 15).until(
        EC.presence_of_element_located((By.ID, "btn-json-original"))
    )


def instalar_mock_copia(selenium):
    """
    Força o fluxo de fallback de cópia e captura o texto selecionado.

    Isso evita depender da área de transferência real do sistema operacional,
    que pode ser bloqueada por HTTP/IP local ou por política do navegador.
    """
    selenium.execute_script("""
        window.__copyDebug = {
            execCommandChamado: false,
            comando: null,
            textoSelecionado: null,
            activeTag: null,
            alertas: []
        };

        window.alert = function(mensagem) {
            window.__copyDebug.alertas.push(String(mensagem));
        };

        try {
            Object.defineProperty(Navigator.prototype, 'clipboard', {
                get: function() {
                    return undefined;
                },
                configurable: true
            });
        } catch (e) {
            window.__copyDebug.clipboardOverrideError = String(e);
        }

        document.execCommand = function(comando) {
            window.__copyDebug.execCommandChamado = true;
            window.__copyDebug.comando = comando;
            window.__copyDebug.activeTag = document.activeElement ? document.activeElement.tagName : null;
            window.__copyDebug.textoSelecionado = document.activeElement && document.activeElement.value
                ? document.activeElement.value
                : null;
            return comando === 'copy';
        };
    """)


def test_json_original_abre_modal_e_exibe_json_formatado(selenium):
    abrir_timeline(selenium)

    selenium.find_element(By.ID, "btn-json-original").click()

    modal = WebDriverWait(selenium, 10).until(
        EC.visibility_of_element_located((By.ID, "modalJsonOriginal"))
    )

    assert modal.is_displayed()

    preview = WebDriverWait(selenium, 10).until(
        EC.presence_of_element_located((By.ID, "json-original-preview"))
    )

    texto = preview.text

    assert len(texto) > 50
    assert "_id" in texto
    assert "contratoCpp" in texto or "campo" in texto


def test_json_original_copiar_json_do_modal_usa_fallback_e_copia_texto(selenium):
    abrir_timeline(selenium)
    instalar_mock_copia(selenium)

    selenium.find_element(By.ID, "btn-json-original").click()

    WebDriverWait(selenium, 10).until(
        EC.visibility_of_element_located((By.ID, "modalJsonOriginal"))
    )

    botoes = selenium.find_elements(By.CSS_SELECTOR, "#modalJsonOriginal button")
    botao_copiar = None

    for botao in botoes:
        if "Copiar JSON" in botao.text:
            botao_copiar = botao
            break

    assert botao_copiar is not None, "Botão Copiar JSON não encontrado no modal."

    botao_copiar.click()

    WebDriverWait(selenium, 10).until(
        lambda driver: driver.execute_script("return window.__copyDebug.execCommandChamado === true")
    )

    debug = selenium.execute_script("return window.__copyDebug")

    assert debug["comando"] == "copy"
    assert debug["textoSelecionado"] is not None
    assert len(debug["textoSelecionado"]) > 50
    assert "_id" in debug["textoSelecionado"]
    assert "contratoCpp" in debug["textoSelecionado"] or "campo" in debug["textoSelecionado"]
    assert any("copiado" in alerta.lower() for alerta in debug["alertas"])


def test_json_original_hover_exibe_preview_bonito(selenium):
    abrir_timeline(selenium)

    botao = selenium.find_element(By.ID, "btn-json-original")
    ActionChains(selenium).move_to_element(botao).perform()

    popover = WebDriverWait(selenium, 10).until(
        EC.visibility_of_element_located((By.ID, "json-original-popover"))
    )

    assert popover.is_displayed()

    conteudo = selenium.find_element(By.ID, "json-original-popover-content").text

    assert len(conteudo) > 20
    assert "_id" in conteudo


def test_json_original_fechar_modal_nao_deixa_modal_visivel(selenium):
    abrir_timeline(selenium)

    selenium.find_element(By.ID, "btn-json-original").click()

    WebDriverWait(selenium, 10).until(
        EC.visibility_of_element_located((By.ID, "modalJsonOriginal"))
    )

    selenium.find_element(By.CSS_SELECTOR, "#modalJsonOriginal .btn-close").click()

    WebDriverWait(selenium, 10).until(
        EC.invisibility_of_element_located((By.ID, "modalJsonOriginal"))
    )

    modal_visivel = selenium.execute_script("""
        const modal = document.getElementById('modalJsonOriginal');
        return modal && modal.classList.contains('show');
    """)

    assert modal_visivel is False


def test_copiar_json_todos_atributos_tambem_usa_mesmo_fluxo_de_copia(selenium):
    abrir_timeline(selenium)
    instalar_mock_copia(selenium)

    # Se o painel de atributos estiver fechado, abrir.
    selenium.execute_script("""
        const painel = document.getElementById('atributos-avancados');
        const btn = document.getElementById('btn-toggle-atributos-avancados');
        if (painel && !painel.classList.contains('show') && btn) {
            btn.click();
        }
    """)

    botao_copiar_atributos = WebDriverWait(selenium, 10).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, ".atributos-actions button.btn-secondary"))
    )

    botao_copiar_atributos.click()

    WebDriverWait(selenium, 10).until(
        lambda driver: driver.execute_script("return window.__copyDebug.execCommandChamado === true")
    )

    debug = selenium.execute_script("return window.__copyDebug")

    assert debug["comando"] == "copy"
    assert debug["textoSelecionado"] is not None
    assert "_id" in debug["textoSelecionado"]
