from pathlib import Path
import re


ROOT_DIR = Path(__file__).resolve().parents[2]
TEMPLATE_PATH = ROOT_DIR / "app" / "templates" / "pesquisa_ccos.html"


def ler_template():
    return TEMPLATE_PATH.read_text(encoding="utf-8")


def extrair_input_por_id(html: str, input_id: str) -> str:
    padrao = re.compile(rf'<input[^>]+id="{re.escape(input_id)}"[^>]*>')
    match = padrao.search(html)
    assert match, f"Input {input_id} não encontrado"
    return match.group(0)


def extrair_select_por_id(html: str, select_id: str) -> str:
    padrao = re.compile(rf'<select[^>]+id="{re.escape(select_id)}"[^>]*>(.*?)</select>', re.DOTALL)
    match = padrao.search(html)
    assert match, f"Select {select_id} não encontrado"
    return match.group(1)


def test_campo_periodo_nao_usa_type_number_para_evitar_bloqueio_de_foco():
    html = ler_template()
    input_periodo = extrair_input_por_id(html, "inputPeriodo")

    assert 'type="text"' in input_periodo
    assert 'inputmode="numeric"' in input_periodo
    assert 'maxlength="2"' in input_periodo
    assert 'oninput="normalizarCampoPeriodo(this)"' in input_periodo
    assert 'type="number"' not in input_periodo


def test_campo_periodo_possui_normalizacao_e_validacao_de_mes():
    html = ler_template()

    assert "function normalizarCampoPeriodo(input)" in html
    assert "input.value.replace(/\\D/g, '').slice(0, 2)" in html
    assert "function obterPeriodoPesquisa()" in html
    assert "periodoNumero < 1 || periodoNumero > 12" in html
    assert "periodo: periodo" in html


def test_fase_remessa_possui_opcao_aud():
    html = ler_template()
    select_fase = extrair_select_por_id(html, "selectFase")

    assert '<option value="AUD">AUD</option>' in select_fase


def test_coluna_ano_mes_rec_possui_label_correto():
    html = ler_template()

    assert "<th>Mês/Ano Rec.</th>" in html
    assert "<th>Ano/Mês Rec.</th>" not in html
    assert "<th>Ano/Mes Rec.</th>" not in html


def test_coluna_ano_mes_rec_usa_mascara_mm_yyyy():
    html = ler_template()

    assert "function formatarAnoMesReconhecimento(mes, ano)" in html
    assert "String(mesNumero).padStart(2, '0') + '/' + anoNumero" in html
    assert "${formatarAnoMesReconhecimento(cco.mesReconhecimento, cco.anoReconhecimento)}" in html
    assert "${cco.mesReconhecimento}/${cco.anoReconhecimento}" not in html
