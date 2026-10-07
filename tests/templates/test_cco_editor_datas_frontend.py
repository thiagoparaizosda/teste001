from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
TEMPLATE_PATH = ROOT_DIR / "app" / "templates" / "cco_editor" / "editar.html"


def ler_template():
    return TEMPLATE_PATH.read_text(encoding="utf-8")


def test_card_de_correcao_mantem_data_original_em_atributo_separado():
    html = ler_template()

    assert 'data-data-correcao="{{ correcao.dataCorrecao }}"' in html
    assert 'data-data-correcao-original="{{ correcao.dataCorrecao }}"' in html


def test_card_de_correcao_tem_funcao_para_formatar_data_data_correcao_no_inspect():
    html = ler_template()

    assert "function formatarAtributoDataCorrecaoCard(card)" in html
    assert "card.dataset.dataCorrecao = valorFormatado;" in html
    assert "card.setAttribute('data-data-correcao', valorFormatado);" in html


def test_inicializacao_formata_data_data_correcao_dos_cards():
    html = ler_template()

    assert "document.querySelectorAll('.correcao-card').forEach(formatarAtributoDataCorrecaoCard);" in html


def test_data_original_continua_disponivel_para_ordenacao():
    html = ler_template()

    assert "card.dataset.dataCorrecaoOriginal = valorOriginal;" in html
    assert "card.setAttribute('data-data-correcao-original', valorOriginal);" in html
    assert "function obterTimestampDataCorrecao(card)" in html
    assert "card.dataset.dataCorrecaoOriginal || card.dataset.dataCorrecao" in html


def test_ordenacao_das_correcoes_nao_usa_new_date_diretamente_no_atributo_formatado():
    html = ler_template()

    assert "obterTimestampDataCorrecao(a) - obterTimestampDataCorrecao(b)" in html
    assert "new Date(a.dataset.dataCorrecao) - new Date(b.dataset.dataCorrecao)" not in html


def test_timestamp_aceita_data_formatada_dd_mm_yyyy_hh_mm_ss():
    html = ler_template()

    assert "function timestampDataParaOrdenacao(valor)" in html
    assert r"^(\d{2})\/(\d{2})\/(\d{4}) (\d{2}):(\d{2}):(\d{2})$" in html
    assert "Number(mes) - 1" in html


def test_alterar_campo_data_correcao_atualiza_atributo_do_card():
    html = ler_template()

    assert "if (nome === 'dataCorrecao')" in html
    assert "const card = document.getElementById('correcao_' + indice);" in html
    assert "card.setAttribute('data-data-correcao', valorFormatado);" in html
