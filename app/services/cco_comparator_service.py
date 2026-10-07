"""
Serviço para comparação detalhada de CCOs (original vs corrigida)
Fornece análise estruturada das diferenças entre documentos
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from decimal import Decimal
from bson.decimal128 import Decimal128

logger = logging.getLogger(__name__)


class CCOComparatorService:
    """
    Serviço responsável por comparar estruturas de CCOs
    e identificar diferenças de forma detalhada
    """
    
    # Campos monetários que devem ser comparados como valores financeiros
    CAMPOS_MONETARIOS = {
        'valorLancamentoTotal', 'valorNaoReconhecido', 'valorReconhecido',
        'valorReconhecivel', 'valorNaoPassivelRecuperacao', 'valorReconhecidoExploracao',
        'valorReconhecidoProducao', 'valorRecusado', 'overHeadExploracao',
        'overHeadProducao', 'overHeadTotal', 'valorReconhecidoComOH',
        'diferencaValor', 'valorReconhecidoComOhOriginal', 'taxaCorrecao',
        'igpmAcumulado', 'igpmAcumuladoReais', 'valorRecuperado', 'valorRecuperadoTotal'
    }
    
    # Campos que devem ser ignorados na comparação
    CAMPOS_IGNORAR = {
        '_class', 'session_id', 'status_promocao', 'data_criacao_correcao',
        'data_promocao', 'usuario_promocao', 'observacoes_promocao', 'versao_promovida'
    }
    
    # Campos de data
    CAMPOS_DATA = {
        'dataReconhecimento', 'dataLancamento', 'dataCorrecao', 'dataCriacaoCorrecao'
    }
    
    # Labels amigáveis para campos
    LABELS_CAMPOS = {
        '_id': 'ID da CCO',
        'contratoCpp': 'Contrato CPP',
        'campo': 'Campo',
        'remessa': 'Remessa',
        'remessaExposicao': 'Remessa Exposição',
        'faseRemessa': 'Fase da Remessa',
        'dataReconhecimento': 'Data Reconhecimento',
        'exercicio': 'Exercício',
        'periodo': 'Período',
        'quantidadeLancamento': 'Quantidade de Lançamentos',
        'valorLancamentoTotal': 'Valor Lançamento Total',
        'valorNaoReconhecido': 'Valor Não Reconhecido',
        'valorReconhecido': 'Valor Reconhecido',
        'valorReconhecivel': 'Valor Reconhecível',
        'valorNaoPassivelRecuperacao': 'Valor Não Passível de Recuperação',
        'valorReconhecidoExploracao': 'Valor Reconhecido Exploração',
        'valorReconhecidoProducao': 'Valor Reconhecido Produção',
        'valorRecusado': 'Valor Recusado',
        'overHeadExploracao': 'Overhead Exploração',
        'overHeadProducao': 'Overhead Produção',
        'overHeadTotal': 'Overhead Total',
        'valorReconhecidoComOH': 'Valor Reconhecido com OH',
        'origemDosGastos': 'Origem dos Gastos',
        'flgRecuperado': 'Recuperada',
        'mesReconhecimento': 'Mês Reconhecimento',
        'anoReconhecimento': 'Ano Reconhecimento',
        'mesAnoReferencia': 'Mês/Ano Referência',
        'faseRespostaGestora': 'Fase Resposta Gestora',
        'dataLancamento': 'Data Lançamento',
        'version': 'Versão',
        'correcoesMonetarias': 'Correções Monetárias',
        'tipo': 'Tipo',
        'subTipo': 'Sub-Tipo',
        'dataCorrecao': 'Data Correção',
        'dataCriacaoCorrecao': 'Data Criação Correção',
        'taxaCorrecao': 'Taxa de Correção',
        'diferencaValor': 'Diferença de Valor',
        'valorReconhecidoComOhOriginal': 'Valor Reconhecido com OH Original',
        'igpmAcumulado': 'IGPM Acumulado',
        'igpmAcumuladoReais': 'IGPM Acumulado (R$)',
        'valorRecuperado': 'Valor Recuperado',
        'valorRecuperadoTotal': 'Valor Recuperado Total',
        'transferencia': 'Transferência',
        'observacao': 'Observação',
        'ativo': 'Ativo'
    }
    
    def __init__(self):
        logger.info("CCOComparatorService inicializado")
    
    def comparar_ccos(self, cco_original: Dict[str, Any], 
                      cco_corrigida: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compara duas CCOs e retorna análise detalhada das diferenças
        
        Args:
            cco_original: CCO original de produção
            cco_corrigida: CCO com correções aplicadas
            
        Returns:
            Dict com análise completa das diferenças
        """
        if not cco_original or not cco_corrigida:
            return {
                'success': False,
                'error': 'Uma ou ambas as CCOs não foram fornecidas',
                'tem_original': bool(cco_original),
                'tem_corrigida': bool(cco_corrigida)
            }
        
        try:
            # Comparar campos raiz (excluindo correcoesMonetarias)
            diferencas_raiz = self._comparar_campos_raiz(cco_original, cco_corrigida)
            
            # Comparar correções monetárias
            analise_correcoes = self._comparar_correcoes_monetarias(
                cco_original.get('correcoesMonetarias', []),
                cco_corrigida.get('correcoesMonetarias', [])
            )
            
            # Calcular impacto financeiro
            impacto_financeiro = self._calcular_impacto_financeiro(cco_original, cco_corrigida)
            
            # Gerar resumo executivo
            resumo = self._gerar_resumo_executivo(diferencas_raiz, analise_correcoes, impacto_financeiro)
            
            return {
                'success': True,
                'diferencas_raiz': diferencas_raiz,
                'analise_correcoes': analise_correcoes,
                'impacto_financeiro': impacto_financeiro,
                'resumo': resumo,
                'metadata': {
                    'cco_id': cco_original.get('_id'),
                    'data_comparacao': datetime.now().isoformat(),
                    'versao_original': cco_original.get('version', 1),
                    'versao_corrigida': cco_corrigida.get('version', 1)
                }
            }
            
        except Exception as e:
            logger.error(f"Erro ao comparar CCOs: {e}")
            return {'success': False, 'error': str(e)}
    
    def _comparar_campos_raiz(self, original: Dict[str, Any], 
                              corrigida: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Compara campos do nível raiz das CCOs
        """
        diferencas = []
        
        # Obter todos os campos únicos de ambos documentos
        todos_campos = set(original.keys()) | set(corrigida.keys())
        
        for campo in sorted(todos_campos):
            # Ignorar campos específicos
            if campo in self.CAMPOS_IGNORAR or campo == 'correcoesMonetarias':
                continue
            
            valor_orig = original.get(campo)
            valor_corr = corrigida.get(campo)
            
            # Comparar valores
            diferenca = self._comparar_valores(campo, valor_orig, valor_corr)
            if diferenca:
                diferencas.append(diferenca)
        
        return diferencas
    
    def _comparar_valores(self, campo: str, valor_orig: Any, 
                          valor_corr: Any) -> Optional[Dict[str, Any]]:
        """
        Compara dois valores e retorna a diferença se houver
        """
        # Converter valores para comparação
        val_orig_conv = self._converter_valor(valor_orig)
        val_corr_conv = self._converter_valor(valor_corr)
        
        # Verificar se são iguais
        if self._valores_iguais(val_orig_conv, val_corr_conv, campo):
            return None
        
        # Calcular diferença numérica se aplicável
        diferenca_numerica = None
        percentual = None
        
        if campo in self.CAMPOS_MONETARIOS:
            try:
                val_orig_float = float(val_orig_conv) if val_orig_conv is not None else 0
                val_corr_float = float(val_corr_conv) if val_corr_conv is not None else 0
                diferenca_numerica = val_corr_float - val_orig_float
                if val_orig_float != 0:
                    percentual = (diferenca_numerica / val_orig_float) * 100
            except (ValueError, TypeError):
                pass
        
        return {
            'campo': campo,
            'label': self.LABELS_CAMPOS.get(campo, campo),
            'valor_original': val_orig_conv,
            'valor_corrigido': val_corr_conv,
            'diferenca_numerica': diferenca_numerica,
            'percentual': percentual,
            'tipo_campo': self._classificar_campo(campo),
            'is_monetario': campo in self.CAMPOS_MONETARIOS,
            'is_data': campo in self.CAMPOS_DATA
        }
    
    def _comparar_correcoes_monetarias(self, correcoes_orig: List[Dict], 
                                        correcoes_corr: List[Dict]) -> Dict[str, Any]:
        """
        Analisa diferenças entre arrays de correções monetárias
        """
        qtd_orig = len(correcoes_orig)
        qtd_corr = len(correcoes_corr)
        
        # Identificar correções novas, removidas e modificadas
        correcoes_novas = []
        correcoes_removidas = []
        correcoes_modificadas = []
        correcoes_mantidas = []
        
        # Criar índice por tipo+data para comparação
        idx_orig = {self._criar_chave_correcao(c): c for c in correcoes_orig}
        idx_corr = {self._criar_chave_correcao(c): c for c in correcoes_corr}
        
        # Encontrar novas correções
        for chave, correcao in idx_corr.items():
            if chave not in idx_orig:
                correcoes_novas.append(self._processar_correcao(correcao, 'NOVA'))
        
        # Encontrar correções removidas
        for chave, correcao in idx_orig.items():
            if chave not in idx_corr:
                correcoes_removidas.append(self._processar_correcao(correcao, 'REMOVIDA'))
        
        # Comparar correções existentes em ambos
        for chave in idx_orig.keys() & idx_corr.keys():
            orig = idx_orig[chave]
            corr = idx_corr[chave]
            
            diferencas = self._comparar_campos_correcao(orig, corr)
            if diferencas:
                correcoes_modificadas.append({
                    'chave': chave,
                    'tipo': orig.get('tipo'),
                    'data_correcao': self._formatar_data(orig.get('dataCorrecao')),
                    'diferencas': diferencas,
                    'correcao_original': self._processar_correcao(orig, 'ORIGINAL'),
                    'correcao_corrigida': self._processar_correcao(corr, 'CORRIGIDA')
                })
            else:
                correcoes_mantidas.append(self._processar_correcao(orig, 'MANTIDA'))
        
        # Timeline comparativa
        timeline_orig = self._construir_timeline(correcoes_orig)
        timeline_corr = self._construir_timeline(correcoes_corr)
        
        return {
            'qtd_original': qtd_orig,
            'qtd_corrigida': qtd_corr,
            'diferenca_quantidade': qtd_corr - qtd_orig,
            'correcoes_novas': correcoes_novas,
            'correcoes_removidas': correcoes_removidas,
            'correcoes_modificadas': correcoes_modificadas,
            'correcoes_mantidas': correcoes_mantidas,
            'timeline_original': timeline_orig,
            'timeline_corrigida': timeline_corr,
            'resumo_tipos': self._resumir_tipos(correcoes_orig, correcoes_corr)
        }
    
    def _criar_chave_correcao(self, correcao: Dict) -> str:
        """Cria chave única para identificar uma correção"""
        tipo = correcao.get('tipo', '')
        data = str(correcao.get('dataCorrecao', ''))[:10]  # Apenas data sem hora
        return f"{tipo}_{data}"
    
    def _processar_correcao(self, correcao: Dict, status: str) -> Dict[str, Any]:
        """Processa uma correção para exibição"""
        correcao_processada = {
            'status': status,
            'tipo': correcao.get('tipo'),
            'subTipo': correcao.get('subTipo'),
            'dataCorrecao': self._formatar_data(correcao.get('dataCorrecao')),
            'dataCriacaoCorrecao': self._formatar_data(correcao.get('dataCriacaoCorrecao')),
            'valorReconhecidoComOH': self._converter_valor(correcao.get('valorReconhecidoComOH')),
            'valorReconhecidoComOhOriginal': self._converter_valor(correcao.get('valorReconhecidoComOhOriginal')),
            'diferencaValor': self._converter_valor(correcao.get('diferencaValor')),
            'taxaCorrecao': self._converter_valor(correcao.get('taxaCorrecao')),
            'igpmAcumulado': self._converter_valor(correcao.get('igpmAcumulado')),
            'igpmAcumuladoReais': self._converter_valor(correcao.get('igpmAcumuladoReais')),
            'observacao': correcao.get('observacao'),
            'ativo': correcao.get('ativo', True),
            'transferencia': correcao.get('transferencia', False),
            'dados_completos': {k: self._converter_valor(v) for k, v in correcao.items()}
        }
        
        if correcao_processada['tipo'] == 'RECUPERACAO':
            correcao_processada['valorRecuperado'] = self._converter_valor(correcao.get('valorRecuperado', 0))
            correcao_processada['valorRecuperadoTotal'] = self._converter_valor(correcao.get('valorRecuperadoTotal', 0))
        
        return correcao_processada 
    
    def _comparar_campos_correcao(self, orig: Dict, corr: Dict) -> List[Dict]:
        """Compara campos de uma correção"""
        diferencas = []
        
        todos_campos = set(orig.keys()) | set(corr.keys())
        
        for campo in todos_campos:
            if campo in {'dataCriacaoCorrecao'}:  # Campos que sempre mudam
                continue
                
            val_orig = self._converter_valor(orig.get(campo))
            val_corr = self._converter_valor(corr.get(campo))
            
            if not self._valores_iguais(val_orig, val_corr, campo):
                diferencas.append({
                    'campo': campo,
                    'label': self.LABELS_CAMPOS.get(campo, campo),
                    'valor_original': val_orig,
                    'valor_corrigido': val_corr
                })
        
        return diferencas
    
    def _construir_timeline(self, correcoes: List[Dict]) -> List[Dict]:
        """Constrói timeline ordenada de correções"""
        timeline = []
        
        for i, corr in enumerate(correcoes):
            timeline.append({
                'indice': i,
                'tipo': corr.get('tipo'),
                'subTipo': corr.get('subTipo'),
                'dataCorrecao': self._formatar_data(corr.get('dataCorrecao')),
                'valorReconhecidoComOH': self._converter_valor(corr.get('valorReconhecidoComOH')),
                'diferencaValor': self._converter_valor(corr.get('diferencaValor')),
                'taxaCorrecao': self._converter_valor(corr.get('taxaCorrecao'))
            })
        
        return timeline
    
    def _resumir_tipos(self, correcoes_orig: List[Dict], 
                       correcoes_corr: List[Dict]) -> Dict[str, Any]:
        """Resume tipos de correções em ambas versões"""
        def contar_tipos(correcoes):
            tipos = {}
            for c in correcoes:
                tipo = c.get('tipo', 'DESCONHECIDO')
                tipos[tipo] = tipos.get(tipo, 0) + 1
            return tipos
        
        tipos_orig = contar_tipos(correcoes_orig)
        tipos_corr = contar_tipos(correcoes_corr)
        
        todos_tipos = set(tipos_orig.keys()) | set(tipos_corr.keys())
        
        return {
            tipo: {
                'original': tipos_orig.get(tipo, 0),
                'corrigida': tipos_corr.get(tipo, 0),
                'diferenca': tipos_corr.get(tipo, 0) - tipos_orig.get(tipo, 0)
            }
            for tipo in sorted(todos_tipos)
        }
    
    def _calcular_impacto_financeiro(self, original: Dict, corrigida: Dict) -> Dict[str, Any]:
        """Calcula impacto financeiro total da correção"""

        def obter_valor_final(cco):
            correcoes = cco.get('correcoesMonetarias', [])

            # Procura da correção mais recente para a mais antiga até
            # encontrar uma que realmente possua valorReconhecidoComOH.
            #
            # Antes o código usava obrigatoriamente correcoes[-1] e,
            # quando essa última correção não possuía o campo,
            # retornava 0. Isso zerava o Impacto Financeiro.
            for correcao in reversed(correcoes):
                if 'valorReconhecidoComOH' not in correcao:
                    continue

                valor = self._converter_valor(
                    correcao.get('valorReconhecidoComOH')
                )

                if valor is not None:
                    return valor

            # Se nenhuma correção possuir valorReconhecidoComOH,
            # usa o valor da própria raiz da CCO.
            valor_raiz = self._converter_valor(
                cco.get('valorReconhecidoComOH', 0)
            )

            return valor_raiz if valor_raiz is not None else 0

        def obter_valor_inicial(cco):
            valor = self._converter_valor(
                cco.get('valorReconhecidoComOH', 0)
            )
            return valor if valor is not None else 0

        valor_inicial_orig = obter_valor_inicial(original)
        valor_final_orig = obter_valor_final(original)
        valor_final_corr = obter_valor_final(corrigida)

        diferenca_total = valor_final_corr - valor_final_orig
        percentual_total = (
            diferenca_total / valor_final_orig * 100
        ) if valor_final_orig else 0

        # Calcular evolução das correções
        evolucao_orig = self._calcular_evolucao_correcoes(original)
        evolucao_corr = self._calcular_evolucao_correcoes(corrigida)

        return {
            'valor_inicial': valor_inicial_orig,
            'valor_final_original': valor_final_orig,
            'valor_final_corrigido': valor_final_corr,
            'diferenca_total': diferenca_total,
            'percentual_total': percentual_total,
            'evolucao_original': evolucao_orig,
            'evolucao_corrigida': evolucao_corr,
            'ganho_correcao': valor_final_corr - valor_inicial_orig,
            'ganho_correcao_original': valor_final_orig - valor_inicial_orig
        }

    def _calcular_evolucao_correcoes(self, cco: Dict) -> List[Dict]:
        """Calcula evolução dos valores através das correções"""
        evolucao = []
        valor_base = self._converter_valor(cco.get('valorReconhecidoComOH', 0))
        
        evolucao.append({
            'etapa': 'Valor Inicial',
            'tipo': 'BASE',
            'valor': valor_base,
            'diferenca': 0
        })
        
        for i, correcao in enumerate(cco.get('correcoesMonetarias', [])):
            valor_atual = self._converter_valor(correcao.get('valorReconhecidoComOH', 0))
            diferenca = self._converter_valor(correcao.get('diferencaValor', 0))
            
            evolucao.append({
                'etapa': f"Correção {i + 1}",
                'tipo': correcao.get('tipo'),
                'data': self._formatar_data(correcao.get('dataCorrecao')),
                'valor': valor_atual,
                'diferenca': diferenca,
                'taxa': self._converter_valor(correcao.get('taxaCorrecao'))
            })
        
        return evolucao
    
    def _gerar_resumo_executivo(self, diferencas_raiz: List, 
                                 analise_correcoes: Dict,
                                 impacto_financeiro: Dict) -> Dict[str, Any]:
        """Gera resumo executivo das diferenças"""
        
        # Contar alterações por categoria
        campos_monetarios_alterados = [d for d in diferencas_raiz if d.get('is_monetario')]
        campos_outros_alterados = [d for d in diferencas_raiz if not d.get('is_monetario')]
        
        return {
            'total_campos_alterados': len(diferencas_raiz),
            'campos_monetarios_alterados': len(campos_monetarios_alterados),
            'campos_outros_alterados': len(campos_outros_alterados),
            'novas_correcoes': len(analise_correcoes.get('correcoes_novas', [])),
            'correcoes_removidas': len(analise_correcoes.get('correcoes_removidas', [])),
            'correcoes_modificadas': len(analise_correcoes.get('correcoes_modificadas', [])),
            'impacto_financeiro': impacto_financeiro.get('diferenca_total', 0),
            'impacto_percentual': impacto_financeiro.get('percentual_total', 0),
            'tem_alteracoes_significativas': (
                len(diferencas_raiz) > 0 or 
                analise_correcoes.get('diferenca_quantidade', 0) != 0
            )
        }
    
    def _converter_valor(self, valor: Any) -> Any:
        """Converte valor do MongoDB para tipo Python"""
        if valor is None:
            return None
        
        if isinstance(valor, Decimal128):
            return float(valor.to_decimal())
        
        if isinstance(valor, Decimal):
            return float(valor)
        
        if hasattr(valor, 'as_datetime'):  # ISODate
            return valor.as_datetime()
        
        if hasattr(valor, 'isoformat'):  # datetime
            return valor.isoformat()
        
        return valor
    
    def _formatar_data(self, valor: Any) -> Optional[str]:
        """Formata data para exibição"""
        if not valor:
            return None
        
        try:
            if isinstance(valor, str):
                return valor[:19].replace('T', ' ')
            if hasattr(valor, 'strftime'):
                return valor.strftime('%d/%m/%Y %H:%M')
            return str(valor)
        except:
            return str(valor) if valor else None
    
    def _valores_iguais(self, val1: Any, val2: Any, campo: str = '') -> bool:
        """Verifica se dois valores são iguais, com tolerância para floats"""
        if val1 is None and val2 is None:
            return True
        
        if val1 is None or val2 is None:
            return False
        
        # Para valores monetários, usar tolerância
        if campo in self.CAMPOS_MONETARIOS:
            try:
                return abs(float(val1) - float(val2)) < 0.01
            except (ValueError, TypeError):
                pass
        
        # Comparação direta
        return val1 == val2
    
    def _classificar_campo(self, campo: str) -> str:
        """Classifica o tipo do campo"""
        if campo in self.CAMPOS_MONETARIOS:
            return 'MONETARIO'
        if campo in self.CAMPOS_DATA:
            return 'DATA'
        if campo in {'flgRecuperado', 'ativo', 'transferencia'}:
            return 'BOOLEANO'
        if campo in {'remessa', 'remessaExposicao', 'exercicio', 'periodo', 'quantidadeLancamento', 'version'}:
            return 'NUMERICO'
        return 'TEXTO'