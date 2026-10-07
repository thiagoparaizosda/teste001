import unittest
from unittest.mock import MagicMock, patch

from flask import Flask, session

from app.middleware.auth_middleware import audit_log


class TestAuditLogDecorator(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        self.app.secret_key = 'test-secret'

    @patch('app.middleware.auth_middleware.AuditService')
    def test_audit_log_records_success_with_resource_id_from_json(self, mock_audit_service):
        """Testa se o decorador registra sucesso usando o cco_id do body da requisição."""
        mock_instance = MagicMock()
        mock_audit_service.return_value = mock_instance

        with self.app.test_request_context(
            '/api/promover',
            method='POST',
            json={'cco_id': 'cco-123'},
            headers={'User-Agent': 'pytest'},
            environ_base={'REMOTE_ADDR': '127.0.0.1'}
        ):
            session['user_data'] = {'email': 'user@example.com'}

            @audit_log('PROMOTE_CORRECAO', 'IPCA', lambda kwargs: kwargs.get('cco_id'))
            def sample_route(**kwargs):
                return {'success': True}

            result = sample_route(cco_id='cco-123')

        self.assertEqual(result, {'success': True})
        mock_instance.log_action.assert_called_once()

        call_kwargs = mock_instance.log_action.call_args.kwargs
        self.assertEqual(call_kwargs['action'], 'PROMOTE_CORRECAO')
        self.assertEqual(call_kwargs['resource_type'], 'IPCA')
        self.assertEqual(call_kwargs['resource_id'], 'cco-123')
        self.assertEqual(call_kwargs['status'], 'SUCCESS')
        self.assertEqual(call_kwargs['user_email'], 'user@example.com')

    @patch('app.middleware.auth_middleware.AuditService')
    def test_audit_log_records_failure_without_crashing(self, mock_audit_service):
        """Testa se o decorador registra falha quando a função decorada lança exceção."""
        mock_instance = MagicMock()
        mock_audit_service.return_value = mock_instance

        with self.app.test_request_context(
            '/api/promover',
            method='POST',
            json={'cco_id': 'cco-123'},
            headers={'User-Agent': 'pytest'},
            environ_base={'REMOTE_ADDR': '127.0.0.1'}
        ):
            session['user_data'] = {'email': 'user@example.com'}

            @audit_log('PROMOTE_CORRECAO', 'IPCA', lambda kwargs: kwargs.get('cco_id'))
            def sample_route(**kwargs):
                raise RuntimeError('boom')

            with self.assertRaises(RuntimeError):
                sample_route(cco_id='cco-123')

        self.assertEqual(mock_instance.log_action.call_count, 1)
        call_kwargs = mock_instance.log_action.call_args.kwargs
        self.assertEqual(call_kwargs['action'], 'PROMOTE_CORRECAO')
        self.assertEqual(call_kwargs['resource_type'], 'IPCA')
        self.assertEqual(call_kwargs['resource_id'], 'cco-123')
        self.assertEqual(call_kwargs['status'], 'FAILED')
        self.assertEqual(call_kwargs['details'], {'error': 'boom'})
