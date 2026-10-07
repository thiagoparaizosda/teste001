from enum import Enum
   
class Role(Enum):
    """Papéis de usuário"""
    ADMIN = 'ADMIN'
    ANALYST = 'ANALYST'
    VIEWER = 'VIEWER'
    # Identifica usuários externos (clientes). Não concede nenhuma permissão por si só —
    # é combinada com as demais roles/permissões do usuário (ex.: ['ANALYST', 'CLIENT']) e serve
    # apenas para negar acesso a recursos restritos a uso interno. Ver User.is_client() e o
    # decorator deny_client() em app/middleware/auth_middleware.py.
    CLIENT = 'CLIENT'

class Permission(Enum):
    """Permissões granulares"""
    # CCO permissions
    CCO_VIEW = 'cco.view'
    CCO_EDIT = 'cco.edit'
    CCO_DELETE = 'cco.delete'
    
    # Correção permissions
    CORRECAO_VIEW = 'correcao.view'
    CORRECAO_CREATE = 'correcao.create'
    CORRECAO_PROMOTE = 'correcao.promote'
    
    # Reports
    REPORT_EXPORT = 'report.export'

    AUDIT = 'audit.view'

# Matriz de permissões
ROLE_PERMISSIONS = {
    Role.VIEWER: [
        Permission.CCO_VIEW,
        Permission.CORRECAO_VIEW,
    ],
    Role.ANALYST: [
        Permission.CCO_VIEW,
        Permission.CCO_EDIT,
        Permission.CORRECAO_VIEW,
        Permission.CORRECAO_CREATE,
        Permission.REPORT_EXPORT,
    ],
    Role.ADMIN: [
        # Todas as permissões
        Permission.CCO_VIEW,
        Permission.CCO_EDIT,
        Permission.CCO_DELETE,
        Permission.CORRECAO_VIEW,
        Permission.CORRECAO_CREATE,
        Permission.CORRECAO_PROMOTE,
        Permission.REPORT_EXPORT,
        Permission.AUDIT
    ],
    # CLIENT não concede nenhuma permissão própria — é apenas uma marcação combinada com as
    # demais roles do usuário. O restante do acesso do usuário continua vindo normalmente das
    # outras permissões/roles atribuídas a ele; CLIENT só é usada para *negar* recursos
    # específicos de uso interno (ver Role.CLIENT e User.is_client()).
    Role.CLIENT: [],
}

def has_permission(user_role: Role, permission: Permission) -> bool:
    """Verifica se role tem permissão"""
    return permission in ROLE_PERMISSIONS.get(user_role, [])