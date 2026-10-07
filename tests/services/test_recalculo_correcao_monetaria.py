from copy import deepcopy

import pytest
from bson.decimal128 import Decimal128
from freezegun import freeze_time

from app.services.recalculo_service import RecalculoService


def montar_service_sem_mongo():
    """
    Cria o service sem chamar __init__, evitando abrir conexão real com MongoDB.
    Os testes abaixo exercitam apenas as regras auxiliares adicionadas.
    """
    return RecalculoService.__new__(RecalculoService)


def decimal_para_float(valor):
    if isinstance(valor, Decimal128):
        return float(valor.to_decimal())
    return float(valor)


def test_nova_correcao_usa_valor_reconhecido_oh_original_da_correcao_monetaria_anterior():
    service = montar_service_sem_mongo()

    cco = {
        "_id": "CCO_TESTE",
        "valorReconhecidoComOH": Decimal128("1000.00"),
    }

    ultima_correcao = {
        "tipo": "RETIFICACAO",
        "valorReconhecidoOhOriginal": Decimal128("777.77"),
        "valorReconhecidoComOH": Decimal128("900.00"),
    }

    resultado = service._obter_valor_reconhecido_oh_original_para_nova_correcao(
        cco,
        ultima_correcao,
    )

    assert isinstance(resultado, Decimal128)
    assert decimal_para_float(resultado) == pytest.approx(777.77)


def test_nova_correcao_aceita_campo_valor_reconhecido_com_oh_original_da_correcao_anterior():
    service = montar_service_sem_mongo()

    cco = {
        "_id": "CCO_TESTE",
        "valorReconhecidoComOH": Decimal128("1000.00"),
    }

    ultima_correcao = {
        "tipo": "RETIFICACAO",
        "valorReconhecidoComOhOriginal": Decimal128("888.88"),
    }

    resultado = service._obter_valor_reconhecido_oh_original_para_nova_correcao(
        cco,
        ultima_correcao,
    )

    assert decimal_para_float(resultado) == pytest.approx(888.88)


def test_nova_correcao_aceita_variacao_com_oh_maiusculo_do_campo_original():
    service = montar_service_sem_mongo()

    cco = {
        "_id": "CCO_TESTE",
        "valorReconhecidoComOH": Decimal128("1000.00"),
    }

    ultima_correcao = {
        "tipo": "RETIFICACAO",
        "valorReconhecidoComOHOriginal": Decimal128("999.99"),
    }

    resultado = service._obter_valor_reconhecido_oh_original_para_nova_correcao(
        cco,
        ultima_correcao,
    )

    assert decimal_para_float(resultado) == pytest.approx(999.99)


def test_nova_correcao_sem_correcao_anterior_usa_valor_reconhecido_com_oh_da_raiz():
    service = montar_service_sem_mongo()

    cco = {
        "_id": "CCO_TESTE",
        "valorReconhecidoComOH": Decimal128("1234.56"),
        "correcoesMonetarias": [],
    }

    resultado = service._obter_valor_reconhecido_oh_original_para_nova_correcao(
        cco,
        None,
    )

    assert isinstance(resultado, Decimal128)
    assert decimal_para_float(resultado) == pytest.approx(1234.56)


def test_nova_correcao_sem_lista_de_correcoes_usa_valor_reconhecido_com_oh_da_raiz():
    service = montar_service_sem_mongo()

    cco = {
        "_id": "CCO_TESTE",
        "valorReconhecidoComOH": Decimal128("4321.99"),
    }

    resultado = service._obter_valor_reconhecido_oh_original_para_nova_correcao(
        cco,
        None,
    )

    assert decimal_para_float(resultado) == pytest.approx(4321.99)


def test_nova_correcao_sem_valor_anterior_e_sem_valor_na_raiz_usa_zero():
    service = montar_service_sem_mongo()

    cco = {
        "_id": "CCO_TESTE",
        "correcoesMonetarias": [],
    }

    resultado = service._obter_valor_reconhecido_oh_original_para_nova_correcao(
        cco,
        None,
    )

    assert isinstance(resultado, Decimal128)
    assert decimal_para_float(resultado) == pytest.approx(0)


def test_executar_correcao_monetaria_cria_nova_correcao_com_valor_original_da_correcao_anterior_e_atualiza_raiz():
    service = montar_service_sem_mongo()

    cco_original = {
        "_id": "CCO_TESTE",
        "contratoCpp": "Contrato",
        "campo": "CAMPO",
        "remessa": 1,
        "remessaExposicao": 1,
        "faseRemessa": "MEN",
        "exercicio": 2024,
        "periodo": 2,
        "flgRecuperado": False,
        "valorReconhecido": Decimal128("100.00"),
        "valorReconhecidoComOH": Decimal128("120.00"),
        "overHeadTotal": Decimal128("20.00"),
        "valorLancamentoTotal": Decimal128("100.00"),
        "quantidadeLancamento": 1,
        "valorNaoReconhecido": Decimal128("0.00"),
        "valorReconhecivel": Decimal128("100.00"),
        "valorNaoPassivelRecuperacao": Decimal128("0.00"),
        "valorReconhecidoExploracao": Decimal128("40.00"),
        "valorReconhecidoProducao": Decimal128("60.00"),
        "overHeadExploracao": Decimal128("8.00"),
        "overHeadProducao": Decimal128("12.00"),
        "correcoesMonetarias": [
            {
                "tipo": "RETIFICACAO",
                "valorReconhecido": Decimal128("150.00"),
                "valorReconhecidoComOH": Decimal128("180.00"),
                "overHeadTotal": Decimal128("30.00"),
                "valorReconhecidoOhOriginal": Decimal128("777.77"),
            }
        ],
    }

    metadata = {
        "tp_original": 50.0,
        "tp_correcao": 60.0,
    }

    cco_recalculada, _ = service._executar_correcao_monetaria(
        deepcopy(cco_original),
        fator_correcao=1.2,
        metadata=metadata,
    )

    nova_correcao = cco_recalculada["correcoesMonetarias"][-1]

    assert decimal_para_float(nova_correcao["valorReconhecidoComOhOriginal"]) == pytest.approx(777.77)

    # Raiz e nova correção são calculadas de forma INDEPENDENTE: a raiz escala o
    # próprio valor original da raiz (100 × 1.2 = 120), a correção escala o valor
    # da última correção existente (150 × 1.2 = 180) — não são iguais, e a raiz
    # não é derivada/copiada da nova correção.
    assert decimal_para_float(cco_recalculada["valorReconhecido"]) == pytest.approx(120.00)
    assert decimal_para_float(nova_correcao["valorReconhecido"]) == pytest.approx(180.00)
    assert cco_recalculada["valorReconhecido"] != nova_correcao["valorReconhecido"]

    assert decimal_para_float(cco_recalculada["overHeadTotal"]) == pytest.approx(24.00)
    assert decimal_para_float(nova_correcao["overHeadTotal"]) == pytest.approx(36.00)


def test_executar_correcao_monetaria_sem_correcoes_anteriores_nao_cria_nova_correcao():
    service = montar_service_sem_mongo()

    cco_original = {
        "_id": "CCO_TESTE",
        "contratoCpp": "Contrato",
        "campo": "CAMPO",
        "remessa": 1,
        "remessaExposicao": 1,
        "faseRemessa": "MEN",
        "exercicio": 2024,
        "periodo": 2,
        "flgRecuperado": False,
        "valorReconhecido": Decimal128("100.00"),
        "valorReconhecidoComOH": Decimal128("120.00"),
        "overHeadTotal": Decimal128("20.00"),
        "valorLancamentoTotal": Decimal128("100.00"),
        "quantidadeLancamento": 1,
        "valorNaoReconhecido": Decimal128("0.00"),
        "valorReconhecivel": Decimal128("100.00"),
        "valorNaoPassivelRecuperacao": Decimal128("0.00"),
        "valorReconhecidoExploracao": Decimal128("40.00"),
        "valorReconhecidoProducao": Decimal128("60.00"),
        "overHeadExploracao": Decimal128("8.00"),
        "overHeadProducao": Decimal128("12.00"),
        "correcoesMonetarias": [],
    }

    metadata = {
        "tp_original": 50.0,
        "tp_correcao": 60.0,
    }

    cco_recalculada, _ = service._executar_correcao_monetaria(
        deepcopy(cco_original),
        fator_correcao=1.2,
        metadata=metadata,
    )

    # Sem histórico de correções monetárias, o recálculo termina na raiz — mesmo
    # resultado do modo RAIZ, nenhuma correção nova é criada.
    assert cco_recalculada.get("correcoesMonetarias") == []
    assert decimal_para_float(cco_recalculada["valorReconhecido"]) == pytest.approx(120.00)
    assert decimal_para_float(cco_recalculada["valorReconhecidoComOH"]) == pytest.approx(144.00)
    assert decimal_para_float(cco_recalculada["overHeadTotal"]) == pytest.approx(24.00)


def test_nova_correcao_nao_cria_variacoes_incorretas_do_campo_original():
    service = montar_service_sem_mongo()

    cco_original = {
        "_id": "CCO_TESTE",
        "contratoCpp": "Contrato",
        "campo": "CAMPO",
        "remessa": 1,
        "remessaExposicao": 1,
        "faseRemessa": "MEN",
        "exercicio": 2024,
        "periodo": 2,
        "flgRecuperado": False,
        "valorReconhecido": Decimal128("100.00"),
        "valorReconhecidoComOH": Decimal128("120.00"),
        "overHeadTotal": Decimal128("20.00"),
        "valorLancamentoTotal": Decimal128("100.00"),
        "quantidadeLancamento": 1,
        "valorNaoReconhecido": Decimal128("0.00"),
        "valorReconhecivel": Decimal128("100.00"),
        "valorNaoPassivelRecuperacao": Decimal128("0.00"),
        "valorReconhecidoExploracao": Decimal128("40.00"),
        "valorReconhecidoProducao": Decimal128("60.00"),
        "overHeadExploracao": Decimal128("8.00"),
        "overHeadProducao": Decimal128("12.00"),
        "correcoesMonetarias": [
            {
                "tipo": "RETIFICACAO",
                "valorReconhecido": Decimal128("150.00"),
                "valorReconhecidoComOH": Decimal128("180.00"),
                "overHeadTotal": Decimal128("30.00"),
                "valorReconhecidoOhOriginal": Decimal128("777.77"),
            }
        ],
    }

    metadata = {
        "tp_original": 50.0,
        "tp_correcao": 60.0,
    }

    cco_recalculada, _ = service._executar_correcao_monetaria(
        deepcopy(cco_original),
        fator_correcao=1.2,
        metadata=metadata,
    )

    nova_correcao = cco_recalculada["correcoesMonetarias"][-1]

    assert "valorReconhecidoComOhOriginal" in nova_correcao
    assert "valorReconhecidoOhOriginal" not in nova_correcao
    assert "valorReconhecidoComOHOriginal" not in nova_correcao
    # valorReconhecidoComOhOriginal é conceito só de correção monetária — a raiz é
    # recalculada de forma independente e nunca recebe esse campo.
    assert "valorReconhecidoOhOriginal" not in cco_recalculada
    assert "valorReconhecidoComOHOriginal" not in cco_recalculada
    assert "valorReconhecidoComOhOriginal" not in cco_recalculada


def test_data_correcao_vem_do_data_reconhecimento_da_cco_formato_canonico():
    service = montar_service_sem_mongo()

    cco_original = {
        "_id": "CCO_TESTE",
        "dataReconhecimento": "2026-03-27T18:19:45+0000",
        "contratoCpp": "Contrato",
        "campo": "CAMPO",
        "remessa": 1,
        "remessaExposicao": 1,
        "faseRemessa": "MEN",
        "exercicio": 2024,
        "periodo": 2,
        "flgRecuperado": False,
        "valorReconhecido": Decimal128("100.00"),
        "valorReconhecidoComOH": Decimal128("120.00"),
        "overHeadTotal": Decimal128("20.00"),
        "valorLancamentoTotal": Decimal128("100.00"),
        "quantidadeLancamento": 1,
        "valorNaoReconhecido": Decimal128("0.00"),
        "valorReconhecivel": Decimal128("100.00"),
        "valorNaoPassivelRecuperacao": Decimal128("0.00"),
        "valorReconhecidoExploracao": Decimal128("40.00"),
        "valorReconhecidoProducao": Decimal128("60.00"),
        "overHeadExploracao": Decimal128("8.00"),
        "overHeadProducao": Decimal128("12.00"),
        # Precisa de histórico não-vazio para que uma nova correção seja criada
        # (sem histórico, o recálculo termina na raiz e não há nova correção).
        "correcoesMonetarias": [{"tipo": "RETIFICACAO", "valorReconhecido": Decimal128("90.00")}],
    }

    metadata = {
        "tp_original": 50.0,
        "tp_correcao": 60.0,
    }

    cco_recalculada, _ = service._executar_correcao_monetaria(
        deepcopy(cco_original),
        fator_correcao=1.2,
        metadata=metadata,
    )

    nova_correcao = cco_recalculada["correcoesMonetarias"][-1]

    assert nova_correcao["dataCorrecao"] == "2026-03-27T18:19:45+0000"


def test_data_correcao_vem_do_data_reconhecimento_datetime_formatado():
    service = montar_service_sem_mongo()

    from datetime import datetime

    cco_original = {
        "_id": "CCO_TESTE",
        "dataReconhecimento": datetime(2026, 3, 27, 18, 19, 45),
        "contratoCpp": "Contrato",
        "campo": "CAMPO",
        "remessa": 1,
        "remessaExposicao": 1,
        "faseRemessa": "MEN",
        "exercicio": 2024,
        "periodo": 2,
        "flgRecuperado": False,
        "valorReconhecido": Decimal128("100.00"),
        "valorReconhecidoComOH": Decimal128("120.00"),
        "overHeadTotal": Decimal128("20.00"),
        "valorLancamentoTotal": Decimal128("100.00"),
        "quantidadeLancamento": 1,
        "valorNaoReconhecido": Decimal128("0.00"),
        "valorReconhecivel": Decimal128("100.00"),
        "valorNaoPassivelRecuperacao": Decimal128("0.00"),
        "valorReconhecidoExploracao": Decimal128("40.00"),
        "valorReconhecidoProducao": Decimal128("60.00"),
        "overHeadExploracao": Decimal128("8.00"),
        "overHeadProducao": Decimal128("12.00"),
        "correcoesMonetarias": [{"tipo": "RETIFICACAO", "valorReconhecido": Decimal128("90.00")}],
    }

    metadata = {
        "tp_original": 50.0,
        "tp_correcao": 60.0,
    }

    cco_recalculada, _ = service._executar_correcao_monetaria(
        deepcopy(cco_original),
        fator_correcao=1.2,
        metadata=metadata,
    )

    nova_correcao = cco_recalculada["correcoesMonetarias"][-1]

    assert nova_correcao["dataCorrecao"] == "2026-03-27T18:19:45+0000"


def test_nova_correcao_com_recuperacao_tem_34_atributos_sem_duplicatas_originais():
    """Garante o schema da nova correção (34 atributos) sem as variações incorretas."""
    service = montar_service_sem_mongo()

    cco_original = {
        "_id": "CCO_TESTE",
        "contratoCpp": "Contrato",
        "campo": "CAMPO",
        "remessa": 1,
        "remessaExposicao": 1,
        "faseRemessa": "MEN",
        "exercicio": 2024,
        "periodo": 2,
        "flgRecuperado": False,
        "valorReconhecido": Decimal128("100.00"),
        "valorReconhecidoComOH": Decimal128("120.00"),
        "overHeadTotal": Decimal128("20.00"),
        "valorLancamentoTotal": Decimal128("100.00"),
        "quantidadeLancamento": 1,
        "valorNaoReconhecido": Decimal128("0.00"),
        "valorReconhecivel": Decimal128("100.00"),
        "valorNaoPassivelRecuperacao": Decimal128("0.00"),
        "valorReconhecidoExploracao": Decimal128("40.00"),
        "valorReconhecidoProducao": Decimal128("60.00"),
        "overHeadExploracao": Decimal128("8.00"),
        "overHeadProducao": Decimal128("12.00"),
        "correcoesMonetarias": [
            {
                "tipo": "RETIFICACAO",
                "igpmAcumulado": Decimal128("4.535028"),
                "igpmAcumuladoReais": Decimal128("2.0"),
                "valorRecuperado": Decimal128("10.00"),
                "valorRecuperadoTotal": Decimal128("20.00"),
            }
        ],
    }

    metadata = {
        "tp_original": 50.0,
        "tp_correcao": 60.0,
    }

    cco_recalculada, _ = service._executar_correcao_monetaria(
        deepcopy(cco_original),
        fator_correcao=1.2,
        metadata=metadata,
    )

    nova_correcao = cco_recalculada["correcoesMonetarias"][-1]

    assert len(nova_correcao) == 34
    assert "valorReconhecidoComOhOriginal" in nova_correcao
    assert "valorReconhecidoOhOriginal" not in nova_correcao
    assert "valorReconhecidoComOHOriginal" not in nova_correcao


def test_data_criacao_correcao_eh_datetime_aware_utc():
    service = montar_service_sem_mongo()

    cco_original = {
        "_id": "CCO_TESTE",
        "dataReconhecimento": "2026-03-27T18:19:45+0000",
        "contratoCpp": "Contrato",
        "campo": "CAMPO",
        "remessa": 1,
        "remessaExposicao": 1,
        "faseRemessa": "MEN",
        "exercicio": 2024,
        "periodo": 2,
        "flgRecuperado": False,
        "valorReconhecido": Decimal128("100.00"),
        "valorReconhecidoComOH": Decimal128("120.00"),
        "overHeadTotal": Decimal128("20.00"),
        "valorLancamentoTotal": Decimal128("100.00"),
        "quantidadeLancamento": 1,
        "valorNaoReconhecido": Decimal128("0.00"),
        "valorReconhecivel": Decimal128("100.00"),
        "valorNaoPassivelRecuperacao": Decimal128("0.00"),
        "valorReconhecidoExploracao": Decimal128("40.00"),
        "valorReconhecidoProducao": Decimal128("60.00"),
        "overHeadExploracao": Decimal128("8.00"),
        "overHeadProducao": Decimal128("12.00"),
        "correcoesMonetarias": [{"tipo": "RETIFICACAO", "valorReconhecido": Decimal128("90.00")}],
    }

    metadata = {
        "tp_original": 50.0,
        "tp_correcao": 60.0,
    }

    cco_recalculada, _ = service._executar_correcao_monetaria(
        deepcopy(cco_original),
        fator_correcao=1.2,
        metadata=metadata,
    )

    nova_correcao = cco_recalculada["correcoesMonetarias"][-1]
    data_criacao = nova_correcao["dataCriacaoCorrecao"]

    from datetime import timezone

    assert data_criacao.tzinfo is not None
    assert data_criacao.utcoffset() == timezone.utc.utcoffset(data_criacao)


def test_igpm_acumulado_herdado_da_ultima_correcao():
    service = montar_service_sem_mongo()

    cco_original = {
        "_id": "CCO_TESTE",
        "contratoCpp": "Contrato",
        "campo": "CAMPO",
        "remessa": 1,
        "remessaExposicao": 1,
        "faseRemessa": "MEN",
        "exercicio": 2024,
        "periodo": 2,
        "flgRecuperado": False,
        "valorReconhecido": Decimal128("100.00"),
        "valorReconhecidoComOH": Decimal128("120.00"),
        "overHeadTotal": Decimal128("20.00"),
        "valorLancamentoTotal": Decimal128("100.00"),
        "quantidadeLancamento": 1,
        "valorNaoReconhecido": Decimal128("0.00"),
        "valorReconhecivel": Decimal128("100.00"),
        "valorNaoPassivelRecuperacao": Decimal128("0.00"),
        "valorReconhecidoExploracao": Decimal128("40.00"),
        "valorReconhecidoProducao": Decimal128("60.00"),
        "overHeadExploracao": Decimal128("8.00"),
        "overHeadProducao": Decimal128("12.00"),
        "correcoesMonetarias": [
            {"tipo": "RETIFICACAO", "igpmAcumulado": Decimal128("4.535028")}
        ],
    }

    metadata = {
        "tp_original": 50.0,
        "tp_correcao": 60.0,
    }

    cco_recalculada, _ = service._executar_correcao_monetaria(
        deepcopy(cco_original),
        fator_correcao=1.2,
        metadata=metadata,
    )

    nova_correcao = cco_recalculada["correcoesMonetarias"][-1]

    assert decimal_para_float(nova_correcao["igpmAcumulado"]) == pytest.approx(4.535028)


# =============================================================================
# BUG-20572 (item 3 — BUG-20471): fallback de dataCorrecao e modos COMPLETO/RAIZ
# Testes derivados dos critérios de aceite da seção 4 da spec:
#   - "Fallback documentado se dataReconhecimento ausente"
#   - "Solução não quebra os demais modos de recálculo (COMPLETO, RAIZ)"
# =============================================================================


@freeze_time("2026-08-21T19:41:13+00:00")
def test_data_correcao_fallback_para_data_atual_quando_data_reconhecimento_ausente():
    service = montar_service_sem_mongo()

    data_correcao = service._formatar_data_correcao({"_id": "CCO_SEM_DATA"})

    assert data_correcao == "2026-08-21T19:41:13+0000"


@freeze_time("2026-08-21T19:41:13+00:00")
@pytest.mark.parametrize(
    "data_reconhecimento",
    ["", "   ", "data-invalida", "31/12/2024"],
)
def test_data_correcao_fallback_para_data_atual_quando_data_reconhecimento_invalida(data_reconhecimento):
    service = montar_service_sem_mongo()

    data_correcao = service._formatar_data_correcao(
        {"_id": "CCO_DATA_INVALIDA", "dataReconhecimento": data_reconhecimento}
    )

    assert data_correcao == "2026-08-21T19:41:13+0000"


def test_data_correcao_aceita_data_reconhecimento_sem_timezone():
    service = montar_service_sem_mongo()

    data_correcao = service._formatar_data_correcao(
        {"_id": "CCO_SEM_TZ", "dataReconhecimento": "2026-03-27T18:19:45"}
    )

    assert data_correcao == "2026-03-27T18:19:45+0000"


def test_modo_completo_nao_cria_variacoes_incorretas_do_campo_original():
    service = montar_service_sem_mongo()

    cco = {
        "_id": "CCO_TESTE",
        "valorReconhecido": Decimal128("100.00"),
        "valorReconhecidoComOH": Decimal128("120.00"),
        "overHeadTotal": Decimal128("20.00"),
        "valorLancamento": Decimal128("100.00"),
        "quantidadeLancamento": 1,
        "correcoesMonetarias": [
            {"tipo": "RETIFICACAO", "valorReconhecido": Decimal128("150.00")}
        ],
    }

    resultado, ultimo_valor_original = service._executar_recalculo_completo(deepcopy(cco), fator_correcao=1.5)

    assert "valorReconhecidoOhOriginal" not in resultado
    assert "valorReconhecidoComOHOriginal" not in resultado
    assert "valorReconhecidoComOhOriginal" not in resultado
    assert decimal_para_float(resultado["valorReconhecido"]) == pytest.approx(150.00)
    assert ultimo_valor_original is None


def test_modo_raiz_aplica_fator_na_raiz_sem_criar_variacoes_incorretas_nem_tocar_correcoes():
    service = montar_service_sem_mongo()

    cco = {
        "_id": "CCO_TESTE",
        "valorReconhecido": Decimal128("100.00"),
        "valorReconhecidoComOH": Decimal128("120.00"),
        "valorRecusado": Decimal128("10.00"),
        "campo": "CAMPO_NAO_FINANCEIRO",
        "correcoesMonetarias": [
            {"tipo": "RETIFICACAO", "valorReconhecido": Decimal128("150.00")}
        ],
    }

    cco_recalculada, ultimo_valor_original = service._executar_recalculo_raiz(
        deepcopy(cco),
        fator_correcao=1.5,
    )

    assert "valorReconhecidoOhOriginal" not in cco_recalculada
    assert "valorReconhecidoComOHOriginal" not in cco_recalculada
    assert len(cco_recalculada["correcoesMonetarias"]) == 1
    assert decimal_para_float(cco_recalculada["valorReconhecido"]) == pytest.approx(150.00)
    assert decimal_para_float(cco_recalculada["valorRecusado"]) == pytest.approx(15.00)
    assert cco_recalculada["campo"] == "CAMPO_NAO_FINANCEIRO"
    assert decimal_para_float(ultimo_valor_original) == pytest.approx(120.00)


class CcoRepoFake:
    def __init__(self, cco):
        self.cco = cco

    def buscar_por_id(self, cco_id):
        return deepcopy(self.cco)


def test_executar_recalculo_tp_modo_raiz_despacha_e_nao_cria_variacoes_incorretas():
    service = RecalculoService.__new__(RecalculoService)
    service.cco_repo = CcoRepoFake(
        {
            "_id": "CCO_TESTE",
            "valorReconhecido": Decimal128("100.00"),
            "valorReconhecidoComOH": Decimal128("120.00"),
            "overHeadTotal": Decimal128("20.00"),
            "correcoesMonetarias": [],
        }
    )

    resultado = service.executar_recalculo_tp(
        "CCO_TESTE",
        tp_original=1.0,
        tp_correcao=1.5,
        modo="RAIZ",
    )

    assert resultado["success"] is True

    cco_recalculada = resultado["resultado"]["cco_recalculada"]

    assert "valorReconhecidoOhOriginal" not in cco_recalculada
    assert "valorReconhecidoComOHOriginal" not in cco_recalculada
    assert decimal_para_float(cco_recalculada["valorReconhecido"]) == pytest.approx(150.00)


# =============================================================================
# BUG-20598: valorRecusado recalculado nos modos COMPLETO e CORRECAO_MONETARIA
# =============================================================================


def test_modo_completo_recalcula_valor_recusado_com_fator():
    service = montar_service_sem_mongo()

    cco = {
        "_id": "CCO_TESTE",
        "valorReconhecido": Decimal128("100.00"),
        "valorReconhecidoComOH": Decimal128("120.00"),
        "overHeadTotal": Decimal128("20.00"),
        "valorLancamento": Decimal128("100.00"),
        "quantidadeLancamento": 1,
        "valorRecusado": Decimal128("100.00"),
        "correcoesMonetarias": [
            {"tipo": "RETIFICACAO", "valorReconhecido": Decimal128("150.00")}
        ],
    }

    resultado, _ = service._executar_recalculo_completo(deepcopy(cco), fator_correcao=1.5)

    assert decimal_para_float(resultado["valorRecusado"]) == pytest.approx(150.00)


def test_correcao_monetaria_recalcula_valor_recusado_na_raiz_sem_tocar_correcao():
    service = montar_service_sem_mongo()

    cco_original = {
        "_id": "CCO_TESTE",
        "contratoCpp": "Contrato",
        "campo": "CAMPO",
        "remessa": 1,
        "remessaExposicao": 1,
        "faseRemessa": "MEN",
        "exercicio": 2024,
        "periodo": 2,
        "flgRecuperado": False,
        "valorReconhecido": Decimal128("100.00"),
        "valorReconhecidoComOH": Decimal128("120.00"),
        "overHeadTotal": Decimal128("20.00"),
        "valorLancamentoTotal": Decimal128("100.00"),
        "quantidadeLancamento": 1,
        "valorNaoReconhecido": Decimal128("0.00"),
        "valorReconhecivel": Decimal128("100.00"),
        "valorNaoPassivelRecuperacao": Decimal128("0.00"),
        "valorReconhecidoExploracao": Decimal128("40.00"),
        "valorReconhecidoProducao": Decimal128("60.00"),
        "overHeadExploracao": Decimal128("8.00"),
        "overHeadProducao": Decimal128("12.00"),
        "valorRecusado": Decimal128("100.00"),
        "correcoesMonetarias": [{"tipo": "RETIFICACAO", "valorReconhecido": Decimal128("90.00")}],
    }

    metadata = {
        "tp_original": 50.0,
        "tp_correcao": 60.0,
    }

    cco_recalculada, _ = service._executar_correcao_monetaria(
        deepcopy(cco_original),
        fator_correcao=1.2,
        metadata=metadata,
    )

    assert decimal_para_float(cco_recalculada["valorRecusado"]) == pytest.approx(120.00)

    nova_correcao = cco_recalculada["correcoesMonetarias"][-1]
    assert "valorRecusado" not in nova_correcao


def test_correcao_monetaria_comparativo_inclui_valor_recusado_da_raiz():
    service = montar_service_sem_mongo()

    cco_original = {
        "_id": "CCO_TESTE",
        "contratoCpp": "Contrato",
        "campo": "CAMPO",
        "remessa": 1,
        "remessaExposicao": 1,
        "faseRemessa": "MEN",
        "exercicio": 2024,
        "periodo": 2,
        "flgRecuperado": False,
        "valorReconhecido": Decimal128("100.00"),
        "valorReconhecidoComOH": Decimal128("120.00"),
        "overHeadTotal": Decimal128("20.00"),
        "valorLancamentoTotal": Decimal128("100.00"),
        "quantidadeLancamento": 1,
        "valorNaoReconhecido": Decimal128("0.00"),
        "valorReconhecivel": Decimal128("100.00"),
        "valorNaoPassivelRecuperacao": Decimal128("0.00"),
        "valorReconhecidoExploracao": Decimal128("40.00"),
        "valorReconhecidoProducao": Decimal128("60.00"),
        "overHeadExploracao": Decimal128("8.00"),
        "overHeadProducao": Decimal128("12.00"),
        "valorRecusado": Decimal128("100.00"),
        "correcoesMonetarias": [],
    }

    cco_recalculada, _ = service._executar_correcao_monetaria(
        deepcopy(cco_original),
        fator_correcao=1.2,
        metadata={"tp_original": 50.0, "tp_correcao": 60.0},
    )

    metadata_recalculo = {
        "tipo_recalculo": "TRACK_PARTICIPATION",
        "modo_recalculo": "CORRECAO_MONETARIA",
        "tp_original": 50.0,
        "tp_correcao": 60.0,
        "fator_correcao": 1.2,
    }

    resultado = service._preparar_resultado_comparativo(
        cco_original,
        cco_recalculada,
        metadata_recalculo,
    )

    comparativo = resultado["comparativo"]

    assert "valorRecusado" in comparativo
    assert comparativo["valorRecusado"]["valor_original"] == pytest.approx(100.00)
    assert comparativo["valorRecusado"]["valor_recalculado"] == pytest.approx(120.00)
    assert comparativo["valorRecusado"]["diferenca"] == pytest.approx(20.00)
    assert comparativo["valorRecusado"]["percentual_variacao"] == pytest.approx(20.00)


def test_modo_completo_comparativo_inclui_valor_recusado():
    service = montar_service_sem_mongo()

    cco_original = {
        "_id": "CCO_TESTE",
        "valorReconhecido": Decimal128("100.00"),
        "valorReconhecidoComOH": Decimal128("120.00"),
        "overHeadTotal": Decimal128("20.00"),
        "valorLancamento": Decimal128("100.00"),
        "valorRecusado": Decimal128("100.00"),
        "correcoesMonetarias": [],
    }

    cco_recalculada, _ = service._executar_recalculo_completo(deepcopy(cco_original), fator_correcao=1.5)

    metadata_recalculo = {
        "tipo_recalculo": "TRACK_PARTICIPATION",
        "modo_recalculo": "COMPLETO",
        "tp_original": 50.0,
        "tp_correcao": 75.0,
        "fator_correcao": 1.5,
    }

    resultado = service._preparar_resultado_comparativo(
        cco_original,
        cco_recalculada,
        metadata_recalculo,
    )

    comparativo = resultado["comparativo"]

    assert "valorRecusado" in comparativo
    assert comparativo["valorRecusado"]["valor_original"] == pytest.approx(100.00)
    assert comparativo["valorRecusado"]["valor_recalculado"] == pytest.approx(150.00)


