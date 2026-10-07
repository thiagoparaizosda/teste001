import os
import socket
from dotenv import load_dotenv

load_dotenv()

MONGO_URI =  os.getenv('MONGO_URI')
MONGO_URI_PRD = os.getenv('MONGO_URI_PRD')
CA_CERTIFICATE_PATH_DEFAULT = os.getenv('CA_CERTIFICATE_PATH_DEFAULT', '')
MONGO_URI_PRD = MONGO_URI_PRD.replace('tlsCAFile=PATH_CERT', f'tlsCAFile={CA_CERTIFICATE_PATH_DEFAULT}')
CACHE_DIR_PATH = os.getenv('CACHE_DIR_PATH', os.path.join(os.getcwd(), 'cache'))
OUTPUT_DIR = os.getenv('OUTPUT_DIR', '/tmp/db_copy')

PESQUISA_AMBINTE_PRODUCAO = os.getenv('PESQUISA_AMBINTE_PRODUCAO', 'False')

# URI ativa do ambiente: PRD quando PESQUISA_AMBINTE_PRODUCAO=True, local caso contrário
MONGO_URI_ATIVO = MONGO_URI_PRD if str(PESQUISA_AMBINTE_PRODUCAO).lower() == 'true' else MONGO_URI

IGNORAR_CORECAO_MONETARIA_VALOR_NEGATIVO = False

class Config:
    EUREKA_SERVER= os.getenv('EUREKA_SERVER', 'http://admin:admin@localhost:8761/eureka/')
    APP_NAME= os.getenv('APP_NAME', "sgpp-cco-tools")
    APP_PORT = int(os.getenv("APP_PORT", 5006))
    INSTANCE_HOST = socket.gethostname()
    URL_AUTH_GATEWAY= os.getenv('URL_AUTH_GATEWAY')
    SECRET_KEY= os.getenv('SECRET_KEY', "secret-key")
    # Chave secreta usada pelo gateway externo para assinar os JWTs.
    # Obrigatória: se ausente, validate_token rejeita todos os tokens (fail-secure).
    GATEWAY_SECRET_KEY = os.getenv('GATEWAY_SECRET_KEY', '')
    DISABLE_AUTH = os.getenv('DISABLE_AUTH', 'False')
    ROLES_FROM_DB = os.getenv('ROLES_FROM_DB', 'True')
    MONGO_URI_GATEWAY = os.getenv('MONGO_URI_GATEWAY', '')
    MONGO_DATABASE_GATEWAY = 'sgppGateway'
    COLECAO_USUARIOS = 'jhi_user' # coleção de usuários
