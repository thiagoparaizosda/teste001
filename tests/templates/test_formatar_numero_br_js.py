# BUG-20572 (item 5 — BUG-20465): formatação de Fator de Alocação / Percentual no frontend
# Gerado por test-agent — baseado na spec, não na implementação.
#
# Critérios da seção 4 da spec:
#   - Fator e Percentual exibidos com vírgula decimal e sem zeros desnecessários.
#   - 1.000000 → 1; 1.500000 → 1,5; 4.199100000000000 conforme regra de casas decimais.
#   - Payload enviado à API continua numérico (formatação apenas na apresentação).
#   - Testes de frontend cobrem inteiros, decimais, zero e negativos (se permitidos).
#
# Os testes executam a função JavaScript real `formatarNumeroBR` contida nos
# templates, via Node.js, validando os exemplos concretos da spec.
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
TEMPLATES = [
    ROOT_DIR / "app" / "templates" / "recalculo" / "executar_recalculo.html",
    ROOT_DIR / "app" / "templates" / "analise_remessas.html",
]

NODE_DISPONIVEL = shutil.which("node") is not None

pytestmark = pytest.mark.skipif(
    not NODE_DISPONIVEL,
    reason="node não disponível no ambiente — necessário para executar a função JS real",
)

# Exemplos da seção 1.5 / 4 da spec + inteiros, decimais, zero e negativos (se permitidos)
# Comportamento numérico — idêntico nos dois templates (exigido pela spec).
CASOS_NUMERICOS_SPEC = [
    {"entrada": "1.000000", "casas": 6, "esperado": "1"},
    {"entrada": "1.500000", "casas": 6, "esperado": "1,5"},
    {"entrada": "4.199100000000000", "casas": 15, "esperado": "4,1991"},
    {"entrada": "0.000000", "casas": 6, "esperado": "0"},
    {"entrada": "-1.500000", "casas": 6, "esperado": "-1,5"},
    {"entrada": "1.234560", "casas": 6, "esperado": "1,23456"},
]

# Comportamento não numérico — NÃO especificado na seção 4; cada template
# adota uma estratégia própria (divergência registrada no test-report):
#   - executar_recalculo.html: isNaN(valor) → '' (campos de fator/variação)
#   - analise_remessas.html:    isNaN → String(valor) (call site usa || 'N/A')
CASOS_NAO_NUMERICOS_POR_TEMPLATE = {
    "executar_recalculo.html": [
        {"entrada": None, "casas": None, "esperado": ""},
        {"entrada": "abc", "casas": 6, "esperado": ""},
    ],
    "analise_remessas.html": [
        {"entrada": None, "casas": None, "esperado": ""},
        {"entrada": "abc", "casas": 6, "esperado": "abc"},
    ],
}


def _extrair_funcao_formatar_numero_br(html: str) -> str:
    token = "function formatarNumeroBR("
    inicio = html.index(token)
    i = inicio
    profundidade = 0
    while i < len(html):
        if html[i] == "{":
            profundidade += 1
        elif html[i] == "}":
            profundidade -= 1
            if profundidade == 0:
                return html[inicio : i + 1]
        i += 1
    raise AssertionError("função formatarNumeroBR não encontrada no template")


def _executar_funcao_no_node(funcao_js: str, casos: list) -> list:
    script = (
        funcao_js
        + "\nconst casos = "
        + json.dumps(casos)
        + ";\nprocess.stdout.write(JSON.stringify(casos.map(c => {"
        "try { return { saida: formatarNumeroBR(c.entrada, c.casas) }; }"
        "catch (e) { return { erro: String(e) }; }"
        "})));"
    )
    proc = subprocess.run(
        ["node", "-e", script],
        capture_output=True,
        text=True,
        cwd=str(ROOT_DIR),
    )
    assert proc.returncode == 0, f"node falhou: {proc.stderr}"
    return json.loads(proc.stdout)


@pytest.mark.parametrize("template", TEMPLATES, ids=lambda p: p.name)
def test_formatar_numero_br_js_atende_exemplos_da_spec(template):
    html = template.read_text(encoding="utf-8")
    funcao = _extrair_funcao_formatar_numero_br(html)

    resultados = _executar_funcao_no_node(funcao, CASOS_NUMERICOS_SPEC)

    for caso, resultado in zip(CASOS_NUMERICOS_SPEC, resultados):
        assert resultado.get("saida", resultado) == caso["esperado"], (
            f"entrada={caso['entrada']!r} casas={caso['casas']!r}: "
            f"esperado {caso['esperado']!r}, obtido {resultado.get('saida', resultado)!r}"
        )


@pytest.mark.parametrize("template", TEMPLATES, ids=lambda p: p.name)
def test_formatar_numero_br_js_comportamento_nao_numerico_por_template(template):
    html = template.read_text(encoding="utf-8")
    funcao = _extrair_funcao_formatar_numero_br(html)
    casos = CASOS_NAO_NUMERICOS_POR_TEMPLATE[template.name]

    resultados = _executar_funcao_no_node(funcao, casos)

    for caso, resultado in zip(casos, resultados):
        assert resultado.get("saida", resultado) == caso["esperado"], (
            f"template={template.name} entrada={caso['entrada']!r}: "
            f"esperado {caso['esperado']!r}, obtido {resultado.get('saida', resultado)!r}"
        )


def test_formatar_numero_br_js_sem_max_casas_usa_padrao_15():
    html = TEMPLATES[0].read_text(encoding="utf-8")
    funcao = _extrair_funcao_formatar_numero_br(html)

    casos = [
        {"entrada": "4.199100000000000", "casas": None, "esperado": "4,1991"},
    ]

    resultado = _executar_funcao_no_node(funcao, casos)[0]

    assert resultado["saida"] == "4,1991"


def test_formatar_numero_br_js_executar_recalculo_nulo_e_nao_numerico_retornam_vazio():
    # Em executar_recalculo.html (campos de fator/variação), valor não numérico
    # deve limpar o campo — comportamento validado também por
    # test_calcular_fator_limpa_campos_quando_tp_invalido.
    html = TEMPLATES[0].read_text(encoding="utf-8")
    funcao = _extrair_funcao_formatar_numero_br(html)

    casos = [
        {"entrada": None, "casas": None},
        {"entrada": "abc", "casas": 6},
    ]

    resultados = _executar_funcao_no_node(funcao, casos)

    for resultado in resultados:
        assert resultado.get("saida", resultado) == ""