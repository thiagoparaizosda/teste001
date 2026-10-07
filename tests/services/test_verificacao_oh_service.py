"""
Testes unitários para o serviço de Verificação de OH (FEAT-001).

Cobre os cenários de aceite da spec specs/2026-Q3/FEAT-001-analise-de-oh-baseline-retroativa.spec.md:
  Cenário 1  - busca respeita filtros e limite de 500 CCOs (FR-001)
  Cenário 2  - classificação OK do bloco RAIZ (FR-002 a FR-006)
  Cenário 3  - base negativa gera ATENÇÃO, não ERRO (FR-004)
  Cenário 4  - cruzamento de faixa aplica cálculo proporcional (FR-005)
  Cenário 5  - exportação CSV contém exatamente 30 colunas (FR-009)
  Cenário 7  - painel de KPIs reflete o resultado da verificação (FR-007)
  Cenário 9  - drill-down exibe a CCO de referência e o contrato/ano completos (FR-010)
  Cenário 11 - GASTO_AEGV é sempre ATENÇÃO, mesmo com OH != 0 (FR-013 — GAP conhecido)
"""

from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from bson.decimal128 import Decimal128

from app.services.verificacao_oh_service import (
    VerificacaoOHService,
    _calcular_oh_exp_por_faixas,
)


def montar_service_com_db(db_mock):
    """Cria o service injetando um mock de Database (sem conexão real ao Mongo)."""
    return VerificacaoOHService(db_mock)


def cco_base(**overrides):
    """CCO com bloco RAIZ 'perfeito': Prod=1%, Exp dentro da 1ª faixa (3%), Total=Exp+Prod."""
    base = {
        "_id": "CCO-001",
        "contratoCpp": "CONTRATO-A",
        "campo": "CAMPO-A",
        "remessa": 10,
        "remessaExposicao": 10,
        "faseRemessa": "MEN",
        "mesAnoReferencia": "2026-01",
        "dataReconhecimento": "2026-01-15",
        "origemDosGastos": "GASTO_COMPARTILHADO",
        "flgRecuperado": False,
        "valorReconhecidoExploracao": Decimal128("1000000.00"),
        "overHeadExploracao": Decimal128("30000.00"),  # 3% de 1.000.000
        "valorReconhecidoProducao": Decimal128("500000.00"),
        "overHeadProducao": Decimal128("5000.00"),  # 1% de 500.000
        "overHeadTotal": Decimal128("35000.00"),  # 30000 + 5000
        "correcoesMonetarias": [],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Cenário 1 — busca respeita filtros e limite de 500 CCOs (FR-001)
# ---------------------------------------------------------------------------

class TestBuscarCcos:
    def test_busca_aplica_filtros_informados(self):
        db_mock = MagicMock()
        cursor_mock = MagicMock()
        cursor_mock.sort.return_value = cursor_mock
        cursor_mock.limit.return_value = []
        db_mock.conta_custo_oleo_entity.find.return_value = cursor_mock

        service = montar_service_com_db(db_mock)
        service.buscar_ccos({
            "contratoCpp": "CONTRATO-A",
            "campo": "CAMPO-A",
            "faseRemessa": "MEN",
            "origemDosGastos": "GASTO_COMPARTILHADO",
            "flgRecuperado": "true",
        })

        query_usada = db_mock.conta_custo_oleo_entity.find.call_args[0][0]
        assert query_usada["contratoCpp"] == "CONTRATO-A"
        assert query_usada["campo"] == "CAMPO-A"
        assert query_usada["faseRemessa"] == "MEN"
        assert query_usada["origemDosGastos"] == "GASTO_COMPARTILHADO"
        assert query_usada["flgRecuperado"] is True

    def test_busca_respeita_limite_maximo_de_500(self):
        db_mock = MagicMock()
        cursor_mock = MagicMock()
        cursor_mock.sort.return_value = cursor_mock
        cursor_mock.limit.return_value = []
        db_mock.conta_custo_oleo_entity.find.return_value = cursor_mock

        service = montar_service_com_db(db_mock)
        service.buscar_ccos({"limite": "10000"})

        cursor_mock.limit.assert_called_once_with(500)

    def test_busca_aceita_sintaxe_min_max_para_remessa(self):
        db_mock = MagicMock()
        cursor_mock = MagicMock()
        cursor_mock.sort.return_value = cursor_mock
        cursor_mock.limit.return_value = []
        db_mock.conta_custo_oleo_entity.find.return_value = cursor_mock

        service = montar_service_com_db(db_mock)
        service.buscar_ccos({"remessa": "10-20"})

        query_usada = db_mock.conta_custo_oleo_entity.find.call_args[0][0]
        assert query_usada["remessa"] == {"$gte": 10, "$lte": 20}


# ---------------------------------------------------------------------------
# Cenário 2 — classificação OK do bloco RAIZ (FR-002 a FR-006)
# ---------------------------------------------------------------------------

def test_bloco_raiz_com_oh_corretos_e_classificado_como_ok():
    db_mock = MagicMock()
    service = montar_service_com_db(db_mock)

    resultados = service.verificar_oh([cco_base()])

    assert len(resultados) == 1
    r = resultados[0]
    assert r["status_geral"] == "OK"
    assert r["status_exploracao"] == "OK"
    assert r["status_producao"] == "OK"
    assert r["status_total"] == "OK"


def test_verificacao_processa_apenas_correcoes_com_algum_campo_oh_populado():
    db_mock = MagicMock()
    service = montar_service_com_db(db_mock)

    cco = cco_base(correcoesMonetarias=[
        {"tipo": "IPCA", "subTipo": "AUTO", "dataCorrecao": "2026-02-01"},  # sem campos de OH
        {
            "tipo": "IPCA", "subTipo": "AUTO", "dataCorrecao": "2026-03-01",
            "valorReconhecidoExploracao": Decimal128("1000000.00"),
            "overHeadExploracao": Decimal128("30000.00"),
            "valorReconhecidoProducao": Decimal128("500000.00"),
            "overHeadProducao": Decimal128("5000.00"),
            "overHeadTotal": Decimal128("35000.00"),
        },
    ])

    resultados = service.verificar_oh([cco])

    # 1 bloco RAIZ + apenas 1 bloco de correção (o sem campos de OH é ignorado)
    assert len(resultados) == 2
    assert resultados[1]["origem"].startswith("CORREÇÃO IPCA/AUTO")


# ---------------------------------------------------------------------------
# Cenário 3 — base negativa gera ATENÇÃO, não ERRO (FR-004)
# ---------------------------------------------------------------------------

def test_base_producao_negativa_e_atencao_nao_erro():
    db_mock = MagicMock()
    service = montar_service_com_db(db_mock)

    cco = cco_base(
        valorReconhecidoProducao=Decimal128("-100.00"),
        overHeadProducao=Decimal128("0.00"),
        overHeadTotal=Decimal128("30000.00"),  # exp(30000) + prod(0)
    )

    resultados = service.verificar_oh([cco])
    r = resultados[0]

    assert r["status_producao"] == "ATENCAO"
    assert r["status_producao"] != "ERRO"


def test_base_exploracao_negativa_e_atencao_nao_erro():
    db_mock = MagicMock()
    service = montar_service_com_db(db_mock)

    cco = cco_base(
        valorReconhecidoExploracao=Decimal128("-500.00"),
        overHeadExploracao=Decimal128("0.00"),
        overHeadTotal=Decimal128("5000.00"),  # exp(0) + prod(5000)
    )

    resultados = service.verificar_oh([cco])
    r = resultados[0]

    assert r["status_exploracao"] == "ATENCAO"
    assert r["status_exploracao"] != "ERRO"


# ---------------------------------------------------------------------------
# Cenário 4 — cruzamento de faixa aplica cálculo proporcional (FR-005)
# ---------------------------------------------------------------------------

def test_cruzamento_de_faixa_calcula_proporcionalmente():
    acumulado_antes = Decimal("4500000")
    valor_exploracao = Decimal("1000000")

    oh_total, fatias = _calcular_oh_exp_por_faixas(acumulado_antes, valor_exploracao)

    # R$500.000 a 3% (R$15.000,00) + R$500.000 a 2% (R$10.000,00) = R$25.000,00
    assert oh_total == Decimal("25000")
    assert len(fatias) == 2
    assert fatias[0]["taxa_pct"] == 3
    assert fatias[0]["valor_na_faixa"] == pytest.approx(500000.0)
    assert fatias[1]["taxa_pct"] == 2
    assert fatias[1]["valor_na_faixa"] == pytest.approx(500000.0)


def test_sem_cruzamento_de_faixa_aplica_taxa_unica():
    acumulado_antes = Decimal("0")
    valor_exploracao = Decimal("1000000")

    oh_total, fatias = _calcular_oh_exp_por_faixas(acumulado_antes, valor_exploracao)

    assert oh_total == Decimal("30000")  # 3% sobre o valor inteiro
    assert len(fatias) == 1
    assert fatias[0]["taxa_pct"] == 3


# ---------------------------------------------------------------------------
# Cenário 5 — exportação CSV com exatamente 30 colunas (FR-009)
# ---------------------------------------------------------------------------

def test_csv_gerado_possui_exatamente_30_colunas_e_bom_utf8():
    db_mock = MagicMock()
    service = montar_service_com_db(db_mock)

    resultados = service.verificar_oh([cco_base()])
    csv_texto = service.gerar_csv(resultados)

    assert csv_texto.startswith("\ufeff")
    primeira_linha = csv_texto.split("\ufeff", 1)[1].splitlines()[0]
    colunas = primeira_linha.split(";")
    assert len(colunas) == 30


def test_csv_usa_ponto_e_virgula_e_virgula_decimal():
    db_mock = MagicMock()
    service = montar_service_com_db(db_mock)

    resultados = service.verificar_oh([cco_base()])
    csv_texto = service.gerar_csv(resultados)

    linhas = csv_texto.lstrip("\ufeff").splitlines()
    assert ";" in linhas[0]
    # valores numéricos usam vírgula como separador decimal (formatação BR)
    assert "30000,0000" in linhas[1] or "30000,00" in linhas[1]


# ---------------------------------------------------------------------------
# Cenário 7 — painel de KPIs reflete exatamente o resultado (FR-007)
# ---------------------------------------------------------------------------

def test_calcular_estatisticas_reflete_contagem_exata():
    db_mock = MagicMock()
    service = montar_service_com_db(db_mock)

    cco_ok = cco_base(_id="CCO-OK")
    cco_erro = cco_base(
        _id="CCO-ERRO",
        overHeadProducao=Decimal128("999.00"),  # não é 1% da base -> ERRO
    )
    cco_atencao = cco_base(
        _id="CCO-ATENCAO",
        origemDosGastos="GASTO_AEGV",
    )

    resultados = service.verificar_oh([cco_ok, cco_erro, cco_atencao])
    stats = service.calcular_estatisticas(resultados)

    assert stats["ccos_unicas"] == 3
    assert stats["total_linhas"] == 3
    assert stats["total_ok"] == 1
    assert stats["total_erros"] == 1
    assert stats["total_atencao"] == 1
    assert stats["erros_producao"] == 1


# ---------------------------------------------------------------------------
# Cenário 9 — drill-down exibe a CCO de referência e o contrato/ano completos (FR-010)
# ---------------------------------------------------------------------------

def test_analise_faixas_retorna_todas_ccos_do_contrato_ano_em_ordem_cronologica():
    db_mock = MagicMock()

    cco_ref = {
        "_id": "CCO-003",
        "contratoCpp": "CONTRATO-A",
        "anoReconhecimento": 2026,
        "origemDosGastos": "GASTO_COMPARTILHADO",
    }

    ccos_do_contrato_ano = [
        {
            "_id": f"CCO-{i:03d}",
            "campo": "CAMPO-A",
            "remessa": i,
            "dataReconhecimento": f"2026-0{i}-01",
            "faseRemessa": "MEN",
            "origemDosGastos": "GASTO_COMPARTILHADO",
            "valorReconhecidoExploracao": Decimal128("1000000.00"),
            "overHeadExploracao": Decimal128("30000.00"),
        }
        for i in range(1, 6)
    ]

    db_mock.conta_custo_oleo_entity.find_one.return_value = cco_ref
    cursor_mock = MagicMock()
    cursor_mock.sort.return_value = ccos_do_contrato_ano
    db_mock.conta_custo_oleo_entity.find.return_value = cursor_mock

    service = montar_service_com_db(db_mock)
    resultado = service.analisar_faixas_exploracao("CCO-003")

    assert resultado["contrato"] == "CONTRATO-A"
    assert resultado["ano"] == 2026
    assert len(resultado["linhas"]) == 5
    assert resultado["linhas"][2]["cco_id"] == "CCO-003"
    assert resultado["linhas"][2]["eh_referencia"] is True
    assert all(not l["eh_referencia"] for i, l in enumerate(resultado["linhas"]) if i != 2)


def test_analise_faixas_lanca_erro_quando_cco_nao_encontrada():
    db_mock = MagicMock()
    db_mock.conta_custo_oleo_entity.find_one.return_value = None

    service = montar_service_com_db(db_mock)

    with pytest.raises(ValueError):
        service.analisar_faixas_exploracao("CCO-INEXISTENTE")


# ---------------------------------------------------------------------------
# Cenário 11 — GASTO_AEGV é sempre ATENÇÃO, mesmo com OH != 0 (FR-013, GAP conhecido)
# ---------------------------------------------------------------------------

def test_origem_gasto_aegv_e_sempre_atencao_mesmo_com_oh_diferente_de_zero():
    db_mock = MagicMock()
    service = montar_service_com_db(db_mock)

    cco = cco_base(
        origemDosGastos="GASTO_AEGV",
        overHeadExploracao=Decimal128("999999.00"),  # completamente fora de qualquer taxa válida
    )

    resultados = service.verificar_oh([cco])
    r = resultados[0]

    assert r["status_geral"] == "ATENCAO"
    assert r["status_exploracao"] == "ATENCAO"
    assert r["status_producao"] == "ATENCAO"
    assert r["status_total"] == "ATENCAO"
