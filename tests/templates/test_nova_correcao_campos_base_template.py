from pathlib import Path
import re


ROOT_DIR = Path(__file__).resolve().parents[2]
TEMPLATE_PATH = ROOT_DIR / "app" / "templates" / "cco_editor" / "editar.html"


CAMPOS_NOVA_CORRECAO = {
    "nc_quantidadeLancamento": "valores_base_retificacao.quantidadeLancamento",
    "nc_igpmAcumuladoReais": "valores_base_retificacao.igpmAcumuladoReais",
    "nc_igpmAcumulado": "valores_base_retificacao.igpmAcumulado",
    "nc_valorReconhecivel": "valores_base_retificacao.valorReconhecivel",
    "nc_valorLancamentoTotal": "valores_base_retificacao.valorLancamentoTotal",
}


def ler_template():
    return TEMPLATE_PATH.read_text(encoding="utf-8")


def extrair_input_por_id(html: str, input_id: str) -> str:
    padrao = re.compile(rf'<input[^>]+id="{re.escape(input_id)}"[^>]*>')
    match = padrao.search(html)

    assert match, f"Input {input_id} não encontrado no template editar.html"

    return match.group(0)


def test_campos_faltantes_da_nova_correcao_vem_de_valores_base_retificacao():
    html = ler_template()

    for input_id, variavel_jinja in CAMPOS_NOVA_CORRECAO.items():
        input_html = extrair_input_por_id(html, input_id)

        assert variavel_jinja in input_html
        assert 'value="0"' not in input_html


def test_nova_correcao_nao_zera_campos_base_identificados_na_missao():
    html = ler_template()

    campos_que_nao_podem_ser_fixos_zero = [
        "nc_quantidadeLancamento",
        "nc_igpmAcumuladoReais",
        "nc_igpmAcumulado",
        "nc_valorReconhecivel",
        "nc_valorLancamentoTotal",
    ]

    for input_id in campos_que_nao_podem_ser_fixos_zero:
        input_html = extrair_input_por_id(html, input_id)

        assert 'value="{{ valores_base_retificacao.' in input_html
        assert ' or 0 }}"' in input_html


def test_campos_faltantes_sao_coletados_no_payload_da_nova_correcao():
    html = ler_template()

    assert "quantidadeLancamento: parseInt(document.getElementById('nc_quantidadeLancamento').value) || 0" in html
    assert "igpmAcumuladoReais: parseValor(document.getElementById('nc_igpmAcumuladoReais').value)" in html
    assert "igpmAcumulado: parseValor(document.getElementById('nc_igpmAcumulado').value)" in html
    assert "valorReconhecivel: parseValor(document.getElementById('nc_valorReconhecivel').value)" in html
    assert "valorLancamentoTotal: parseValor(document.getElementById('nc_valorLancamentoTotal').value)" in html
