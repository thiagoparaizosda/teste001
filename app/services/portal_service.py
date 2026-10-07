"""
Serviço/Helper para lógicas da camada de portal (dashboard, gráficos e CCO).
Extraído de app/routes/portal_ui.py para reduzir acoplamento e facilitar testes.
"""

import json
import logging
import re
from collections import Counter, defaultdict
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pymongo import MongoClient

from app.config import PESQUISA_AMBINTE_PRODUCAO
from app.utils.converters import (
    validar_e_converter_valor_monetario,
    converter_decimal128_para_float,
    formatar_data_brasileira,
    formatar_data_simples,
)

logger = logging.getLogger(__name__)


class PortalService:
    def __init__(self, mongo_uri: str, mongo_uri_prd: str = None):
        self.mongo_uri = mongo_uri
        self._client: Optional[MongoClient] = None
        self._db = None

        self.mongo_uri_prd = mongo_uri_prd
        self._client_prd: Optional[MongoClient] = None
        self._db_prd = None

    # --- Infra Mongo ---
    def _get_db(self):
        
        if PESQUISA_AMBINTE_PRODUCAO:
            return self._get_db_prd()
        
        if self._db is None:
            self._client = MongoClient(self.mongo_uri)
            self._db = self._client.sgppServices
        return self._db
    
    def _get_db_prd(self):
        if self._db_prd is None:
            self._client_prd = MongoClient(self.mongo_uri_prd)
            self._db_prd = self._client_prd.sgppServices
        return self._db_prd
    
    # --- Dashboard e estatísticas ---
    @staticmethod
    def processar_estatisticas(dados: Dict[str, Any]) -> Dict[str, Any]:
        remessas = dados['remessasAnalisadas']
        is_detalhada = dados.get('tipoAnalise') == 'DETALHADA'

        stats = {
            'tipoAnalise': dados.get('tipoAnalise', 'SIMPLIFICADA'),
            'resumo_geral': {
                'total_remessas': len(remessas),
                'total_fases': sum(len(r['fasesComReconhecimento']) for r in remessas),
                'ccos_encontradas': int(dados['estatisticas'].get('totalCCOsEncontradas', 0)),
                'ccos_nao_encontradas': int(dados['estatisticas'].get('totalCCOsNaoEncontradas', 0)),
                'fases_com_ccos_duplicadas': int(dados['estatisticas'].get('totalCCOsDuplicadas', 0)),
            },
            'por_exercicio': defaultdict(lambda: {'remessas': 0, 'fases': 0, 'valor_total': 0}),
            'por_fase': defaultdict(int),
            'valores': {
                'total_reconhecido_remessas': 0,
                'total_reconhecido_ccos': 0,
                'maior_valor_remessa': 0,
                'menor_valor_remessa': float('inf'),
                'total_overhead': 0,
                'total_correcoes_monetarias': 0
            },
            'datas': {
                'primeira_remessa': None,
                'ultima_remessa': None,
                'tempo_medio_reconhecimento': 0
            },
            'consolidacao_detalhada': {}
        }

        if is_detalhada and 'consolidacaoGeral' in dados.get('estatisticas', {}):
            stats['consolidacao_detalhada'] = dados['estatisticas']['consolidacaoGeral']
            stats['consolidacao_detalhada']['totalGastos'] = int(
                dados['estatisticas']['consolidacaoGeral'].get('contadores', {}).get('total', 0)
            )

        datas_reconhecimento = []
        valores_remessa = []

        for remessa in remessas:
            exercicio = int(remessa['exercicio'])
            stats['por_exercicio'][exercicio]['remessas'] += 1
            stats['por_exercicio'][exercicio]['fases'] += len(remessa['fasesComReconhecimento'])

            valor_remessa = 0
            if is_detalhada and 'consolidacaoRemessa' in remessa:
                valor_remessa = remessa['consolidacaoRemessa']['valores']['reconhecido']

            for fase in remessa['fasesComReconhecimento']:
                stats['por_fase'][fase['fase']] += 1

                if not is_detalhada and 'valorReconhecido' in fase:
                    valor_remessa += fase.get('valorReconhecido', 0)

                if is_detalhada and 'consolidacao' in fase:
                    valor_fase = fase['consolidacao']['valores']['reconhecido']
                    stats['valores']['total_reconhecido_remessas'] += valor_fase

                if fase.get('dataReconhecimento'):
                    try:
                        data = datetime.fromisoformat(fase['dataReconhecimento'].replace('Z', '+00:00'))
                        datas_reconhecimento.append(data)
                    except Exception:
                        pass

                if fase.get('cco') and fase['cco'].get('statusCCO') == 'ENCONTRADA':
                    try:
                        if 'valorReconhecido' in fase['cco']:
                            valor_cco = validar_e_converter_valor_monetario(fase['cco']['valorReconhecido'])
                            stats['valores']['total_reconhecido_ccos'] += valor_cco
                        if 'overHeadTotal' in fase['cco']:
                            overhead = validar_e_converter_valor_monetario(fase['cco']['overHeadTotal'])
                            stats['valores']['total_overhead'] += overhead
                        if 'igpmAcumuladoReais' in fase['cco']:
                            correcao = validar_e_converter_valor_monetario(fase['cco']['igpmAcumuladoReais'])
                            stats['valores']['total_correcoes_monetarias'] += correcao
                    except Exception as ex:
                        logger.warning(f"Erro ao processar valores CCO: {ex}")

            if valor_remessa > 0:
                valores_remessa.append(valor_remessa)
                stats['por_exercicio'][exercicio]['valor_total'] += valor_remessa

        if valores_remessa:
            stats['valores']['maior_valor_remessa'] = max(valores_remessa)
            stats['valores']['menor_valor_remessa'] = min(valores_remessa)
        else:
            stats['valores']['menor_valor_remessa'] = 0

        if datas_reconhecimento:
            datas_normalizadas = []
            for data in datas_reconhecimento:
                if hasattr(data, 'replace') and getattr(data, 'tzinfo', None):
                    datas_normalizadas.append(data.replace(tzinfo=None))
                else:
                    datas_normalizadas.append(data)
            datas_normalizadas.sort()
            stats['datas']['primeira_remessa'] = datas_normalizadas[0].strftime('%d/%m/%Y')
            stats['datas']['ultima_remessa'] = datas_normalizadas[-1].strftime('%d/%m/%Y')
            if len(datas_normalizadas) > 1:
                diferenca_total = (datas_normalizadas[-1] - datas_normalizadas[0]).days
                stats['datas']['tempo_medio_reconhecimento'] = diferenca_total / len(datas_normalizadas)

        stats['por_exercicio'] = dict(stats['por_exercicio'])
        stats['por_fase'] = dict(stats['por_fase'])
        return stats

    @staticmethod
    def gerar_dados_fases_tempo(dados_analise: Dict[str, Any]) -> List[Dict[str, Any]]:
        dados = []
        for remessa in dados_analise['remessasAnalisadas']:
            for fase in remessa['fasesComReconhecimento']:
                if fase.get('dataReconhecimento'):
                    try:
                        data = datetime.fromisoformat(fase['dataReconhecimento'].replace('Z', '+00:00'))
                        dados.append({
                            'data': data.strftime('%Y-%m'),
                            'fase': fase['fase'],
                            'remessa': remessa['remessa'],
                            'valor': fase.get('valorReconhecido', 0)
                        })
                    except Exception:
                        pass
        return dados

    @staticmethod
    def gerar_dados_valores_remessa(dados_analise: Dict[str, Any]) -> List[Dict[str, Any]]:
        dados = []
        is_detalhada = dados_analise.get('tipoAnalise') == 'DETALHADA'
        for remessa in dados_analise['remessasAnalisadas']:
            if is_detalhada and 'consolidacaoRemessa' in remessa:
                consolidacao = remessa['consolidacaoRemessa']['valores']
                dados.append({
                    'remessa': remessa['remessa'],
                    'exercicio': remessa['exercicio'],
                    'periodo': remessa['periodo'],
                    'valorReconhecido': consolidacao['reconhecido'],
                    'valorLancamentoTotal': consolidacao['lancamentoTotal'],
                    'valorNaoReconhecido': consolidacao['naoReconhecido'],
                    'valorRecusado': consolidacao['recusado'],
                    'valorNaoPassivelReconhecimento': consolidacao['naoPassivelReconhecimento'],
                    'fases': len(remessa['fasesComReconhecimento'])
                })
            else:
                valor_total = sum(fase.get('valorReconhecido', 0) for fase in remessa['fasesComReconhecimento'])
                dados.append({
                    'remessa': remessa['remessa'],
                    'exercicio': remessa['exercicio'],
                    'periodo': remessa['periodo'],
                    'valorReconhecido': valor_total,
                    'valorLancamentoTotal': valor_total,
                    'valorNaoReconhecido': 0,
                    'valorRecusado': 0,
                    'valorNaoPassivelReconhecimento': 0,
                    'fases': len(remessa['fasesComReconhecimento'])
                })
        return dados

    @staticmethod
    def gerar_dados_distribuicao_fases(dados_analise: Dict[str, Any]) -> List[Dict[str, Any]]:
        contadores = Counter()
        for remessa in dados_analise['remessasAnalisadas']:
            for fase in remessa['fasesComReconhecimento']:
                contadores[fase['fase']] += 1
        return [{'fase': fase, 'count': count} for fase, count in contadores.items()]

    @staticmethod
    def gerar_dados_gastos_por_fase(dados_analise: Dict[str, Any]) -> Dict[str, Any]:
        """Gera dados de gastos consolidados por fase"""
        dados_fases = {}
        
        for remessa in dados_analise['remessasAnalisadas']:
            for fase in remessa.get('fasesComReconhecimento', []):
                fase_nome = fase['fase']
                
                if fase_nome not in dados_fases:
                    dados_fases[fase_nome] = {
                        'contadores': {
                            'total': 0,
                            'reconhecido': 0,
                            'recAutomatico': 0,
                            'naoReconhecido': 0,
                            'recusados': 0
                        },
                        'valores': {
                            'lancamentoTotal': 0,
                            'reconhecido': 0,
                            'naoReconhecido': 0,
                            'recusado': 0
                        }
                    }
                
                # Consolidar contadores
                if 'consolidacao' in fase:
                    for key, value in fase['consolidacao']['contadores'].items():
                        if key in dados_fases[fase_nome]['contadores']:
                            dados_fases[fase_nome]['contadores'][key] += value
                    
                    # Consolidar valores
                    for key, value in fase['consolidacao']['valores'].items():
                        if key in dados_fases[fase_nome]['valores']:
                            dados_fases[fase_nome]['valores'][key] += value
        
        return dados_fases

    @staticmethod
    def gerar_dados_gastos_consolidado(dados_analise: Dict[str, Any]) -> Dict[str, Any]:
        """Gera dados de gastos consolidados de todas as fases"""
        if 'consolidacaoGeral' in dados_analise.get('estatisticas', {}):
            consolidacao = dados_analise['estatisticas']['consolidacaoGeral']
            return {
                'contadores': consolidacao.get('contadores', {}),
                'valores': consolidacao.get('valores', {})
            }
        
        return {
            'contadores': {},
            'valores': {}
        }

    @staticmethod
    def eh_analise_remessa_unica(dados_analise: Dict[str, Any]) -> bool:
        """Verifica se é análise de remessa única"""
        return dados_analise.get('estatisticas', {}).get('totalRemessas', 0) == 1

    # --- CCO Details / Timeline ---
    @staticmethod
    def extrair_valores_cco(cco_data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            'quantidadeLancamento': cco_data.get('quantidadeLancamento', 0),
            'valorLancamentoTotal': validar_e_converter_valor_monetario(cco_data.get('valorLancamentoTotal', 0)),
            'valorReconhecido': validar_e_converter_valor_monetario(cco_data.get('valorReconhecido', 0)),
            'valorReconhecidoComOH': validar_e_converter_valor_monetario(cco_data.get('valorReconhecidoComOH', 0)),
            'valorNaoReconhecido': validar_e_converter_valor_monetario(cco_data.get('valorNaoReconhecido', 0)),
            'valorReconhecivel': validar_e_converter_valor_monetario(cco_data.get('valorReconhecivel', 0)),
            'valorReconhecidoExploracao': validar_e_converter_valor_monetario(cco_data.get('valorReconhecidoExploracao', 0)),
            'valorReconhecidoProducao': validar_e_converter_valor_monetario(cco_data.get('valorReconhecidoProducao', 0)),
            'overHeadExploracao': validar_e_converter_valor_monetario(cco_data.get('overHeadExploracao', 0)),
            'overHeadProducao': validar_e_converter_valor_monetario(cco_data.get('overHeadProducao', 0)),
            'overHeadTotal': validar_e_converter_valor_monetario(cco_data.get('overHeadTotal', 0)),
            'valorNaoPassivelRecuperacao': validar_e_converter_valor_monetario(cco_data.get('valorNaoPassivelRecuperacao', 0)),
            'valorReconhecidoComOhOriginal': validar_e_converter_valor_monetario(cco_data.get('valorReconhecidoComOhOriginal', 0)),
            'flgRecuperado': cco_data.get('flgRecuperado', False),
            'transferencia': cco_data.get('transferencia', '')
        }

    @staticmethod
    def extrair_valores_originais_cco(cco_data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            'valorReconhecidoOriginal': validar_e_converter_valor_monetario(cco_data.get('valorReconhecido', 0)),
            'valorReconhecidoComOHOriginal': validar_e_converter_valor_monetario(cco_data.get('valorReconhecidoComOhOriginal', 0))
        }

    @staticmethod
    def remessas_detalhadas_list(dados_analise: Dict[str, Any]) -> List[Dict[str, Any]]:
        detalhes = []
        is_detalhada = dados_analise.get('tipoAnalise') == 'DETALHADA'
        for remessa in dados_analise['remessasAnalisadas']:
            for fase in remessa['fasesComReconhecimento']:
                detalhe = {
                    'remessaId': remessa['id'],
                    'remessa': remessa['remessa'],
                    'exercicio': int(remessa['exercicio']),
                    'periodo': int(remessa['periodo']),
                    'mesAnoReferencia': remessa['mesAnoReferencia'],
                    'contratoCPP': remessa['contratoCPP'],
                    'campo': remessa['campo'],
                    'fase': fase['fase'],
                    'dataReconhecimento': fase.get('dataReconhecimento', ''),
                    'dataLancamento': fase.get('dataLancamento', ''),
                    'ccoEncontrada': 'Sim' if fase.get('cco') and fase['cco'].get('statusCCO') == 'ENCONTRADA' else 'Não',
                    'ccoId': fase.get('cco', {}).get('id', ''),
                    'statusCCO': fase.get('cco', {}).get('statusCCO', 'N/A'),
                    'observacao': fase.get('cco', {}).get('observacao', '')
                }
                
                if fase.get('cco') and fase['cco'].get('statusCCO') == "CCOS_DUPLICADAS":
                    detalhe["ccoEncontrada"] = "DUPLICADAS"
                    # Para CSV, usar formato simples sem HTML
                    itens = [item.strip() for item in fase.get('cco', {}).get('id', '').split("|") if item.strip()]
                    detalhe['statusCCO'] = ' | '.join(itens)  # Formato CSV-friendly
                    
                if is_detalhada and fase.get('consolidacao'):
                    cons = fase['consolidacao']['valores']
                    detalhe.update({
                        'valorReconhecidoFase': cons.get('reconhecido', 0),
                        'valorLancamentoTotalFase': cons.get('lancamentoTotal', 0),
                        'quantidadeGastosFase': fase['consolidacao']['contadores']['total'],
                        'reconhecidosAutomaticosFase': int(fase['consolidacao']['contadores']['recAutomatico']) or 0,
                        'classificacoesTop': extrair_top_classificacoes(fase['consolidacao']['classificacoes']),
                        'responsaveisTop': extrair_top_responsaveis(fase['consolidacao']['responsaveis']),
                        'moedasUtilizadas': ' | '.join(fase['consolidacao']['moedas'].keys()) if fase['consolidacao']['moedas'] else ''
                    })
                else:
                    # Análise simplificada
                    detalhe.update({
                        'valorReconhecidoFase': fase.get('valorReconhecido', 0),
                        'valorLancamentoTotalFase': 0,
                        'quantidadeGastosFase': 0,
                        'reconhecidosAutomaticosFase': 0,
                        'classificacoesTop': '',
                        'responsaveisTop': '',
                        'moedasUtilizadas': ''
                    })
                
                # Processar valores CCO
                if fase.get('cco') and fase['cco'].get('statusCCO') == 'ENCONTRADA':
                    cco = fase['cco']
                    detalhe.update({
                        'valorCCO': validar_e_converter_valor_monetario(cco.get('valorReconhecido', 0)),
                        'valorCCOComOH': validar_e_converter_valor_monetario(cco.get('valorReconhecidoComOH', 0)),
                        'overheadTotal': validar_e_converter_valor_monetario(cco.get('overHeadTotal', 0)),
                        'correcaoMonetaria': validar_e_converter_valor_monetario(cco.get('diferencaValor', 0)),
                        'taxaCorrecao': validar_e_converter_valor_monetario(cco.get('taxaCorrecao', 0)),
                        'tipoCorrecao': cco.get('tipo', ''),
                        'dataCorrecao': cco.get('dataCorrecao', '')
                    })
                else:
                    detalhe.update({
                        'valorCCO': 0,
                        'valorCCOComOH': 0,
                        'overheadTotal': 0,
                        'correcaoMonetaria': 0,
                        'taxaCorrecao': 0,
                        'tipoCorrecao': '',
                        'dataCorrecao': ''
                    })
                
                detalhes.append(detalhe)
        return detalhes

    @staticmethod
    def gerar_descricao_evento(tipo: str, correcao: Dict[str, Any]) -> str:
        try:
            if tipo in ['IPCA', 'IGPM']:
                taxa = converter_decimal128_para_float(correcao.get('taxaCorrecao', 0))
                if taxa > 0:
                    return f"Aplicação de correção monetária {tipo} - Taxa: {taxa:.4f}%"
                return f"Correção monetária {tipo} aplicada"
            if tipo == 'RECUPERACAO':
                valor_recuperado = converter_decimal128_para_float(correcao.get('valorRecuperado', 0))
                valor_recuperado_total = converter_decimal128_para_float(correcao.get('valorRecuperadoTotal', 0))
                if valor_recuperado > 0:
                    return f"Recuperação de valor: R$ {valor_recuperado:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                if valor_recuperado_total > 0:
                    return f"Recuperação total: R$ {valor_recuperado_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                return "Recuperação de valor realizada"
            if tipo == 'INVALIDACAO_RECONHECIMENTO_PARCIAL':
                return "Invalidação parcial do reconhecimento com transferência de valores"
            if tipo == 'RETIFICACAO':
                return "Ajuste manual realizado nos valores da CCO"
            return f"Evento do tipo {tipo} aplicado à CCO"
        except Exception:
            return f"Evento do tipo {tipo}"

    @classmethod
    def processar_evento_correcao(cls, correcao: Dict[str, Any], sequencia: int) -> Dict[str, Any]:
        tipo = correcao.get('tipo', 'DESCONHECIDO')
        tipo_map = {
            'IPCA': {'titulo': 'Correção Monetária IPCA', 'icone': 'fas fa-chart-line', 'cor': 'info'},
            'IGPM': {'titulo': 'Correção Monetária IGPM', 'icone': 'fas fa-chart-line', 'cor': 'info'},
            'RECUPERACAO': {'titulo': 'Recuperação de Valor', 'icone': 'fas fa-download', 'cor': 'warning'},
            'INVALIDACAO_RECONHECIMENTO_PARCIAL': {'titulo': 'Invalidação Parcial', 'icone': 'fas fa-repeat', 'cor': 'dark'},
            'RETIFICACAO': {'titulo': 'Retificação Manual', 'icone': 'fas fa-edit', 'cor': 'secondary'}
        }
        config = tipo_map.get(tipo, {'titulo': tipo, 'icone': 'fas fa-question-circle', 'cor': 'secondary'})

        descricao = cls.gerar_descricao_evento(tipo, correcao)
        valores = {
            'valorReconhecido': converter_decimal128_para_float(correcao.get('valorReconhecido', 0)),
            'valorReconhecidoComOH': converter_decimal128_para_float(correcao.get('valorReconhecidoComOH', 0)),
            'overHeadTotal': converter_decimal128_para_float(correcao.get('overHeadTotal', 0)),
            'diferencaValor': converter_decimal128_para_float(correcao.get('diferencaValor', 0)),
            'valorRecuperado': converter_decimal128_para_float(correcao.get('valorRecuperado', 0)),
            'valorRecuperadoTotal': converter_decimal128_para_float(correcao.get('valorRecuperadoTotal', 0)),
            'taxaCorrecao': converter_decimal128_para_float(correcao.get('taxaCorrecao', 0)),
            'igpmAcumulado': converter_decimal128_para_float(correcao.get('igpmAcumulado', 0)),
            'igpmAcumuladoReais': converter_decimal128_para_float(correcao.get('igpmAcumuladoReais', 0)),
            'valorLancamentoTotal': converter_decimal128_para_float(correcao.get('valorLancamentoTotal', 0)),
            'valorNaoReconhecido': converter_decimal128_para_float(correcao.get('valorNaoReconhecido', 0)),
            'valorReconhecivel': converter_decimal128_para_float(correcao.get('valorReconhecivel', 0)),
            'valorNaoPassivelRecuperacao': converter_decimal128_para_float(correcao.get('valorNaoPassivelRecuperacao', 0))
        }
        detalhes = {
            'subTipo': correcao.get('subTipo', ''),
            'ativo': correcao.get('ativo', True),
            'observacao': correcao.get('observacao', ''),
            'transferencia': correcao.get('transferencia', False),
            'quantidadeLancamento': correcao.get('quantidadeLancamento', 0),
            'contrato': correcao.get('contrato', ''),
            'campo': correcao.get('campo', ''),
            'faseRemessa': correcao.get('faseRemessa', '')
        }
        return {
            'tipo': tipo,
            'sequencia': sequencia,
            'dataCorrecao': correcao.get('dataCorrecao'),
            'dataCorrecaoFormatada': formatar_data_brasileira(correcao.get('dataCorrecao')),
            'dataCriacaoCorrecao': formatar_data_brasileira(correcao.get('dataCriacaoCorrecao')),
            'titulo': config['titulo'],
            'descricao': descricao,
            'valores': valores,
            'detalhes': detalhes,
            'icone': config['icone'],
            'cor': config['cor']
        }

    @classmethod
    def extrair_valores_atuais_cco(cls, cco_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extrai valores atuais da CCO (última correção ou valores da raiz)"""
        valores_atuais = {}
        
        dataLancamento = formatar_data_brasileira(cco_data.get('dataLancamento'))
        dataReconhecimento = formatar_data_brasileira(cco_data.get('dataReconhecimento'))
        valores_atuais['data_lancamento'] = formatar_data_brasileira(dataLancamento)
        valores_atuais['data_reconhecimento'] = formatar_data_brasileira(dataReconhecimento)
        
        # Se tem correções monetárias, usar a última
        if 'correcoesMonetarias' in cco_data and cco_data['correcoesMonetarias']:
            ultima_correcao = cco_data['correcoesMonetarias'][-1]
            fonte = ultima_correcao
            dataAtualizacao =ultima_correcao.get('dataCorrecao') or ultima_correcao.get('dataCriacaoCorrecao')
            dataCorrecao = ultima_correcao.get('dataCorrecao')
            dataCriacaoCorrecao = ultima_correcao.get('dataCriacaoCorrecao')
            valores_atuais['fonte'] = f"Última correção ({ultima_correcao.get('tipo', 'N/A')})"
            valores_atuais['data_atualizacao'] = formatar_data_brasileira(dataAtualizacao)
            valores_atuais['data_correcao'] = formatar_data_brasileira(dataCorrecao)
            valores_atuais['data_criacao_correcao'] = formatar_data_brasileira(dataCriacaoCorrecao)
            
            
        else:
            # Usar valores da raiz da CCO
            fonte = cco_data
            valores_atuais['fonte'] = "Valores originais da CCO"
            #valores_atuais['data_atualizacao'] = cco_data.get('dataLancamento')
        
        # Extrair valores principais
        valores_atuais.update({
            'valorReconhecido': converter_decimal128_para_float(fonte.get('valorReconhecido', 0)),
            'valorReconhecidoComOH': converter_decimal128_para_float(fonte.get('valorReconhecidoComOH', 0)),
            'overHeadTotal': converter_decimal128_para_float(fonte.get('overHeadTotal', 0)),
            'valorLancamentoTotal': converter_decimal128_para_float(fonte.get('valorLancamentoTotal', 0)),
            'valorReconhecivel': converter_decimal128_para_float(fonte.get('valorReconhecivel', 0)),
            'valorNaoReconhecido': converter_decimal128_para_float(fonte.get('valorNaoReconhecido', 0)),
            'valorNaoPassivelRecuperacao': converter_decimal128_para_float(fonte.get('valorNaoPassivelRecuperacao', 0)),
            'quantidadeLancamento': fonte.get('quantidadeLancamento', 0),
            'flgRecuperado': fonte.get('flgRecuperado', False),
            
            # Valores extras (podem não existir)
            'valorRecuperado': converter_decimal128_para_float(fonte.get('valorRecuperado', 0)),
            'valorRecuperadoTotal': converter_decimal128_para_float(fonte.get('valorRecuperadoTotal', 0)),
            'taxaCorrecao': converter_decimal128_para_float(fonte.get('taxaCorrecao', 0)),
            'igpmAcumulado': converter_decimal128_para_float(fonte.get('igpmAcumulado', 0)),
            'igpmAcumuladoReais': converter_decimal128_para_float(fonte.get('igpmAcumuladoReais', 0)),
            'diferencaValor': converter_decimal128_para_float(fonte.get('diferencaValor', 0)),
            'overHeadExploracao': converter_decimal128_para_float(fonte.get('overHeadExploracao', 0)),
            'overHeadProducao': converter_decimal128_para_float(fonte.get('overHeadProducao', 0)),
            'valorReconhecidoExploracao': converter_decimal128_para_float(fonte.get('valorReconhecidoExploracao', 0)),
            'valorReconhecidoProducao': converter_decimal128_para_float(fonte.get('valorReconhecidoProducao', 0)),
            
            # Informações adicionais
            'ativo': fonte.get('ativo', True),
            'subTipo': fonte.get('subTipo', ''),
            'transferencia': fonte.get('transferencia', False),
            'icone': 'fas fa-plus-circle',
            'cor': 'success'
        })
        
        return valores_atuais
 

    @classmethod
    def processar_timeline_cco(cls, cco_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        timeline = []
        # Evento inicial (valores atuais/raiz)
        timeline.append({
            'tipo': 'CRIACAO',
            'titulo': 'CCO Criada',
            #'dataCorrecao': cco_data.get('dataLancamento'),
            'descricao': f"CCO criada para remessa {cco_data.get('remessa')} - Fase {cco_data.get('faseRemessa')}",
            'detalhes': {
                'dataLancamento': formatar_data_brasileira(cco_data.get('dataLancamento')),
                'dataReconhecimento': formatar_data_brasileira(cco_data.get('dataReconhecimento')),
                'contrato': cco_data.get('contratoCpp'),
                'campo': cco_data.get('campo', ''),
                'remessa': cco_data.get('remessa', ''),
                'remessaExposicao': cco_data.get('remessaExposicao', ''),
                'quantidadeLancamento': cco_data.get('quantidadeLancamento', 0),
                'anoReconhecimento': cco_data.get('anoReconhecimento', 0),
                'mesReconhecimento': cco_data.get('mesReconhecimento', 0),
                'mesAnoReferencia': cco_data.get('mesAnoReferencia', ''),
                'faseRemessa': cco_data.get('faseRemessa', ''),
                'faseRespostaGestora': cco_data.get('faseRespostaGestora', ''),
                'periodo': cco_data.get('periodo', 0),
                'version': cco_data.get('version', 0)
            },
            'valores': {
                'valorReconhecido': converter_decimal128_para_float(cco_data.get('valorReconhecido', 0)),
                'valorReconhecidoComOH': converter_decimal128_para_float(cco_data.get('valorReconhecidoComOH', 0)),
                'overHeadTotal': converter_decimal128_para_float(cco_data.get('overHeadTotal', 0)),
                'valorLancamentoTotal': converter_decimal128_para_float(cco_data.get('valorLancamentoTotal', 0)),
                'valorNaoReconhecido': converter_decimal128_para_float(cco_data.get('valorNaoReconhecido', 0)),
                'valorReconhecidoExploracao': converter_decimal128_para_float(cco_data.get('valorReconhecidoExploracao', 0)),
                'valorReconhecidoProducao': converter_decimal128_para_float(cco_data.get('valorReconhecidoProducao', 0)),
                'overHeadExploracao': converter_decimal128_para_float(cco_data.get('overHeadExploracao', 0)),
                'overHeadProducao': converter_decimal128_para_float(cco_data.get('overHeadProducao', 0)),
                'valorReconhecivel': converter_decimal128_para_float(cco_data.get('valorReconhecivel', 0)),
                'valorNaoPassivelRecuperacao': converter_decimal128_para_float(cco_data.get('valorNaoPassivelRecuperacao', 0)),
                'valorRecusado': converter_decimal128_para_float(cco_data.get('valorRecusado', 0)),
                'diferencaValor': converter_decimal128_para_float(cco_data.get('diferencaValor', 0))
            },
            'icone': 'fas fa-plus-circle',
            'cor': 'success'
        })

        if 'correcoesMonetarias' in cco_data and cco_data['correcoesMonetarias']:
            for i, correcao in enumerate(cco_data['correcoesMonetarias']):
                evento = cls.processar_evento_correcao(correcao, i + 1)
                timeline.append(evento)

        timeline.sort(key=lambda x: x.get('dataCorrecao', '1900-01-01'), reverse=True)
        return timeline


    def get_timeline_with_cutoff(self, cco_id: str, data_corte: Optional[str] = None) -> Dict[str, Any]:
        """
        Retorna a timeline da CCO com filtro opcional por data de corte.

        Quando data_corte não é informada, retorna a timeline completa.
        Quando data_corte é informada, retorna apenas os eventos até a data informada.

        Args:
            cco_id: ID da CCO.
            data_corte: Data limite no formato YYYY-MM-DD.

        Returns:
            Dict contendo:
                - estado_temporal
                - cco_id
                - data_corte
                - eventos
                - valores_em_data_corte
        """
        cco = self._get_db_prd().conta_custo_oleo_entity.find_one({"_id": cco_id})

        if not cco:
            return {
                "erro": "CCO não encontrada",
                "cco_id": cco_id
            }

        timeline = self.processar_timeline_cco(cco)
        valores_atuais = self.extrair_valores_atuais_cco(cco)

        if not data_corte:
            return {
                "estado_temporal": False,
                "cco_id": cco_id,
                "data_corte": None,
                "eventos": timeline,
                "valores_em_data_corte": valores_atuais
            }

        try:
            data_limite = datetime.strptime(data_corte, "%Y-%m-%d").date()
        except ValueError:
            raise ValueError("Formato de data inválido. Use YYYY-MM-DD.")

        eventos_filtrados = []

        for evento in timeline:
            data_evento = self._extrair_data_evento_timeline(evento)

            if data_evento is None:
                continue

            if isinstance(data_evento, datetime):
                data_evento = data_evento.date()

            if isinstance(data_evento, date) and data_evento <= data_limite:
                eventos_filtrados.append(evento)

        valores_em_data_corte = self._recalcular_valores_timeline_filtrada(
            eventos_filtrados,
            valores_atuais
        )

        return {
            "estado_temporal": True,
            "cco_id": cco_id,
            "data_corte": data_corte,
            "eventos": eventos_filtrados,
            "valores_em_data_corte": valores_em_data_corte
        }

    @staticmethod
    def _extrair_data_evento_timeline(evento: Dict[str, Any]) -> Optional[date]:
        """
        Tenta extrair a data de um evento da timeline.

        O método aceita diferentes nomes de campos porque os eventos da timeline
        podem vir da CCO original ou de correções monetárias.
        """
        possiveis_campos = [
            "data",
            "dataCorrecao",
            "dataCriacaoCorrecao",
            "dataAtualizacao",
            "createdAt",
            "updatedAt",
        ]

        for campo in possiveis_campos:
            valor = evento.get(campo)

            data_extraida = PortalService._converter_valor_para_data(valor)

            if data_extraida:
                return data_extraida

        data_formatada = evento.get("dataCorrecaoFormatada")
        data_extraida = PortalService._converter_valor_para_data(data_formatada)

        if data_extraida:
            return data_extraida

        detalhes = evento.get("detalhes", {}) or {}

        for campo in ["dataLancamento", "dataReconhecimento", "dataCorrecao", "dataCriacaoCorrecao"]:
            data_extraida = PortalService._converter_valor_para_data(detalhes.get(campo))

            if data_extraida:
                return data_extraida

        return None

    @staticmethod
    def _converter_valor_para_data(valor: Any) -> Optional[date]:
        """
        Converte valores de data em date/datetime/string para date.

        Aceita formatos comuns:
            - datetime/date
            - YYYY-MM-DD
            - YYYY-MM-DDTHH:MM:SS
            - DD/MM/YYYY
            - DD/MM/YYYY HH:MM
            - DD/MM/YYYY HH:MM:SS
        """
        if not valor:
            return None

        if isinstance(valor, datetime):
            return valor.date()

        if isinstance(valor, date):
            return valor

        if not isinstance(valor, str):
            return None

        texto = valor.strip()

        if not texto:
            return None

        texto = texto.replace("Z", "+00:00")

        try:
            return datetime.fromisoformat(texto).date()
        except ValueError:
            pass

        formatos = [
            "%Y-%m-%d",
            "%Y-%m-%d %H:%M:%S",
            "%d/%m/%Y",
            "%d/%m/%Y %H:%M",
            "%d/%m/%Y %H:%M:%S",
        ]

        for formato in formatos:
            try:
                return datetime.strptime(texto[:19], formato).date()
            except ValueError:
                continue

        return None

    @staticmethod
    def _recalcular_valores_timeline_filtrada(
        eventos_filtrados: List[Dict[str, Any]],
        valores_padrao: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Recalcula valores principais com base no evento mais recente dentro do corte.

        Observação:
            processar_timeline_cco ordena a timeline em ordem decrescente.
            Portanto, o primeiro evento filtrado tende a ser o mais recente
            até a data de corte.
        """
        if not eventos_filtrados:
            return {
                "valorReconhecido": 0,
                "valorReconhecidoComOH": 0,
                "overHeadTotal": 0,
                "diferencaValor": 0,
                "valorRecuperado": 0,
                "valorRecuperadoTotal": 0,
                "taxaCorrecao": 0,
                "igpmAcumulado": 0,
                "igpmAcumuladoReais": 0,
                "valorNaoReconhecido": 0,
                "valorLancamentoTotal": 0,
                "valorReconhecivel": 0,
                "valorNaoPassivelRecuperacao": 0,
                "overHeadExploracao": 0,
                "overHeadProducao": 0,
                "valorReconhecidoExploracao": 0,
                "valorReconhecidoProducao": 0,
                "fonte": "Nenhum evento encontrado até a data de corte"
            }

        evento_referencia = eventos_filtrados[0]
        valores_evento = evento_referencia.get("valores", {}) or {}

        campos_valores = [
            "valorReconhecido",
            "valorReconhecidoComOH",
            "overHeadTotal",
            "diferencaValor",
            "valorRecuperado",
            "valorRecuperadoTotal",
            "taxaCorrecao",
            "igpmAcumulado",
            "igpmAcumuladoReais",
            "valorNaoReconhecido",
            "valorLancamentoTotal",
            "valorReconhecivel",
            "valorNaoPassivelRecuperacao",
            "overHeadExploracao",
            "overHeadProducao",
            "valorReconhecidoExploracao",
            "valorReconhecidoProducao",
        ]

        valores_recalculados = {}

        for campo in campos_valores:
            valores_recalculados[campo] = valores_evento.get(
                campo,
                valores_padrao.get(campo, 0)
            )

        valores_recalculados.update({
            "fonte": "Valores recalculados até a data de corte",
            "tipo_evento_referencia": evento_referencia.get("tipo"),
            "titulo_evento_referencia": evento_referencia.get("titulo"),
            "data_evento_referencia": evento_referencia.get("dataCorrecaoFormatada")
        })

        return valores_recalculados


    # --- Pesquisa de CCOs ---
    def pesquisar_ccos(self, filtros: Dict[str, Any], limite: int = 500) -> List[Dict[str, Any]]:
        
        projecao = {
            '_id': 1,
            'contratoCpp': 1,
            'campo': 1,
            'remessa': 1,
            'remessaExposicao': 1,
            'faseRemessa': 1,
            'faseRespostaGestora': 1,
            'exercicio': 1,
            'periodo': 1,
            'mesAnoReferencia': 1,
            'mesReconhecimento': 1,
            'anoReconhecimento': 1,
            'origemDosGastos': 1,
            'flgRecuperado': 1,
            'dataLancamento': 1,
            'dataReconhecimento': 1,
            'quantidadeLancamento': 1,
            'valorReconhecido': 1,
            'valorReconhecidoComOH': 1,
            'overHeadTotal': 1,
            'correcoesMonetarias': {'$slice': -1}
        }
        cursor = self._get_db().conta_custo_oleo_entity.find(filtros, projecao).sort('dataReconhecimento',-1).limit(limite)
        resultados = []
        for cco in cursor:
            valores_atuais = self.extrair_valores_resumidos_cco(cco)
            resultados.append({
                'id': str(cco['_id']),
                'contratoCpp': cco.get('contratoCpp', ''),
                'campo': cco.get('campo', ''),
                'remessa': cco.get('remessa', 0),
                'remessaExposicao': cco.get('remessaExposicao', 0),
                'faseRemessa': cco.get('faseRemessa', ''),
                'faseRespostaGestora': cco.get('faseRespostaGestora', ''),
                'exercicio': cco.get('exercicio', 0),
                'periodo': cco.get('periodo', 0),
                'mesAnoReferencia': cco.get('mesAnoReferencia', ''),
                'anoReconhecimento': cco.get('anoReconhecimento', 0),
                'mesReconhecimento': cco.get('mesReconhecimento', 0),
                'origemDosGastos': cco.get('origemDosGastos', ''),
                'flgRecuperado': cco.get('flgRecuperado', False),
                'dataLancamento': formatar_data_brasileira(cco.get('dataLancamento')),
                'dataReconhecimento': formatar_data_brasileira(cco.get('dataReconhecimento')),
                'quantidadeLancamento': cco.get('quantidadeLancamento', 0),
                'valorReconhecido': valores_atuais['valorReconhecido'],
                'valorReconhecidoComOH': valores_atuais['valorReconhecidoComOH'],
                'overHeadTotal': valores_atuais['overHeadTotal'],
                'temCorrecoes': len(cco.get('correcoesMonetarias', [])) > 0,
                'ultimaAtualizacao': valores_atuais['ultimaAtualizacao']
            })
        return resultados

    @staticmethod
    def extrair_valores_resumidos_cco(cco_data: Dict[str, Any]) -> Dict[str, Any]:
        valores = {
            'valorReconhecido': 0,
            'valorReconhecidoComOH': 0,
            'overHeadTotal': 0,
            'ultimaAtualizacao': ''
        }
        if 'correcoesMonetarias' in cco_data and cco_data['correcoesMonetarias']:
            ultima_correcao = cco_data['correcoesMonetarias'][-1]
            valores['valorReconhecido'] = converter_decimal128_para_float(ultima_correcao.get('valorReconhecido', 0))
            valores['valorReconhecidoComOH'] = converter_decimal128_para_float(ultima_correcao.get('valorReconhecidoComOH', 0))
            valores['overHeadTotal'] = converter_decimal128_para_float(ultima_correcao.get('overHeadTotal', 0))
            valores['ultimaAtualizacao'] = formatar_data_simples(ultima_correcao.get('dataCorrecao') or ultima_correcao.get('dataCriacaoCorrecao'))
        else:
            valores['valorReconhecido'] = converter_decimal128_para_float(cco_data.get('valorReconhecido', 0))
            valores['valorReconhecidoComOH'] = converter_decimal128_para_float(cco_data.get('valorReconhecidoComOH', 0))
            valores['overHeadTotal'] = converter_decimal128_para_float(cco_data.get('overHeadTotal', 0))
            valores['ultimaAtualizacao'] = formatar_data_simples(cco_data.get('dataLancamento'))
        return valores

    # --- Listagens simples ---
    def listar_contratos(self) -> List[str]:
        db = self._get_db()
        contratos = db.conta_custo_oleo_entity.distinct('contratoCpp')
        return sorted([c for c in contratos if c])

    def listar_campos_por_contrato(self, contrato: str) -> List[str]:
        db = self._get_db()
        campos = db.conta_custo_oleo_entity.distinct('campo', {'contratoCpp': contrato})
        return sorted([c for c in campos if c])

    @staticmethod
    def fase_resposta_gestora_valida_para_filtro(fase: str) -> bool:
        """Valida quais fases de resposta gestora podem aparecer no filtro.

        Regras:
        - trazer somente REV, REV1 até REV99;
        - trazer somente ABCR, ABCR1 até ABCR99;
        - ignorar valores fora do padrão, como 2014FAN, 25MUM ou REV1666354677259.
        """
        return bool(re.fullmatch(r'(REV|ABCR)\d{0,2}', fase or ''))

    @staticmethod
    def normalizar_fase_para_lista(fase: Any, campo_origem: str = '') -> str:
        """Normaliza a fase somente para exibição no filtro.

        Regras:
        - fases sequenciais válidas devem permanecer completas na lista;
          exemplo: ABCR1, ABCR2, REV1, REV2, REV99;
        - faseRespostaGestora só entra na lista se for REV/ABCR com no máximo 2 dígitos;
        - quando a origem for faseRemessa e o valor for FISC, exibir AUD.
        """
        fase_normalizada = str(fase or '').strip().upper()

        if not fase_normalizada:
            return ''

        if campo_origem == 'faseRemessa' and fase_normalizada == 'FISC':
            return 'AUD'

        if campo_origem == 'faseRespostaGestora' and not PortalService.fase_resposta_gestora_valida_para_filtro(fase_normalizada):
            return ''

        return fase_normalizada

    def listar_fases_disponiveis(self) -> List[str]:
        """Lista fases distintas de faseRemessa e faseRespostaGestora.

        Usa distinct nos dois campos para que novas fases sejam carregadas
        automaticamente no filtro da tela /pesquisa-ccos sem alteração de HTML.

        Fases sequenciais não são agrupadas. Se existirem ABCR1, ABCR2,
        REV1 e REV2 no banco, todas aparecem individualmente no filtro.

        Para faseRespostaGestora, somente valores REV/ABCR com até 2 dígitos
        são considerados. Exemplos inválidos ignorados: 2014FAN, 25MUM,
        REV1666354677259.
        """
        db = self._get_db()
        colecao = db.conta_custo_oleo_entity

        fases_remessa = colecao.distinct('faseRemessa')
        fases_resposta_gestora = colecao.distinct('faseRespostaGestora')

        fases = set()

        for fase in fases_remessa or []:
            fase_normalizada = self.normalizar_fase_para_lista(fase, 'faseRemessa')
            if fase_normalizada:
                fases.add(fase_normalizada)

        for fase in fases_resposta_gestora or []:
            fase_normalizada = self.normalizar_fase_para_lista(fase, 'faseRespostaGestora')
            if fase_normalizada:
                fases.add(fase_normalizada)

        return sorted(fases)

    def get_timeline_with_cutoff(self, cco_id: str, data_corte: Optional[str] = None) -> Dict[str, Any]:
        """
        Retorna timeline filtrada por data de corte.
        
        Args:
            cco_id: ID da CCO
            data_corte: Data limite em formato YYYY-MM-DD (opcional)
            
        Returns:
            Dicionário com timeline filtrada e estado temporal
            
        Raises:
            ValueError: Se data_corte for fornecida em formato inválido
        """
        try:
            # Validar e parsear data_corte antes de consultar o banco.
            # Assim uma data inválida sempre retorna erro de validação,
            # mesmo quando a CCO não existir.
            data_corte_obj = None
            if data_corte:
                try:
                    data_corte_obj = datetime.strptime(data_corte, '%Y-%m-%d').date()
                except ValueError:
                    raise ValueError(f"Formato de data inválido: {data_corte}. Use YYYY-MM-DD")

            # Buscar CCO do banco de dados
            db = self._get_db()
            cco_data = db.conta_custo_oleo_entity.find_one({"_id": cco_id})
            
            if not cco_data:
                return {
                    'estado_temporal': False,
                    'erro': f'CCO {cco_id} não encontrada',
                    'eventos': [],
                    'valores_em_data_corte': {}
                }
            
            # Processar timeline completa
            timeline_completa = self.processar_timeline_cco(cco_data)
            
            # Se não houver data_corte, retornar timeline completa
            if not data_corte:
                return {
                    'estado_temporal': False,
                    'cco_id': cco_id,
                    'data_corte': None,
                    'eventos': timeline_completa,
                    'valores_em_data_corte': self.extrair_valores_atuais_cco(cco_data)
                }
            
            # Filtrar eventos até data_corte
            eventos_filtrados = []
            evento_criacao = None
            
            for evento in timeline_completa:
                if evento['tipo'] == 'CRIACAO':
                    evento_criacao = evento
                    eventos_filtrados.append(evento)
                else:
                    # Parsear dataCorrecao
                    data_evento_str = evento.get('dataCorrecao')
                    if data_evento_str:
                        try:
                            # Tentar diferentes formatos
                            if isinstance(data_evento_str, str):
                                if 'T' in data_evento_str:
                                    data_evento = datetime.fromisoformat(
                                        data_evento_str.replace('Z', '+00:00')
                                    ).date()
                                else:
                                    data_evento = datetime.strptime(data_evento_str[:10], '%Y-%m-%d').date()
                            else:
                                data_evento = data_evento_str
                            
                            # Incluir se evento ocorreu antes ou na data de corte
                            if data_evento <= data_corte_obj:
                                eventos_filtrados.append(evento)
                        except Exception as e:
                            logger.warning(f"Erro ao parsear data do evento: {data_evento_str} - {e}")
                            # Se não conseguir parsear, incluir o evento (ser permissivo)
                            eventos_filtrados.append(evento)
            
            # Recalcular valores em data_corte
            valores_em_corte = self._recalcular_valores_em_data(
                cco_data, 
                eventos_filtrados, 
                data_corte_obj
            )
            
            return {
                'estado_temporal': True,
                'cco_id': cco_id,
                'data_corte': data_corte,
                'total_eventos': len(timeline_completa),
                'eventos_ate_corte': len(eventos_filtrados),
                'eventos': eventos_filtrados,
                'valores_em_data_corte': valores_em_corte
            }
            
        except ValueError as ve:
            logger.error(f"Erro na validação: {ve}")
            raise
        except Exception as e:
            logger.error(f"Erro ao processar timeline com cutoff: {e}")
            return {
                'estado_temporal': False,
                'cco_id': cco_id,
                'erro': str(e),
                'eventos': [],
                'valores_em_data_corte': {}
            }

    @staticmethod
    def _recalcular_valores_em_data(
        cco_data: Dict[str, Any],
        eventos_filtrados: List[Dict[str, Any]],
        data_corte: Any
    ) -> Dict[str, Any]:
        """
        Recalcula valores acumulados até a data de corte.
        
        Args:
            cco_data: Dados da CCO original
            eventos_filtrados: Lista de eventos até data de corte
            data_corte: Data limite (date object)
            
        Returns:
            Dicionário com valores recalculados em data_corte
        """
        # Iniciar com valores da CCO original (evento de criação)
        valores = {
            'dataReconhecimento': formatar_data_brasileira(cco_data.get('dataReconhecimento')),
            'dataLancamento': formatar_data_brasileira(cco_data.get('dataLancamento')),
            'quantidadeLancamento': cco_data.get('quantidadeLancamento', 0),
            'valorReconhecido': converter_decimal128_para_float(cco_data.get('valorReconhecido', 0)),
            'valorReconhecidoComOH': converter_decimal128_para_float(cco_data.get('valorReconhecidoComOH', 0)),
            'overHeadTotal': converter_decimal128_para_float(cco_data.get('overHeadTotal', 0)),
            'valorLancamentoTotal': converter_decimal128_para_float(cco_data.get('valorLancamentoTotal', 0)),
            'valorReconhecivel': converter_decimal128_para_float(cco_data.get('valorReconhecivel', 0)),
            'valorNaoReconhecido': converter_decimal128_para_float(cco_data.get('valorNaoReconhecido', 0)),
            'valorNaoPassivelRecuperacao': converter_decimal128_para_float(cco_data.get('valorNaoPassivelRecuperacao', 0)),
            'overHeadExploracao': converter_decimal128_para_float(cco_data.get('overHeadExploracao', 0)),
            'overHeadProducao': converter_decimal128_para_float(cco_data.get('overHeadProducao', 0)),
            'valorReconhecidoExploracao': converter_decimal128_para_float(cco_data.get('valorReconhecidoExploracao', 0)),
            'valorReconhecidoProducao': converter_decimal128_para_float(cco_data.get('valorReconhecidoProducao', 0)),
            'valorRecuperado': 0,
            'valorRecuperadoTotal': 0,
            'ipca_acumulado': 0,
            'igpm_acumulado': 0,
            'igpm_acumulado_reais': 0,
            'diferencaValor_total': 0
        }
        
        # Processar eventos para atualizar valores até data_corte
        for evento in eventos_filtrados:
            if evento['tipo'] == 'CRIACAO':
                continue
            
            evento_valores = evento.get('valores', {})
            
            # Atualizar com valores mais recentes do evento
            valores.update({
                'valorReconhecido': evento_valores.get('valorReconhecido', valores['valorReconhecido']),
                'valorReconhecidoComOH': evento_valores.get('valorReconhecidoComOH', valores['valorReconhecidoComOH']),
                'overHeadTotal': evento_valores.get('overHeadTotal', valores['overHeadTotal']),
                'diferencaValor_total': evento_valores.get('diferencaValor', valores['diferencaValor_total']),
                'igpm_acumulado': evento_valores.get('igpmAcumulado', valores['igpm_acumulado']),
                'igpm_acumulado_reais': evento_valores.get('igpmAcumuladoReais', valores['igpm_acumulado_reais']),
            })
            
            # Acumular valores de recuperação
            if evento['tipo'] == 'RECUPERACAO':
                valores['valorRecuperado'] += evento_valores.get('valorRecuperado', 0)
                valores['valorRecuperadoTotal'] += evento_valores.get('valorRecuperadoTotal', 0)
        
        return valores

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

def buscar_ccos_completas_para_exportacao(self, filtros: Dict[str, Any], limite: int = 5000) -> List[Dict[str, Any]]:
    db = self._get_db()

    cursor = (
        db.conta_custo_oleo_entity
        .find(filtros)
        .sort([("dataReconhecimento", 1), ("_id", 1)])
        .limit(limite)
    )

    return list(cursor)