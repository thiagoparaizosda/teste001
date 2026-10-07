from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
TEMPLATE_PATH = ROOT_DIR / "app" / "templates" / "recalculo" / "executar_recalculo.html"


def ler_template():
    return TEMPLATE_PATH.read_text(encoding="utf-8")


def test_calcular_fator_utiliza_helper_de_formatacao_brasileira():
    html = ler_template()

    assert "function formatarNumeroBR(valor, maxCasasDecimais)" in html
    assert "fatorCorrecao.value = formatarNumeroBR(fator, 6);" in html
    assert "variacaoPercentual.value = formatarNumeroBR(variacao, 3) + '%';" in html


def test_helper_formatar_numero_br_remove_zeros_a_direita():
    html = ler_template()

    # A implementação usa replace dos zeros à direita e troca o ponto pela vírgula.
    assert ".replace(/\\.?0+$/, '')" in html
    assert ".replace('.', ',')" in html


def test_calcular_fator_nao_usa_tofixed_direto():
    html = ler_template()

    assert "fatorCorrecao.value = fator.toFixed(6);" not in html
    assert "variacaoPercentual.value = variacao.toFixed(3) + '%';" not in html


def test_calcular_fator_limpa_campos_quando_tp_invalido():
    html = ler_template()

    assert "fatorCorrecao.value = '';" in html
    assert "variacaoPercentual.value = '';" in html
