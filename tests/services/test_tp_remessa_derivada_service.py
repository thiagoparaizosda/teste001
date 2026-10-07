from copy import deepcopy

import pytest
from bson.decimal128 import Decimal128
from bson.int64 import Int64

from app.services.tp_remessa_derivada_service import TPRemessaDerivadaService


class ResultadoUpdateFake:
    def __init__(self, modified_count=1):
        self.modified_count = modified_count


class CollectionRemessaDerivadaFake:
    def __init__(self, remessa):
        self.remessa = deepcopy(remessa)
        self.filtro_recebido = None
        self.update_recebido = None

    def find_one(self, filtro):
        self.filtro_recebido = filtro
        return deepcopy(self.remessa)

    def update_one(self, filtro, update):
        self.filtro_recebido = filtro
        self.update_recebido = deepcopy(update)
        return ResultadoUpdateFake(modified_count=1)


class DbPrdFake:
    def __init__(self, remessa):
        self.remessa_derivada_campo_entity = CollectionRemessaDerivadaFake(remessa)


def decimal_para_float(valor):
    if isinstance(valor, Decimal128):
        return float(valor.to_decimal())
    return float(valor)


def montar_service(remessa):
    db = DbPrdFake(remessa)
    service = TPRemessaDerivadaService(db)
    return service, db.remessa_derivada_campo_entity


def test_atualiza_apenas_gastos_com_fase_remessa_igual_a_fase_da_cco():
    remessa = {
        "_id": "REMESSA_001",
        "version": Int64(3),
        "gastos": [
            {
                "item": "MEN_1",
                "faseRemessa": "MEN",
                "tractParticipationPercentual": Decimal128("1.0"),
                "valorConvertido": Decimal128("100.00"),
            },
            {
                "item": "ROP_1",
                "faseRemessa": "ROP",
                "tractParticipationPercentual": Decimal128("1.0"),
                "valorConvertido": Decimal128("200.00"),
            },
            {
                "item": "MEN_2_COM_ESPACO",
                "faseRemessa": " men ",
                "tractParticipationPercentual": Decimal128("1.0"),
                "valorConvertido": Decimal128("300.00"),
            },
            {
                "item": "SEM_FASE",
                "tractParticipationPercentual": Decimal128("1.0"),
                "valorConvertido": Decimal128("400.00"),
            },
        ],
    }

    service, collection = montar_service(remessa)

    resultado = service.atualizar_tp_remessa_derivada(
        cco_recalculada={
            "_id": "CCO_TESTE",
            "idRemessaGeradora": "REMESSA_001",
            "faseRemessa": "MEN",
        },
        metadata_recalculo={
            "tp_original": 1.0,
            "tp_correcao": 1.5,
            "fator_correcao": 1.5,
        },
    )

    assert resultado["success"] is True
    assert resultado["total_gastos_afetados"] == 2

    gastos_atualizados = collection.update_recebido["$set"]["gastos"]

    gasto_men_1 = gastos_atualizados[0]
    gasto_rop_1 = gastos_atualizados[1]
    gasto_men_2 = gastos_atualizados[2]
    gasto_sem_fase = gastos_atualizados[3]

    assert decimal_para_float(gasto_men_1["tractParticipationPercentual"]) == pytest.approx(1.5)
    assert decimal_para_float(gasto_men_1["valorConvertido"]) == pytest.approx(150.00)

    assert decimal_para_float(gasto_men_2["tractParticipationPercentual"]) == pytest.approx(1.5)
    assert decimal_para_float(gasto_men_2["valorConvertido"]) == pytest.approx(450.00)

    assert decimal_para_float(gasto_rop_1["tractParticipationPercentual"]) == pytest.approx(1.0)
    assert decimal_para_float(gasto_rop_1["valorConvertido"]) == pytest.approx(200.00)

    assert decimal_para_float(gasto_sem_fase["tractParticipationPercentual"]) == pytest.approx(1.0)
    assert decimal_para_float(gasto_sem_fase["valorConvertido"]) == pytest.approx(400.00)


def test_compara_somente_campo_fase_remessa_e_ignora_outros_campos_de_fase():
    remessa = {
        "_id": "REMESSA_001",
        "version": Int64(1),
        "gastos": [
            {
                "item": "NAO_DEVE_ALTERAR",
                "faseRemessa": "ROP",
                "fase": "MEN",
                "faseRespostaGestora": "MEN",
                "tractParticipationPercentual": Decimal128("1.0"),
                "valorConvertido": Decimal128("100.00"),
            }
        ],
    }

    service, collection = montar_service(remessa)

    resultado = service.atualizar_tp_remessa_derivada(
        cco_recalculada={
            "_id": "CCO_TESTE",
            "idRemessaGeradora": "REMESSA_001",
            "faseRemessa": "MEN",
        },
        metadata_recalculo={
            "tp_original": 1.0,
            "tp_correcao": 1.5,
            "fator_correcao": 1.5,
        },
    )

    assert resultado["success"] is False
    assert "Nenhum gasto encontrado" in resultado["error"]
    assert collection.update_recebido is None


def test_substitui_tract_participation_percentual_e_nao_cria_tp_nem_metadata_no_gasto():
    remessa = {
        "_id": "REMESSA_001",
        "version": Int64(1),
        "gastos": [
            {
                "item": "MEN_1",
                "faseRemessa": "MEN",
                "tractParticipationPercentual": Decimal128("1.0"),
                "valorConvertido": Decimal128("100.00"),
            }
        ],
    }

    service, collection = montar_service(remessa)

    resultado = service.atualizar_tp_remessa_derivada(
        cco_recalculada={
            "_id": "CCO_TESTE",
            "idRemessaGeradora": "REMESSA_001",
            "faseRemessa": "MEN",
        },
        metadata_recalculo={
            "tp_original": 1.0,
            "tp_correcao": 1.5,
            "fator_correcao": 1.5,
        },
    )

    assert resultado["success"] is True

    gasto_atualizado = collection.update_recebido["$set"]["gastos"][0]

    assert decimal_para_float(gasto_atualizado["tractParticipationPercentual"]) == pytest.approx(1.5)
    assert "tp" not in gasto_atualizado
    assert "metadataAtualizacaoTP" not in gasto_atualizado


def test_mantem_metadata_atualizacao_tp_apenas_na_raiz_da_remessa_derivada():
    remessa = {
        "_id": "REMESSA_001",
        "version": Int64(7),
        "gastos": [
            {
                "item": "MEN_1",
                "faseRemessa": "MEN",
                "tractParticipationPercentual": Decimal128("1.0"),
                "valorConvertido": Decimal128("100.00"),
            }
        ],
    }

    service, collection = montar_service(remessa)

    resultado = service.atualizar_tp_remessa_derivada(
        cco_recalculada={
            "_id": "CCO_TESTE",
            "idRemessaGeradora": "REMESSA_001",
            "faseRemessa": "MEN",
        },
        metadata_recalculo={
            "tp_original": 1.0,
            "tp_correcao": 1.5,
            "fator_correcao": 1.5,
        },
    )

    assert resultado["success"] is True

    update_set = collection.update_recebido["$set"]
    gasto_atualizado = update_set["gastos"][0]

    assert "metadataAtualizacaoTP" in update_set
    assert update_set["metadataAtualizacaoTP"]["origem"] == "RECALCULO_TP_CCO"
    assert update_set["metadataAtualizacaoTP"]["ccoId"] == "CCO_TESTE"
    assert update_set["metadataAtualizacaoTP"]["faseRemessa"] == "MEN"
    assert update_set["metadataAtualizacaoTP"]["totalGastosAfetados"] == 1

    assert "metadataAtualizacaoTP" not in gasto_atualizado


def test_atualiza_todos_os_campos_monetarios_existentes_no_gasto_da_mesma_fase():
    remessa = {
        "_id": "REMESSA_001",
        "version": Int64(1),
        "gastos": [
            {
                "item": "MEN_1",
                "faseRemessa": "MEN",
                "tractParticipationPercentual": Decimal128("1.0"),
                "valorMoedaOBJReal": Decimal128("10.00"),
                "valorMoedaOBJRealOriginal": Decimal128("20.00"),
                "valorMoedaACC": Decimal128("30.00"),
                "valorMoedaTrans": Decimal128("40.00"),
                "valorConvertido": Decimal128("50.00"),
                "valorReconhecido": Decimal128("60.00"),
                "valorNaoReconhecido": Decimal128("70.00"),
                "valorReconhecivel": Decimal128("80.00"),
                "valorNaoPassivelRecuperacao": Decimal128("90.00"),
                "valorRecusado": Decimal128("100.00"),
            }
        ],
    }

    service, collection = montar_service(remessa)

    resultado = service.atualizar_tp_remessa_derivada(
        cco_recalculada={
            "_id": "CCO_TESTE",
            "idRemessaGeradora": "REMESSA_001",
            "faseRemessa": "MEN",
        },
        metadata_recalculo={
            "tp_original": 1.0,
            "tp_correcao": 1.5,
            "fator_correcao": 1.5,
        },
    )

    assert resultado["success"] is True
    assert resultado["campos_monetarios_alterados"] == 10

    gasto_atualizado = collection.update_recebido["$set"]["gastos"][0]

    assert decimal_para_float(gasto_atualizado["valorMoedaOBJReal"]) == pytest.approx(15.00)
    assert decimal_para_float(gasto_atualizado["valorMoedaOBJRealOriginal"]) == pytest.approx(30.00)
    assert decimal_para_float(gasto_atualizado["valorMoedaACC"]) == pytest.approx(45.00)
    assert decimal_para_float(gasto_atualizado["valorMoedaTrans"]) == pytest.approx(60.00)
    assert decimal_para_float(gasto_atualizado["valorConvertido"]) == pytest.approx(75.00)
    assert decimal_para_float(gasto_atualizado["valorReconhecido"]) == pytest.approx(90.00)
    assert decimal_para_float(gasto_atualizado["valorNaoReconhecido"]) == pytest.approx(105.00)
    assert decimal_para_float(gasto_atualizado["valorReconhecivel"]) == pytest.approx(120.00)
    assert decimal_para_float(gasto_atualizado["valorNaoPassivelRecuperacao"]) == pytest.approx(135.00)
    assert decimal_para_float(gasto_atualizado["valorRecusado"]) == pytest.approx(150.00)


def test_retorna_erro_quando_cco_nao_tem_id_remessa_geradora():
    service, collection = montar_service({"_id": "REMESSA_001", "gastos": []})

    resultado = service.atualizar_tp_remessa_derivada(
        cco_recalculada={
            "_id": "CCO_TESTE",
            "faseRemessa": "MEN",
        },
        metadata_recalculo={
            "tp_original": 1.0,
            "tp_correcao": 1.5,
            "fator_correcao": 1.5,
        },
    )

    assert resultado["success"] is False
    assert "idRemessaGeradora" in resultado["error"]
    assert collection.update_recebido is None


def test_retorna_erro_quando_cco_nao_tem_fase_remessa():
    service, collection = montar_service({"_id": "REMESSA_001", "gastos": []})

    resultado = service.atualizar_tp_remessa_derivada(
        cco_recalculada={
            "_id": "CCO_TESTE",
            "idRemessaGeradora": "REMESSA_001",
        },
        metadata_recalculo={
            "tp_original": 1.0,
            "tp_correcao": 1.5,
            "fator_correcao": 1.5,
        },
    )

    assert resultado["success"] is False
    assert "faseRemessa" in resultado["error"]
    assert collection.update_recebido is None


def test_retorna_erro_quando_metadata_nao_tem_fator_ou_tp_correcao():
    service, collection = montar_service({"_id": "REMESSA_001", "gastos": []})

    resultado = service.atualizar_tp_remessa_derivada(
        cco_recalculada={
            "_id": "CCO_TESTE",
            "idRemessaGeradora": "REMESSA_001",
            "faseRemessa": "MEN",
        },
        metadata_recalculo={
            "tp_original": 1.0,
        },
    )

    assert resultado["success"] is False
    assert "fator_correcao" in resultado["error"]
    assert collection.update_recebido is None
