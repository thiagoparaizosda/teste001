import json
import os

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


pytestmark = pytest.mark.e2e

BASE_URL = os.getenv("BASE_URL", "http://localhost:5006")
PESQUISA_CCOS_URL = os.getenv("PESQUISA_CCOS_URL", f"{BASE_URL}/pesquisa-ccos")


def abrir_pagina_pesquisa(driver):
    driver.get(PESQUISA_CCOS_URL)

    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "tabelaCCOs"))
    )


def instalar_fetch_mock_pesquisa_e_exportacao(driver):
    """
    Intercepta apenas as chamadas usadas neste teste:
    - /api/pesquisar-ccos
    - /api/ccos/export

    A chamada de contratos/campos pode continuar indo para o backend real.
    """
    driver.execute_script("""
        window.__exportRequest = null;
        window.__pesquisaRequest = null;

        const originalFetch = window.fetch;

        window.fetch = function(url, options) {
            const urlTexto = String(url);

            if (urlTexto.includes('/api/pesquisar-ccos')) {
                window.__pesquisaRequest = {
                    url: urlTexto,
                    method: options && options.method,
                    body: options && options.body
                };

                return Promise.resolve({
                    ok: true,
                    json: function() {
                        return Promise.resolve({
                            success: true,
                            total: 2,
                            resultados: [
                                {
                                    id: 'CCO_TEST_001',
                                    contratoCpp: 'CONTRATO-001',
                                    campo: 'ARAM',
                                    remessa: 30,
                                    faseRemessa: 'MEN',
                                    mesReconhecimento: 3,
                                    anoReconhecimento: 2023,
                                    periodo: 1,
                                    origemDosGastos: 'GASTO_EXCLUSIVO',
                                    flgRecuperado: false,
                                    temCorrecoes: true,
                                    ultimaAtualizacao: '16/04/2024'
                                },
                                {
                                    id: 'CCO_TEST_002',
                                    contratoCpp: 'CONTRATO-001',
                                    campo: 'ARAM',
                                    remessa: 31,
                                    faseRemessa: 'MEN',
                                    mesReconhecimento: 4,
                                    anoReconhecimento: 2023,
                                    periodo: 2,
                                    origemDosGastos: 'GASTO_EXCLUSIVO',
                                    flgRecuperado: true,
                                    temCorrecoes: false,
                                    ultimaAtualizacao: '17/04/2024'
                                }
                            ]
                        });
                    }
                });
            }

            if (urlTexto.includes('/api/ccos/export')) {
                window.__exportRequest = {
                    url: urlTexto,
                    method: options && options.method,
                    body: options && options.body
                };

                return Promise.resolve({
                    ok: true,
                    headers: {
                        get: function(name) {
                            if (String(name).toLowerCase() === 'content-disposition') {
                                return 'attachment; filename="CCOs_Planificadas_TESTE.xlsx"';
                            }
                            return null;
                        }
                    },
                    blob: function() {
                        return Promise.resolve(new Blob(['teste'], {
                            type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                        }));
                    }
                });
            }

            return originalFetch.apply(this, arguments);
        };
    """)


def preencher_filtros_e_pesquisar(driver):
    """
    Simula o fluxo real do usuário:
    1. Seleciona contrato
    2. Preenche filtros
    3. Clica em Pesquisar
    4. Aguarda a tabela/resultados
    """
    driver.execute_script("""
        const selectContrato = document.getElementById('selectContrato');
        selectContrato.innerHTML = '<option value="">Selecione...</option><option value="CONTRATO-001">CONTRATO-001</option>';
        selectContrato.value = 'CONTRATO-001';

        const selectCampo = document.getElementById('selectCampo');
        selectCampo.innerHTML = '<option value="">Todos</option><option value="ARAM">ARAM</option>';
        selectCampo.value = 'ARAM';

        document.getElementById('inputRemessa').value = '30';
        document.getElementById('inputExercicio').value = '2023';
        document.getElementById('inputPeriodo').value = '1';
        document.getElementById('selectFase').value = 'MEN';
        document.getElementById('selectOrigem').value = 'GASTO_EXCLUSIVO';
    """)

    botao_pesquisar = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "button[onclick='pesquisarPorFiltros()']"))
    )

    driver.execute_script("arguments[0].click();", botao_pesquisar)

    WebDriverWait(driver, 10).until(
        EC.visibility_of_element_located((By.ID, "containerResultados"))
    )

    WebDriverWait(driver, 10).until(
        lambda d: "2 resultado(s)" in d.find_element(By.ID, "totalResultados").text
    )


def aguardar_controles_datatable(driver):
    """
    Aguarda os controles do DataTables serem movidos para o cabeçalho customizado.
    """
    WebDriverWait(driver, 10).until(
        lambda d: d.find_element(By.ID, "containerExibirDataTable").text.strip() != ""
    )

    WebDriverWait(driver, 10).until(
        lambda d: d.find_element(By.ID, "containerPesquisaDataTable").text.strip() != ""
    )


def test_pesquisa_ccos_exibe_botao_exportar_lista_e_nao_exibe_excel_por_linha(selenium):
    abrir_pagina_pesquisa(selenium)
    instalar_fetch_mock_pesquisa_e_exportacao(selenium)
    preencher_filtros_e_pesquisar(selenium)

    tabela = selenium.find_element(By.ID, "tabelaCCOs")

    assert "Ações" in tabela.text
    assert "Exportar" not in tabela.text
    assert "Excel" not in tabela.text

    botao_exportar_lista = WebDriverWait(selenium, 10).until(
        EC.visibility_of_element_located((By.ID, "btnExportarListaCcos"))
    )

    assert botao_exportar_lista.is_displayed()
    assert "Exportar lista" in botao_exportar_lista.text


def test_pesquisa_ccos_mantem_botao_timeline_por_linha(selenium):
    abrir_pagina_pesquisa(selenium)
    instalar_fetch_mock_pesquisa_e_exportacao(selenium)
    preencher_filtros_e_pesquisar(selenium)

    botoes_timeline = selenium.find_elements(By.CSS_SELECTOR, ".btn-timeline")

    assert len(botoes_timeline) >= 2
    assert all("Timeline" in botao.text for botao in botoes_timeline)


def test_pesquisa_ccos_controles_ficam_no_layout_correto(selenium):
    abrir_pagina_pesquisa(selenium)
    instalar_fetch_mock_pesquisa_e_exportacao(selenium)
    preencher_filtros_e_pesquisar(selenium)
    aguardar_controles_datatable(selenium)

    total = selenium.find_element(By.ID, "totalResultados")
    container_exibir = selenium.find_element(By.ID, "containerExibirDataTable")
    container_pesquisa = selenium.find_element(By.ID, "containerPesquisaDataTable")
    botao_exportar = selenium.find_element(By.ID, "btnExportarListaCcos")

    assert "2 resultado(s)" in total.text
    assert "Exibir" in container_exibir.text
    assert "resultados por página" in container_exibir.text
    assert "Pesquisar" in container_pesquisa.text
    assert botao_exportar.is_displayed()

    y_exibir = container_exibir.location["y"]
    y_pesquisa = container_pesquisa.location["y"]
    y_exportar = botao_exportar.location["y"]

    # Exibir, Pesquisar e Exportar lista devem ficar na mesma linha.
    assert abs(y_exibir - y_pesquisa) <= 8
    assert abs(y_pesquisa - y_exportar) <= 8


def test_pesquisa_ccos_clique_exportar_lista_chama_endpoint_com_filtros(selenium):
    abrir_pagina_pesquisa(selenium)
    instalar_fetch_mock_pesquisa_e_exportacao(selenium)
    preencher_filtros_e_pesquisar(selenium)

    botao_exportar = WebDriverWait(selenium, 10).until(
        EC.element_to_be_clickable((By.ID, "btnExportarListaCcos"))
    )

    selenium.execute_script("arguments[0].click();", botao_exportar)

    WebDriverWait(selenium, 10).until(
        lambda driver: driver.execute_script("return window.__exportRequest !== null")
    )

    export_request = selenium.execute_script("return window.__exportRequest")
    pesquisa_request = selenium.execute_script("return window.__pesquisaRequest")

    assert "/api/ccos/export" in export_request["url"]
    assert export_request["method"] == "POST"

    body_exportacao = json.loads(export_request["body"])
    body_pesquisa = json.loads(pesquisa_request["body"])

    assert body_exportacao == body_pesquisa
    assert body_exportacao["contratoCpp"] == "CONTRATO-001"
    assert body_exportacao["campo"] == "ARAM"
    assert body_exportacao["remessa"] == "30"
    assert body_exportacao["faseRemessa"] == "MEN"
