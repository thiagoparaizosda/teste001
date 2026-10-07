from app.utils import rate_limit
from app.utils.rate_limit import verificar_rate_limit_export


def limpar_rate_limit():
    rate_limit._export_rate_limit.clear()


def test_rate_limit_permite_ate_o_limite():
    limpar_rate_limit()

    chave = "ip_teste_1"

    assert verificar_rate_limit_export(chave, limite=2, janela_segundos=60) is True
    assert verificar_rate_limit_export(chave, limite=2, janela_segundos=60) is True


def test_rate_limit_bloqueia_apos_limite():
    limpar_rate_limit()

    chave = "ip_teste_2"

    assert verificar_rate_limit_export(chave, limite=2, janela_segundos=60) is True
    assert verificar_rate_limit_export(chave, limite=2, janela_segundos=60) is True
    assert verificar_rate_limit_export(chave, limite=2, janela_segundos=60) is False


def test_rate_limit_por_chave_independente():
    limpar_rate_limit()

    assert verificar_rate_limit_export("ip_a", limite=1, janela_segundos=60) is True
    assert verificar_rate_limit_export("ip_a", limite=1, janela_segundos=60) is False

    assert verificar_rate_limit_export("ip_b", limite=1, janela_segundos=60) is True
