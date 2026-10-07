from flask import Flask, Blueprint, current_app, render_template, request, jsonify, redirect, session, url_for, send_file
import json
import os
from datetime import datetime, timedelta
from collections import Counter, defaultdict, deque
import pandas as pd
import re
from decimal import Decimal
import logging
from bson.decimal128 import Decimal128
from bson.objectid import ObjectId

import io
import unicodedata
from app.services.excel_export_service import gerar_excel_timeline
from app.services.cco_list_export_service import gerar_excel_lista_ccos_planificada
from app.utils.rate_limit import verificar_rate_limit_export

from app.config import MONGO_URI, MONGO_URI_PRD
from app.middleware.auth_middleware import require_permission
from app.models.permission import Permission
from app.utils.converters import processar_json_mongodb, validar_e_converter_valor_monetario, converter_decimal128_para_float, formatar_data_brasileira, formatar_data_simples
from app.utils.cache_utils import CacheManager
from app.services.portal_service import PortalService

portal_bp = Blueprint('portal_ui', __name__)

logger = logging.getLogger(__name__)

dados_analise = None
portal_service = PortalService(MONGO_URI, MONGO_URI_PRD)

@portal_bp.context_processor
def inject_today_date():
    return {'today_date': datetime.today().strftime('%Y-%m-%d')}

@portal_bp.route('/')
@require_permission(Permission.CCO_VIEW)
def index():
    """Página inicial com menu de funcionalidades"""
    current_app.logger.info("### CHEGOU NO REDIRECT FINAL ###")
    return render_template('index.html', titulo="Portal de Análises PPSA")

@portal_bp.route('/verificacao-remessas-ccos')
@require_permission(Permission.CCO_VIEW)
def verificacao_remessas_ccos():
    """Página de verificação de remessas vs CCOs (antigo index)"""
    return render_template('verificacao_remessas_ccos.html', titulo="Verificação Remessas x CCOs")

@portal_bp.route('/upload', methods=['POST'])
@require_permission(Permission.CCO_VIEW)
def upload_file():
    """Endpoint para upload do arquivo JSON"""
    global dados_analise
    
    if 'file' not in request.files:
        return jsonify({'error': 'Nenhum arquivo selecionado'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Nenhum arquivo selecionado'}), 400
    
    if file and file.filename.endswith('.json'):
        try:
            # Ler conteúdo do arquivo
            content = file.read().decode('utf-8')
            
            # Processar JSON com tipos BSON do MongoDB
            dados_analise = processar_json_mongodb(content)
            
            # Validar estrutura básica
            if 'remessasAnalisadas' not in dados_analise or 'estatisticas' not in dados_analise:
                return jsonify({'error': 'Arquivo JSON não possui estrutura esperada'}), 400
            
            return jsonify({'success': True, 'message': 'Arquivo carregado com sucesso'})
            
        except json.JSONDecodeError as e:
            return jsonify({'error': f'JSON inválido: {str(e)}'}), 400
        except ValueError as e:
            return jsonify({'error': f'Erro na conversão de tipos BSON: {str(e)}'}), 400
        except Exception as e:
            return jsonify({'error': f'Erro ao processar arquivo: {str(e)}'}), 500
    
    return jsonify({'error': 'Apenas arquivos JSON são aceitos'}), 400

# @portal_bp.route('/dashboard')
# def dashboard():
#     """Página principal do dashboard"""
#     global dados_analise
    
#     if dados_analise is None:
#         return redirect(url_for('portal_ui.index'))
    
#     # Processar dados para o dashboard
#     stats = processar_estatisticas(dados_analise)
    
#     return render_template('dashboard.html', 
#                          dados=dados_analise, 
#                          stats=stats,
#                          titulo="Dashboard - Análise Remessas x CCOs")

@portal_bp.route('/dashboard')
@require_permission(Permission.CCO_VIEW)
def dashboard():
    """Página principal do dashboard"""
    global dados_analise
    
    # Verificar se há dados da análise por filtros no cache
    cache_key = request.args.get('cache_key')
    if cache_key:
        try:
            cache_manager = CacheManager(scope='user')
            dados_cache = cache_manager.get_data(f"analise_temp_{cache_key}")
            if dados_cache:
                dados_analise = dados_cache
                # Remover do cache após uso
                cache_manager.delete_data(f"analise_temp_{cache_key}")
        except Exception as e:
            logger.error(f"Erro ao recuperar dados do cache: {e}")
    
    if dados_analise is None:
        return redirect(url_for('portal_ui.index'))
    
    # Processar dados para o dashboard
    stats = portal_service.processar_estatisticas(dados_analise)
    
    return render_template('dashboard.html', 
                         dados=dados_analise, 
                         stats=stats,
                         titulo="Dashboard - Análise Remessas x CCOs")
    

@portal_bp.route('/api/dados-grafico/<tipo>')
@require_permission(Permission.CCO_VIEW)
def dados_grafico(tipo):
    """API para fornecer dados específicos para gráficos"""
    global dados_analise
    
    if dados_analise is None:
        return jsonify({'error': 'Nenhum dado carregado'}), 400
    
    if tipo == 'fases_tempo':
        return jsonify(portal_service.gerar_dados_fases_tempo(dados_analise))
    elif tipo == 'valores_remessa':
        return jsonify(portal_service.gerar_dados_valores_remessa(dados_analise))
    elif tipo == 'distribuicao_fases':
        return jsonify(portal_service.gerar_dados_distribuicao_fases(dados_analise))
    elif tipo == 'timeline_reconhecimento':
        return jsonify(gerar_dados_timeline())
    elif tipo == 'gastos_por_fase':
        return jsonify(portal_service.gerar_dados_gastos_por_fase(dados_analise))
    elif tipo == 'gastos_consolidado':
        return jsonify(portal_service.gerar_dados_gastos_consolidado(dados_analise))
    
    return jsonify({'error': 'Tipo de gráfico não reconhecido'}), 400

def processar_estatisticas(dados):
    """Compat: delega para PortalService"""
    return portal_service.processar_estatisticas(dados)

def gerar_dados_fases_tempo():
    return portal_service.gerar_dados_fases_tempo(dados_analise)

def gerar_dados_valores_remessa():
    return portal_service.gerar_dados_valores_remessa(dados_analise)

def gerar_dados_distribuicao_fases():
    return portal_service.gerar_dados_distribuicao_fases(dados_analise)

def gerar_dados_distribuicao_gastos_por_fases():
    return portal_service.gerar_dados_distribuicao_gastos_por_fases(dados_analise)

# def gerar_dados_timeline():
#     """Gera dados para timeline de reconhecimentos"""
#     timeline = []
#     is_detalhada = dados_analise.get('tipoAnalise') == 'DETALHADA'
    
#     for remessa in dados_analise['remessasAnalisadas']:
#         for fase in remessa['fasesComReconhecimento']:
#             if fase.get('dataReconhecimento'):
#                 # Para análise detalhada, usar valores da consolidação da fase
#                 if is_detalhada and 'consolidacao' in fase:
#                     valor = fase['consolidacao']['valores']['reconhecido']
#                 else:
#                     # Para análise simplificada, usar valor da fase (se existir)
#                     valor = fase.get('valorReconhecido', 0)
                
#                 timeline.append({
#                     'data': fase['dataReconhecimento'],
#                     'remessa': remessa['remessa'],
#                     'fase': fase['fase'],
#                     'valor': valor,
#                     'exercicio': remessa['exercicio'],
#                     'periodo': remessa['periodo']
#                 })
    
#     # Ordenar por data
#     timeline.sort(key=lambda x: x['data'])
    
#     return timeline
def gerar_dados_timeline():
    """Gera dados para timeline de reconhecimentos"""
    timeline = []
    is_detalhada = dados_analise.get('tipoAnalise') == 'DETALHADA'
    
    for remessa in dados_analise['remessasAnalisadas']:
        for fase in remessa['fasesComReconhecimento']:
            if fase.get('dataReconhecimento'):
                if is_detalhada and 'consolidacao' in fase:
                    valor = fase['consolidacao']['valores']['reconhecido']
                    quantidade_itens = fase['consolidacao']['contadores']['total']
                else:
                    valor = fase.get('valorReconhecido', 0)
                    quantidade_itens = 1  # Para análise simplificada
                
                timeline.append({
                    'data': fase['dataReconhecimento'],
                    'remessa': remessa['remessa'],
                    'fase': fase['fase'],
                    'valor': valor,
                    'quantidadeItens': quantidade_itens,
                    'exercicio': remessa['exercicio'],
                    'periodo': remessa['periodo']
                })
    
    timeline.sort(key=lambda x: x['data'])
    return timeline

@portal_bp.route('/api/remessa-detalhada/<remessa_id>')
@require_permission(Permission.CCO_VIEW)
def remessa_detalhada(remessa_id):
    """API para obter detalhes completos de uma remessa"""
    global dados_analise
    
    if dados_analise is None:
        return jsonify({'error': 'Nenhum dado carregado'}), 400
    
    # Buscar remessa específica
    remessa_encontrada = None
    for remessa in dados_analise['remessasAnalisadas']:
        if remessa['id'] == remessa_id:
            remessa_encontrada = remessa
            break
    
    if not remessa_encontrada:
        return jsonify({'error': 'Remessa não encontrada'}), 404
    
    # Preparar dados detalhados
    detalhes = {
        'informacoes_basicas': {
            'id': remessa_encontrada['id'],
            'remessa': remessa_encontrada['remessa'],
            'contratoCPP': remessa_encontrada['contratoCPP'],
            'campo': remessa_encontrada['campo'],
            'exercicio': remessa_encontrada['exercicio'],
            'periodo': remessa_encontrada['periodo'],
            'mesAnoReferencia': remessa_encontrada['mesAnoReferencia'],
            'faseRemessaAtual': remessa_encontrada['faseRemessaAtual'],
            'origemDoGasto': remessa_encontrada['origemDoGasto'],
            'gastosCompartilhados': remessa_encontrada['gastosCompartilhados'],
            'fatorAlocacao':   remessa_encontrada.get('fatorAlocacao', 'INDEFINIDO'),
            'version': remessa_encontrada.get('version', 0)
        },
        'fases': [],
        'consolidacao_remessa': remessa_encontrada.get('consolidacaoRemessa'),
        'resumo_ccos': {
            'total_ccos': len(remessa_encontrada['fasesComReconhecimento']),
            'ccos_encontradas': 0,
            'valor_total_ccos': 0,
            'overhead_total': 0,
            'correcoes_monetarias_total': 0
        }
    }
    
    # Processar fases
    for fase in remessa_encontrada['fasesComReconhecimento']:
        fase_detalhada = {
            'fase': fase['fase'],
            'faseOriginal': fase['faseOriginal'],
            'dataReconhecimento': fase.get('dataReconhecimento'),
            'dataLancamento': fase.get('dataLancamento'),
            'consolidacao': fase.get('consolidacao'),
            'cco': None
        }
        
        # Processar CCO se existir
        if fase.get('cco') and fase['cco'].get('statusCCO') == 'ENCONTRADA':
            detalhes['resumo_ccos']['ccos_encontradas'] += 1
            
            cco_data = fase['cco']
            fase_detalhada['cco'] = {
                'id': cco_data.get('id'),
                'statusCCO': cco_data.get('statusCCO'),
                'informacoes_basicas': {
                    'contratoCpp': cco_data.get('contratoCpp'),
                    'campo': cco_data.get('campo'),
                    'remessa': cco_data.get('remessa'),
                    'faseRemessa': cco_data.get('faseRemessa'),
                    'exercicio': cco_data.get('exercicio'),
                    'periodo': cco_data.get('periodo')
                },
                'valores_atuais': extrair_valores_cco(cco_data),
                'correcao_monetaria': {
                    'tipo': cco_data.get('tipo'),
                    'subTipo': cco_data.get('subTipo'),
                    'dataCorrecao': cco_data.get('dataCorrecao'),
                    'taxaCorrecao': validar_e_converter_valor_monetario(cco_data.get('taxaCorrecao', 0)),
                    'igpmAcumulado': validar_e_converter_valor_monetario(cco_data.get('igpmAcumulado', 0)),
                    'diferencaValor': validar_e_converter_valor_monetario(cco_data.get('diferencaValor', 0))
                },
                'datas': {
                    'dataReconhecimento': cco_data.get('dataReconhecimento'),
                    'dataLancamento': cco_data.get('dataLancamento'),
                    'dataCorrecao': cco_data.get('dataCorrecao')
                }
            }
            
            # Atualizar resumo
            valores = fase_detalhada['cco']['valores_atuais']
            detalhes['resumo_ccos']['valor_total_ccos'] += valores.get('valorReconhecidoComOH', 0)
            detalhes['resumo_ccos']['overhead_total'] += valores.get('overHeadTotal', 0)
            detalhes['resumo_ccos']['correcoes_monetarias_total'] += validar_e_converter_valor_monetario(cco_data.get('diferencaValor', 0))
        
        detalhes['fases'].append(fase_detalhada)
    
    return jsonify(detalhes)

@portal_bp.route('/api/cco-detalhada/<cco_id>')
@require_permission(Permission.CCO_VIEW)
def cco_detalhada(cco_id):
    """API para obter detalhes completos de uma CCO"""
    global dados_analise
    
    if dados_analise is None:
        return jsonify({'error': 'Nenhum dado carregado'}), 400
    
    # Buscar CCO específica
    cco_encontrada = None
    remessa_origem = None
    fase_origem = None
    
    for remessa in dados_analise['remessasAnalisadas']:
        for fase in remessa['fasesComReconhecimento']:
            if fase.get('cco') and fase['cco'].get('id') == cco_id:
                cco_encontrada = fase['cco']
                remessa_origem = remessa
                fase_origem = fase
                break
        if cco_encontrada:
            break
    
    if not cco_encontrada:
        return jsonify({'error': 'CCO não encontrada'}), 404
    
    # Preparar dados detalhados da CCO
    detalhes = {
        'informacoes_basicas': {
            'id': cco_encontrada.get('id'),
            'contratoCpp': cco_encontrada.get('contratoCpp') or cco_encontrada.get('contrato') or remessa_origem['contratoCPP'],
            'campo': cco_encontrada.get('campo') or remessa_origem['campo'],
            'remessa': cco_encontrada.get('remessa') or remessa_origem['remessa'],
            'faseRemessa': cco_encontrada.get('faseRemessa'),
            'exercicio': cco_encontrada.get('exercicio') or remessa_origem['exercicio'],
            'periodo': cco_encontrada.get('periodo') or remessa_origem['periodo'],
            'statusCCO': cco_encontrada.get('statusCCO')
        },
        'valores_originais': portal_service.extrair_valores_originais_cco(cco_encontrada),
        'valores_atuais': portal_service.extrair_valores_cco(cco_encontrada),
        'correcao_monetaria': {
            'aplicada': bool(cco_encontrada.get('tipo')),
            'tipo': cco_encontrada.get('tipo'),
            'subTipo': cco_encontrada.get('subTipo'),
            'dataCorrecao': cco_encontrada.get('dataCorrecao'),
            'dataCriacaoCorrecao': cco_encontrada.get('dataCriacaoCorrecao'),
            'taxaCorrecao': validar_e_converter_valor_monetario(cco_encontrada.get('taxaCorrecao', 0)),
            'igpmAcumulado': validar_e_converter_valor_monetario(cco_encontrada.get('igpmAcumulado', 0)),
            'igpmAcumuladoReais': validar_e_converter_valor_monetario(cco_encontrada.get('igpmAcumuladoReais', 0)),
            'diferencaValor': validar_e_converter_valor_monetario(cco_encontrada.get('diferencaValor', 0)),
            'ativo': cco_encontrada.get('ativo', False)
        },
        'datas': {
            'dataReconhecimento': cco_encontrada.get('dataReconhecimento'),
            'dataLancamento': cco_encontrada.get('dataLancamento'),
            'dataCorrecao': cco_encontrada.get('dataCorrecao'),
            'dataCriacaoCorrecao': cco_encontrada.get('dataCriacaoCorrecao')
        },
        'contexto_remessa': {
            'remessaId': remessa_origem['id'],
            'remessaNumero': remessa_origem['remessa'],
            'exercicio': remessa_origem['exercicio'],
            'periodo': remessa_origem['periodo'],
            'mesAnoReferencia': remessa_origem['mesAnoReferencia'],
            'fase': fase_origem['fase'],
            'consolidacao_fase': fase_origem.get('consolidacao')
        },
        'transferencia': cco_encontrada.get('transferencia', ''),
        'observacoes': cco_encontrada.get('observacao', '')
    }
    
    return jsonify(detalhes)

def extrair_valores_cco(cco_data):
    # Compatibilidade: delega para o serviço
    return portal_service.extrair_valores_cco(cco_data)

def extrair_valores_originais_cco(cco_data):
    # Compatibilidade: delega para o serviço
    return portal_service.extrair_valores_originais_cco(cco_data)

@portal_bp.route('/api/remessas-detalhadas')
@require_permission(Permission.CCO_VIEW)
def remessas_detalhadas():
    """API para tabela detalhada de remessas"""
    global dados_analise
    if dados_analise is None:
        return jsonify({'error': 'Nenhum dado carregado'}), 400
    detalhes = portal_service.remessas_detalhadas_list(dados_analise)
    return jsonify(detalhes)

# def extrair_top_classificacoes(classificacoes, top=3):
#     """Extrai as top classificações para exibição"""
#     if not classificacoes:
#         return ''
    
#     sorted_class = sorted(classificacoes.items(), key=lambda x: x[1], reverse=True)[:top]
#     return ', '.join([f"{k}({v})" for k, v in sorted_class])

# def extrair_top_responsaveis(responsaveis, top=3):
#     """Extrai os top responsáveis para exibição"""
#     if not responsaveis:
#         return ''
    
#     sorted_resp = sorted(responsaveis.items(), key=lambda x: x[1], reverse=True)[:top]
#     return ', '.join([f"{k}({v})" for k, v in sorted_resp])

def extrair_top_classificacoes(classificacoes, top=3):
    """Extrai as top classificações para exibição em formato CSV-friendly"""
    if not classificacoes:
        return ''
    
    sorted_class = sorted(classificacoes.items(), key=lambda x: x[1], reverse=True)[:top]
    # Usar formato mais simples sem parênteses problemáticos
    return ' | '.join([f"{k}:{v}" for k, v in sorted_class])

def extrair_top_responsaveis(responsaveis, top=3):
    """Extrai os top responsáveis para exibição em formato CSV-friendly"""
    if not responsaveis:
        return ''
    
    sorted_resp = sorted(responsaveis.items(), key=lambda x: x[1], reverse=True)[:top]
    # Usar formato mais simples sem parênteses problemáticos
    return ' | '.join([f"{k}:{v}" for k, v in sorted_resp])

@portal_bp.route('/cco-timeline/<cco_id>')
@require_permission(Permission.CCO_VIEW)
def cco_timeline(cco_id):
    """Página de timeline completa da CCO"""
    # try:
    # Buscar CCO completa no MongoDB via serviço
    cco_completa = portal_service._get_db_prd().conta_custo_oleo_entity.find_one({"_id": cco_id})
    
    if not cco_completa:
        return render_template('erro.html', 
                                erro="CCO não encontrada", 
                                mensagem=f"CCO com ID {cco_id} não foi encontrada no banco de dados.")
    
    # Processar timeline
    timeline_data = portal_service.processar_timeline_cco(cco_completa)
    
    # Extrair valores atuais (última correção ou valores da raiz)
    valores_atuais = portal_service.extrair_valores_atuais_cco(cco_completa)
    
    return render_template('cco_timeline.html', 
                            cco=cco_completa,
                            timeline=timeline_data,
                            valores_atuais=valores_atuais,
                            cco_json=json.dumps(cco_completa, indent=2, default=str),
                            titulo=f"Timeline CCO - {cco_id}")
                             
    # except Exception as e:
    #     logger.error(f"Erro ao carregar timeline da CCO {cco_id}: {e}")
    #     return render_template('erro.html', 
    #                          erro="Erro interno", 
    #                          mensagem="Erro ao carregar dados da CCO.")

@portal_bp.route('/api/cco-timeline/<cco_id>')
@require_permission(Permission.CCO_VIEW)
def api_cco_timeline(cco_id):
    """
    API para retornar timeline da CCO com filtro opcional por data de corte.
    
    Query parameters:
        data_corte (opcional): Data limite em formato YYYY-MM-DD
        
    Response:
        {
            "estado_temporal": boolean,
            "cco_id": string,
            "data_corte": string (null se não fornecido),
            "eventos": array,
            "valores_em_data_corte": object,
            "erro": string (se houver erro)
        }
    """
    try:
        data_corte = request.args.get('data_corte', None)
        
        # Validar formato de data se fornecido
        if data_corte:
            try:
                datetime.strptime(data_corte, '%Y-%m-%d')
            except ValueError:
                return jsonify({
                    'erro': 'Formato de data inválido',
                    'mensagem': 'Use formato YYYY-MM-DD (ex: 2024-12-31)',
                    'data_fornecida': data_corte
                }), 400
        
        # Chamar serviço para processar timeline com cutoff
        resultado = portal_service.get_timeline_with_cutoff(cco_id, data_corte)
        
        # Se houve erro na busca
        if 'erro' in resultado:
            return jsonify(resultado), 404
        
        return jsonify(resultado), 200
        
    except ValueError as ve:
        return jsonify({
            'erro': 'Erro na validação',
            'mensagem': str(ve)
        }), 400
    except Exception as e:
        logger.error(f"Erro ao processar timeline da CCO {cco_id}: {e}")
        return jsonify({
            'erro': 'Erro interno',
            'mensagem': f'Erro ao processar timeline: {str(e)}'
        }), 500
   

def extrair_valores_atuais_cco(cco_data):
    # Compatibilidade: delega para o serviço
    return portal_service.extrair_valores_atuais_cco(cco_data)

def processar_timeline_cco(cco_data):
    # Compatibilidade: delega para o serviço
    return portal_service.processar_timeline_cco(cco_data)

def processar_evento_correcao(correcao, sequencia):
    # Compatibilidade: delega para o serviço
    return portal_service.processar_evento_correcao(correcao, sequencia)

def gerar_descricao_evento(tipo, correcao):
    # Compatibilidade: delega para o serviço
    return portal_service.gerar_descricao_evento(tipo, correcao)
 
@portal_bp.route('/pesquisa-ccos')
@require_permission(Permission.CCO_VIEW)
def pesquisa_ccos():
    """Página de pesquisa de CCOs"""
    return render_template('pesquisa_ccos.html', titulo="Pesquisa de CCOs")

@portal_bp.route('/api/pesquisar-ccos', methods=['POST'])
@require_permission(Permission.CCO_VIEW)
def api_pesquisar_ccos():
    """API para pesquisar CCOs por filtros"""
    try:
        dados = request.get_json()
        
        # Validar se contratoCPP está presente (obrigatório)
        if not dados.get('contratoCpp') and not dados.get('id'):
            return jsonify({'error': 'Filtros de pesquisa inválidos'}), 400
        
        # Construir filtro MongoDB usando a mesma regra da exportação.
        # Regra de fase:
        # - MEN/ROP/RAD/REC: pesquisa em faseRemessa ou faseRespostaGestora,
        #   sem trazer registros cuja faseRespostaGestora inicie com REV ou ABCR.
        # - REV/ABCR: pesquisa em faseRespostaGestora por prefixo, ignorando o número final
        #   (REV1, REV2, ABCR1, ABCR2 etc.).
        filtro_mongo = montar_filtros_pesquisa_ccos(dados)
        
        resultados = portal_service.pesquisar_ccos(filtro_mongo)
        
        return jsonify({
            'success': True,
            'resultados': resultados,
            'total': len(resultados),
            'filtro_aplicado': filtro_mongo
        })
        
    except Exception as e:
        logger.error(f"Erro ao pesquisar CCOs: {e}")
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500

def extrair_valores_resumidos_cco(cco_data):
    # Compatibilidade: delega para o serviço
    return portal_service.extrair_valores_resumidos_cco(cco_data)

@portal_bp.route('/api/contratos-disponiveis')
@require_permission(Permission.CCO_VIEW)
def api_contratos_disponiveis():
    """API para listar contratos disponíveis"""
    try:
        contratos = portal_service.listar_contratos()
        return jsonify({'contratos': contratos})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@portal_bp.route('/api/campos-por-contrato/<contrato>')
@require_permission(Permission.CCO_VIEW)
def api_campos_por_contrato(contrato):
    """API para listar campos por contrato"""
    try:
        campos = portal_service.listar_campos_por_contrato(contrato)
        return jsonify({'campos': campos})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@portal_bp.route('/api/fases-ccos-disponiveis')
@require_permission(Permission.CCO_VIEW)
def api_fases_ccos_disponiveis():
    """API para listar fases disponíveis na pesquisa de CCOs.

    A lista é carregada via distinct nos campos faseRemessa e faseRespostaGestora,
    evitando manutenção manual do select quando novas fases surgirem no banco.
    """
    try:
        fases = portal_service.listar_fases_disponiveis()
        return jsonify({'fases': fases})
    except Exception as e:
        logger.error(f"Erro ao listar fases disponíveis: {e}")
        return jsonify({'error': str(e)}), 500

def _adicionar_condicao_and(filtro_mongo: dict, condicao: dict) -> None:
    """Adiciona uma condição ao $and preservando os demais filtros."""
    if '$and' not in filtro_mongo:
        filtro_mongo['$and'] = []
    filtro_mongo['$and'].append(condicao)


def normalizar_fase_pesquisa_cco(fase: str) -> str:
    """Normaliza fase selecionada no filtro sem remover numeração sequencial."""
    return (fase or '').strip().upper()


def valores_fase_remessa_para_pesquisa(fase: str) -> list:
    """Retorna valores de faseRemessa equivalentes ao valor exibido no filtro.

    Regra específica:
    - quando o usuário seleciona AUD, também pesquisar FISC em faseRemessa,
      pois FISC deve aparecer como AUD no filtro.
    """
    fase_normalizada = normalizar_fase_pesquisa_cco(fase)

    if not fase_normalizada:
        return []

    if fase_normalizada == 'AUD':
        return ['AUD', 'FISC']

    return [fase_normalizada]


def aplicar_filtro_fase_pesquisa_cco(filtro_mongo: dict, fase: str) -> None:
    """Aplica filtro dinâmico de fase na pesquisa/exportação de CCOs.

    A fase selecionada é pesquisada em:
    - faseRemessa, por igualdade;
    - faseRespostaGestora, por igualdade.

    As fases sequenciais não são agrupadas. Selecionar ABCR1 filtra ABCR1;
    selecionar ABCR2 filtra ABCR2; selecionar REV1 filtra REV1 etc.

    Exceção:
    - selecionar AUD também considera faseRemessa FISC.
    """
    fase_normalizada = normalizar_fase_pesquisa_cco(fase)

    if not fase_normalizada:
        return

    _adicionar_condicao_and(filtro_mongo, {
        '$or': [
            {'faseRemessa': {'$in': valores_fase_remessa_para_pesquisa(fase_normalizada)}},
            {'faseRespostaGestora': fase_normalizada}
        ]
    })


def montar_filtros_pesquisa_ccos(dados):
    """
    Monta o filtro MongoDB usado pela pesquisa/exportação de CCOs.

    Esta função foi criada para reaproveitar na exportação em lote a mesma lógica
    de filtros usada na tela de pesquisa, sem alterar a rota já existente de busca.
    """
    dados = dados or {}
    filtro_mongo = {}

    if dados.get('id'):
        filtro_mongo['_id'] = dados['id']
        return filtro_mongo

    if dados.get('contratoCpp'):
        filtro_mongo['contratoCpp'] = dados['contratoCpp']
    if dados.get('campo'):
        filtro_mongo['campo'] = dados['campo']
    if dados.get('remessa'):
        filtro_mongo['remessa'] = int(dados['remessa'])
    if dados.get('faseRemessa'):
        aplicar_filtro_fase_pesquisa_cco(filtro_mongo, dados['faseRemessa'])
    if dados.get('origemDosGastos'):
        filtro_mongo['origemDosGastos'] = dados['origemDosGastos']
    if dados.get('exercicio'):
        filtro_mongo['exercicio'] = int(dados['exercicio'])
    if dados.get('periodo'):
        filtro_mongo['periodo'] = int(dados['periodo'])
    if dados.get('flgRecuperado') is not None:
        filtro_mongo['flgRecuperado'] = dados['flgRecuperado']

    return filtro_mongo

@portal_bp.route("/api/ccos/export", methods=["POST"])
@require_permission(Permission.CCO_VIEW)
def exportar_lista_ccos():
    """
    Exporta todas as CCOs retornadas pelos filtros da tela de pesquisa.

    Diferente da exportação da timeline individual, este endpoint gera um único
    arquivo Excel planificado contendo:
        - uma linha PRINCIPAL para cada CCO;
        - uma linha CORRECAO_N para cada correção monetária da CCO.
    """
    try:
        filtros_request = request.get_json() or {}

        if not filtros_request.get('contratoCpp') and not filtros_request.get('id'):
            return jsonify({
                "error": "Filtros de exportação inválidos",
                "mensagem": "Informe ao menos o ID da CCO ou o Contrato CPP."
            }), 400

        filtros = montar_filtros_pesquisa_ccos(filtros_request)

        db = portal_service._get_db_prd()
        cursor = (
            db.conta_custo_oleo_entity
            .find(filtros)
            .sort([("dataReconhecimento", 1), ("_id", 1)])
            .limit(5000)
        )
        ccos = list(cursor)

        if not ccos:
            return jsonify({
                "error": "Nenhuma CCO encontrada para exportação"
            }), 404

        workbook = gerar_excel_lista_ccos_planificada(ccos)

        output = io.BytesIO()
        workbook.save(output)
        output.seek(0)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"CCOs_Planificadas_{timestamp}.xlsx"

        return send_file(
            output,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        logger.error(f"Erro ao exportar lista de CCOs: {e}")
        return jsonify({
            "error": "Erro interno ao exportar lista de CCOs",
            "mensagem": str(e)
        }), 500

@portal_bp.route("/api/cco-timeline/<cco_id>/export")
@require_permission(Permission.CCO_VIEW)
def export_timeline_xls(cco_id):
    formato = request.args.get("format", "xlsx")
    data_corte = request.args.get("data_corte")

    if formato != "xlsx":
        return jsonify({
            "error": "Formato não suportado",
            "formatos_suportados": ["xlsx"]
        }), 400

    # Rate limit: máximo de 10 exportações por minuto por IP
    ip_cliente = request.remote_addr or "unknown"

    if not verificar_rate_limit_export(ip_cliente, limite=10, janela_segundos=60):
        return jsonify({
            "error": "Limite de exportações excedido",
            "mensagem": "Máximo de 10 exportações por minuto. Tente novamente em instantes."
        }), 429

    try:
        if data_corte:
            try:
                datetime.strptime(data_corte, "%Y-%m-%d")
            except ValueError:
                return jsonify({
                    "error": "Formato de data inválido",
                    "mensagem": "Use o formato YYYY-MM-DD. Exemplo: 2024-12-31",
                    "data_fornecida": data_corte
                }), 400

        cco = portal_service._get_db_prd().conta_custo_oleo_entity.find_one({"_id": cco_id})

        if not cco:
            return jsonify({
                "error": "CCO não encontrada",
                "cco_id": cco_id
            }), 404

        timeline_resultado = portal_service.get_timeline_with_cutoff(cco_id, data_corte)

        if timeline_resultado.get("erro"):
            return jsonify(timeline_resultado), 404

        eventos = timeline_resultado.get("eventos", [])

        if len(eventos) > 1000:
            return jsonify({
                "error": "Timeline muito grande para exportação",
                "mensagem": "O limite máximo é de 1000 eventos.",
                "total_eventos": len(eventos)
            }), 400

        excel_file = gerar_excel_timeline(cco, timeline_resultado, data_corte)

        output = io.BytesIO()
        excel_file.save(output)
        output.seek(0)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = _montar_nome_arquivo_timeline(cco, timestamp)

        return send_file(
            output,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        logger.error(f"Erro ao exportar timeline da CCO {cco_id}: {e}")
        return jsonify({
            "error": "Erro interno ao exportar timeline",
            "mensagem": str(e)
        }), 500

def _normalizar_nome_arquivo(valor, padrao="NA"):
    """
    Normaliza um valor para uso seguro no nome do arquivo.

    Exemplos:
        "GASTO EXCLUSIVO" -> "GASTO_EXCLUSIVO"
        "MEN/ROP" -> "MEN_ROP"
        None -> "NA"
    """
    if valor is None or str(valor).strip() == "":
        return padrao

    texto = str(valor).strip()
    texto = unicodedata.normalize("NFKD", texto)
    texto = texto.encode("ASCII", "ignore").decode("ASCII")
    texto = re.sub(r"[^A-Za-z0-9_-]+", "_", texto)
    texto = re.sub(r"_+", "_", texto).strip("_")

    return texto or padrao


def _montar_nome_arquivo_timeline(cco, timestamp):
    """
    Monta o nome do arquivo sem usar o ID da CCO.

    Campos usados:
        Campo
        Remessa
        Fase
        Ano/Mês Reconhecimento
        Período
        Origem
    """
    campo = _normalizar_nome_arquivo(cco.get("campo"))
    remessa = _normalizar_nome_arquivo(cco.get("remessa"))
    fase = _normalizar_nome_arquivo(cco.get("faseRemessa"))

    ano = _normalizar_nome_arquivo(cco.get("anoReconhecimento"))

    mes_raw = cco.get("mesReconhecimento")
    try:
        mes = f"{int(mes_raw):02d}"
    except (TypeError, ValueError):
        mes = _normalizar_nome_arquivo(mes_raw)

    periodo = _normalizar_nome_arquivo(cco.get("periodo"))
    origem = _normalizar_nome_arquivo(cco.get("origemDosGastos"))

    # return (
    #     f"Timeline_CCO_"
    #     f"Campo_{campo}_"
    #     f"Remessa_{remessa}_"
    #     f"Fase_{fase}_"
    #     f"Rec_{ano}-{mes}_"
    #     f"Periodo_{periodo}_"
    #     f"Origem_{origem}_"
    #     f"{timestamp}.xlsx"
    # )

    return (
        f"Timeline_CCO_"
        f"{campo}_"
        f"{remessa}_"
        f"{fase}_"
        f"{ano}-{mes}_"
        f"{periodo}.xlsx"
    )
