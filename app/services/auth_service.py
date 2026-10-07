import logging
import jwt
import requests

from datetime import datetime, timezone
from flask import current_app
from app.config import Config
from app.utils.cache_utils import cache
from pymongo import MongoClient

logger = logging.getLogger(__name__)

_BLOCKLIST_PREFIX = "blocklist:jti:"


class AuthService:

    @property
    def gateway_url(self):
        return Config.URL_AUTH_GATEWAY

    @property
    def secret_key(self):
        return Config.SECRET_KEY

    def authenticate(self, email, senha):
        current_app.logger.info("authenticate: Validando autenticação... email: %s", email)
        url = self.gateway_url
        current_app.logger.info("URL de autenticação: %s", url)
        headers = {
            "Content-Type": "application/json"
        }

        payload = {
            "username": email,
            "password": senha
        }

        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json(), ""
        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"Erro ao autenticar usuário: {e}")
            error_msg = e.response.text if e.response else str(e)
            return None, error_msg

    def validate_token(self, token):
        """
        Valida um token JWT emitido pelo gateway externo.

        Regras (fail-secure):
        - RN-002: GATEWAY_SECRET_KEY ausente → rejeita imediatamente.
        - RN-004: token sem campo 'jti' → rejeita.
        - RN-006: jti presente na blocklist → rejeita como revogado.
        Verifica assinatura + expiração em todos os casos.
        """
        gateway_key = Config.GATEWAY_SECRET_KEY

        if not gateway_key:
            current_app.logger.warning(
                "validate_token: GATEWAY_SECRET_KEY não configurada. "
                "Rejeitando token (fail-secure)."
            )
            return False, "Configuração de segurança ausente"

        try:
            payload = jwt.decode(
                token,
                gateway_key,
                algorithms=['HS512', 'HS256'],
            )
        except jwt.ExpiredSignatureError:
            current_app.logger.warning("validate_token: token expirado.")
            return False, "Token expirado"
        except jwt.InvalidTokenError as e:
            current_app.logger.warning("validate_token: token inválido — %s", str(e))
            return False, "Token inválido"

        current_app.logger.info(
            "validate_token: assinatura verificada. Claims presentes: %s",
            list(payload.keys())
        )

        # jti é opcional (RFC 7519). Quando presente, verifica blocklist (RN-006).
        # Quando ausente, token é aceito mas não suporta revogação via blocklist.
        jti = payload.get('jti')
        if jti:
            blocklist_key = f"{_BLOCKLIST_PREFIX}{jti}"
            if cache.get(blocklist_key) is not None:
                current_app.logger.info(
                    "validate_token: token revogado (jti=%s).", jti
                )
                return False, "Token revogado"
        else:
            current_app.logger.info(
                "validate_token: token sem 'jti' — revogação via blocklist não disponível."
            )

        return True, payload

    def get_user_from_db(self, email):
        current_app.logger.info("Recuperando usuário do banco de dados. Email: %s", email)
        try:
            collection = self.conectar_mongo_especific(
                Config.MONGO_URI_GATEWAY,
                Config.COLECAO_USUARIOS,
                Config.MONGO_DATABASE_GATEWAY
            )
            user = collection.find_one({'login': email})
            return user
        except Exception as e:
            current_app.logger.error(f"Erro ao buscar usuário: {str(e)}")
            return None

    @staticmethod
    def conectar_mongo_especific(uri, colecao_nome, database=None):
        logger.info("Conectando no MongoDB...")
        # Conecta ao servidor MongoDB. Certifique-se de ter o MongoDB em execução.
        try:
            banco_dados = MongoClient(uri)[database]
            colecao = banco_dados[colecao_nome]
            return colecao
        except Exception as e:
            logger.error("Ocorreu um erro na conexão com o MongoDB: %s", e, exc_info=True)
            raise e