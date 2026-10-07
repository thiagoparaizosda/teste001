# tests/templates/test_bug_19471_contador_campos_raiz.py
# BUG-19471: Contadores de campos alterados na aba Campos Raiz não contabilizam
# campos recalculados automaticamente
# Gerado por test-agent — baseado na spec (specs/2026-Q3/BUG-19471-contador-campos-alterados.spec.md),
# não na implementação.
# Revisar antes de commitar
from pathlib import Path

import pytest


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
    assinatura = "addEventListener('DOMContentLoaded'"
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

    raise AssertionError("Não foi possível extrair o bloco DOMContentLoaded")


class TestRegistrarCamposRecalculadosNaRaiz:
    """FR-001 (spec §1 e §3.1): aplicarRegrasRaiz() deve passar
    registrarAlteracao=true (parâmetros 5 e 6 = true, true) nas 3 chamadas
    setValorCampo dos campos recalculados, espelhando aplicarRegrasCorrecoes()."""

    def test_valor_reconhecido_e_registrado_como_alteracao(self):
        html = ler_template()
        funcao = extrair_funcao(html, "aplicarRegrasRaiz")

        assert "setValorCampo('valorReconhecido', vrExp + vrProd, 'raiz', null, true, true)" in funcao

    def test_overhead_total_e_registrado_como_alteracao(self):
        html = ler_template()
        funcao = extrair_funcao(html, "aplicarRegrasRaiz")

        assert "setValorCampo('overHeadTotal', ohExp + ohProd, 'raiz', null, true, true)" in funcao

    def test_valor_reconhecido_com_oh_e_registrado_como_alteracao(self):
        html = ler_template()
        funcao = extrair_funcao(html, "aplicarRegrasRaiz")

        assert "setValorCampo('valorReconhecidoComOH', vr + oh, 'raiz', null, true, true)" in funcao

    def test_nenhum_recalculado_da_raiz_usar_registrar_alteracao_false(self):
        """Caso de erro/negativo: os 3 recalculados NÃO podem cair no default
        (registrarAlteracao=false). A spec é explícita: parâmetro 6 = true."""
        html = ler_template()
        funcao = extrair_funcao(html, "aplicarRegrasRaiz")

        for campo in ("valorReconhecido", "overHeadTotal", "valorReconhecidoComOH"):
            chamada = f"setValorCampo('{campo}'"
            inicio = funcao.index(chamada)
            fim_linha = funcao.index(";", inicio)
            linha = funcao[inicio:fim_linha]

            assert linha.endswith("'raiz', null, true, true)"), (
                f"Chamada de {campo} deve terminar com registrarAlteracao=true: {linha}"
            )

    def test_formulas_dos_tres_recalculados_seguem_a_spec(self):
        """Spec: valorReconhecido = vrExploracao + vrProducao;
        overHeadTotal = ohExploracao + ohProducao;
        valorReconhecidoComOH = valorReconhecido + overHeadTotal."""
        html = ler_template()
        funcao = extrair_funcao(html, "aplicarRegrasRaiz")

        assert "const vrExp = getValorCampo('valorReconhecidoExploracao', 'raiz')" in funcao
        assert "const vrProd = getValorCampo('valorReconhecidoProducao', 'raiz')" in funcao
        assert "setValorCampo('valorReconhecido', vrExp + vrProd" in funcao

        assert "const ohExp = getValorCampo('overHeadExploracao', 'raiz')" in funcao
        assert "const ohProd = getValorCampo('overHeadProducao', 'raiz')" in funcao
        assert "setValorCampo('overHeadTotal', ohExp + ohProd" in funcao

        assert "const vr = getValorCampo('valorReconhecido', 'raiz')" in funcao
        assert "const oh = getValorCampo('overHeadTotal', 'raiz')" in funcao
        assert "setValorCampo('valorReconhecidoComOH', vr + oh" in funcao

    def test_guard_inicializando_tela_impede_registro_durante_carga(self):
        """Spec §3.1: o guard `!inicializandoTela` em setValorCampo impede o
        registro durante a inicialização da tela (sem falso positivo no load)."""
        html = ler_template()
        funcao = extrair_funcao(html, "setValorCampo")

        assert "if (registrarAlteracao && !inicializandoTela)" in funcao
        assert "marcarAlteracao(nome, input.value)" in funcao


class TestDatasFormatadasNoCarregamento:
    """FR-002/FR-005 (spec §1 e §3.2): inicializarFormatacaoDatas() deve ser
    invocada no DOMContentLoaded e formatar os campos .campo-data para
    dd/MM/yyyy HH:mm:ss, definindo data-valor-raw-original para comparação."""

    def test_dom_content_loaded_chama_inicializar_formatacao_datas_primeira_acao(self):
        html = ler_template()
        bloco = extrair_bloco_dom_content_loaded(html)

        primeira_chamada = bloco.index("inicializarFormatacaoDatas();")

        # Deve vir antes de aplicarRegrasCorrecoes() (que ordena por datas formatadas)
        assert primeira_chamada < bloco.index("aplicarRegrasCorrecoes();")

    def test_inicializar_formatacao_datas_formata_campos_campo_data(self):
        html = ler_template()
        funcao = extrair_funcao(html, "inicializarFormatacaoDatas")

        assert "querySelectorAll('.campo-data')" in funcao
        assert "formatarDataParaFrontend(valorOriginal)" in funcao
        assert "input.value = valorFormatado" in funcao

    def test_inicializar_formatacao_datas_define_valor_raw_original(self):
        """Spec §2 (causa raiz): sem data-valor-raw-original, marcarAlteracao()
        compara formato BR contra ISO bruto -> falso positivo. O fix deve definir
        o atributo para cada .campo-data."""
        html = ler_template()
        funcao = extrair_funcao(html, "inicializarFormatacaoDatas")

        assert "input.dataset.valorRawOriginal = valorFormatado" in funcao
        assert "input.setAttribute('data-valor-raw-original', valorFormatado)" in funcao

    def test_campos_de_data_do_cco_estao_mapeados_no_template(self):
        """Spec §1: dataLancamento e demais datas do CCO são tratadas como
        .campo-data — devem estar no conjunto campos_data_cco do template."""
        html = ler_template()

        for campo in ("dataLancamento", "dataReconhecimento", "dataCriacao", "dataAtualizacao"):
            assert f"'{campo}'" in html


class TestContadoresIncluemRecalculados:
    """FR-003/FR-004 (spec §1 §4): ao editar overHeadExploracao, os contadores
    (badge #countAlteracoesRaiz e card Resumo) devem refletir campo editado +
    recalculados; reverter deve remover a contagem."""

    def test_atualizar_resumo_usa_alteracoes_raiz_como_fonte_unica_dos_contadores(self):
        """Badge e Resumo compartilham Object.keys(alteracoesRaiz).length —
        se os recalculados entram no objeto, ambos os contadores refletem."""
        html = ler_template()
        funcao = extrair_funcao(html, "atualizarResumo")

        assert "const countRaiz = Object.keys(alteracoesRaiz).length" in funcao
        assert "document.getElementById('countAlteracoesRaiz').textContent = countRaiz" in funcao
        assert "Raiz:</strong> ' + countRaiz" in funcao
        assert "document.getElementById('resumoAlteracoes').innerHTML" in funcao

    def test_marcar_alteracao_adiciona_campo_quando_valor_difere_do_original(self):
        """Quando o valor recalculado difere do original, marcarAlteracao()
        registra o campo em alteracoesRaiz (fonte dos contadores)."""
        html = ler_template()
        funcao = extrair_funcao(html, "marcarAlteracao")

        assert "alteracoesRaiz[campo] = valorAlteracao" in funcao
        assert "container.classList.add('campo-alterado')" in funcao

    def test_marcar_alteracao_remove_campo_quando_revertido_ao_original(self):
        """Critério de aceite: 'Reverter o campo editado ao valor original ->
        contadores voltam ao estado anterior' (delete remove a contagem)."""
        html = ler_template()
        funcao = extrair_funcao(html, "marcarAlteracao")

        assert "delete alteracoesRaiz[campo]" in funcao
        assert "container.classList.remove('campo-alterado')" in funcao

    def test_marcar_alteracao_compara_data_com_valor_raw_original(self):
        """Critério de aceite: 'Tocar em um campo de data e reverter ao valor
        original -> contador não aumenta'. Para datas, o original comparado deve
        ser o data-valor-raw-original (normalizado no load), não o ISO bruto."""
        html = ler_template()
        funcao = extrair_funcao(html, "marcarAlteracao")

        assert "campoEhData(campo)" in funcao
        assert "input.dataset.valorRawOriginal || container.dataset.valorOriginal" in funcao

    def test_salvar_envia_alteracoes_raiz_para_o_backend(self):
        """Spec §3.1: o payload de salvar passa a incluir os recalculados,
        persistindo-os em registro_alteracoes (alteracoes_raiz no POST)."""
        html = ler_template()
        funcao = extrair_funcao(html, "executarSalvamento")

        assert "alteracoes_raiz: alteracoesRaiz" in funcao
        assert "/cco-editor/api/salvar" in funcao


class TestSemRegressaoNaAbaCorrecoes:
    """FR-008 (spec §4): contadores da aba Correções permanecem sem regressão.
    aplicarRegrasCorrecoes() já registra os recalculados (registrarAlteracao)."""

    def test_aplicar_regras_correcoes_continua_registrando_overhead_total(self):
        html = ler_template()
        funcao = extrair_funcao(html, "aplicarRegrasCorrecoes")
        helper = extrair_funcao(html, "calcularOverheadTotalCorrecao")

        assert "const registrarAlteracao = !inicializandoTela" in funcao
        assert "setValorCampo('overHeadTotal', overheadTotalCalculado, 'correcao', indice, true, registrarAlteracao)" in helper

    def test_aplicar_regras_correcoes_continua_registrando_valor_com_oh_e_diferenca(self):
        html = ler_template()
        funcao = extrair_funcao(html, "aplicarRegrasCorrecoes")

        assert "setValorCampo('valorReconhecidoComOH', valorComOHCalculado, 'correcao', indice, true, true)" in funcao
        assert "setValorCampo('diferencaValor', diferencaCalculada, 'correcao', indice, true, true)" in funcao


class TestDestaqueVisualCalculado:
    """Spec §3.1: o destaque visual dos recalculados segue azul ('Calculado'),
    pois .campo-calculado é declarado depois de .campo-alterado (ambos
    !important)."""

    def test_campo_calculado_declarado_apos_campo_alterado(self):
        html = ler_template()

        indice_alterado = html.index(".campo-alterado {")
        indice_calculado = html.index(".campo-calculado {")

        assert indice_calculado > indice_alterado
        assert ".campo-alterado { background-color: #fff3cd !important" in html
        assert ".campo-calculado { background-color: #d1ecf1 !important" in html

    def test_set_valor_campo_marca_recalculado_como_calculado(self):
        html = ler_template()
        funcao = extrair_funcao(html, "setValorCampo")

        assert "input.classList.add('campo-calculado')" in funcao
        assert "icon-calculado" in funcao