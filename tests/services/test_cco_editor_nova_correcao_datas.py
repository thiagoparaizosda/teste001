from datetime import datetime, timezone
from unittest.mock import patch, Mock
from bson.decimal128 import Decimal128

from app.services.cco_editor_service import CCOEditorService


def test_nova_correcao_data_correcao_string_e_data_criacao_datetime():
    service = CCOEditorService.__new__(CCOEditorService)
    service.db = Mock()

    cco = {
        "_id": "CCO-TESTE",
        "contratoCpp": "CTR",
        "campo": "CAMPO",
        "faseRemessa": "FASE",
        "correcoesMonetarias": [],
        "valorReconhecido": Decimal128("100"),
        "valorReconhecidoComOH": Decimal128("110"),
        "overHeadExploracao": Decimal128("5"),
        "overHeadProducao": Decimal128("5"),
        "overHeadTotal": Decimal128("10"),
    }

    correcao = {
        "tipo": "RETIFICACAO",
        "subTipo": "MANUAL",
        "valorReconhecidoComOH": 120,
    }

    agora = datetime(2026, 6, 23, 4, 42, 45, 300000, tzinfo=timezone.utc)

    with patch("app.services.cco_editor_service.datetime") as mock_datetime:
        mock_datetime.now.return_value = agora
        mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

        resultado = service._adicionar_correcao(
            cco=cco,
            correcao=correcao,
            cco_original=cco.copy(),
            observacoes="Teste",
            registro=[],
        )

    assert resultado["success"] is True

    nova_correcao = cco["correcoesMonetarias"][-1]

    assert nova_correcao["dataCorrecao"] == "2026-06-23T04:42:45.300+0000"
    assert isinstance(nova_correcao["dataCorrecao"], str)

    assert nova_correcao["dataCriacaoCorrecao"] == agora
    assert isinstance(nova_correcao["dataCriacaoCorrecao"], datetime)
