from pathlib import Path


TEMPLATE_PATH = Path("app/templates/cco_timeline.html")


def ler_template():
    assert TEMPLATE_PATH.exists(), f"Template não encontrado: {TEMPLATE_PATH}"
    return TEMPLATE_PATH.read_text(encoding="utf-8")


def test_template_tem_botao_json_original_com_preview_customizado():
    html = ler_template()

    assert 'id="btn-json-original"' in html
    assert 'onclick="mostrarJsonOriginal()"' in html
    assert 'onmouseenter="mostrarPreviewJsonOriginal(event)"' in html
    assert 'onmouseleave="ocultarPreviewJsonOriginal()"' in html
    assert 'data-json-preview="{{ cco_json[:2500] | e }}"' in html
    assert 'id="json-original-popover"' in html
    assert 'id="json-original-popover-content"' in html


def test_template_tem_modal_json_original_com_botao_copiar_usando_mesma_funcao_dos_atributos():
    html = ler_template()

    assert 'id="modalJsonOriginal"' in html
    assert 'id="json-original-preview"' in html
    assert 'onclick="copiarAtributosJSON(event)"' in html


def test_template_nao_usa_mais_monaco_editor_no_json_original():
    html = ler_template()

    assert "monaco.editor.create" not in html
    assert "require.config" not in html
    assert "loader.js" not in html
    assert "require.min.js" not in html


def test_template_usa_bootstrap5_para_fechar_modal():
    html = ler_template()

    assert 'data-bs-dismiss="modal"' in html
    assert 'data-dismiss="modal"' not in html


def test_template_tem_fallback_de_copia_para_contexto_nao_seguro():
    html = ler_template()

    assert "function copiarTextoSeguro" in html
    assert "function copiarTextoFallback" in html
    assert "window.isSecureContext" in html
    assert "document.execCommand('copy')" in html or 'document.execCommand("copy")' in html


def test_template_fallback_de_copia_cria_textarea_dentro_do_modal():
    html = ler_template()

    assert "botaoOrigem.closest('.modal')" in html
    assert "modalAberto.querySelector('.modal-body')" in html
    assert "container.appendChild(textarea)" in html


def test_template_corrige_foco_ao_fechar_modal_para_evitar_warning_aria_hidden():
    html = ler_template()

    assert "hide.bs.modal" in html
    assert "document.activeElement.blur()" in html
