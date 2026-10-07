from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
TEMPLATE_PATH = ROOT_DIR / "app" / "templates" / "pesquisa_ccos.html"
ROUTE_PATH = ROOT_DIR / "app" / "routes" / "portal_ui.py"
SERVICE_PATH = ROOT_DIR / "app" / "services" / "portal_service.py"


def ler_template():
    return TEMPLATE_PATH.read_text(encoding="utf-8")


def ler_rota():
    return ROUTE_PATH.read_text(encoding="utf-8")


def ler_service():
    return SERVICE_PATH.read_text(encoding="utf-8")


def test_select_fase_remessa_nao_possui_fases_hardcoded():
    html = ler_template()

    assert '<select class="form-select" id="selectFase">' in html
    assert '<option value="">Todas</option>' in html

    for fase in ["MEN", "ROP", "RAD", "REC", "REV", "ABCR", "AUD", "ABCR1", "ABCR2"]:
        assert f'<option value="{fase}">{fase}</option>' not in html


def test_frontend_carrega_fases_por_api_distinct():
    html = ler_template()

    assert "carregarFasesRemessa();" in html
    assert "function carregarFasesRemessa()" in html
    assert "/api/fases-ccos-disponiveis" in html
    assert "data.fases.forEach" in html
    assert "option.value = fase" in html
    assert "option.textContent = fase" in html


def test_frontend_envia_fase_remessa_selecionada_no_payload():
    html = ler_template()

    assert "faseRemessa: document.getElementById('selectFase').value" in html


def test_backend_possui_endpoint_para_listar_fases_disponiveis():
    rota = ler_rota()

    assert "@portal_bp.route('/api/fases-ccos-disponiveis')" in rota
    assert "def api_fases_ccos_disponiveis()" in rota
    assert "portal_service.listar_fases_disponiveis()" in rota
    assert "return jsonify({'fases': fases})" in rota


def test_service_lista_fases_distintas_de_fase_remessa_e_fase_resposta_gestora():
    service = ler_service()

    assert "def listar_fases_disponiveis(self)" in service
    assert "colecao.distinct('faseRemessa')" in service
    assert "colecao.distinct('faseRespostaGestora')" in service


def test_service_nao_remove_numero_de_fases_sequenciais_validas_na_lista():
    service = ler_service()

    assert "def normalizar_fase_para_lista(fase: Any, campo_origem: str = '') -> str" in service
    assert "return re.sub(r'\\d+$', '', fase_normalizada)" not in service
    assert "ABCR1, ABCR2, REV1, REV2, REV99" in service
    assert "return fase_normalizada" in service


def test_service_substitui_fisc_por_aud_somente_quando_origem_for_fase_remessa():
    service = ler_service()

    assert "if campo_origem == 'faseRemessa' and fase_normalizada == 'FISC':" in service
    assert "return 'AUD'" in service
    assert "self.normalizar_fase_para_lista(fase, 'faseRemessa')" in service
    assert "self.normalizar_fase_para_lista(fase, 'faseRespostaGestora')" in service


def test_service_filtra_fase_resposta_gestora_para_apenas_rev_e_abcr_validos():
    service = ler_service()

    assert "def fase_resposta_gestora_valida_para_filtro(fase: str) -> bool:" in service
    assert "re.fullmatch(r'(REV|ABCR)\\d{0,2}', fase or '')" in service
    assert "campo_origem == 'faseRespostaGestora'" in service
    assert "not PortalService.fase_resposta_gestora_valida_para_filtro(fase_normalizada)" in service


def test_service_documenta_exemplos_invalidos_de_fase_resposta_gestora():
    service = ler_service()

    assert "2014FAN" in service
    assert "25MUM" in service
    assert "REV1666354677259" in service


def test_backend_nao_remove_numero_da_fase_selecionada_no_filtro():
    rota = ler_rota()

    assert "def normalizar_fase_pesquisa_cco(fase: str) -> str:" in rota
    assert "return (fase or '').strip().upper()" in rota
    assert "return re.sub(r'\\d+$', '', fase_normalizada)" not in rota


def test_backend_filtra_fase_resposta_gestora_por_igualdade_para_abcr1_abcr2_rev1_rev2():
    rota = ler_rota()

    assert "def aplicar_filtro_fase_pesquisa_cco(filtro_mongo: dict, fase: str) -> None:" in rota
    assert "{'faseRespostaGestora': fase_normalizada}" in rota
    assert "'$regex'" not in rota
    assert "\\\\d*$" not in rota


def test_backend_filtra_fase_remessa_por_lista_de_equivalencias():
    rota = ler_rota()

    assert "{'faseRemessa': {'$in': valores_fase_remessa_para_pesquisa(fase_normalizada)}}" in rota


def test_backend_quando_usuario_seleciona_aud_tambem_pesquisa_fisc_em_fase_remessa():
    rota = ler_rota()

    assert "def valores_fase_remessa_para_pesquisa(fase: str) -> list:" in rota
    assert "if fase_normalizada == 'AUD':" in rota
    assert "return ['AUD', 'FISC']" in rota


def test_api_pesquisar_ccos_usa_mesma_montagem_de_filtro_da_exportacao():
    rota = ler_rota()

    assert "def montar_filtros_pesquisa_ccos(dados):" in rota
    assert "filtro_mongo = montar_filtros_pesquisa_ccos(dados)" in rota
    assert "filtros = montar_filtros_pesquisa_ccos(filtros_request)" in rota
    assert "aplicar_filtro_fase_pesquisa_cco(filtro_mongo, dados['faseRemessa'])" in rota


def test_tabela_resultados_possui_coluna_fase_resposta_gestora():
    html = ler_template()

    assert '<th class="col-fase-resposta-gestora">Fase Resposta Gestora</th>' in html
    assert '<td class="col-fase-resposta-gestora">' in html
    assert "cco.faseRespostaGestora" in html


def test_coluna_fase_resposta_gestora_aparece_quando_algum_resultado_possui_valor():
    html = ler_template()

    assert "function faseRespostaGestoraPreenchida(faseRespostaGestora)" in html
    assert "function deveExibirColunaFaseRespostaGestora(resultados = [])" in html
    assert "return resultados.some(cco => faseRespostaGestoraPreenchida(cco.faseRespostaGestora));" in html


def test_datatable_foi_ajustado_com_indices_apos_incluir_fase_resposta_gestora():
    html = ler_template()

    assert "{ targets: [10, 11], className: 'text-end' }" in html
    assert "{ targets: [9, 10], className: 'text-end' }" not in html


def test_service_retorna_fase_resposta_gestora_para_a_tabela():
    service = ler_service()

    assert "'faseRespostaGestora': 1" in service
    assert "'faseRespostaGestora': cco.get('faseRespostaGestora', '')" in service