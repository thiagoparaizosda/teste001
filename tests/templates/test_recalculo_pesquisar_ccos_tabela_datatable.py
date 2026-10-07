from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
TEMPLATE_PATH = ROOT_DIR / "app" / "templates" / "recalculo" / "pesquisar_ccos.html"


def ler_template():
    return TEMPLATE_PATH.read_text(encoding="utf-8")


def test_tabela_resultados_mantem_colunas_originais_do_arquivo_de_recalculo():
    html = ler_template()

    colunas = [
        "ID da CCO",
        "Contrato",
        "Campo",
        "Remessa",
        "Remessa Exposição",
        "Fase",
        "Exercício",
        "Período",
        "Valor Reconhecido",
        "Status",
        "Ações",
    ]

    for coluna in colunas:
        assert f"<th>{coluna}</th>" in html


def test_tabela_resultados_mantem_botoes_originais_de_acao():
    html = ler_template()

    assert "btn-recalcular" in html
    assert "btn-timeline" in html
    assert "Recalcular CCO" in html
    assert "Ver Timeline" in html
    assert "/recalculo/executar/" in html
    assert "/cco-timeline/" in html
    assert "window.open" in html


def test_tabela_resultados_tem_wrapper_com_scroll_horizontal():
    html = ler_template()

    assert 'class="card-body p-0 resultados-card-body"' in html
    assert 'class="table-responsive tabela-resultados-scroll"' in html
    assert "overflow-x: auto" in html
    assert "overflow-y: hidden" in html
    assert "-webkit-overflow-scrolling: touch" in html


def test_tabela_resultados_nao_usa_largura_fixa_exagerada():
    html = ler_template()

    assert "width: max-content" in html
    assert "min-width: 100%" in html
    assert "white-space: nowrap" in html

    # Garante que não voltou o ajuste anterior que criou espaço branco à direita.
    assert "min-width: 1450px" not in html
    assert "min-width: 1350px" not in html


def test_tabela_resultados_inicializa_datatable_com_paginacao():
    html = ler_template()

    assert "$('#tabelaResultados').DataTable({" in html
    assert "pageLength: 10" in html
    assert "lengthMenu:" in html
    assert "[10, 25, 50, 100, -1]" in html
    assert "[10, 25, 50, 100, 'Todos']" in html


def test_tabela_resultados_inicializa_datatable_com_scrollx():
    html = ler_template()

    assert "scrollX: true" in html
    assert "autoWidth: false" in html
    assert "columns.adjust()" in html


def test_tabela_resultados_configura_idioma_portugues_do_datatable():
    html = ler_template()

    assert "cdn.datatables.net/plug-ins/1.13.4/i18n/pt-BR.json" in html


def test_tabela_resultados_define_ordenacao_padrao_por_remessa():
    html = ler_template()

    assert "order: [[3, 'desc']]" in html


def test_tabela_resultados_define_coluna_acoes_sem_ordenacao():
    html = ler_template()

    assert "{ targets: [10], orderable: false }" in html


def test_tabela_resultados_define_coluna_valor_reconhecido_alinhada_a_direita():
    html = ler_template()

    assert "{ targets: [8], className: 'text-end' }" in html


def test_datatable_eh_destruido_antes_de_nova_pesquisa_para_evitar_controles_duplicados():
    html = ler_template()

    assert "function destruirTabelaResultados()" in html
    assert "$.fn.DataTable.isDataTable('#tabelaResultados')" in html
    assert "$('#tabelaResultados').DataTable().clear().destroy();" in html
    assert "tabelaResultadosDataTable = null;" in html


def test_exibir_resultados_recria_datatable_a_cada_pesquisa():
    html = ler_template()

    assert "function exibirResultados(resultados)" in html
    assert "destruirTabelaResultados();" in html
    assert "inicializarTabelaResultados();" in html


def test_limpar_filtros_remove_datatable_e_resultados_da_tela():
    html = ler_template()

    assert "btnLimparFiltros.addEventListener('click'" in html
    assert "destruirTabelaResultados();" in html
    assert "corpoTabela.innerHTML = '';" in html
    assert "totalResultados.textContent = '0';" in html


def test_tabela_resultados_mantem_renderizacao_dos_dados_originais():
    html = ler_template()

    campos_renderizados = [
        "cco.id",
        "cco.contratoCpp",
        "cco.campo",
        "cco.remessa",
        "cco.remessaExposicao",
        "cco.faseRemessa",
        "cco.exercicio",
        "cco.periodo",
        "cco.valorReconhecidoComOH",
        "cco.flgRecuperado",
    ]

    for campo in campos_renderizados:
        assert campo in html


def test_tabela_resultados_nao_copia_estrutura_completa_da_outra_tela():
    html = ler_template()

    # A tela de recálculo deve continuar usando seus próprios ids/estrutura.
    assert "tabelaCCOs" not in html
    assert "containerPesquisaDataTable" not in html
    assert "containerExibirDataTable" not in html
    assert "btnExportarListaCcos" not in html
