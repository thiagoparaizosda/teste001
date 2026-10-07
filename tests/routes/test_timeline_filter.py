"""
Testes unitários para o endpoint de timeline filtrada por data de corte.

Testa:
- Validação de formato de data
- Filtro de eventos até data de corte
- Recalcuio de valores acumulados
- Estado temporal na resposta
- Casos de erro (CCO não encontrada, data inválida, etc.)
"""

import pytest
import json
from datetime import datetime, date
from unittest.mock import Mock, patch, MagicMock
from bson import Decimal128

from app.services.portal_service import PortalService


class TestTimelineFilterService:
    """Testes para o método get_timeline_with_cutoff do PortalService"""
    
    @pytest.fixture
    def portal_service(self):
        """Fixture para criar instância do PortalService com mock de BD"""
        with patch('app.services.portal_service.MongoClient'):
            service = PortalService("mongodb://test", "mongodb://test-prd")
            return service
    
    @pytest.fixture
    def cco_data_completo(self):
        """Fixture com dados completos de uma CCO com múltiplas correções"""
        return {
            '_id': 'CCO-001',
            'contratoCpp': 'CONTRATO-001',
            'campo': 'CAMPO-001',
            'remessa': 2024001,
            'faseRemessa': 'FASE-01',
            'exercicio': 2024,
            'periodo': 1,
            'dataLancamento': '2024-01-15',
            'dataReconhecimento': '2024-01-20',
            'quantidadeLancamento': 100,
            'valorReconhecido': Decimal128('1000.00'),
            'valorReconhecidoComOH': Decimal128('1100.00'),
            'overHeadTotal': Decimal128('100.00'),
            'valorLancamentoTotal': Decimal128('1000.00'),
            'valorReconhecivel': Decimal128('1000.00'),
            'valorNaoReconhecido': Decimal128('0.00'),
            'valorNaoPassivelRecuperacao': Decimal128('0.00'),
            'overHeadExploracao': Decimal128('50.00'),
            'overHeadProducao': Decimal128('50.00'),
            'valorReconhecidoExploracao': Decimal128('500.00'),
            'valorReconhecidoProducao': Decimal128('500.00'),
            'correcoesMonetarias': [
                {
                    'tipo': 'IPCA',
                    'subTipo': 'CORRECAO_AUTOMATICA',
                    'dataCorrecao': '2024-06-15',
                    'dataCriacaoCorrecao': '2024-06-16',
                    'taxaCorrecao': Decimal128('0.0423'),
                    'valorReconhecido': Decimal128('1042.30'),
                    'valorReconhecidoComOH': Decimal128('1146.53'),
                    'overHeadTotal': Decimal128('104.23'),
                    'diferencaValor': Decimal128('46.53'),
                    'igpmAcumulado': Decimal128('0.0423'),
                    'igpmAcumuladoReais': Decimal128('42.30'),
                    'ativo': True
                },
                {
                    'tipo': 'IGPM',
                    'subTipo': 'CORRECAO_AUTOMATICA',
                    'dataCorrecao': '2024-12-15',
                    'dataCriacaoCorrecao': '2024-12-16',
                    'taxaCorrecao': Decimal128('0.0312'),
                    'valorReconhecido': Decimal128('1074.82'),
                    'valorReconhecidoComOH': Decimal128('1182.30'),
                    'overHeadTotal': Decimal128('107.48'),
                    'diferencaValor': Decimal128('82.30'),
                    'igpmAcumulado': Decimal128('0.0755'),
                    'igpmAcumuladoReais': Decimal128('75.50'),
                    'ativo': True
                }
            ]
        }
    
    def test_timeline_sem_data_corte(self, portal_service, cco_data_completo):
        """Testa retorno de timeline completa quando não há data_corte"""
        with patch.object(portal_service, '_get_db') as mock_get_db:
            mock_db = Mock()
            mock_get_db.return_value = mock_db
            mock_db.conta_custo_oleo_entity.find_one.return_value = cco_data_completo
            
            with patch.object(PortalService, 'processar_timeline_cco') as mock_timeline:
                mock_timeline.return_value = [
                    {'tipo': 'CRIACAO', 'titulo': 'CCO Criada'},
                    {'tipo': 'IPCA', 'dataCorrecao': '2024-06-15'},
                    {'tipo': 'IGPM', 'dataCorrecao': '2024-12-15'}
                ]
                
                resultado = portal_service.get_timeline_with_cutoff('CCO-001', None)
                
                assert resultado['estado_temporal'] == False
                assert resultado['cco_id'] == 'CCO-001'
                assert resultado['data_corte'] is None
                assert len(resultado['eventos']) == 3
    
    def test_timeline_com_data_corte_valida(self, portal_service, cco_data_completo):
        """Testa filtro de timeline com data_corte válida (YYYY-MM-DD)"""
        with patch.object(portal_service, '_get_db') as mock_get_db:
            mock_db = Mock()
            mock_get_db.return_value = mock_db
            mock_db.conta_custo_oleo_entity.find_one.return_value = cco_data_completo
            
            with patch.object(PortalService, 'processar_timeline_cco') as mock_timeline:
                mock_timeline.return_value = [
                    {'tipo': 'CRIACAO', 'titulo': 'CCO Criada', 'dataCorrecao': None},
                    {'tipo': 'IPCA', 'dataCorrecao': '2024-06-15', 'valores': {'valorReconhecido': 1042.30}},
                    {'tipo': 'IGPM', 'dataCorrecao': '2024-12-15', 'valores': {'valorReconhecido': 1074.82}}
                ]
                
                resultado = portal_service.get_timeline_with_cutoff('CCO-001', '2024-08-31')
                
                assert resultado['estado_temporal'] == True
                assert resultado['data_corte'] == '2024-08-31'
                assert resultado['cco_id'] == 'CCO-001'
                # Deve incluir apenas CRIACAO e IPCA (junho < agosto)
                assert resultado['eventos_ate_corte'] == 2
    
    def test_timeline_data_corte_invalida_formato(self, portal_service):
        """Testa erro quando data_corte está em formato inválido"""
        with patch.object(portal_service, '_get_db') as mock_get_db:
            mock_db = Mock()
            mock_get_db.return_value = mock_db
            mock_db.conta_custo_oleo_entity.find_one.return_value = None
            
            with pytest.raises(ValueError, match="Formato de data inválido"):
                portal_service.get_timeline_with_cutoff('CCO-001', '31/08/2024')
    
    def test_timeline_cco_nao_encontrada(self, portal_service):
        """Testa resposta quando CCO não é encontrada no banco"""
        with patch.object(portal_service, '_get_db') as mock_get_db:
            mock_db = Mock()
            mock_get_db.return_value = mock_db
            mock_db.conta_custo_oleo_entity.find_one.return_value = None
            
            resultado = portal_service.get_timeline_with_cutoff('CCO-INEXISTENTE', None)
            
            assert resultado['estado_temporal'] == False
            assert 'erro' in resultado
            assert 'não encontrada' in resultado['erro']
            assert resultado['eventos'] == []
    
    def test_recalcular_valores_em_data(self):
        """Testa recalcuio de valores em data de corte"""
        cco_data = {
            'dataLancamento': '2024-01-15',
            'dataReconhecimento': '2024-01-20',
            'quantidadeLancamento': 100,
            'valorReconhecido': Decimal128('1000.00'),
            'valorReconhecidoComOH': Decimal128('1100.00'),
            'overHeadTotal': Decimal128('100.00'),
            'valorLancamentoTotal': Decimal128('1000.00'),
            'valorReconhecivel': Decimal128('1000.00'),
            'valorNaoReconhecido': Decimal128('0.00'),
            'valorNaoPassivelRecuperacao': Decimal128('0.00'),
            'overHeadExploracao': Decimal128('50.00'),
            'overHeadProducao': Decimal128('50.00'),
            'valorReconhecidoExploracao': Decimal128('500.00'),
            'valorReconhecidoProducao': Decimal128('500.00')
        }
        
        eventos = [
            {'tipo': 'CRIACAO'},
            {
                'tipo': 'IPCA',
                'dataCorrecao': '2024-06-15',
                'valores': {
                    'valorReconhecido': 1042.30,
                    'valorReconhecidoComOH': 1146.53,
                    'overHeadTotal': 104.23,
                    'diferencaValor': 46.53,
                    'igpmAcumulado': 0.0423,
                    'igpmAcumuladoReais': 42.30
                }
            }
        ]
        
        resultado = PortalService._recalcular_valores_em_data(
            cco_data, 
            eventos, 
            date(2024, 8, 31)
        )
        
        assert resultado['valorReconhecido'] == 1042.30
        assert resultado['valorReconhecidoComOH'] == 1146.53
        assert resultado['diferencaValor_total'] == 46.53
        assert resultado['igpm_acumulado'] == 0.0423
    
    def test_valores_em_data_corte_antes_primeira_correcao(self):
        """Testa valores em data anterior a primeira correção (retorna original)"""
        cco_data = {
            'dataLancamento': '2024-01-15',
            'dataReconhecimento': '2024-01-20',
            'quantidadeLancamento': 100,
            'valorReconhecido': Decimal128('1000.00'),
            'valorReconhecidoComOH': Decimal128('1100.00'),
            'overHeadTotal': Decimal128('100.00'),
            'valorLancamentoTotal': Decimal128('1000.00'),
            'valorReconhecivel': Decimal128('1000.00'),
            'valorNaoReconhecido': Decimal128('0.00'),
            'valorNaoPassivelRecuperacao': Decimal128('0.00'),
            'overHeadExploracao': Decimal128('50.00'),
            'overHeadProducao': Decimal128('50.00'),
            'valorReconhecidoExploracao': Decimal128('500.00'),
            'valorReconhecidoProducao': Decimal128('500.00')
        }
        
        eventos = [
            {'tipo': 'CRIACAO'},
        ]
        
        resultado = PortalService._recalcular_valores_em_data(
            cco_data, 
            eventos, 
            date(2024, 3, 31)
        )
        
        # Deve manter os valores originais
        assert resultado['valorReconhecido'] == 1000.0
        assert resultado['valorReconhecidoComOH'] == 1100.0
        assert resultado['overHeadTotal'] == 100.0


class TestTimelineFilterEndpoint:
    """Testes para o endpoint /api/cco-timeline/<cco_id>"""
    
    def test_endpoint_sem_parametros(self, client, mock_api_gateway):
        """Testa endpoint sem data_corte retorna timeline completa"""
        with patch('app.routes.portal_ui.portal_service.get_timeline_with_cutoff') as mock_get:
            mock_get.return_value = {
                'estado_temporal': False,
                'cco_id': 'CCO-001',
                'data_corte': None,
                'eventos': [{'tipo': 'CRIACAO'}, {'tipo': 'IPCA'}],
                'valores_em_data_corte': {}
            }
            
            response = client.get('/api/cco-timeline/CCO-001')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['estado_temporal'] == False
            assert len(data['eventos']) == 2
    
    def test_endpoint_com_data_corte_valida(self, client, mock_api_gateway):
        """Testa endpoint com data_corte válida"""
        with patch('app.routes.portal_ui.portal_service.get_timeline_with_cutoff') as mock_get:
            mock_get.return_value = {
                'estado_temporal': True,
                'cco_id': 'CCO-001',
                'data_corte': '2024-08-31',
                'eventos': [{'tipo': 'CRIACAO'}, {'tipo': 'IPCA'}],
                'valores_em_data_corte': {'valorReconhecido': 1042.30}
            }
            
            response = client.get('/api/cco-timeline/CCO-001?data_corte=2024-08-31')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['estado_temporal'] == True
            assert data['data_corte'] == '2024-08-31'
    
    def test_endpoint_data_corte_formato_invalido(self, client, mock_api_gateway):
        """Testa erro ao usar data_corte com formato inválido"""
        response = client.get('/api/cco-timeline/CCO-001?data_corte=31-08-2024')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'erro' in data
        assert 'YYYY-MM-DD' in data['mensagem']
    
    def test_endpoint_cco_nao_encontrada(self, client, mock_api_gateway):
        """Testa erro quando CCO não é encontrada"""
        with patch('app.routes.portal_ui.portal_service.get_timeline_with_cutoff') as mock_get:
            mock_get.return_value = {
                'estado_temporal': False,
                'cco_id': 'CCO-INEXISTENTE',
                'erro': 'CCO CCO-INEXISTENTE não encontrada'
            }
            
            response = client.get('/api/cco-timeline/CCO-INEXISTENTE')
            
            assert response.status_code == 404
            data = json.loads(response.data)
            assert 'erro' in data
    
    def test_endpoint_erro_interno(self, client, mock_api_gateway):
        """Testa tratamento de erro interno"""
        with patch('app.routes.portal_ui.portal_service.get_timeline_with_cutoff') as mock_get:
            mock_get.side_effect = Exception("Erro de conexão com BD")
            
            response = client.get('/api/cco-timeline/CCO-001')
            
            assert response.status_code == 500
            data = json.loads(response.data)
            assert 'erro' in data
            assert 'interno' in data['erro'].lower()


class TestTimelineFilterCacheing:
    """Testes para cache de resultados de timeline com filtro"""
    
    def test_cache_resulta_para_mesma_cco_e_data(self):
        """Testa se cache retorna resultado idêntico para mesma CCO + data"""
        # Nota: Implementar cache é um extra
        # Este teste documenta a intenção de cache
        pass
    
    def test_cache_invalida_com_nova_correcao(self):
        """Testa se cache é invalidado quando nova correção é adicionada"""
        # Nota: Implementar invalidação de cache é um extra
        # Este teste documenta a intenção
        pass
