from flask import Flask, session, g

from app.middleware.gateway_middleware import GatewayMiddleware
from app.utils.cache_utils import configure_cache
from app.config import Config
from app.models.permission import Permission
from app.utils.formatters import (
    formatar_decimal,
    formatar_data,
    formatar_boolean,
    formatar_tipo_dado,
    formatar_valor_por_tipo,
    identificar_tipo_dado,
)

def create_app():
    """
    Cria e configura a aplicação Flask com blueprints, configurações e integração com MongoDB.
    """
    app = Flask(__name__)
    app.wsgi_app = GatewayMiddleware(app.wsgi_app, '/sgpp-cco-tools')
    
    app.jinja_env.filters["formatar_decimal"] = formatar_decimal
    app.jinja_env.filters["formatar_data"] = formatar_data
    app.jinja_env.filters["formatar_boolean"] = formatar_boolean
    app.jinja_env.filters["formatar_tipo_dado"] = formatar_tipo_dado
    app.jinja_env.filters["formatar_valor_por_tipo"] = formatar_valor_por_tipo
    app.jinja_env.filters["identificar_tipo_dado"] = identificar_tipo_dado

    @app.context_processor
    def inject_user_context():
        user_data = session.get('user_data')
        
        if user_data:
            from app.models.user import User
            user = User(
                id=user_data.get('id'),
                email=user_data.get('email'),
                roles=user_data.get('roles', []),
                nome_completo=user_data.get('nome_completo')
            )
        else:
            class Anonymous:
                def has_permission(self, p): return False
                def is_client(self): return False
                @property
                def is_authenticated(self): return False
            user = Anonymous()

        return dict(current_user=user)
    
    @app.before_request
    def load_user_to_g():
        user_data = session.get('user_data')
        if user_data:
            # Criamos o objeto User a partir da sessão para o 'g'
            from app.models.user import User
            g.current_user = User(
                id=user_data.get('id'),
                email=user_data.get('email'),
                roles=user_data.get('roles', []),
                nome_completo=user_data.get('nome_completo')
            )
        else:
            g.current_user = None
    
    app.config['DEBUG'] = False
    app.config['SECRET_KEY'] = Config.SECRET_KEY
    app.config['UPLOAD_FOLDER'] = 'uploads'
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB
    
    configure_cache(app)
    
    # Registro de Blueprints
    try:
        from app.middleware.eureka_middleware import eureka_bp
        from app.routes.auth_routes import auth_bp
        from app.routes.portal_ui import portal_bp
        from app.routes.analise_ui import analise_bp
        from app.routes.recalculo_ui import recalculo_bp
        from app.routes.ipca_correcao_routes import ipca_correcao_bp
        from app.routes.ipca_promocao_routes import ipca_promocao_bp
        from app.routes.cco_editor_routes import cco_editor_bp
        from app.routes.audit_routes import audit_bp
        from app.routes.verificacao_oh_routes import verificacao_oh_bp
        from app.routes.verificacao_tp_routes import verificacao_tp_bp
        from app.routes.verificacao_ipca_routes import verificacao_ipca_bp

        blueprints = [eureka_bp, auth_bp, portal_bp, analise_bp, recalculo_bp, ipca_correcao_bp, ipca_promocao_bp, cco_editor_bp, audit_bp, verificacao_oh_bp, verificacao_tp_bp, verificacao_ipca_bp]
        for bp in blueprints:
            app.register_blueprint(bp)
    
    except Exception as e:
        print(f"Erro ao carregar o módulo routes.portal: {e}")
        raise e

    @app.context_processor
    def inject_globals():
        return dict(
            Permission=Permission
        )
    
    return app
