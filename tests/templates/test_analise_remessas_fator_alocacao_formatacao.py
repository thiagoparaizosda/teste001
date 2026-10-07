from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
TEMPLATE_PATH = ROOT_DIR / "app" / "templates" / "analise_remessas.html"


def ler_template():
    return TEMPLATE_PATH.read_text(encoding="utf-8")


def test_pagina_define_helper_formatar_numero_br():
    html = ler_template()

    assert "function formatarNumeroBR(valor, maxCasasDecimais)" in html
    assert ".replace(/\\.?0+$/, '')" in html
    assert ".replace('.', ',')" in html


def test_fator_allocacao_usado_nao_exibe_valor_cru():
    html = ler_template()

    assert "${info.fatorAlocacao || 'N/A'}" not in html
    assert "${formatarNumeroBR(info.fatorAlocacao) || 'N/A'}" in html


def test_fator_allocacao_mantem_label():
    html = ler_template()

    assert "<td>Fator Alocação</td>" in html
