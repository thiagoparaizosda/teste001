"""
Serviço para edição manual de CCOs
Permite alteração de atributos e criação de correções do tipo RETIFICACAO
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from copy import deepcopy
from decimal import Decimal
from bson.decimal128 import Decimal128

logger = logging.getLogger(__name__)


class CCOEditorService:
    """
    Serviço responsável por gerenciar edição manual de CCOs
    """
    
    # Campos que NÃO podem ser alterados na raiz
    CAMPOS_BLOQUEADOS_RAIZ = {
        '_id', 'contratoCpp', 'campo', 'remessa', 'remessaExposicao',
        'faseRemessa', 'dataReconhecimento', 'exercicio', 'periodo',
        'origemDosGastos', 'idRemessaGeradora', 'versionRemessaGeradora',
        'mesReconhecimento', 'anoReconhecimento', 'mesAnoReferencia',
        'faseRespostaGestora', 'version', '_class'
    }
    
    # Campos que NÃO podem ser alterados nas correções monetárias
    CAMPOS_BLOQUEADOS_CORRECAO = {
        'contrato', 'campo', 'faseRemessa'
    }
    
    # Campos monetários (devem ser tratados como Decimal128)
    CAMPOS_MONETARIOS = {
        'valorLancamentoTotal', 'valorNaoReconhecido', 'valorReconhecido',
        'valorReconhecivel', 'valorNaoPassivelRecuperacao', 'valorReconhecidoExploracao',
        'valorReconhecidoProducao', 'valorRecusado', 'overHeadExploracao',
        'overHeadProducao', 'overHeadTotal', 'valorReconhecidoComOH',
        'diferencaValor', 'valorReconhecidoComOhOriginal', 'taxaCorrecao',
        'igpmAcumulado', 'igpmAcumuladoReais', 'valorRecuperado', 'valorRecuperadoTotal'
    }
    
    # Campos inteiros
    CAMPOS_INTEIROS = {
        'remessa', 'remessaExposicao', 'exercicio', 'periodo',
        'quantidadeLancamento', 'mesReconhecimento', 'anoReconhecimento'
    }
    
    # Campos booleanos
    CAMPOS_BOOLEANOS = {
        'flgRecuperado', 'ativo', 'transferencia'
    }
    
    # Labels amigáveis para campos
    LABELS_CAMPOS = {
        '_id': 'ID da CCO',
        'contratoCpp': 'Contrato CPP',
        'contrato': 'Contrato',
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
    
    def __init__(self, db_connection, db_connection_prd=None):
        """
        Inicializa o serviço
        
        Args:
            db_connection: Conexão com MongoDB local/temporário
            db_connection_prd: Conexão com MongoDB de produção
        """
        self.db = db_connection
        self.db_prd = db_connection_prd
        logger.info("CCOEditorService inicializado")
    
    def buscar_cco_para_edicao(self, cco_id: str, forcar_producao: bool = False) -> Dict[str, Any]:
        """
        Busca uma CCO e prepara os dados para edição

        Se já existir um rascunho de edição pendente (coleção
        conta_custo_oleo_corrigida_entity) para essa CCO, ele é usado como
        base em vez do documento de produção — assim reabrir a edição não
        descarta alterações já salvas. Use forcar_producao=True para ignorar
        o rascunho pendente e carregar sempre o original de produção.

        Args:
            cco_id: ID da CCO
            forcar_producao: quando True, ignora rascunho pendente e busca
                sempre o documento original em produção

        Returns:
            Dict com dados da CCO e metadados para edição
        """
        try:
            rascunho_pendente = None
            if not forcar_producao:
                rascunho_pendente = self.db.conta_custo_oleo_corrigida_entity.find_one({'_id': cco_id})

            if rascunho_pendente:
                cco = rascunho_pendente
                tem_rascunho_pendente = True
            else:
                # Buscar CCO em produção
                cco = self.db_prd.conta_custo_oleo_entity.find_one({'_id': cco_id})
                tem_rascunho_pendente = False

            if not cco:
                return {'success': False, 'error': 'CCO não encontrada'}

            # Preparar estrutura de campos editáveis
            campos_raiz = self._preparar_campos_editaveis_raiz(cco)
            correcoes = self._preparar_correcoes_editaveis(cco.get('correcoesMonetarias', []))

            # Obter valores da última correção ou raiz para nova RETIFICACAO
            valores_base_retificacao = self._obter_valores_base_retificacao(cco)

            return {
                'success': True,
                'cco': self._converter_cco_para_json(cco),
                'campos_raiz': campos_raiz,
                'correcoes': correcoes,
                'valores_base_retificacao': valores_base_retificacao,
                'campos_bloqueados_raiz': list(self.CAMPOS_BLOQUEADOS_RAIZ),
                'campos_bloqueados_correcao': list(self.CAMPOS_BLOQUEADOS_CORRECAO),
                'labels': self.LABELS_CAMPOS,
                'tem_rascunho_pendente': tem_rascunho_pendente
            }

        except Exception as e:
            logger.error(f"Erro ao buscar CCO para edição {cco_id}: {e}")
            return {'success': False, 'error': str(e)}

    def descartar_rascunho_edicao(self, cco_id: str) -> Dict[str, Any]:
        """Remove o rascunho de edição pendente (se existir), voltando ao original de produção."""
        try:
            resultado = self.db.conta_custo_oleo_corrigida_entity.delete_one({'_id': cco_id})
            return {'success': True, 'removido': resultado.deleted_count > 0}
        except Exception as e:
            logger.error(f"Erro ao descartar rascunho de edição da CCO {cco_id}: {e}")
            return {'success': False, 'error': str(e)}
    
    def _preparar_campos_editaveis_raiz(self, cco: Dict) -> List[Dict]:
        """Prepara lista de campos editáveis na raiz da CCO"""
        campos = []
        
        # Ordem preferencial dos campos
        ordem_campos = [
            'quantidadeLancamento', 'valorLancamentoTotal', 'valorReconhecido',
            'valorNaoReconhecido', 'valorReconhecivel', 'valorNaoPassivelRecuperacao',
            'valorReconhecidoExploracao', 'valorReconhecidoProducao', 'valorRecusado',
            'overHeadExploracao', 'overHeadProducao', 'overHeadTotal',
            'valorReconhecidoComOH', 'flgRecuperado', 'dataLancamento'
        ]
        
        for campo in ordem_campos:
            if campo in cco and campo not in self.CAMPOS_BLOQUEADOS_RAIZ:
                campos.append(self._criar_campo_editavel(campo, cco.get(campo)))
        
        # Adicionar outros campos não listados
        for campo, valor in cco.items():
            if campo not in self.CAMPOS_BLOQUEADOS_RAIZ and campo not in ordem_campos:
                if campo != 'correcoesMonetarias':
                    campos.append(self._criar_campo_editavel(campo, valor))
        
        return campos
    
    def _preparar_correcoes_editaveis(self, correcoes: List[Dict]) -> List[Dict]:
        """Prepara lista de correções com campos editáveis"""
        correcoes_editaveis = []
        
        for idx, correcao in enumerate(correcoes):
            campos_editaveis = []
            
            for campo, valor in correcao.items():
                # Campos bloqueados (contrato/campo/faseRemessa) são expostos como
                # somente-leitura no template para permitir validação contra a raiz,
                # mas permanecem não editáveis (editavel=False via _criar_campo_editavel).
                campos_editaveis.append(self._criar_campo_editavel(campo, valor))
            
            correcoes_editaveis.append({
                'indice': idx,
                'tipo': correcao.get('tipo', 'DESCONHECIDO'),
                'subTipo': correcao.get('subTipo', ''),
                'dataCorrecao': self._formatar_data(correcao.get('dataCorrecao')),
                'campos': campos_editaveis,
                'dados_completos': self._converter_valores_para_json(correcao)
            })
        
        return correcoes_editaveis
    
    def _criar_campo_editavel(self, nome: str, valor: Any) -> Dict:
        """Cria estrutura de campo editável"""
        tipo = self._identificar_tipo_campo(nome, valor)
        
        return {
            'nome': nome,
            'label': self.LABELS_CAMPOS.get(nome, nome),
            'valor': self._converter_valor_para_json(valor),
            'tipo': tipo,
            'editavel': nome not in self.CAMPOS_BLOQUEADOS_RAIZ and nome not in self.CAMPOS_BLOQUEADOS_CORRECAO,
            'is_monetario': nome in self.CAMPOS_MONETARIOS,
            'is_booleano': nome in self.CAMPOS_BOOLEANOS,
            'is_inteiro': nome in self.CAMPOS_INTEIROS
        }
    
    def _identificar_tipo_campo(self, nome: str, valor: Any) -> str:
        """Identifica o tipo de um campo"""
        if nome in self.CAMPOS_MONETARIOS:
            return 'monetario'
        if nome in self.CAMPOS_BOOLEANOS:
            return 'booleano'
        if nome in self.CAMPOS_INTEIROS:
            return 'inteiro'
        if isinstance(valor, (datetime,)) or 'data' in nome.lower():
            return 'data'
        return 'texto'
    
    def _obter_valores_base_retificacao(self, cco: Dict) -> Dict:
        """Obtém valores base para criar nova correção RETIFICACAO"""
        correcoes = cco.get('correcoesMonetarias', [])
        
        # Usar última correção ou raiz
        if correcoes:
            fonte = correcoes[-1]
        else:
            fonte = cco
        
        # Campos a copiar para RETIFICACAO
        campos_copiar = [
            'valorReconhecido', 'valorReconhecidoComOH', 'overHeadExploracao',
            'overHeadProducao', 'overHeadTotal', 'quantidadeLancamento',
            'valorLancamentoTotal', 'valorNaoPassivelRecuperacao', 'valorReconhecivel',
            'valorNaoReconhecido', 'valorReconhecidoExploracao', 'valorReconhecidoProducao',
            'taxaCorrecao', 'igpmAcumulado', 'igpmAcumuladoReais'
        ]
        
        valores = {
            'tipo': 'RETIFICACAO',
            'subTipo': 'MANUAL',
            'contrato': cco.get('contratoCpp', ''),
            'campo': cco.get('campo', ''),
            'faseRemessa': cco.get('faseRemessa', ''),
            'ativo': True,
            'transferencia': False,
            'observacao': ''
        }
        
        for campo in campos_copiar:
            if campo in fonte:
                valores[campo] = self._converter_valor_para_json(fonte[campo])
            elif campo in cco:
                valores[campo] = self._converter_valor_para_json(cco[campo])

        # valorReconhecidoComOhOriginal da nova correção segue a mesma regra
        # aplicada às correções existentes: é o valorReconhecidoComOH da
        # correção anterior (ou da raiz, se ainda não há correções).
        if 'valorReconhecidoComOH' in fonte:
            valores['valorReconhecidoComOhOriginal'] = self._converter_valor_para_json(fonte['valorReconhecidoComOH'])
        elif 'valorReconhecidoComOH' in cco:
            valores['valorReconhecidoComOhOriginal'] = self._converter_valor_para_json(cco['valorReconhecidoComOH'])

        return valores
    
    def aplicar_edicao(self, cco_id: str, alteracoes: Dict[str, Any], 
                       user_id: str, observacoes: str = '') -> Dict[str, Any]:
        """
        Aplica edições na CCO e salva na coleção temporária
        
        Args:
            cco_id: ID da CCO original
            alteracoes: Dict com alterações a aplicar
                - alteracoes_raiz: Dict com alterações nos campos raiz
                - alteracoes_correcoes: List com alterações nas correções existentes
                - nova_retificacao: Dict com dados da nova correção RETIFICACAO (opcional)
            user_id: ID do usuário que está editando
            observacoes: Observações gerais da edição
            
        Returns:
            Dict com resultado da operação
        """
        try:
            # Buscar CCO original
            cco_original = self.db_prd.conta_custo_oleo_entity.find_one({'_id': cco_id})
            if not cco_original:
                return {'success': False, 'error': 'CCO não encontrada'}
            
            # Criar cópia para edição
            cco_editada = deepcopy(cco_original)
            
            # Registrar alterações realizadas
            registro_alteracoes = []
            
            # Aplicar alterações na raiz
            if alteracoes.get('alteracoes_raiz'):
                resultado_raiz = self._aplicar_alteracoes_raiz(
                    cco_editada, alteracoes['alteracoes_raiz'], registro_alteracoes
                )
                if not resultado_raiz['success']:
                    return resultado_raiz
            
            # Aplicar alterações nas correções existentes
            if alteracoes.get('alteracoes_correcoes'):
                resultado_correcoes = self._aplicar_alteracoes_correcoes(
                    cco_editada, alteracoes['alteracoes_correcoes'], registro_alteracoes
                )
                if not resultado_correcoes['success']:
                    return resultado_correcoes
            
            # Adicionar nova correção RETIFICACAO se fornecida
            if alteracoes.get('nova_correcao'):
                resultado_retificacao = self._adicionar_correcao(
                    cco_editada, alteracoes['nova_correcao'], 
                    cco_original, observacoes, registro_alteracoes
                )
                if not resultado_retificacao['success']:
                    return resultado_retificacao
            
            # Gerar session_id único
            session_id = str(uuid.uuid4())
            
            # Verificar se já existe edição pendente para esta CCO
            existente = self.db.conta_custo_oleo_corrigida_entity.find_one({'_id': cco_id})
            if existente:
                # Remover edição anterior
                self.db.conta_custo_oleo_corrigida_entity.delete_one({'_id': cco_id})
            
            # Adicionar metadados da edição
            cco_editada['session_id'] = session_id
            cco_editada['status_promocao'] = 'PENDENTE'
            cco_editada['data_criacao_correcao'] = datetime.now(timezone.utc)
            cco_editada['tipo_edicao'] = 'MANUAL'
            cco_editada['usuario_edicao'] = user_id
            cco_editada['observacao'] = observacoes
            cco_editada['registro_alteracoes'] = registro_alteracoes
            
            # Salvar na coleção temporária
            self.db.conta_custo_oleo_corrigida_entity.insert_one(cco_editada)
            
            # Salvar sessão de edição
            self._salvar_sessao_edicao(session_id, cco_id, user_id, alteracoes, 
                                        registro_alteracoes, observacoes)
            
            return {
                'success': True,
                'session_id': session_id,
                'cco_id': cco_id,
                'total_alteracoes': len(registro_alteracoes),
                'registro_alteracoes': registro_alteracoes,
                'message': 'Edição salva com sucesso. Use a funcionalidade de promoção para aplicar em produção.'
            }
            
        except Exception as e:
            logger.error(f"Erro ao aplicar edição na CCO {cco_id}: {e}")
            return {'success': False, 'error': str(e)}
    
    def _aplicar_alteracoes_raiz(self, cco: Dict, alteracoes: Dict, 
                                  registro: List) -> Dict[str, Any]:
        """Aplica alterações nos campos raiz da CCO"""
        for campo, novo_valor in alteracoes.items():
            if campo in self.CAMPOS_BLOQUEADOS_RAIZ:
                return {
                    'success': False, 
                    'error': f'Campo "{campo}" não pode ser alterado'
                }
            
            valor_antigo = cco.get(campo)
            valor_convertido = self._converter_valor_de_json(campo, novo_valor)
            
            if not self._valores_iguais(valor_antigo, valor_convertido):
                cco[campo] = valor_convertido
                registro.append({
                    'tipo': 'ALTERACAO_RAIZ',
                    'campo': campo,
                    'label': self.LABELS_CAMPOS.get(campo, campo),
                    'valor_antigo': self._converter_valor_para_json(valor_antigo),
                    'valor_novo': novo_valor,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                })
        
        return {'success': True}
    
    def _aplicar_alteracoes_correcoes(self, cco: Dict, alteracoes: List[Dict], 
                                       registro: List) -> Dict[str, Any]:
        """Aplica alterações nas correções monetárias existentes"""
        correcoes = cco.get('correcoesMonetarias', [])
        
        for alt in alteracoes:
            indice = alt.get('indice')
            campos = alt.get('campos', {})
            
            if indice is None or indice >= len(correcoes):
                return {
                    'success': False,
                    'error': f'Índice de correção inválido: {indice}'
                }
            
            correcao = correcoes[indice]
            
            for campo, novo_valor in campos.items():
                if campo in self.CAMPOS_BLOQUEADOS_CORRECAO:
                    return {
                        'success': False,
                        'error': f'Campo "{campo}" não pode ser alterado em correções monetárias'
                    }
                
                valor_antigo = correcao.get(campo)
                valor_convertido = self._converter_valor_de_json(campo, novo_valor)
                
                if not self._valores_iguais(valor_antigo, valor_convertido):
                    correcao[campo] = valor_convertido
                    registro.append({
                        'tipo': 'ALTERACAO_CORRECAO',
                        'indice_correcao': indice,
                        'tipo_correcao': correcao.get('tipo'),
                        'campo': campo,
                        'label': self.LABELS_CAMPOS.get(campo, campo),
                        'valor_antigo': self._converter_valor_para_json(valor_antigo),
                        'valor_novo': novo_valor,
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    })
        
        return {'success': True}
    
    def _adicionar_correcao(self, cco: Dict, correcao: Dict,
                                cco_original: Dict, observacoes: str,
                                registro: List) -> Dict[str, Any]:
        """Adiciona nova correção RETIFICACAO"""
        
        # Inicializar array de correções se não existir
        if 'correcoesMonetarias' not in cco:
            cco['correcoesMonetarias'] = []
        
        # Obter valores base da última correção ou raiz
        valores_base = self._obter_valores_base_retificacao(cco_original)
        
        agora_utc = datetime.now(timezone.utc)
        data_correcao_formatada = agora_utc.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + '+0000'

        # Criar nova correção # TODO analisar com mais detalhes se essas recuperações de valores está correta.
        nova_correcao = {
            'tipo': correcao.get('tipo', 'RETIFICACAO'),
            'subTipo': correcao.get('subTipo', 'MANUAL'),
            'contrato': cco.get('contratoCpp', ''),
            'campo': cco.get('campo', ''),
            'dataCorrecao': data_correcao_formatada,
            'dataCriacaoCorrecao': agora_utc,
            'observacao': correcao.get('observacao', observacoes or 'Retificação manual via Portal'),
            'valorReconhecido': valores_base.get('valorReconhecido', 0),
            'valorReconhecidoComOH': valores_base.get('valorReconhecidoComOH', 0),
            'overHeadExploracao': valores_base.get('overHeadExploracao', 0),
            'overHeadProducao': valores_base.get('overHeadProducao', 0),
            'overHeadTotal': valores_base.get('overHeadTotal', 0),
            'diferencaValor': 0,
            'valorReconhecidoComOhOriginal': valores_base.get('valorReconhecidoComOH', 0),
            'valorRecuperado': 0,
            'valorRecuperadoTotal': valores_base.get('valorRecuperadoTotal', 0),
            'faseRemessa': cco.get('faseRemessa', ''),
            'ativo': bool(correcao.get('ativo', True)),
            'quantidadeLancamento': cco.get('quantidadeLancamento', 0),
            'valorLancamentoTotal': cco.get('valorLancamentoTotal', 0),
            'valorNaoPassivelRecuperacao': cco.get('valorNaoPassivelRecuperacao', 0),
            'valorReconhecivel': cco.get('valorReconhecivel', 0),
            'valorNaoReconhecido': valores_base.get('valorNaoReconhecido', cco.get('valorReconhecivel', 0)), # analisar melhor
            'valorReconhecidoExploracao': valores_base.get('valorReconhecidoExploracao', 0),
            'valorReconhecidoProducao': valores_base.get('valorReconhecidoProducao', 0),
            'igpmAcumulado': valores_base.get('igpmAcumulado', 0),
            'igpmAcumuladoReais': valores_base.get('igpmAcumuladoReais', 0),
            'transferencia': bool(correcao.get('transferencia', False))
        }
        
        # Campos que devem ser copiados/atualizados
        campos_valor = [
            'valorReconhecido', 'valorReconhecidoComOH', 'overHeadExploracao',
            'overHeadProducao', 'overHeadTotal', 'quantidadeLancamento',
            'valorLancamentoTotal', 'valorNaoPassivelRecuperacao', 'valorReconhecivel',
            'valorNaoReconhecido', 'valorReconhecidoExploracao', 'valorReconhecidoProducao',
            'taxaCorrecao', 'igpmAcumulado', 'igpmAcumuladoReais'
        ]
        
        # Calcular diferença de valor (aritmética em Decimal, nunca em float,
        # para não introduzir arredondamento em valores financeiros)
        valor_oh_anterior = self._converter_valor_para_decimal(valores_base.get('valorReconhecidoComOH', 0))

        for campo in campos_valor:
            if campo in correcao:
                valor_convertido = self._converter_valor_de_json(campo, correcao[campo])
                nova_correcao[campo] = valor_convertido
            elif campo in valores_base:
                nova_correcao[campo] = self._converter_valor_de_json(campo, valores_base[campo])

        # Calcular valorReconhecidoComOhOriginal e diferencaValor
        valor_oh_novo = self._converter_valor_para_decimal(nova_correcao.get('valorReconhecidoComOH', 0))
        nova_correcao['valorReconhecidoComOhOriginal'] = Decimal128(valor_oh_anterior)
        nova_correcao['diferencaValor'] = Decimal128(abs(valor_oh_novo - valor_oh_anterior))
        
        if correcao.get('tipo', 'RETIFICACAO') == 'RECUPERACAO':
            nova_correcao['valorRecuperado'] = Decimal128(str(correcao.get('valorRecuperado', 0)))
            nova_correcao['valorRecuperadoTotal'] = Decimal128(str(correcao.get('valorRecuperadoTotal', 0)))
        else:
            del nova_correcao['valorRecuperado']
            del nova_correcao['valorRecuperadoTotal']
        
        # Adicionar correção
        cco['correcoesMonetarias'].append(nova_correcao)
        
        # Atualizar flgRecuperado se necessário
        if valor_oh_novo != 0 and cco.get('flgRecuperado', False):
            cco['flgRecuperado'] = False
            registro.append({
                'tipo': 'ALTERACAO_FLAG',
                'campo': 'flgRecuperado',
                'label': 'Recuperada',
                'valor_antigo': True,
                'valor_novo': False,
                'motivo': 'CCO reativada devido novo valor',
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
        
        registro.append({
            'tipo': 'NOVA_RETIFICACAO',
            'indice_correcao': len(cco['correcoesMonetarias']) - 1,
            # decimal.Decimal não é serializável em JSON/BSON diretamente; o registro é só
            # trilha de auditoria, então guarda como string (sem perder precisão) em vez de float.
            'valor_oh_anterior': format(valor_oh_anterior, 'f'),
            'valor_oh_novo': format(valor_oh_novo, 'f'),
            'diferenca': format(valor_oh_novo - valor_oh_anterior, 'f'),
            'observacao': nova_correcao['observacao'],
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
        return {'success': True}
    
    def _salvar_sessao_edicao(self, session_id: str, cco_id: str, user_id: str,
                              alteracoes: Dict, registro: List, observacoes: str):
        """Salva sessão de edição para histórico e auditoria"""
        sessao = {
            'session_id': session_id,
            'cco_id': cco_id,
            'user_id': user_id,
            'tipo': 'EDICAO_MANUAL',
            'status': 'PENDENTE',
            'created_at': datetime.now(timezone.utc),
            'updated_at': datetime.now(timezone.utc),
            'alteracoes_solicitadas': alteracoes,
            'registro_alteracoes': registro,
            'observacoes': observacoes,
            'total_alteracoes': len(registro)
        }
        
        self.db.cco_edit_sessions.insert_one(sessao)
    
    def obter_sessao_edicao(self, session_id: str) -> Dict[str, Any]:
        """Obtém detalhes de uma sessão de edição"""
        sessao = self.db.cco_edit_sessions.find_one({'session_id': session_id})
        if not sessao:
            return {'success': False, 'error': 'Sessão não encontrada'}
        
        return {
            'success': True,
            'sessao': self._converter_valores_para_json(sessao)
        }
    
    # Métodos auxiliares de conversão
    def _converter_valor_para_json(self, valor: Any) -> Any:
        """Converte valor MongoDB para JSON serializável

        Decimal128/Decimal são convertidos para string em notação fixa (não
        para float): float64 tem ~15-17 dígitos significativos, contra até 34
        do Decimal128, e valores financeiros não podem perder precisão só por
        terem sido lidos para exibição/edição.
        """
        if valor is None:
            return None
        if isinstance(valor, Decimal128):
            return format(valor.to_decimal(), 'f')
        if isinstance(valor, Decimal):
            return format(valor, 'f')
        if hasattr(valor, 'isoformat'):
            return valor.isoformat()
        return valor
    
    def _converter_valor_para_float(self, valor: Any) -> float:
        """Converte valor para float"""
        if valor is None:
            return 0.0
        if isinstance(valor, Decimal128):
            return float(valor.to_decimal())
        if isinstance(valor, (int, float, Decimal)):
            return float(valor)
        try:
            return float(valor)
        except:
            return 0.0

    def _converter_valor_para_decimal(self, valor: Any) -> Decimal:
        """Converte valor para Decimal, sem passar por float (evita perda de precisão)"""
        if valor is None:
            return Decimal('0')
        if isinstance(valor, Decimal128):
            return valor.to_decimal()
        if isinstance(valor, Decimal):
            return valor
        try:
            return Decimal(str(valor))
        except Exception:
            return Decimal('0')

    def _converter_valor_de_json(self, campo: str, valor: Any) -> Any:
        """Converte valor JSON para tipo MongoDB apropriado"""
        if valor is None:
            return None
        
        if campo == 'diferencaValor':
            # diferencaValor é sempre persistido como valor absoluto (nunca negativo).
            return Decimal128(str(abs(Decimal(str(valor)))))

        if campo in self.CAMPOS_MONETARIOS:
            return Decimal128(str(valor))
        
        if campo in self.CAMPOS_INTEIROS:
            return int(valor)
        
        if campo in self.CAMPOS_BOOLEANOS:
            return bool(valor)
        
        return valor
    
    def _converter_cco_para_json(self, cco: Dict) -> Dict:
        """Converte CCO inteira para JSON serializável"""
        return self._converter_valores_para_json(cco)
    
    def _converter_valores_para_json(self, obj: Any) -> Any:
        """Converte recursivamente valores para JSON"""
        if isinstance(obj, dict):
            return {k: self._converter_valores_para_json(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._converter_valores_para_json(item) for item in obj]
        return self._converter_valor_para_json(obj)
    
    def _valores_iguais(self, val1: Any, val2: Any) -> bool:
        """Compara dois valores com tolerância para floats"""
        v1 = self._converter_valor_para_float(val1) if isinstance(val1, (Decimal128, Decimal)) else val1
        v2 = self._converter_valor_para_float(val2) if isinstance(val2, (Decimal128, Decimal)) else val2
        
        if isinstance(v1, float) and isinstance(v2, float):
            return abs(v1 - v2) < 0.01
        
        return v1 == v2
    
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