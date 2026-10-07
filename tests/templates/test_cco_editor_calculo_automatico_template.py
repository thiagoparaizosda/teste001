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


def test_botao_calculo_automatico_existe_e_fica_separado_do_acumulado_reais():
    html = ler_template()

    assert 'id="calc_{{ correcao.indice }}_igpmAcumuladoReais"' in html
    assert 'id="btn_auto_calculo_{{ correcao.indice }}"' in html
    assert "Cálculo Automático: Ligado" in html

    indice_botao = html.index('id="btn_auto_calculo_{{ correcao.indice }}"')
    trecho_botao = html[indice_botao - 600:indice_botao + 600]

    assert "input-group" not in trecho_botao
    assert "col-md-4 mt-2 d-flex align-items-end justify-content-end" in trecho_botao


def test_botao_controla_os_quatro_campos_calculados_da_correcao():
    html = ler_template()
    funcao = extrair_funcao(html, "atualizarBotaoCalculoAutomaticoCorrecao")

    assert "_overHeadTotal" in funcao
    assert "_valorReconhecidoComOhOriginal" in funcao
    assert "_valorReconhecidoComOH" in funcao
    assert "_diferencaValor" in funcao
    assert "calculo-auto-desligado" in funcao


def test_on_campo_change_guarda_ultimo_campo_alterado_da_correcao():
    html = ler_template()
    funcao = extrair_funcao(html, "onCampoChange")

    assert "ultimoCampoAlteradoCorrecao[indice] = nome" in funcao
    assert "aplicarRegras(contexto, indice)" in funcao
    assert "validarTudo()" in funcao


def test_funcao_de_toggle_recalcula_ao_ligar_novamente_o_automatico():
    html = ler_template()
    funcao = extrair_funcao(html, "toggleCalculoAutomaticoCorrecao")

    assert "calculoAutomaticoCorrecoes[indice]" in funcao
    assert "atualizarBotaoCalculoAutomaticoCorrecao(indice)" in funcao
    assert "if (isCalculoAutomaticoCorrecaoAtivo(indice))" in funcao
    assert "aplicarRegrasCorrecoes()" in funcao
    assert "validarTudo()" in funcao


def test_formula_overhead_total_eh_exploracao_mais_producao():
    html = ler_template()
    funcao = extrair_funcao(html, "calcularOverheadTotalCorrecao")

    assert "overHeadExploracao" in funcao
    assert "overHeadProducao" in funcao
    assert "setValorCampo('overHeadTotal'" in funcao
    assert "+ getValorCampo('overHeadProducao', 'correcao', indice)" in funcao


def test_formula_valor_reconhecido_com_oh_original_eh_valor_reconhecido_mais_overhead_total():
    html = ler_template()
    funcao = extrair_funcao(html, "calcularValorOriginalComOHCorrecao")

    assert "getValorCampo('valorReconhecido', 'correcao', indice)" in funcao
    assert "calcularOverheadTotalCorrecao(indice, registrarAlteracao)" in funcao
    assert "valorReconhecido + overheadTotal" in funcao
    assert "setValorCampo('valorReconhecidoComOhOriginal'" in funcao


def test_campos_que_disparam_recalculo_do_valor_original_com_oh_estao_mapeados():
    html = ler_template()
    funcao = extrair_funcao(html, "campoAlteradoDeveRecalcularValorOriginalComOH")

    assert "'valorReconhecido'" in funcao
    assert "'overHeadTotal'" in funcao
    assert "'overHeadExploracao'" in funcao
    assert "'overHeadProducao'" in funcao


def test_valor_reconhecido_com_oh_tem_formula_por_tipo_de_correcao():
    html = ler_template()
    funcao = extrair_funcao(html, "aplicarRegrasCorrecoes")

    assert "tipo === 'IPCA' || tipo === 'IGPM'" in funcao
    assert "valorComOHCalculado = valorComOhOriginal * taxa" in funcao

    assert "tipo === 'RECUPERACAO'" in funcao
    assert "valorComOHCalculado = valorComOhOriginal - valorRecuperado" in funcao

    assert "valorComOHCalculado = valorComOhOriginal" in funcao


def test_diferenca_valor_eh_valor_original_menos_valor_com_oh():
    html = ler_template()
    funcao = extrair_funcao(html, "aplicarRegrasCorrecoes")

    assert "diferencaCalculada = valorComOhOriginal - valorComOHCalculado" in funcao
    assert "setValorCampo('diferencaValor', diferencaCalculada" in funcao


def test_quatro_campos_so_sao_sobrescritos_quando_calculo_automatico_esta_ligado():
    html = ler_template()
    funcao = extrair_funcao(html, "aplicarRegrasCorrecoes")

    trecho_automatico = funcao.split("if (calculoAutomaticoAtivo)", 1)[1].split("// Acumulados visuais continuam", 1)[0]
    trecho_pos_automatico = funcao.split("// Acumulados visuais continuam", 1)[1]

    assert "calcularOverheadTotalCorrecao(indice, registrarAlteracao)" in trecho_automatico
    assert "calcularValorOriginalComOHCorrecao(indice, registrarAlteracao)" in trecho_automatico
    assert "setValorCampo('valorReconhecidoComOH'" in trecho_automatico
    assert "setValorCampo('diferencaValor'" in trecho_automatico

    assert "setValorCampo(" not in trecho_pos_automatico


def test_acumulado_reais_usa_diferenca_atual_quando_automatico_estiver_desligado():
    html = ler_template()
    funcao = extrair_funcao(html, "aplicarRegrasCorrecoes")

    assert "const diferencaAtual = getValorCampo('diferencaValor', 'correcao', indice)" in funcao
    assert "igpmAcumuladoReais += Math.abs(diferencaAtual)" in funcao


def test_validacao_cobre_overhead_original_valor_com_oh_e_diferenca():
    html = ler_template()
    funcao = extrair_funcao(html, "validarCorrecoes")

    assert "campo: 'overHeadTotal'" in funcao
    assert "overHeadExploracao + overHeadProducao" in funcao

    assert "campo: 'valorReconhecidoComOhOriginal'" in funcao
    assert "valorReconhecido + overHeadTotal" in funcao

    assert "campo: 'valorReconhecidoComOH'" in funcao
    assert "campo: 'diferencaValor'" in funcao
    assert "valorReconhecidoComOhOriginal - valorReconhecidoComOH" in funcao
