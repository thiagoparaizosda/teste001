from datetime import datetime, date
from decimal import Decimal, InvalidOperation

from bson import Decimal128, ObjectId
from markupsafe import Markup


def _converter_para_decimal(valor):
    if valor is None:
        return Decimal("0")

    if isinstance(valor, Decimal128):
        return valor.to_decimal()

    if isinstance(valor, Decimal):
        return valor

    try:
        return Decimal(str(valor))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")


def formatar_decimal(valor):
    """Formata Decimal128/Decimal/number para string monetária brasileira."""
    numero = _converter_para_decimal(valor)

    texto = f"{numero:,.2f}"
    texto = texto.replace(",", "X").replace(".", ",").replace("X", ".")

    return f"R$ {texto}"


def formatar_data(data):
    """Formata ISODate/datetime/date/string para DD/MM/YYYY HH:MM."""
    if data is None or data == "":
        return "-"

    if isinstance(data, datetime):
        return data.strftime("%d/%m/%Y %H:%M")

    if isinstance(data, date):
        return data.strftime("%d/%m/%Y")

    if isinstance(data, str):
        texto = data.strip()

        if not texto:
            return "-"

        try:
            # Trata strings ISO com Z no final
            texto = texto.replace("Z", "+00:00")
            data_convertida = datetime.fromisoformat(texto)
            return data_convertida.strftime("%d/%m/%Y %H:%M")
        except ValueError:
            return data

    return str(data)


def formatar_boolean(valor):
    """Formata boolean para Sim/Não com badge."""
    if valor is None:
        return Markup('<span class="badge bg-secondary">N/A</span>')

    if valor is True:
        return Markup('<span class="badge bg-success">Sim</span>')

    if valor is False:
        return Markup('<span class="badge bg-danger">Não</span>')

    return str(valor)


def identificar_tipo_dado(valor):
    """Identifica o tipo de dado para exibição no template."""
    if isinstance(valor, Decimal128):
        return "Decimal128"

    if isinstance(valor, Decimal):
        return "Decimal"

    if isinstance(valor, bool):
        return "boolean"

    if isinstance(valor, datetime):
        return "ISODate"

    if isinstance(valor, date):
        return "date"

    if isinstance(valor, ObjectId):
        return "ObjectId"

    if isinstance(valor, int):
        return "int"

    if isinstance(valor, float):
        return "float"

    if isinstance(valor, list):
        return "array"

    if isinstance(valor, dict):
        return "object"

    if valor is None:
        return "null"

    return "string"


def formatar_tipo_dado(tipo):
    """Retorna badge colorido por tipo."""
    cores = {
        "string": "secondary",
        "int": "primary",
        "float": "primary",
        "Decimal": "success",
        "Decimal128": "success",
        "ISODate": "info",
        "date": "info",
        "boolean": "warning",
        "ObjectId": "dark",
        "array": "dark",
        "object": "primary",
        "null": "secondary",
    }

    cor = cores.get(tipo, "secondary")
    classe_extra = " text-dark" if cor in ["warning", "info"] else ""

    return Markup(f'<span class="badge bg-{cor}{classe_extra}">{tipo}</span>')


def formatar_valor_por_tipo(valor):
    """Formata qualquer valor conforme seu tipo."""
    tipo = identificar_tipo_dado(valor)

    if tipo in ["Decimal128", "Decimal", "float"]:
        return formatar_decimal(valor)

    if tipo in ["ISODate", "date"]:
        return formatar_data(valor)

    if tipo == "boolean":
        return formatar_boolean(valor)

    if tipo == "ObjectId":
        return str(valor)

    if tipo == "null":
        return "-"

    if tipo in ["array", "object"]:
        return str(valor)

    return str(valor)