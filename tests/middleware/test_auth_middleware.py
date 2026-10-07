import unittest
from unittest.mock import patch
from flask import Blueprint, Flask, g, session

from app.middleware.auth_middleware import login_required, require_role 

class TestDecorators(unittest.TestCase):

    def setUp(self):
        self.app = Flask(__name__)
        self.app.secret_key = 'test_secret'
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

        @self.app.before_request
        def inject_current_user():
            user_data = session.get('user_data', {})

            class DummyUser:
                def __init__(self, roles):
                    self.role = roles[0] if roles else None

                def has_permission(self, permission):
                    return False

            g.current_user = DummyUser(user_data.get('roles', [])) if user_data else None

        auth_bp = Blueprint('auth', __name__)

        @self.app.route('/test-protected')
        @login_required()
        def protected_route():
            return {"message": "success"}, 200

        @self.app.route('/test-role')
        @login_required()
        @require_role('ROLE_ADMIN')
        def admin_route():
            return {"message": "admin_success"}, 200
        
        @auth_bp.route('/login')
        def login():
            return "Página de Login"
        
        self.app.register_blueprint(auth_bp)

    @patch('app.middleware.auth_middleware.auth_service')
    def test_login_required_no_session(self, mock_auth_service):
        """Testa se redireciona para login quando não há token na sessão."""
        with self.app.test_request_context('/test-protected'):
            response = self.client.get('/test-protected')
            self.assertEqual(response.status_code, 302)
            self.assertIn('/login', response.location)

    @patch('app.middleware.auth_middleware.auth_service')
    def test_login_required_valid_token_with_bearer(self, mock_auth_service):
        """Testa se remove o prefixo 'Bearer ' e valida com sucesso."""
        mock_auth_service.validate_token.return_value = (True, {'sub': 'user123'})

        with self.client.session_transaction() as sess:
            sess['token'] = 'Bearer valid_token_123'
            sess['roles'] = ['ROLE_USER']

        response = self.client.get('/test-protected')
    
        mock_auth_service.validate_token.assert_called_with('valid_token_123')
        self.assertEqual(response.status_code, 200)

    @patch('app.middleware.auth_middleware.auth_service')
    def test_require_role_success(self, mock_auth_service):
        """Testa se permite acesso quando o usuário tem a role correta."""
        mock_auth_service.validate_token.return_value = (True, {'sub': 'user123'})

        with self.client.session_transaction() as sess:
            sess['token'] = 'valid_token'
            sess['user_data'] = {'roles': ['ROLE_ADMIN']}

        response = self.client.get('/test-role')
        self.assertEqual(response.status_code, 200)
    
    @patch('app.middleware.auth_middleware.auth_service')
    def test_require_role_forbidden(self, mock_auth_service):
        """Testa 403 quando a role é diferente."""
        mock_auth_service.validate_token.return_value = (True, {'sub': 'user123'})

        with self.client.session_transaction() as sess:
            sess['token'] = 'valid-token'
            sess['user_data'] = {'roles': ['ROLE_USER']}

        response = self.client.get('/test-role')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()['error'], 'Forbidden')

if __name__ == '__main__':
    unittest.main()