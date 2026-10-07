import pytest

def renderizar_template_pesquisa_ccos(app):
    with app.test_request_context("/pesquisa-ccos"):
        return app.jinja_env.get_template("pesquisa_ccos.html").render(
            titulo="Pesquisa de CCOs"
        )


def test_pesquisa_ccos_nao_tem_coluna_exportar_por_linha(app):
    html = renderizar_template_pesquisa_ccos(app)

    assert "<th>Exportar</th>" not in html
    assert "onclick=\"exportarTimeline('${cco.id}')\"" not in html
    assert "btn-exportar" not in html


def test_pesquisa_ccos_mantem_coluna_acoes_e_botao_timeline(app):
    html = renderizar_template_pesquisa_ccos(app)

    assert "<th>Ações</th>" in html
    assert "abrirTimeline('${cco.id}')" in html
    assert "btn-timeline" in html
    assert "fa-history" in html


def test_pesquisa_ccos_tem_botao_exportar_lista(app):
    html = renderizar_template_pesquisa_ccos(app)

    assert 'id="btnExportarListaCcos"' in html
    assert "Exportar lista" in html
    assert "fa-file-excel" in html
    assert "onclick=\"exportarListaCcos()\"" in html


def test_pesquisa_ccos_tem_containers_de_controles_no_layout(app):
    html = renderizar_template_pesquisa_ccos(app)

    assert "resultados-header-top" in html
    assert "resultados-header-bottom" in html
    assert 'id="containerExibirDataTable"' in html
    assert 'id="containerPesquisaDataTable"' in html
    assert "posicionarControlesResultados" in html


def test_pesquisa_ccos_exporta_lista_usando_filtros_da_ultima_pesquisa(app):
    html = renderizar_template_pesquisa_ccos(app)

    assert "let ultimosFiltrosPesquisa = null" in html
    assert "ultimosFiltrosPesquisa = dados" in html
    assert "function exportarListaCcos()" in html
    assert "/api/ccos/export" in html
    assert "body: JSON.stringify(ultimosFiltrosPesquisa)" in html


def test_pesquisa_ccos_datatable_ajustado_sem_coluna_exportar(app):
    html = renderizar_template_pesquisa_ccos(app)

    assert "order: [[4, 'desc']]" in html
    assert "targets: [0], orderable: false" in html
    assert "targets: [9, 10]" in html