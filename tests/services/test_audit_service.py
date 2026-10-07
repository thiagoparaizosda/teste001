import unittest
from unittest.mock import MagicMock, patch

from flask import Flask

from app.services.audit_service import AuditService


class TestAuditService(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True

    @patch('app.services.audit_service.MongoClient')
    def test_log_action_persists_expected_document(self, mock_mongo_client):
        """Testa se o log_action grava os campos corretos no MongoDB."""
        mock_collection = MagicMock()
        mock_db = MagicMock()
        mock_client = MagicMock()

        mock_client.sgppServices = mock_db
        mock_db.cco_audit_logs = mock_collection
        mock_mongo_client.return_value = mock_client

        service = AuditService('mongodb://test')

        with self.app.test_request_context(
            '/audit',
            method='POST',
            headers={'User-Agent': 'pytest'},
            environ_base={'REMOTE_ADDR': '127.0.0.1'}
        ):
            service.log_action(
                action='PROMOTE_CORRECAO',
                resource_type='IPCA',
                resource_id='cco-123',
                details={'origin': 'unit-test'},
                status='SUCCESS',
                user_email='user@example.com'
            )

        mock_collection.insert_one.assert_called_once()
        audit_document = mock_collection.insert_one.call_args.args[0]

        self.assertEqual(audit_document['user_id'], 'user@example.com')
        self.assertEqual(audit_document['username'], 'user@example.com')
        self.assertEqual(audit_document['action'], 'PROMOTE_CORRECAO')
        self.assertEqual(audit_document['resource_type'], 'IPCA')
        self.assertEqual(audit_document['resource_id'], 'cco-123')
        self.assertEqual(audit_document['details'], {'origin': 'unit-test'})
        self.assertEqual(audit_document['status'], 'SUCCESS')
        self.assertEqual(audit_document['ip_address'], '127.0.0.1')
        self.assertEqual(audit_document['user_agent'], 'pytest')
        self.assertIn('timestamp', audit_document)
