from app.services.recalculo_service import RecalculoService


class ClientFake:
    def __init__(self, uri=""):
        self.uri = uri
        self.sgppServices = type("DB", (), {"conta_custo_oleo_entity": object()})()
        self.temp_recalculos = type("DB", (), {"conta_custo_oleo_entity": object()})()


def test_temporarios_sao_persistidos_na_base_sgpp_services(monkeypatch):
    cliente = ClientFake()
    monkeypatch.setattr(
        "app.services.recalculo_service.MongoClient",
        lambda uri="": cliente,
    )

    service = RecalculoService("mongodb://localhost:27017/", "mongodb://prd:27017/")

    assert service.db_local is cliente.sgppServices
    assert service.db_local is not cliente.temp_recalculos


class ColecaoFake:
    def __init__(self):
        self.inseridos = []

    def insert_one(self, documento):
        self.inseridos.append(documento)
        return type("Resultado", (), {"inserted_id": "ID_GERADO"})()


class DbLocalFake:
    def __init__(self):
        self.ccos_recalculadas = ColecaoFake()
        self.eventos_recalculo = ColecaoFake()


def test_salvar_resultado_temporario_persiste_em_db_local_e_cria_evento():
    service = RecalculoService.__new__(RecalculoService)
    db_local = DbLocalFake()
    service.db_local = db_local

    resultado = {
        "cco_original": {"_id": "CCO_TESTE"},
        "cco_recalculada": {"_id": "CCO_TESTE", "valorReconhecido": 100},
        "metadata_recalculo": {"tipo_recalculo": "TRACK_PARTICIPATION"},
        "comparativo": {},
    }

    resposta = service.salvar_resultado_temporario(resultado)

    assert resposta["success"] is True
    assert len(db_local.ccos_recalculadas.inseridos) == 1
    assert len(db_local.eventos_recalculo.inseridos) == 1

    doc_temp = db_local.ccos_recalculadas.inseridos[0]
    assert doc_temp["status"] == "TEMPORARIO"
    assert doc_temp["cco_original"]["_id"] == "CCO_TESTE"
    assert doc_temp["cco_recalculada"]["_id"] == "CCO_TESTE"

