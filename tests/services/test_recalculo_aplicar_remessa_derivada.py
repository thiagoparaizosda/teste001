from copy import deepcopy

from bson import ObjectId

from app.services.recalculo_service import RecalculoService


class CollectionTemporariosFake:
    def __init__(self, documento_temp):
        self.documento_temp = deepcopy(documento_temp)
        self.update_recebido = None

    def find_one(self, filtro):
        return deepcopy(self.documento_temp)

    def update_one(self, filtro, update):
        self.update_recebido = deepcopy(update)


class DbLocalFake:
    def __init__(self, documento_temp):
        self.ccos_recalculadas = CollectionTemporariosFake(documento_temp)


class TPRemessaDerivadaServiceFake:
    chamadas = []

    def __init__(self, db_prd):
        self.db_prd = db_prd

    def atualizar_tp_remessa_derivada(self, cco_recalculada, metadata_recalculo):
        self.__class__.chamadas.append({
            "cco_recalculada": deepcopy(cco_recalculada),
            "metadata_recalculo": deepcopy(metadata_recalculo),
        })

        return {
            "success": True,
            "total_gastos_afetados": 2,
            "campos_monetarios_alterados": 4,
        }


class TPRemessaDerivadaServiceComErroFake:
    chamadas = []

    def __init__(self, db_prd):
        self.db_prd = db_prd

    def atualizar_tp_remessa_derivada(self, cco_recalculada, metadata_recalculo):
        self.__class__.chamadas.append({
            "cco_recalculada": deepcopy(cco_recalculada),
            "metadata_recalculo": deepcopy(metadata_recalculo),
        })

        return {
            "success": False,
            "error": "Nenhum gasto encontrado na remessa derivada para a fase MEN",
        }


def montar_service(documento_temp):
    service = RecalculoService.__new__(RecalculoService)
    service.db_local = DbLocalFake(documento_temp)
    service.db_prd = object()
    service._atualizar_cco_e_criar_evento = lambda cco, observacoes: {
        "success": True,
        "nova_versao": 10,
    }
    return service


def montar_documento_temp(id_temporario):
    return {
        "_id": ObjectId(id_temporario),
        "cco_recalculada": {
            "_id": "CCO_TESTE",
            "idRemessaGeradora": "REMESSA_001",
            "faseRemessa": "MEN",
        },
        "metadata_recalculo": {
            "observacoes": "Teste de aplicação definitiva",
            "tp_original": 1.0,
            "tp_correcao": 1.5,
            "fator_correcao": 1.5,
        },
    }


def test_aplicar_recalculo_definitivo_com_flag_true_chama_atualizacao_da_remessa_derivada(monkeypatch):
    id_temporario = "665f1f77bcf86cd799439011"
    documento_temp = montar_documento_temp(id_temporario)
    service = montar_service(documento_temp)

    TPRemessaDerivadaServiceFake.chamadas = []
    monkeypatch.setattr(
        "app.services.recalculo_service.TPRemessaDerivadaService",
        TPRemessaDerivadaServiceFake,
    )

    resultado = service.aplicar_recalculo_definitivo(
        id_temporario,
        atualizar_remessa_derivada=True,
    )

    assert resultado["success"] is True
    assert resultado["nova_versao"] == 10
    assert resultado["remessa_derivada"]["success"] is True
    assert resultado["remessa_derivada"]["total_gastos_afetados"] == 2

    assert len(TPRemessaDerivadaServiceFake.chamadas) == 1
    assert TPRemessaDerivadaServiceFake.chamadas[0]["cco_recalculada"]["_id"] == "CCO_TESTE"
    assert TPRemessaDerivadaServiceFake.chamadas[0]["metadata_recalculo"]["tp_correcao"] == 1.5

    update_temp = service.db_local.ccos_recalculadas.update_recebido["$set"]
    assert update_temp["status"] == "APLICADO"
    assert update_temp["atualizar_remessa_derivada"] is True
    assert update_temp["resultado_atualizacao_remessa_derivada"]["success"] is True


def test_aplicar_recalculo_definitivo_com_flag_false_nao_chama_atualizacao_da_remessa_derivada(monkeypatch):
    id_temporario = "665f1f77bcf86cd799439012"
    documento_temp = montar_documento_temp(id_temporario)
    service = montar_service(documento_temp)

    TPRemessaDerivadaServiceFake.chamadas = []
    monkeypatch.setattr(
        "app.services.recalculo_service.TPRemessaDerivadaService",
        TPRemessaDerivadaServiceFake,
    )

    resultado = service.aplicar_recalculo_definitivo(
        id_temporario,
        atualizar_remessa_derivada=False,
    )

    assert resultado["success"] is True
    assert "remessa_derivada" not in resultado
    assert len(TPRemessaDerivadaServiceFake.chamadas) == 0

    update_temp = service.db_local.ccos_recalculadas.update_recebido["$set"]
    assert update_temp["status"] == "APLICADO"
    assert update_temp["atualizar_remessa_derivada"] is False
    assert update_temp["resultado_atualizacao_remessa_derivada"] is None


def test_aplicar_recalculo_definitivo_mantem_cco_aplicada_quando_atualizacao_da_remessa_derivada_falha(monkeypatch):
    id_temporario = "665f1f77bcf86cd799439013"
    documento_temp = montar_documento_temp(id_temporario)
    service = montar_service(documento_temp)

    TPRemessaDerivadaServiceComErroFake.chamadas = []
    monkeypatch.setattr(
        "app.services.recalculo_service.TPRemessaDerivadaService",
        TPRemessaDerivadaServiceComErroFake,
    )

    resultado = service.aplicar_recalculo_definitivo(
        id_temporario,
        atualizar_remessa_derivada=True,
    )

    assert resultado["success"] is True
    assert resultado["nova_versao"] == 10
    assert resultado["remessa_derivada"]["success"] is False
    assert "warning" in resultado
    assert "não foi possível atualizar" in resultado["warning"]

    update_temp = service.db_local.ccos_recalculadas.update_recebido["$set"]
    assert update_temp["status"] == "APLICADO"
    assert update_temp["atualizar_remessa_derivada"] is True
    assert update_temp["resultado_atualizacao_remessa_derivada"]["success"] is False
