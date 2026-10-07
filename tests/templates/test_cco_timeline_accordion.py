from pathlib import Path
import re

import pytest


TEMPLATE_PATH = (
    Path(__file__).resolve().parents[2]
    / "app"
    / "templates"
    / "cco_timeline.html"
)


@pytest.fixture(scope="module")
def template_source():
    """Carrega o template real da Timeline da CCO."""
    assert TEMPLATE_PATH.exists(), (
        f"Template não encontrado em: {TEMPLATE_PATH}. "
        "Este teste deve ficar em tests/templates/."
    )
    return TEMPLATE_PATH.read_text(encoding="utf-8")


def _extract_function(source: str, function_name: str) -> str:
    """Extrai uma função JavaScript pelo balanceamento das chaves."""
    marker = f"function {function_name}("
    start = source.find(marker)
    assert start != -1, f"Função JavaScript {function_name} não encontrada no template."

    brace_start = source.find("{", start)
    assert brace_start != -1, f"Início da função {function_name} não encontrado."

    depth = 0
    for index in range(brace_start, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start:index + 1]

    pytest.fail(f"Fim da função {function_name} não encontrado.")


def _extract_internal_accordion(source: str) -> str:
    """Recorta somente o accordion de Todos os Atributos da CCO."""
    start_marker = '<div class="accordion" id="accordion-atributos">'
    start = source.find(start_marker)
    assert start != -1, "Accordion #accordion-atributos não encontrado."

    # O accordion termina antes do preview do JSON Original.
    end_marker = "<!-- Preview bonito do JSON Original -->"
    end = source.find(end_marker, start)
    assert end != -1, "Fim da seção de atributos não encontrado."

    return source[start:end]


def test_accordion_de_atributos_nao_deve_fechar_categoria_anterior(template_source):
    """
    Regressão: várias categorias devem poder permanecer abertas ao mesmo tempo.

    O atributo data-bs-parent faz o Bootstrap fechar automaticamente o item
    anteriormente aberto, portanto ele não pode existir nos collapses internos.
    """
    accordion = _extract_internal_accordion(template_source)

    assert 'data-bs-parent="#accordion-atributos"' not in accordion
    assert "data-bs-parent='#accordion-atributos'" not in accordion


def test_todas_as_categorias_continuam_sendo_collapses_independentes(template_source):
    """Garante que as categorias principais continuam existentes e independentes."""
    accordion = _extract_internal_accordion(template_source)

    categorias = {
        "cat-identificacao",
        "cat-valores",
        "cat-datas",
        "cat-flags",
        "cat-metadados",
    }

    for categoria_id in categorias:
        assert re.search(
            rf'id="{re.escape(categoria_id)}"\s+class="accordion-collapse collapse(?: show)?"',
            accordion,
        ), f"Collapse #{categoria_id} não encontrado ou teve sua estrutura alterada."


def test_botoes_das_categorias_apontam_para_o_collapse_correto(template_source):
    """Cada botão deve continuar controlando somente a própria categoria."""
    accordion = _extract_internal_accordion(template_source)

    pares = {
        "cat-identificacao": "cat-identificacao",
        "cat-valores": "cat-valores",
        "cat-datas": "cat-datas",
        "cat-flags": "cat-flags",
        "cat-metadados": "cat-metadados",
    }

    for target_id, controls_id in pares.items():
        pattern = (
            rf'<button[^>]*class="accordion-button[^\"]*"[^>]*'
            rf'data-bs-toggle="collapse"[^>]*'
            rf'data-bs-target="#{re.escape(target_id)}"[^>]*'
            rf'aria-controls="{re.escape(controls_id)}"'
        )
        assert re.search(pattern, accordion, flags=re.DOTALL), (
            f"Botão responsável por #{target_id} não está configurado corretamente."
        )


def test_fallback_do_accordion_nao_fecha_os_outros_itens(template_source):
    """
    Regressão para ambientes sem bootstrap.Collapse.

    O fallback deve alternar apenas o target clicado e nunca percorrer os outros
    .accordion-collapse para fechá-los.
    """
    start = template_source.find("document.addEventListener('click', function(event)")
    assert start != -1, "Handler de clique do accordion não encontrado."

    end = template_source.find("let atributosSearchDebounceTimer", start)
    assert end != -1, "Fim do handler de clique do accordion não encontrado."

    handler = template_source[start:end]

    assert "const estaAberto = target.classList.contains('show');" in handler
    assert "target.classList.remove('show');" in handler
    assert "target.classList.add('show');" in handler

    # Essa era a lógica que causava o fechamento dos outros accordions no fallback.
    assert "accordion.querySelectorAll('.accordion-collapse')" not in handler
    assert "if (item !== target)" not in handler


def test_busca_remove_display_inline_quando_bootstrap_controla_o_collapse(template_source):
    """
    Regressão do defeito original do QA.

    Durante a busca, não pode sobrar display:block/none inline quando o Bootstrap
    estiver responsável pelo Collapse, pois isso conflita com a classe .show.
    """
    function_source = _extract_function(
        template_source,
        "atualizarEstadoCategoriaAtributos",
    )

    assert "const bootstrapDisponivel" in function_source
    assert "collapse.style.removeProperty('display');" in function_source

    # display inline fica permitido somente no fallback sem Bootstrap.
    assert "if (!bootstrapDisponivel)" in function_source
    assert "collapse.style.display = 'block';" in function_source
    assert "collapse.style.display = 'none';" in function_source


def test_busca_abre_painel_principal_sem_forcar_display_com_bootstrap(template_source):
    """A pesquisa deve abrir Todos os Atributos sem recriar o conflito de display."""
    function_source = _extract_function(
        template_source,
        "abrirPainelAtributosSeNecessario",
    )

    assert "collapseEl.style.removeProperty('display');" in function_source
    assert "bootstrap.Collapse.getOrCreateInstance" in function_source
    assert "instance.show();" in function_source


def test_busca_continua_expandindo_categoria_com_resultado(template_source):
    """A correção de múltiplos abertos não pode quebrar a expansão dos resultados."""
    function_source = _extract_function(template_source, "filtrarAtributos")

    assert "abrirPainelAtributosSeNecessario();" in function_source
    assert (
        "atualizarEstadoCategoriaAtributos(categoria, encontrouNaCategoria, encontrouNaCategoria);"
        in function_source
    )


def test_limpar_busca_nao_fecha_categorias_abertas(template_source):
    """
    Limpar o filtro deve apenas restaurar linhas/categorias, sem recolher collapses.
    """
    function_source = _extract_function(template_source, "filtrarAtributos")

    empty_search_start = function_source.find("if (termo === '')")
    assert empty_search_start != -1

    search_execution_start = function_source.find(
        "abrirPainelAtributosSeNecessario();",
        empty_search_start,
    )
    assert search_execution_start != -1

    empty_search_block = function_source[empty_search_start:search_execution_start]

    assert "categoria.style.display = '';" in empty_search_block
    assert "linha.style.display = '';" in empty_search_block
    assert "classList.remove('show')" not in empty_search_block
    assert "classList.add('collapsed')" not in empty_search_block
