# ================================================
# Gunicorn Configuration - Portal PPSA
# Configuração otimizada para produção
# ================================================

import multiprocessing
import os

# Configuração de Workers
# Fórmula recomendada: (2 x número_de_cores) + 1
workers = int(os.getenv("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1))

# Tipo de worker
# 'sync' - padrão, bloqueante, bom para CPU-bound
# 'gevent' ou 'eventlet' - assíncrono, bom para I/O-bound
worker_class = os.getenv("GUNICORN_WORKER_CLASS", "sync")

# Configuração de Threads (para worker_class='sync')
threads = int(os.getenv("GUNICORN_THREADS", 2))

# Bind - endereço e porta
bind = os.getenv("GUNICORN_BIND", "0.0.0.0:5009")

# Timeouts
# Timeout para workers (importante para operações longas como análises financeiras)
timeout = int(os.getenv("GUNICORN_TIMEOUT", 300))  # 5 minutos
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", 120))  # 2 minutos
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", 5))

# Worker Connections (para workers assíncronos)
worker_connections = int(os.getenv("GUNICORN_WORKER_CONNECTIONS", 1000))

# Restart workers
# Reiniciar workers após processar N requisições (previne memory leaks)
max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", 1000))
max_requests_jitter = int(os.getenv("GUNICORN_MAX_REQUESTS_JITTER", 50))

# Preload app
# Carregar aplicação antes de fazer fork dos workers (economiza memória)
preload_app = os.getenv("GUNICORN_PRELOAD_APP", "true").lower() == "true"

# Backlog
# Número máximo de conexões pendentes
backlog = int(os.getenv("GUNICORN_BACKLOG", 2048))

# Logging
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")
accesslog = os.getenv("GUNICORN_ACCESS_LOG", "-")  # "-" para stdout
errorlog = os.getenv("GUNICORN_ERROR_LOG", "-")    # "-" para stderr

# Formato de log de acesso
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Proxy settings
forwarded_allow_ips = os.getenv("GUNICORN_FORWARDED_ALLOW_IPS", "*")

# Diretório temporário
tmp_upload_dir = os.getenv("GUNICORN_TMP_UPLOAD_DIR", "/tmp")

# ================================================
# Hooks para logging e monitoramento
# ================================================

def on_starting(server):
    """Executado quando o servidor inicia"""
    server.log.info("=" * 60)
    server.log.info("Portal PPSA - Iniciando servidor Gunicorn")
    server.log.info(f"Workers: {workers}")
    server.log.info(f"Worker Class: {worker_class}")
    server.log.info(f"Bind: {bind}")
    server.log.info(f"Timeout: {timeout}s")
    server.log.info("=" * 60)

def on_reload(server):
    """Executado quando há reload do servidor"""
    server.log.info("Portal PPSA - Recarregando configuração")

def worker_int(worker):
    """Executado quando worker é interrompido"""
    worker.log.info(f"Worker {worker.pid} - Interrompendo graciosamente")

def worker_abort(worker):
    """Executado quando worker é abortado"""
    worker.log.warning(f"Worker {worker.pid} - Abortado!")

def post_fork(server, worker):
    """Executado após fork de cada worker"""
    server.log.info(f"Worker {worker.pid} - Iniciado")

def pre_exec(server):
    """Executado antes de exec() para hot reload"""
    server.log.info("Portal PPSA - Preparando para hot reload")

def when_ready(server):
    """Executado quando servidor está pronto para aceitar conexões"""
    server.log.info("Portal PPSA - Servidor pronto para aceitar conexões")

# ================================================
# SSL/TLS Configuration (se necessário)
# ================================================
# Descomente e configure se precisar de HTTPS

# keyfile = "/path/to/key.pem"
# certfile = "/path/to/cert.pem"
# ssl_version = ssl.PROTOCOL_TLSv1_2
# cert_reqs = ssl.CERT_NONE
# ca_certs = "/path/to/ca_certs.pem"

# ================================================
# Configurações adicionais de segurança
# ================================================

# Limitar tamanho do cabeçalho da requisição
limit_request_line = int(os.getenv("GUNICORN_LIMIT_REQUEST_LINE", 4096))
limit_request_fields = int(os.getenv("GUNICORN_LIMIT_REQUEST_FIELDS", 100))
limit_request_field_size = int(os.getenv("GUNICORN_LIMIT_REQUEST_FIELD_SIZE", 8190))