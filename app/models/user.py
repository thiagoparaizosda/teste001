import logging
from dataclasses import dataclass
from typing import List, Optional

from .permission import Role, Permission
from app.models.permission import ROLE_PERMISSIONS, Role, Permission

_log = logging.getLogger(__name__)

@dataclass
class User():
    def __init__(self, 
                id: str, 
                email: str, 
                roles: List[str], 
                username: Optional[str] = None, 
                nome_completo: Optional[str] = None):
        self.id = id
        self.username = username
        self.email = email
        self.roles = roles
        self.nome_completo = nome_completo

    # def get_id(self):
    #     return str(self.id)
    
    def is_client(self) -> bool:
        """
        Retorna True se o usuário possui a role CLIENT (usuário externo).
        CLIENT não concede permissões — é só uma marcação usada para negar acesso a recursos
        de uso interno, combinada com as demais roles/permissões do usuário.
        """
        return Role.CLIENT.value in self.roles

    def has_permission(self, permission: Permission) -> bool:
        """
        Verifica se usuário tem permissão.
        Suporta dois modelos de autorização presentes no JWT do gateway:
          1. Role-based: 'ADMIN' → ROLE_PERMISSIONS[Role.ADMIN] contém a permissão
          2. Direct grant: 'CCO_VIEW' == Permission.CCO_VIEW.name
        """
        try:
            target_perm = next(p for p in Permission if p.value == permission.value)

            _log.info(
                "[has_permission] email=%r verificando permissão=%r (name=%r) | roles do usuário: %s",
                self.email, target_perm.value, target_perm.name, self.roles
            )

            for role_name in self.roles:
                # Modelo 1 — mapeamento via Role enum (ADMIN, ANALYST, VIEWER)
                try:
                    user_role_enum = Role(role_name)
                    granted = target_perm in ROLE_PERMISSIONS.get(user_role_enum, [])
                    _log.info(
                        "[has_permission] Modelo1 role=%r → Role enum=%r granted=%s",
                        role_name, user_role_enum, granted
                    )
                    if granted:
                        return True
                except ValueError:
                    _log.debug(
                        "[has_permission] Modelo1 role=%r não é Role enum válido, tentando Modelo2.", role_name
                    )

                # Modelo 2 — permissão concedida diretamente pelo nome ('CCO_VIEW')
                #            ou pelo valor ('cco.view') — suporta grants diretos do DB
                granted = role_name == target_perm.name or role_name == target_perm.value
                _log.info(
                    "[has_permission] Modelo2 role=%r == perm.name=%r | perm.value=%r → %s",
                    role_name, target_perm.name, target_perm.value, granted
                )
                if granted:
                    return True

            _log.info(
                "[has_permission] NEGADO email=%r permissão=%r roles=%s",
                self.email, target_perm.value, self.roles
            )
            return False
        except (StopIteration, Exception) as exc:
            _log.error("[has_permission] Erro inesperado: %s", exc, exc_info=True)
            return False