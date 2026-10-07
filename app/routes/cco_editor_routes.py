"""
Rotas para funcionalidade de edição manual de CCOs
"""

import logging
import json
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from pymongo import MongoClient

from app.models.permission import Permission
from app.services.audit_service import AuditAction
from app.services.cco_editor_service import CCOEditorService
from app.services.cco_comparator_service import CCOComparatorService
from app.config import MONGO_URI, MONGO_URI_PRD
from app.middleware.auth_middleware import audit_log, require_permission

logger = logging.getLogger(__name__)

# Criar blueprint
cco_editor_bp = Blueprint('cco_editor', __name__, url_prefix='/cco-editor')


def get_services():
    """Inicializar serviços"""
    client = MongoClient(MONGO_URI)
    db = client.sgppServices
    client_prd = MongoClient(MONGO_URI_PRD)
    db_prd = client_prd.sgppServices
    
    editor_service = CCOEditorService(db, db_prd)
    comparator_service = CCOComparatorService()
    
    return editor_service, comparator_service, db, db_prd


def json_response(data, status=200):
    """Helper para respostas JSON padronizadas"""
    response = jsonify(data)
    response.status_code = status
    return response

@cco_editor_bp.context_processor
def inject_today_date():
    return {'today_date': datetime.today().strftime('%Y-%m-%d')}

@cco_editor_bp.route('/')
@require_permission(Permission.CCO_EDIT)
def index():
    """Página principal de edição de CCOs"""
    return render_template('cco_editor/index.html', 
                         titulo="Edição Manual de CCOs")


@cco_editor_bp.route('/pesquisar')
@require_permission(Permission.CCO_EDIT)
def pesquisar():
    """Página de pesquisa de CCO para edição"""
    return render_template('cco_editor/pesquisar.html',
                         titulo="Pesquisar CCO para Edição")


@cco_editor_bp.route('/editar/<cco_id>')
@require_permission(Permission.CCO_EDIT)
@audit_log(AuditAction.EDIT_CCO, 'CCO', lambda kwargs: kwargs.get('cco_id'))
def editar_cco(cco_id):
    """Página de edição de uma CCO específica"""
    try:
        editor_service, _, _, _ = get_services()
        forcar_producao = request.args.get('forcar_producao') in ('1', 'true', 'True')
        resultado = editor_service.buscar_cco_para_edicao(cco_id, forcar_producao=forcar_producao)

        if not resultado['success']:
            # Quando a Pesquisa Rápida recebe um ID inválido, não deixa o
            # usuário preso no template genérico de erro. Retorna para a tela
            # principal da Edição Manual de CCOs com uma mensagem de aviso.
            flash(
                resultado.get('error', 'CCO não encontrada'),
                'warning'
            )
            return redirect(url_for('cco_editor.index'))

        return render_template('cco_editor/editar.html',
                             cco=resultado['cco'],
                             campos_raiz=resultado['campos_raiz'],
                             correcoes=resultado['correcoes'],
                             valores_base_retificacao=resultado['valores_base_retificacao'],
                             campos_bloqueados_raiz=resultado['campos_bloqueados_raiz'],
                             campos_bloqueados_correcao=resultado['campos_bloqueados_correcao'],
                             labels=resultado['labels'],
                             tem_rascunho_pendente=resultado['tem_rascunho_pendente'],
                             titulo=f"Editar CCO - {cco_id}")
        
    except Exception as e:
        logger.error(f"Erro ao carregar CCO para edição {cco_id}: {e}")
        return render_template('erro.html',
                             erro="Erro interno",
                             mensagem="Erro ao carregar CCO para edição.")


@cco_editor_bp.route('/revisar/<cco_id>')
@require_permission(Permission.CCO_EDIT)
def revisar_edicao(cco_id):
    """Página de revisão/comparação da edição antes de promover"""
    try:
        editor_service, comparator_service, db, db_prd = get_services()
        
        # Buscar CCO corrigida
        cco_corrigida = db.conta_custo_oleo_corrigida_entity.find_one({'_id': cco_id})
        if not cco_corrigida:
            return render_template('erro.html',
                                 erro="Edição não encontrada",
                                 mensagem="Não foi encontrada edição pendente para esta CCO.")
        
        # Buscar CCO original
        cco_original = db_prd.conta_custo_oleo_entity.find_one({'_id': cco_id})
        
        # Comparar CCOs
        comparacao = comparator_service.comparar_ccos(cco_original, cco_corrigida)
        
        # Obter sessão de edição se existir
        sessao = db.cco_edit_sessions.find_one({'cco_id': cco_id, 'status': 'PENDENTE'})
        
        return render_template('cco_editor/revisar.html',
                             cco_corrigida=_converter_tipos(cco_corrigida),
                             cco_original=_converter_tipos(cco_original) if cco_original else None,
                             comparacao=comparacao,
                             sessao=_converter_tipos(sessao) if sessao else None,
                             titulo=f"Revisar Edição - {cco_id}")
        
    except Exception as e:
        logger.error(f"Erro ao carregar revisão de edição {cco_id}: {e}")
        return render_template('erro.html',
                             erro="Erro interno",
                             mensagem="Erro ao carregar revisão da edição.")


# ========== APIs ==========

@cco_editor_bp.route('/api/pesquisar', methods=['POST'])
@require_permission(Permission.CCO_EDIT)
def api_pesquisar_cco():
    """API para pesquisar CCO por ID ou filtros"""
    try:
        dados = request.get_json()
        _, _, _, db_prd = get_services()
        
        # Construir query
        query = {}
        
        if dados.get('cco_id'):
            query['_id'] = dados['cco_id']
        else:
            if dados.get('contratoCpp'):
                query['contratoCpp'] = dados['contratoCpp']
            if dados.get('campo'):
                query['campo'] = dados['campo']
            if dados.get('remessa'):
                query['remessa'] = int(dados['remessa'])
        
        if not query:
            return json_response({'success': False, 'error': 'Informe ao menos um filtro'}, 400)
        
        # Buscar CCOs
        cursor = db_prd.conta_custo_oleo_entity.find(query)
        resultados = []
        
        for cco in cursor:
            correcoes = cco.get('correcoesMonetarias', [])
            ultima_correcao = correcoes[-1] if correcoes else cco
            
            resultados.append({
                'id': cco['_id'],
                'contratoCpp': cco.get('contratoCpp'),
                'campo': cco.get('campo'),
                'remessa': cco.get('remessa'),
                'faseRemessa': cco.get('faseRemessa'),
                'flgRecuperado': cco.get('flgRecuperado', False),
                'valorReconhecidoComOH': _converter_decimal(ultima_correcao.get('valorReconhecidoComOH', 0)),
                'totalCorrecoes': len(correcoes),
                'version': cco.get('version', 1)
            })
        
        return json_response({
            'success': True,
            'resultados': resultados,
            'total': len(resultados)
        })
        
    except Exception as e:
        logger.error(f"Erro ao pesquisar CCO: {e}")
        return json_response({'success': False, 'error': str(e)}, 500)


@cco_editor_bp.route('/api/carregar/<cco_id>')
@require_permission(Permission.CCO_EDIT)
def api_carregar_cco(cco_id):
    """API para carregar dados de uma CCO para edição"""
    try:
        editor_service, _, _, _ = get_services()
        resultado = editor_service.buscar_cco_para_edicao(cco_id)
        
        return json_response(resultado)
        
    except Exception as e:
        logger.error(f"Erro ao carregar CCO {cco_id}: {e}")
        return json_response({'success': False, 'error': str(e)}, 500)


@cco_editor_bp.route('/api/salvar', methods=['POST'])
@require_permission(Permission.CCO_EDIT)
def api_salvar_edicao():
    """API para salvar edição de CCO"""
    try:
        dados = request.get_json()
        
        cco_id = dados.get('cco_id')
        if not cco_id:
            return json_response({'success': False, 'error': 'ID da CCO é obrigatório'}, 400)
        
        alteracoes = {
            'alteracoes_raiz': dados.get('alteracoes_raiz', {}),
            'alteracoes_correcoes': dados.get('alteracoes_correcoes', []),
            'nova_correcao': dados.get('nova_correcao')
        }
        
        user_id = dados.get('user_id', 'usuario_portal')
        observacoes = dados.get('observacoes', '')
        
        editor_service, _, _, _ = get_services()
        resultado = editor_service.aplicar_edicao(cco_id, alteracoes, user_id, observacoes)
        
        return json_response(resultado)
        
    except Exception as e:
        logger.error(f"Erro ao salvar edição: {e}")
        return json_response({'success': False, 'error': str(e)}, 500)


@cco_editor_bp.route('/api/descartar-rascunho/<cco_id>', methods=['POST'])
@require_permission(Permission.CCO_EDIT)
@audit_log(AuditAction.EDIT_CCO, 'CCO', lambda kwargs: kwargs.get('cco_id'))
def api_descartar_rascunho(cco_id):
    """API para descartar o rascunho de edição pendente de uma CCO, voltando ao original de produção"""
    try:
        editor_service, _, _, _ = get_services()
        resultado = editor_service.descartar_rascunho_edicao(cco_id)
        return json_response(resultado)

    except Exception as e:
        logger.error(f"Erro ao descartar rascunho de edição da CCO {cco_id}: {e}")
        return json_response({'success': False, 'error': str(e)}, 500)


@cco_editor_bp.route('/api/preview', methods=['POST'])
@require_permission(Permission.CCO_EDIT)
def api_preview_edicao():
    """API para pré-visualizar edição sem salvar"""
    try:
        dados = request.get_json()
        
        cco_id = dados.get('cco_id')
        if not cco_id:
            return json_response({'success': False, 'error': 'ID da CCO é obrigatório'}, 400)
        
        _, comparator_service, _, db_prd = get_services()
        
        # Buscar CCO original
        cco_original = db_prd.conta_custo_oleo_entity.find_one({'_id': cco_id})
        if not cco_original:
            return json_response({'success': False, 'error': 'CCO não encontrada'}, 404)
        
        # Simular alterações
        from copy import deepcopy
        cco_simulada = deepcopy(cco_original)
        
        # Aplicar alterações simuladas na raiz
        if dados.get('alteracoes_raiz'):
            for campo, valor in dados['alteracoes_raiz'].items():
                cco_simulada[campo] = valor
        
        # Comparar
        comparacao = comparator_service.comparar_ccos(
            _converter_tipos(cco_original),
            _converter_tipos(cco_simulada)
        )
        
        return json_response({
            'success': True,
            'comparacao': comparacao
        })
        
    except Exception as e:
        logger.error(f"Erro ao gerar preview: {e}")
        return json_response({'success': False, 'error': str(e)}, 500)


@cco_editor_bp.route('/api/contratos')
@require_permission(Permission.CCO_EDIT)
def api_contratos():
    """API para listar contratos disponíveis"""
    try:
        _, _, _, db_prd = get_services()
        
        contratos = db_prd.conta_custo_oleo_entity.distinct('contratoCpp')
        contratos_ordenados = sorted([c for c in contratos if c])
        
        return json_response({
            'success': True,
            'contratos': contratos_ordenados
        })
        
    except Exception as e:
        logger.error(f"Erro ao listar contratos: {e}")
        return json_response({'success': False, 'error': str(e)}, 500)


@cco_editor_bp.route('/api/campos-por-contrato/<contrato>')
@require_permission(Permission.CCO_EDIT)
def api_campos_por_contrato(contrato):
    """API para listar campos por contrato"""
    try:
        _, _, _, db_prd = get_services()
        
        campos = db_prd.conta_custo_oleo_entity.distinct('campo', {'contratoCpp': contrato})
        campos_ordenados = sorted([c for c in campos if c])
        
        return json_response({
            'success': True,
            'campos': campos_ordenados
        })
        
    except Exception as e:
        logger.error(f"Erro ao listar campos: {e}")
        return json_response({'success': False, 'error': str(e)}, 500)


@cco_editor_bp.route('/api/edicoes-pendentes')
@require_permission(Permission.CCO_EDIT)
def api_edicoes_pendentes():
    """API para listar edições pendentes"""
    try:
        _, _, db, _ = get_services()
        
        pipeline = [
            {'$match': {'status_promocao': 'PENDENTE', 'tipo_edicao': 'MANUAL'}},
            {'$sort': {'data_criacao_correcao': -1}},
            {'$limit': 50},
            {'$project': {
                '_id': 1,
                'contratoCpp': 1,
                'campo': 1,
                'remessa': 1,
                'session_id': 1,
                'data_criacao_correcao': 1,
                'usuario_edicao': 1,
                'observacao': 1
            }}
        ]
        
        edicoes = list(db.conta_custo_oleo_corrigida_entity.aggregate(pipeline))
        
        return json_response({
            'success': True,
            'edicoes': _converter_tipos(edicoes),
            'total': len(edicoes)
        })
        
    except Exception as e:
        logger.error(f"Erro ao listar edições pendentes: {e}")
        return json_response({'success': False, 'error': str(e)}, 500)


@cco_editor_bp.route('/api/descartar/<cco_id>', methods=['DELETE'])
@require_permission(Permission.CCO_EDIT)
def api_descartar_edicao(cco_id):
    """API para descartar uma edição pendente"""
    try:
        _, _, db, _ = get_services()
        
        # Remover CCO corrigida
        resultado = db.conta_custo_oleo_corrigida_entity.delete_one({
            '_id': cco_id,
            'tipo_edicao': 'MANUAL',
            'status_promocao': 'PENDENTE'
        })
        
        if resultado.deleted_count == 0:
            return json_response({
                'success': False,
                'error': 'Edição não encontrada ou já foi promovida'
            }, 404)
        
        # Atualizar sessão
        db.cco_edit_sessions.update_one(
            {'cco_id': cco_id, 'status': 'PENDENTE'},
            {'$set': {'status': 'DESCARTADA', 'updated_at': datetime.now()}}
        )
        
        return json_response({
            'success': True,
            'message': 'Edição descartada com sucesso'
        })
        
    except Exception as e:
        logger.error(f"Erro ao descartar edição {cco_id}: {e}")
        return json_response({'success': False, 'error': str(e)}, 500)


# ========== Helpers ==========

def _converter_decimal(valor):
    """Converte Decimal128 para float"""
    from bson.decimal128 import Decimal128
    if isinstance(valor, Decimal128):
        return float(valor.to_decimal())
    return float(valor) if valor else 0


def _converter_tipos(obj):
    """Converte tipos MongoDB para JSON serializável"""
    from bson.decimal128 import Decimal128
    
    if isinstance(obj, dict):
        return {k: _converter_tipos(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_converter_tipos(item) for item in obj]
    elif isinstance(obj, Decimal128):
        return float(obj.to_decimal())
    elif hasattr(obj, 'isoformat'):
        return obj.isoformat()
    else:
        return obj