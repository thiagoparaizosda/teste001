from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
TEMPLATE_PATH = ROOT_DIR / "app" / "templates" / "cco_timeline.html"


def ler_template():
    return TEMPLATE_PATH.read_text(encoding="utf-8")


def test_card_timeline_nao_recolhe_ao_clicar_nas_informacoes_quando_expandido():
    html = ler_template()

    assert "function toggleCardTimeline(event, index, forcarToggle = false)" in html
    assert "event.stopPropagation();" in html
    assert "const cardExpandido = !(body.style.display === 'none' || !body.style.display);" in html
    assert "const clicouNoToggle = forcarToggle || (event && event.target.closest('.timeline-toggle-icon'));" in html
    assert "if (cardExpandido && !clicouNoToggle)" in html
    assert "return;" in html


def test_seta_da_timeline_eh_o_controle_explicito_de_recolher_card():
    html = ler_template()

    assert 'class="timeline-toggle-icon" role="button" tabindex="0"' in html
    assert 'onclick="toggleCardTimeline(event, {{ loop.index }}, true)"' in html
    assert "aria-label=\"Expandir ou recolher card da timeline\"" in html


def test_ver_detalhes_impede_propagacao_para_o_card():
    html = ler_template()

    assert "function toggleDetalhes(event, index)" in html
    assert "event.stopPropagation();" in html
    assert 'class="toggle-detalhes"' in html


def test_campos_dos_detalhes_sao_exibidos_com_nome_original_do_banco():
    html = ler_template()

    assert "{{ key }}:" in html
    assert "{{ key | title }}" not in html
    assert "{% if key == 'subTipo' %}Sub Tipo:" not in html
    assert "{% elif key == 'faseRemessa' %}Fase:" not in html


def test_area_clicavel_do_ver_detalhes_fica_restrita_ao_texto_do_link():
    html = ler_template()

    assert "display: inline-flex;" in html
    assert "line-height: 1.2;" in html


def test_detalhes_da_timeline_usam_grid_para_evitar_sobreposicao_de_valor():
    html = ler_template()

    assert '.detalhe-item {' in html
    assert 'grid-template-columns: minmax(180px, 42%) minmax(0, 1fr);' in html
    assert 'class="detalhe-campo"' in html
    assert 'class="detalhe-valor"' in html
    assert 'overflow-wrap: anywhere;' in html
    assert '<strong>{{ key }}:</strong>' not in html
    assert 'class="col-4">\n                                <strong>{{ key }}:</strong>' not in html


def test_botoes_exportar_excel_e_copiar_json_usam_estilo_padronizado_outline_sm():
    html = ler_template()

    assert 'class="btn btn-sm btn-outline-success ms-2 btn-exportar-excel-timeline"' in html
    assert 'class="btn btn-success ms-2 btn-exportar-excel-timeline"' not in html
    assert 'class="btn btn-sm btn-outline-secondary" type="button" onclick="copiarAtributosJSON(event)"' in html
    assert 'class="btn btn-sm btn-secondary" type="button" onclick="copiarAtributosJSON(event)"' not in html
