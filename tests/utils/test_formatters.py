from datetime import datetime, date
from decimal import Decimal

from bson import Decimal128, ObjectId

from app.utils.formatters import (
    formatar_decimal,
    formatar_data,
    formatar_boolean,
    formatar_tipo_dado,
    formatar_valor_por_tipo,
    identificar_tipo_dado,
)


def test_formatar_decimal_com_decimal128():
    valor = Decimal128("1234567.89")

    assert formatar_decimal(valor) == "R$ 1.234.567,89"


def test_formatar_decimal_com_decimal():
    valor = Decimal("1500.50")

    assert formatar_decimal(valor) == "R$ 1.500,50"


def test_formatar_decimal_com_none():
    assert formatar_decimal(None) == "R$ 0,00"


def test_formatar_data_com_datetime():
    valor = datetime(2024, 12, 31, 15, 45)

    assert formatar_data(valor) == "31/12/2024 15:45"


def test_formatar_data_com_date():
    valor = date(2024, 12, 31)

    assert formatar_data(valor) == "31/12/2024"


def test_formatar_data_com_string_iso():
    valor = "2024-12-31T15:45:00"

    assert formatar_data(valor) == "31/12/2024 15:45"


def test_formatar_data_com_none():
    assert formatar_data(None) == "-"


def test_formatar_boolean_true():
    resultado = str(formatar_boolean(True))

    assert "Sim" in resultado
    assert "bg-success" in resultado


def test_formatar_boolean_false():
    resultado = str(formatar_boolean(False))

    assert "Não" in resultado
    assert "bg-danger" in resultado


def test_formatar_boolean_none():
    resultado = str(formatar_boolean(None))

    assert "N/A" in resultado
    assert "bg-secondary" in resultado


def test_identificar_tipo_decimal128():
    assert identificar_tipo_dado(Decimal128("10.50")) == "Decimal128"


def test_identificar_tipo_datetime():
    assert identificar_tipo_dado(datetime.now()) == "ISODate"


def test_identificar_tipo_boolean():
    assert identificar_tipo_dado(True) == "boolean"


def test_identificar_tipo_objectid():
    assert identificar_tipo_dado(ObjectId()) == "ObjectId"


def test_formatar_tipo_dado():
    resultado = str(formatar_tipo_dado("Decimal128"))

    assert "Decimal128" in resultado
    assert "bg-success" in resultado


def test_formatar_valor_por_tipo_decimal128():
    valor = Decimal128("999.99")

    assert formatar_valor_por_tipo(valor) == "R$ 999,99"


def test_formatar_valor_por_tipo_boolean():
    resultado = str(formatar_valor_por_tipo(True))

    assert "Sim" in resultado

def test_formatar_data_string_vazia():
    assert formatar_data("") == "-"


def test_formatar_data_string_invalida_retorna_original():
    assert formatar_data("data-invalida") == "data-invalida"


def test_formatar_decimal_string_invalida():
    assert formatar_decimal("abc") == "R$ 0,00"


def test_identificar_tipo_none():
    assert identificar_tipo_dado(None) == "null"


def test_formatar_valor_por_tipo_none():
    assert formatar_valor_por_tipo(None) == "-"