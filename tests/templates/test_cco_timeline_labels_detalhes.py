from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
TEMPLATE_PATH = ROOT_DIR / "app" / "templates" / "cco_timeline.html"


def ler_template():
    return TEMPLATE_PATH.read_text(encoding="utf-8")


def test_detalhes_da_timeline_possuem_mapa_de_labels_amigaveis():
    html = ler_template()

    assert "labels_detalhes_timeline = {" in html
    assert "'dataLancamento': 'Data do Lançamento'" in html
    assert "'dataReconhecimento': 'Data do Reconhecimento'" in html
    assert "'contrato': 'Contrato'" in html


def test_detalhes_da_timeline_nao_exibem_chave_crua_por_padrao():
    html = ler_template()

    assert "{{ labels_detalhes_timeline.get(key, key) }}:" in html
    assert "{{ key }}:" not in html


def test_campos_da_imagem_estao_com_labels_para_usuario():
    html = ler_template()

    assert "'remessaExposicao': 'Remessa de Exposição'" in html
    assert "'quantidadeLancamento': 'Quantidade de Lançamentos'" in html
    assert "'anoReconhecimento': 'Ano do Reconhecimento'" in html
    assert "'mesReconhecimento': 'Mês do Reconhecimento'" in html
    assert "'mesAnoReferencia': 'Mês/Ano de Referência'" in html
    assert "'faseRemessa': 'Fase da Remessa'" in html
    assert "'faseRespostaGestora': 'Fase Resposta Gestora'" in html
    assert "'periodo': 'Período'" in html
    assert "'version': 'Versão'" in html


def test_data_criacao_correcao_tambem_usa_label_amigavel():
    html = ler_template()

    assert "dataCriacaoCorrecao:</div>" not in html
    assert "labels_detalhes_timeline.get('dataCriacaoCorrecao', 'Data de Criação da Correção')" in html


def test_labels_de_valores_financeiros_principais_estao_humanizados():
    html = ler_template()

    assert "'valorReconhecido': 'Valor Reconhecido'" in html
    assert "'valorReconhecidoComOH': 'Valor Reconhecido com OH'" in html
    assert "'valorNaoPassivelRecuperacao': 'Valor Não Passível de Recuperação'" in html
    assert "'diferencaValor': 'Diferença de Valor'" in html
