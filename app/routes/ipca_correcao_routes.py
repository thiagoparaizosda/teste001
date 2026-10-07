from datetime import datetime

from flask import Blueprint, request, jsonify, render_template
from app.config import MONGO_URI, MONGO_URI_PRD, Config
from app.models.permission import Permission
from app.services.ipca_correcao_orquestrador import IPCACorrectionOrchestrator
from app.services.ipca_correcao_engine import IPCACorrectionEngine
from app.services.ipca_gap_analyzer import IPCAGapAnalyzer
from app.utils.converters import converter_decimal128_para_float
from pymongo import MongoClient
from app.middleware.auth_middleware import require_permission, get_current_user_id
import logging

logger = logging.getLogger(__name__)

ipca_correcao_bp = Blueprint('ipca_correcao', __name__, url_prefix='/ipca-correcao')


def get_services():
    client = MongoClient(MONGO_URI)
    db = client.sgppServices
    client_prd = MongoClient(MONGO_URI_PRD)
    db_prd = client_prd.sgppServices

    gap_analyzer = IPCAGapAnalyzer(db, db_prd)
    correction_engine = IPCACorrectionEngine(db, db_prd, gap_analyzer)
    orchestrator = IPCACorrectionOrchestrator(db, db_prd, gap_analyzer, correction_engine)

    return orchestrator

@ipca_correcao_bp.context_processor
def inject_today_date():
    return {'today_date': datetime.today().strftime('%Y-%m-%d')}


def _buscar_info_cco(cco_id: str) -> dict:
    """Busca dados de identificação de uma CCO pelo ID."""
    try:
        client_prd = MongoClient(MONGO_URI_PRD)
        db_prd = client_prd.sgppServices
        cco = db_prd.conta_custo_oleo_entity.find_one(
            {"_id": cco_id},
            {"_id": 1, "contratoCpp": 1, "remessa": 1, "faseRemessa": 1, "origemDosGastos": 1}
        )
        if cco:
            return {
                "id": str(cco.get("_id", "")),
                "contratoCpp": cco.get("contratoCpp", ""),
                "remessa": cco.get("remessa", ""),
                "faseRemessa": cco.get("faseRemessa", ""),
                "origemDosGastos": cco.get("origemDosGastos", ""),
            }
    except Exception as e:
        logger.warning(f"Não foi possível buscar info da CCO {cco_id}: {e}")
    return {}


@ipca_correcao_bp.route('/')
@require_permission(Permission.CORRECAO_CREATE)
def index():
    """Página principal de correção IPCA"""
    cco_id = request.args.get('cco_id', '')
    return render_template('recalculo/ipca_analise_e_recalculo.html', cco_id_inicial=cco_id)


@ipca_correcao_bp.route('/index')
@require_permission(Permission.CORRECAO_CREATE)
def index_2():
    """Página principal de correção IPCA (alias)"""
    return render_template('recalculo/index.html')


@ipca_correcao_bp.route('/pesquisar-ccos')
@require_permission(Permission.CORRECAO_CREATE)
def pesquisar_ccos():
    """Tela de pesquisa de CCOs para correção IPCA"""
    return render_template('ipca_correcao/pesquisar_ccos.html')


@ipca_correcao_bp.route('/api/pesquisar-ccos', methods=['POST'])
@require_permission(Permission.CORRECAO_CREATE)
def api_pesquisar_ccos():
    """API para pesquisar CCOs disponíveis para correção IPCA"""
    try:
        dados = request.get_json()
        if not dados:
            return jsonify({'success': False, 'error': 'Dados não fornecidos'}), 400

        filtro_mongo = {}

        if dados.get('id'):
            filtro_mongo['_id'] = dados['id']
        else:
            if not dados.get('contratoCpp'):
                return jsonify({'success': False, 'error': 'Contrato CPP é obrigatório'}), 400
            filtro_mongo['contratoCpp'] = dados['contratoCpp']
            if dados.get('campo'):
                filtro_mongo['campo'] = dados['campo']
            if dados.get('remessa'):
                filtro_mongo['remessa'] = int(dados['remessa'])
            if dados.get('faseRemessa'):
                filtro_mongo['faseRemessa'] = dados['faseRemessa']
            if dados.get('origemDosGastos'):
                filtro_mongo['origemDosGastos'] = dados['origemDosGastos']
            if dados.get('exercicio'):
                filtro_mongo['exercicio'] = int(dados['exercicio'])
            if dados.get('periodo'):
                filtro_mongo['periodo'] = int(dados['periodo'])

        projecao = {
            '_id': 1, 'contratoCpp': 1, 'campo': 1, 'remessa': 1,
            'faseRemessa': 1, 'exercicio': 1, 'periodo': 1,
            'origemDosGastos': 1, 'valorReconhecidoComOH': 1, 'flgRecuperado': 1,
        }

        client_prd = MongoClient(MONGO_URI_PRD)
        db_prd = client_prd.sgppServices
        cursor = db_prd.conta_custo_oleo_entity.find(filtro_mongo, projecao).limit(100)
        ccos = list(cursor.sort([('remessa', -1), ('faseRemessa', 1)]))

        resultados = [
            {
                'id': str(c['_id']),
                'contratoCpp': c.get('contratoCpp', ''),
                'campo': c.get('campo', ''),
                'remessa': c.get('remessa', ''),
                'faseRemessa': c.get('faseRemessa', ''),
                'exercicio': c.get('exercicio', ''),
                'periodo': c.get('periodo', ''),
                'origemDosGastos': c.get('origemDosGastos', ''),
                'valorReconhecidoComOH': converter_decimal128_para_float(c.get('valorReconhecidoComOH', 0)),
                'flgRecuperado': c.get('flgRecuperado', False),
            }
            for c in ccos
        ]

        return jsonify({'success': True, 'resultados': resultados, 'total': len(resultados)})

    except Exception as e:
        logger.error(f"Erro na API pesquisar-ccos IPCA: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@ipca_correcao_bp.route('/api/iniciar-analise', methods=['POST'])
@require_permission(Permission.CORRECAO_CREATE)
def iniciar_analise():
    """API para iniciar análise de CCO"""
    try:
        data = request.get_json()
        cco_id = data.get('cco_id')

        if not cco_id:
            return jsonify({'success': False, 'error': 'CCO ID é obrigatório'}), 400

        user_id = get_current_user_id()

        cco_info = _buscar_info_cco(cco_id)
        
        if cco_info == {}:
            return jsonify({'success': False, 'error': 'CCO não encontrada'}), 404
            
        orchestrator = get_services()
        resultado = orchestrator.iniciar_analise_cco(cco_id, user_id)

        if resultado.get('success'):
            resultado['cco_info'] = cco_info

        return jsonify(resultado)

    except Exception as e:
        logger.error(f"Erro na API iniciar-analise: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@ipca_correcao_bp.route('/api/gerar-propostas', methods=['POST'])
@require_permission(Permission.CORRECAO_CREATE)
def gerar_propostas():
    """API para gerar propostas de correção"""
    try:
        data = request.get_json()
        session_id = data.get('session_id')

        if not session_id:
            return jsonify({'success': False, 'error': 'Session ID é obrigatório'}), 400

        orchestrator = get_services()
        resultado = orchestrator.gerar_propostas_correcao(session_id)

        return jsonify(resultado)

    except Exception as e:
        logger.error(f"Erro na API gerar-propostas: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@ipca_correcao_bp.route('/api/aprovar-correcoes', methods=['POST'])
@require_permission(Permission.CORRECAO_PROMOTE)
def aprovar_correcoes():
    """API para aprovar correções selecionadas"""
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        corrections_approved = data.get('corrections_approved', [])

        if not session_id:
            return jsonify({'success': False, 'error': 'Session ID é obrigatório'}), 400

        proposal_mode = data.get('proposal_mode', 'COMPENSACAO')
        orchestrator = get_services()
        resultado = orchestrator.aprovar_correcoes(session_id, corrections_approved, proposal_mode)

        return jsonify(resultado)

    except Exception as e:
        logger.error(f"Erro na API aprovar-correcoes: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@ipca_correcao_bp.route('/api/aplicar-correcoes', methods=['POST'])
@require_permission(Permission.CORRECAO_CREATE)
def aplicar_correcoes():
    """API para aplicar correções aprovadas"""
    try:
        data = request.get_json()
        session_id = data.get('session_id')

        if not session_id:
            return jsonify({'success': False, 'error': 'Session ID é obrigatório'}), 400

        orchestrator = get_services()
        resultado = orchestrator.aplicar_correcoes(session_id)

        return jsonify(resultado)

    except Exception as e:
        logger.error(f"Erro na API aplicar-correcoes: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@ipca_correcao_bp.route('/api/status-sessao/<session_id>')
@require_permission(Permission.CORRECAO_CREATE)
def status_sessao(session_id):
    """API para consultar status de uma sessão"""
    try:
        orchestrator = get_services()
        resultado = orchestrator.get_session_status(session_id)

        return jsonify(resultado)

    except Exception as e:
        logger.error(f"Erro na API status-sessao: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@ipca_correcao_bp.route('/api/avaliar-ipca-vigente', methods=['POST'])
@require_permission(Permission.CORRECAO_CREATE)
def avaliar_ipca_vigente():
    """API para avaliar aplicação de IPCA do ano vigente"""
    try:
        data = request.get_json()
        cco_id = data.get('cco_id')

        user_id = get_current_user_id()

        orchestrator = get_services()
        resultado = orchestrator.avaliar_ipca_ano_vigente(cco_id, user_id)

        return jsonify(resultado)

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
