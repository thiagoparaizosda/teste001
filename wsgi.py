"""
WSGI Entry Point - Portal PPSA
Ponto de entrada para servidores WSGI (Gunicorn, uWSGI, etc.)
"""

import os
import sys

# Adicionar diretório raiz ao path se necessário
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app

# Criar instância da aplicação
app = create_app()

if __name__ == "__main__":
    # Para execução direta (desenvolvimento)
    # Em produção, use gunicorn: gunicorn wsgi:app
    port = int(os.getenv("PORT", 5009))
    debug = os.getenv("FLASK_DEBUG", "False").lower() == "true"
    
    app.run(
        host="0.0.0.0",
        port=port,
        debug=debug
    )