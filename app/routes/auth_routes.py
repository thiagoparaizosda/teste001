import jwt

from flask import flash, redirect, render_template, request, Blueprint, current_app, session, url_for
from datetime import datetime, timedelta, timezone
from app.middleware.auth_middleware import audit_log
from app.models.user import User
from app.services.audit_service import AuditAction
from app.utils.cache import CacheManager
from app.utils.cache_utils import cache
from app.config import Config

from app.services.auth_service import AuthService

auth_bp = Blueprint('auth', __name__)
auth_service = AuthService()

_BLOCKLIST_PREFIX = "blocklist:jti:"

@auth_bp.context_processor
def inject_today_date():
    return {'today_date': datetime.today().strftime('%Y-%m-%d')}

@auth_bp.route('/login', methods=['GET', 'POST'])
@audit_log(AuditAction.LOGIN, 'AUTH')
def login():
    if request.method == 'POST':
        data = request.get_json(silent=True) or request.form
    
        email = data.get('email')
        password = data.get('password')
        
        try:
            auth_response, error = auth_service.authenticate(email, password)
            
            if auth_response:
                token = auth_response.get('id_token')
                
                if token:
                    decoded_token = jwt.decode(
                        token,
                        options={"verify_signature": False},
                        algorithms=['HS512', 'HS256', 'RS256', 'RS512'],
                    )

                    current_app.logger.info(
                        "[LOGIN] Claims presentes no JWT: %s", list(decoded_token.keys())
                    )

                    user_id = decoded_token.get('sub') or email
                    
                    #if recuperar roles a partir do token:
                    if Config.ROLES_FROM_DB == 'False':
                        current_app.logger.warning(
                            "[LOGIN] Recuperando roles a partir do token"
                        )
                        auth_data = decoded_token.get('auth', '')
                        
                        current_app.logger.warning(
                            "[LOGIN] Campo 'auth' bruto do JWT: %r (tipo: %s)",
                            auth_data, type(auth_data).__name__
                        )

                        roles_list = [r.strip().replace('ROLE_', '') for r in auth_data.split(',')] if auth_data else []
                    
                    
                    else: #recuperar roles da base de dados
                        current_app.logger.warning(
                                                    "[LOGIN] Recuperando roles a partir da base de dados"
                                                )
                        user = auth_service.get_user_from_db(email)
                        if user:
                            roles_list = [
                                authority['_id'].replace('ROLE_', '')
                                for authority in user['authorities']
                            ]
                        else:
                            roles_list = []
                            current_app.logger.warning(
                                                    "[LOGIN] não foi possível recuperar os roles do usuário %s da base de dados", email)
                    
                    current_app.logger.warning(
                        "[LOGIN] roles_list após processamento: %s", roles_list
                    )
                    
                    session['user_data'] = {
                        'id': user_id,
                        'email': email,
                        'roles': roles_list
                    }
                    session['token'] = token
                    session['token_exp'] = decoded_token.get('exp')
                    session.modified = True
                    session.permanent = True
                    auth_bp.permanent_session_lifetime = timedelta(hours=8)

                    current_app.logger.info(
                        "[LOGIN] session['user_data'] gravado: id=%r email=%r roles=%s",
                        user_id, email, roles_list
                    )

                    CacheManager().clear_cache()

                current_app.logger.info(
                    "[LOGIN] Acesso concedido. email=%r roles=%s", email, roles_list
                )
                return redirect(url_for('portal_ui.index'))
                    
            flash(f'Credenciais inválidas: {error}', 'danger')
        except Exception as e:
            current_app.logger.error(f"Erro no login: {str(e)}")
            flash('Erro no servidor', 'danger')

    return render_template('login.html', titulo="Login - Portal de Análises PPSA")

@auth_bp.route('/logout')
def logout():
    # RN-005: registrar token na blocklist antes de limpar a sessão
    token = session.get('token')
    if token:
        try:
            decoded = jwt.decode(
                token,
                options={"verify_signature": False},
                algorithms=['HS512', 'HS256', 'RS256', 'RS512'],
            )
            jti = decoded.get('jti')
            exp = decoded.get('exp')
            if jti and exp:
                ttl = max(0, int(exp - datetime.now(timezone.utc).timestamp()))
                if ttl > 0:
                    blocklist_key = f"{_BLOCKLIST_PREFIX}{jti}"
                    cache.set(blocklist_key, "1", timeout=ttl)
                    current_app.logger.info(
                        "logout: token revogado na blocklist (jti=%s, ttl=%ds).", jti, ttl
                    )
        except Exception as e:
            current_app.logger.error("logout: erro ao revogar token na blocklist: %s", e, exc_info=True)

    try:
        CacheManager().clear_cache()
    except Exception as e:
        current_app.logger.error(f"Erro ao limpar cache do usuário: {e}")

    current_app.logger.info("Usuário desconectado.")

    session.clear()

    flash('Você foi desconectado.', 'info')
    return redirect(url_for('auth.login'))