import pytest
from datetime import datetime
from bson import Decimal128


@pytest.fixture
def cco_exemplo():
    return {
        "_id": "CCO_TEST_001",
        "contratoCpp": "CONTRATO-001",
        "campo": "CAMPO_TESTE",
        "remessa": "REM-001",
        "faseRemessa": "FASE-01",
        "periodo": "2024-03",
        "anoReconhecimento": 2024,
        "mesReconhecimento": 3,

        "valorReconhecido": Decimal128("1234567.89"),
        "valorReconhecidoComOH": Decimal128("1300000.00"),
        "valorLancamentoTotal": Decimal128("1500000.00"),
        "valorReconhecivel": Decimal128("1400000.00"),
        "valorNaoReconhecido": Decimal128("1000.00"),
        "valorNaoPassivelRecuperacao": Decimal128("500.00"),
        "overHeadTotal": Decimal128("10000.00"),
        "overHeadExploracao": Decimal128("4000.00"),
        "overHeadProducao": Decimal128("6000.00"),
        "valorReconhecidoExploracao": Decimal128("700000.00"),
        "valorReconhecidoProducao": Decimal128("567000.00"),
        "valorRecuperado": Decimal128("300.00"),
        "valorRecuperadoTotal": Decimal128("500.00"),
        "taxaCorrecao": 0.1234,
        "igpmAcumulado": 0.15,
        "igpmAcumuladoReais": Decimal128("15000.00"),
        "ipcaAcumulado": 0.10,
        "ipcaAcumuladoReais": Decimal128("10000.00"),
        "diferencaValor": Decimal128("2000.00"),
        "quantidadeLancamento": 10,

        "dataLancamento": datetime(2024, 3, 15, 14, 30),
        "dataReconhecimento": datetime(2024, 3, 16, 10, 0),
        "dataCriacao": datetime(2024, 3, 17, 9, 0),
        "dataAtualizacao": datetime(2024, 3, 18, 11, 0),
        "dataCriacaoCorrecao": datetime(2024, 3, 19, 12, 0),
        "dataCorrecao": datetime(2024, 3, 20, 13, 0),
        "createdAt": datetime(2024, 3, 21, 14, 0),
        "updatedAt": datetime(2024, 3, 22, 15, 0),

        "ativo": True,
        "flgRecuperado": False,
        "recuperado": True,
        "corrigido": False,
        "processado": True,
        "status": "ATIVO",
        "situacao": "PROCESSADO",
        "tipo": "IPCA",
        "subTipo": "CORRECAO",
        "transferencia": False,

        "campoExtraString": "valor extra",
        "campoExtraArray": [1, 2, 3],
        "campoExtraObject": {"chave": "valor"},
    }


@pytest.fixture
def valores_atuais():
    return {
        "data_lancamento": "15/03/2024",
        "data_reconhecimento": "16/03/2024",
        "fonte": "Teste",
        "data_atualizacao": "18/03/2024",
        "valorReconhecido": 1234567.89,
        "valorReconhecidoComOH": 1300000.00,
        "overHeadTotal": 10000.00,
        "quantidadeLancamento": 10,
        "valorNaoReconhecido": 1000.00,
        "valorLancamentoTotal": 1500000.00,
        "valorReconhecivel": 1400000.00,
        "valorNaoPassivelRecuperacao": 500.00,
        "overHeadExploracao": 4000.00,
        "overHeadProducao": 6000.00,
        "valorReconhecidoExploracao": 700000.00,
        "valorReconhecidoProducao": 567000.00,
        "valorRecuperado": 300.00,
        "taxaCorrecao": 0.1234,
        "igpmAcumuladoReais": 15000.00,
    }


@pytest.fixture
def timeline():
    return [
        {
            "dataCorrecao": True,
            "dataCorrecaoFormatada": "15/03/2024",
            "titulo": "Criação da CCO",
            "descricao": "CCO criada",
            "cor": "primary",
            "icone": "fas fa-plus",
            "tipo": "CRIACAO",
            "valores": {
                "valorReconhecido": 1234567.89,
                "valorReconhecidoComOH": 1300000.00,
                "overHeadTotal": 10000.00,
                "diferencaValor": 0,
                "valorRecuperado": 0,
                "valorRecuperadoTotal": 0,
                "taxaCorrecao": 0,
                "igpmAcumuladoReais": 0,
                "valorNaoReconhecido": 0,
                "valorReconhecidoExploracao": 700000.00,
                "valorReconhecidoProducao": 567000.00,
            },
            "detalhes": {
                "ativo": True,
                "observacao": "Teste"
            },
            "dataCriacaoCorrecao": None,
        }
    ]


def renderizar_template_timeline(app, cco_exemplo, valores_atuais, timeline):
    """
    Renderiza o template dentro de um request context.

    Isso evita o erro:
    RuntimeError: Unable to build URLs outside an active request

    O template cco_timeline.html estende o base.html, e o base.html usa url_for().
    Por isso, app.app_context() sozinho não é suficiente para renderizar esse template.
    """
    with app.test_request_context("/cco-timeline/CCO_TEST_001"):
        return app.jinja_env.get_template("cco_timeline.html").render(
            titulo="Timeline CCO Teste",
            cco=cco_exemplo,
            valores_atuais=valores_atuais,
            timeline=timeline,
            cco_json="{}",
        )


def test_template_renderiza_card_atributos(app, cco_exemplo, valores_atuais, timeline):
    html = renderizar_template_timeline(app, cco_exemplo, valores_atuais, timeline)

    assert "Todos os Atributos da CCO" in html
    assert "search-atributos" in html
    assert "accordion-atributos" in html


def test_template_renderiza_campos_principais(app, cco_exemplo, valores_atuais, timeline):
    html = renderizar_template_timeline(app, cco_exemplo, valores_atuais, timeline)

    campos_obrigatorios = [
        "_id",
        "contratoCpp",
        "campo",
        "valorReconhecido",
        "dataLancamento",
        "flgRecuperado",
        "campoExtraString",
    ]

    for campo in campos_obrigatorios:
        assert campo in html


def test_template_formata_decimal128(app, cco_exemplo, valores_atuais, timeline):
    html = renderizar_template_timeline(app, cco_exemplo, valores_atuais, timeline)

    assert "R$ 1.234.567,89" in html


def test_template_formata_boolean(app, cco_exemplo, valores_atuais, timeline):
    html = renderizar_template_timeline(app, cco_exemplo, valores_atuais, timeline)

    assert "Sim" in html
    assert "Não" in html


def test_template_contem_funcoes_busca(app, cco_exemplo, valores_atuais, timeline):
    html = renderizar_template_timeline(app, cco_exemplo, valores_atuais, timeline)

    assert "filtrarAtributos" in html
    assert "limparBuscaAtributos" in html
    assert "search-results-count" in html
    assert "no-results-msg" in html

def test_template_renderiza_todos_os_atributos_do_mock(app, cco_exemplo, valores_atuais, timeline):
    html = renderizar_template_timeline(app, cco_exemplo, valores_atuais, timeline)

    for campo in cco_exemplo.keys():
        assert campo in html, f"Campo {campo} não foi renderizado no template"