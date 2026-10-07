from functools import wraps
from flask import flash, jsonify, current_app, session, redirect, url_for, g, request
from app.config import Config

from app.models.permission import Permission
from app.services.audit_service import AuditService
from app.services.auth_service import AuthService

from app.config import MONGO_URI_ATIVO

auth_service = AuthService()

DEFAULT_USER = 'default_user_portal'

def get_current_user_id() -> str:
    """Retorna o ID do usuário da sessão atual.

    Quando DISABLE_AUTH=True retorna o usuário padrão.
    Caso contrário lê session['user_data'] priorizando 'id', depois 'email'.
    """
    if Config.DISABLE_AUTH == 'True':
        return DEFAULT_USER
    user_data = session.get('user_data', {})
    return user_data.get('id') or user_data.get('email') or DEFAULT_USER


def login_required():
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            current_app.logger.debug("login_required >> Verificando autenticação...")
            if Config.DISABLE_AUTH == 'True':
                return f(*args, **kwargs)
            
            try:
                if not session or not session.get('token'):
                    current_app.logger.debug("Token ausente. Redirecionando...")
                    return redirect(url_for('auth.login'))
                
                token = session.get('token')
                user_data = session.get('user_data', {})
                roles = user_data.get('roles', [])
                
                current_app.logger.warning(f"roles user login: {str(roles)}" )
                
                if token and token.startswith('Bearer '):
                    token = token.split(" ")[1]

                valid, result = auth_service.validate_token(token)

                if valid:
                    g.user = {
                        'roles': roles
                    }
                    g.tipo_requisicao = 'web'
                    return f(*args, **kwargs)

                flash('Sessão expirada. Por favor, logue novamente.', 'warning')
                return redirect(url_for('auth.login'))
            except Exception as e:
                current_app.logger.error(f"Erro na autenticação: {str(e)}")
                return jsonify({"error": str(e)}), 401
        return decorated_function
    return decorator

def require_role(*allowed_roles):
    """
    Decorator que requer um ou mais roles específicos.
    
    Usage:
        @require_role(Role.ADMIN)
        @require_role(Role.ADMIN, Role.ANALYST)
    """
    def decorator(f):
        @wraps(f)
        @login_required()  # Sempre requer autenticação
        def decorated_function(*args, **kwargs):
            user = g.current_user
            
            if user.role not in allowed_roles:
                allowed_role_values = [getattr(role, 'value', role) for role in allowed_roles]
                return jsonify({
                    'error': 'Forbidden',
                    'message': f'Requires role: {allowed_role_values}'
                }), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator
   
def require_permission(permission: Permission):
    """
    Decorator que requer permissão específica.
    
    Usage:
        @require_permission(Permission.CCO_EDIT)
    """
    def decorator(f):
        @wraps(f)
        @login_required()
        def decorated_function(*args, **kwargs):
            if Config.DISABLE_AUTH == 'True':
                return f(*args, **kwargs)
            
            user = getattr(g, 'current_user', None)

            current_app.logger.info(
                "[require_permission] permissão=%r | g.current_user=%r | roles=%s",
                permission.value,
                user.email if user else None,
                user.roles if user else 'N/A',
            )

            if not user or not user.has_permission(permission):
                current_app.logger.warning(
                    "[require_permission] ACESSO NEGADO email=%r permissão=%r roles=%s",
                    user.email if user else None,
                    permission.value,
                    user.roles if user else 'N/A',
                )
                if request.is_json:
                    return jsonify({
                        "success": False,
                        "error": f"É necessário a permissão {permission.value} para acessar essa funcionalidade."
                    }), 403

                flash(f"É necessário a permissão {permission.value} para acessar essa funcionalidade.", "danger")
                return redirect(url_for('portal_ui.index'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def deny_client():
    """
    Decorator que bloqueia o acesso de usuários com a role CLIENT (usuários externos),
    independentemente de quais outras permissões/roles esse usuário possua.

    Usado em recursos de uso interno (equipe de suporte) que não devem ficar disponíveis para
    clientes, ex.: Análise de Remessas, Verificação de OH, Verificação de TP. Combinar com
    @require_permission ou @login_required conforme a rota exigir.

    Usage:
        @meu_bp.route('/recurso-interno')
        @require_permission(Permission.CCO_VIEW)
        @deny_client()
        def recurso_interno():
            ...
    """
    def decorator(f):
        @wraps(f)
        @login_required()
        def decorated_function(*args, **kwargs):
            if Config.DISABLE_AUTH == 'True':
                return f(*args, **kwargs)

            user = getattr(g, 'current_user', None)

            if user and user.is_client():
                current_app.logger.warning(
                    "[deny_client] ACESSO NEGADO (usuário CLIENT) email=%r roles=%s",
                    user.email, user.roles
                )
                if request.is_json:
                    return jsonify({
                        "success": False,
                        "error": "Este recurso não está disponível para o seu perfil de usuário."
                    }), 403

                flash("Este recurso não está disponível para o seu perfil de usuário.", "danger")
                return redirect(url_for('portal_ui.index'))

            return f(*args, **kwargs)
        return decorated_function
    return decorator

def audit_log(action, resource_type=None, get_resource_id=None):
    """
    Decorator para auditoria automática.
    
    Usage:
        @audit_log(AuditAction.EDIT_CCO, 'CCO', lambda kwargs: kwargs.get('cco_id'))
        def edit_cco(cco_id):
            pass
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            audit_service = AuditService(MONGO_URI_ATIVO)

            user_data = session.get('user_data', {})
            resource_id = None
            if get_resource_id:
                try:
                    resource_id = get_resource_id(kwargs)
                except TypeError:
                    resource_id = get_resource_id()
            
            try:
                # Executar função
                result = f(*args, **kwargs)

                if not user_data: 
                    user_data = session.get('user_data', {})
                user_email = user_data.get('email', 'unknown')
                
                if action != 'LOGIN' or (user_email != 'unknown'):
                    # Log success
                    audit_service.log_action(
                        action=action,
                        resource_type=resource_type,
                        resource_id=resource_id,
                        status='SUCCESS',
                        user_email=user_email
                    )

                return result

            except Exception as e:
                # Log failure
                audit_service.log_action(
                    action=action,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    details={'error': str(e)},
                    status='FAILED'
                )
                raise
        
        return decorated_function
    return decorator
