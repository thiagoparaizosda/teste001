import unittest
import jwt
import time
from unittest.mock import PropertyMock, patch, MagicMock
from flask import Flask
import requests
from app.services.auth_service import AuthService
from app.config import Config
from app.utils.cache_utils import cache


class TestAuthService(unittest.TestCase):

    def setUp(self):
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        self.service = AuthService()
        self.secret = "test-secret"

        # RN-002: mockeia GATEWAY_SECRET_KEY para evitar rejeição precoce (fail-secure)
        self.patcher_key = patch.object(Config, 'GATEWAY_SECRET_KEY', self.secret)
        self.patcher_key.start()

        self.email = "admin"
        self.senha = "admin"

    def tearDown(self):
        self.patcher_key.stop()

    # ------------------------------------------------------------------
    # Testes de sucesso
    # ------------------------------------------------------------------

    def test_validate_token_success(self):
        """Testa validação de um token JWT íntegro com jti e dentro da validade."""
        payload = {
            "sub": "user123",
            "jti": "unique-token-id-123",
            "exp": int(time.time()) + 3600,
        }
        token = jwt.encode(payload, self.secret, algorithm='HS256')

        with self.app.app_context():
            with patch.object(cache, 'get', return_value=None):
                valid, result = self.service.validate_token(token)

        self.assertTrue(valid)
        self.assertEqual(result['sub'], "user123")

    # ------------------------------------------------------------------
    # RN-002: GATEWAY_SECRET_KEY ausente → rejeita imediatamente
    # ------------------------------------------------------------------

    def test_validate_token_missing_gateway_key(self):
        """RN-002: Sem GATEWAY_SECRET_KEY configurada deve retornar fail-secure."""
        self.patcher_key.stop()
        try:
            with patch.object(Config, 'GATEWAY_SECRET_KEY', ''):
                payload = {
                    "sub": "user123",
                    "jti": "unique-token-id-123",
                    "exp": int(time.time()) + 3600,
                }
                token = jwt.encode(payload, self.secret, algorithm='HS256')

                with self.app.app_context():
                    valid, result = self.service.validate_token(token)

                self.assertFalse(valid)
                self.assertEqual(result, "Configuração de segurança ausente")
        finally:
            self.patcher_key.start()

    # ------------------------------------------------------------------
    # RN-003: token expirado
    # ------------------------------------------------------------------

    def test_validate_token_expired(self):
        """Testa token que já passou da data de expiração."""
        payload = {
            "sub": "user123",
            "jti": "expired-jti",
            "exp": int(time.time()) - 3600,
        }
        token = jwt.encode(payload, self.secret, algorithm='HS256')

        with self.app.app_context():
            valid, result = self.service.validate_token(token)

        self.assertFalse(valid)
        self.assertEqual(result, "Token expirado")

    # ------------------------------------------------------------------
    # RN-004: token sem jti → inválido
    # ------------------------------------------------------------------

    def test_validate_token_missing_jti(self):
        """BUG-20521_B: Token sem 'jti' deve ser aceito — jti é opcional (RFC 7519).
        A verificação de blocklist é pulada; revogação não fica disponível para esse token."""
        payload = {
            "sub": "user123",
            "exp": int(time.time()) + 3600,
        }
        token = jwt.encode(payload, self.secret, algorithm='HS256')

        with self.app.app_context():
            valid, result = self.service.validate_token(token)

        self.assertTrue(valid)
        self.assertEqual(result.get('sub'), 'user123')

    # ------------------------------------------------------------------
    # RN-006: token revogado na blocklist
    # ------------------------------------------------------------------

    def test_validate_token_revoked_in_blocklist(self):
        """RN-006: Token presente na blocklist do cache deve ser rejeitado."""
        jti = "revoked-token-jti-999"
        payload = {
            "sub": "user123",
            "jti": jti,
            "exp": int(time.time()) + 3600,
        }
        token = jwt.encode(payload, self.secret, algorithm='HS256')

        with self.app.app_context():
            with patch.object(cache, 'get', return_value="1") as mock_cache_get:
                valid, result = self.service.validate_token(token)
                mock_cache_get.assert_called_once_with(f"blocklist:jti:{jti}")

        self.assertFalse(valid)
        self.assertEqual(result, "Token revogado")

    # ------------------------------------------------------------------
    # Assinatura inválida
    # ------------------------------------------------------------------

    def test_validate_token_invalid_secret(self):
        """Testa token assinado com chave diferente da configurada."""
        payload = {
            "sub": "user123",
            "jti": "some-jti",
            "exp": int(time.time()) + 3600,
        }
        token = jwt.encode(payload, "chave-errada", algorithm='HS256')

        with self.app.app_context():
            valid, result = self.service.validate_token(token)

        self.assertFalse(valid)
        self.assertEqual(result, "Token inválido")

    # ------------------------------------------------------------------
    # authenticate — falha de credenciais
    # ------------------------------------------------------------------

    @patch('app.services.auth_service.requests.post')
    def test_authenticate_failure(self, mock_post):
        """Testa falha de autenticação (ex: senha errada)."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "401 Client Error", response=mock_response
        )
        mock_post.return_value = mock_response

        with self.app.app_context():
            result, error = self.service.authenticate(self.email, self.senha)

        self.assertIsNone(result)
        self.assertIn("Unauthorized", error)


if __name__ == '__main__':
    unittest.main()
