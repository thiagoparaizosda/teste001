from bson.decimal128 import Decimal128

from app.services.cco_editor_service import CCOEditorService


def test_valores_base_retificacao_copia_campos_faltantes_da_ultima_correcao():
    service = CCOEditorService.__new__(CCOEditorService)

    cco = {
        "quantidadeLancamento": 1,
        "valorLancamentoTotal": Decimal128("10.00"),
        "valorReconhecivel": Decimal128("20.00"),
        "igpmAcumulado": Decimal128("1.00"),
        "igpmAcumuladoReais": Decimal128("2.00"),
        "correcoesMonetarias": [
            {
                "quantidadeLancamento": 99,
                "valorLancamentoTotal": Decimal128("1234.56"),
                "valorReconhecivel": Decimal128("987.65"),
                "igpmAcumulado": Decimal128("1.1234"),
                "igpmAcumuladoReais": Decimal128("456.78"),
            }
        ],
    }

    valores = service._obter_valores_base_retificacao(cco)

    # Campos monetários/Decimal128 voltam como string decimal em notação fixa
    # (não float) para não perder precisão — ver _converter_valor_para_json.
    assert valores["quantidadeLancamento"] == 99
    assert valores["valorLancamentoTotal"] == "1234.56"
    assert valores["valorReconhecivel"] == "987.65"
    assert valores["igpmAcumulado"] == "1.1234"
    assert valores["igpmAcumuladoReais"] == "456.78"


def test_valores_base_retificacao_usa_raiz_quando_nao_existir_correcao():
    service = CCOEditorService.__new__(CCOEditorService)

    cco = {
        "quantidadeLancamento": 7,
        "valorLancamentoTotal": Decimal128("700.00"),
        "valorReconhecivel": Decimal128("650.00"),
        "igpmAcumulado": Decimal128("1.0500"),
        "igpmAcumuladoReais": Decimal128("50.00"),
        "correcoesMonetarias": [],
    }

    valores = service._obter_valores_base_retificacao(cco)

    assert valores["quantidadeLancamento"] == 7
    assert valores["valorLancamentoTotal"] == "700.00"
    assert valores["valorReconhecivel"] == "650.00"
    assert valores["igpmAcumulado"] == "1.0500"
    assert valores["igpmAcumuladoReais"] == "50.00"


def test_valores_base_retificacao_preserva_precisao_alem_do_float64():
    """Regressão: valores com mais dígitos do que um float64 suporta com
    exatidão não podem ser arredondados ao serem lidos para a Nova Correção.
    """
    service = CCOEditorService.__new__(CCOEditorService)

    valor_alta_precisao = "123456789.123456789012345"
    cco = {
        "valorReconhecidoComOH": Decimal128(valor_alta_precisao),
        "correcoesMonetarias": [],
    }

    valores = service._obter_valores_base_retificacao(cco)

    assert valores["valorReconhecidoComOhOriginal"] == valor_alta_precisao


def test_campos_faltantes_estao_mapeados_para_copiar_na_nova_retificacao():
    service = CCOEditorService.__new__(CCOEditorService)

    cco = {
        "quantidadeLancamento": 3,
        "valorLancamentoTotal": Decimal128("300.00"),
        "valorReconhecivel": Decimal128("250.00"),
        "igpmAcumulado": Decimal128("1.0300"),
        "igpmAcumuladoReais": Decimal128("30.00"),
        "correcoesMonetarias": [],
    }

    valores = service._obter_valores_base_retificacao(cco)

    for campo in [
        "quantidadeLancamento",
        "valorLancamentoTotal",
        "valorReconhecivel",
        "igpmAcumulado",
        "igpmAcumuladoReais",
    ]:
        assert campo in valores
