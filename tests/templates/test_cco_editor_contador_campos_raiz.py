from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
TEMPLATE_PATH = ROOT_DIR / "app" / "templates" / "cco_editor" / "editar.html"


def ler_template():
    return TEMPLATE_PATH.read_text(encoding="utf-8")


def extrair_funcao(html: str, nome_funcao: str) -> str:
    assinatura = f"function {nome_funcao}"
    inicio = html.index(assinatura)
    abre_chave = html.index("{", inicio)

    nivel = 0
    for pos in range(abre_chave, len(html)):
        char = html[pos]

        if char == "{":
            nivel += 1
        elif char == "}":
            nivel -= 1

            if nivel == 0:
                return html[inicio:pos + 1]

    raise AssertionError(f"Não foi possível extrair a função {nome_funcao}")


def extrair_bloco_dom_content_loaded(html: str) -> str:
    marca = "document.addEventListener('DOMContentLoaded', function() {"
    inicio = html.index(marca)
    abre_chave = html.index("{", inicio)

    nivel = 0
    for pos in range(abre_chave, len(html)):
        char = html[pos]

        if char == "{":
            nivel += 1
        elif char == "}":
            nivel -= 1

            if nivel == 0:
                return html[inicio:pos + 1]

    raise AssertionError("Bloco DOMContentLoaded não encontrado")


def test_aplicar_regras_raiz_registra_campos_recalculados_como_alteracao():
    funcao = extrair_funcao(ler_template(), "aplicarRegrasRaiz")

    assert "setValorCampo('valorReconhecido', vrExp + vrProd, 'raiz', null, true, true)" in funcao
    assert "setValorCampo('overHeadTotal', ohExp + ohProd, 'raiz', null, true, true)" in funcao
    assert "setValorCampo('valorReconhecidoComOH', vr + oh, 'raiz', null, true, true)" in funcao


def test_aplicar_regras_raiz_nao_deixa_nenhum_set_valor_campo_sem_registro():
    funcao = extrair_funcao(ler_template(), "aplicarRegrasRaiz")

    chamadas_set_valor_campo = funcao.split("setValorCampo(")[1:]

    assert len(chamadas_set_valor_campo) == 3
    for chamada in chamadas_set_valor_campo:
        assert "'raiz', null, true, true)" in chamada


def test_dom_content_loaded_chama_inicializar_formatacao_datas_primeiro():
    bloco = extrair_bloco_dom_content_loaded(ler_template())

    pos_inicializacao = bloco.index("inicializarFormatacaoDatas()")
    pos_aplicar_correcoes = bloco.index("aplicarRegrasCorrecoes()")

    assert pos_inicializacao < pos_aplicar_correcoes


def test_inicializacao_de_datas_define_data_valor_raw_original():
    funcao = extrair_funcao(ler_template(), "inicializarFormatacaoDatas")

    assert "input.dataset.valorRawOriginal = valorFormatado;" in funcao
    assert "container.dataset.valorOriginal = valorFormatado;" in funcao


def test_marcar_alteracao_compara_datas_pelo_valor_formatado_original():
    funcao = extrair_funcao(ler_template(), "marcarAlteracao")

    assert "input.dataset.valorRawOriginal || container.dataset.valorOriginal" in funcao