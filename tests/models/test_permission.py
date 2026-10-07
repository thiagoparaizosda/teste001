import unittest
from app.models import permission
from app.models.permission import Permission, Role, has_permission, ROLE_PERMISSIONS

class TestPermissions(unittest.TestCase):

    def test_admin_has_all_permissions(self):
        """Garante que o ADMIN tenha acesso a tudo que foi definido."""
        for permission in Permission:
            with self.subTest(permission=permission):
                self.assertTrue(
                    has_permission(Role.ADMIN, permission),
                    f"ADMIN deveria ter a permissão {permission.value}"
                )

    def test_viewer_restrictions(self):
        """Garante que o VIEWER só tenha permissões de leitura."""
        # Permissões permitidas
        self.assertTrue(has_permission(Role.VIEWER, Permission.CCO_VIEW))
        self.assertTrue(has_permission(Role.VIEWER, Permission.CORRECAO_VIEW))
        
        # Permissões proibidas
        self.assertFalse(has_permission(Role.VIEWER, Permission.CCO_DELETE))

    def test_analyst_intermediate_permissions(self):
        """Verifica se o ANALYST tem permissões de criação mas não de gestão/delete."""
        self.assertTrue(has_permission(Role.ANALYST, Permission.CORRECAO_CREATE))
        self.assertTrue(has_permission(Role.ANALYST, Permission.REPORT_EXPORT))
        
        # Não deve deletar nem gerenciar usuários
        self.assertFalse(has_permission(Role.ANALYST, Permission.CCO_DELETE))

    def test_invalid_role(self):
        """Testa o comportamento com uma role inexistente ou None."""
        self.assertFalse(has_permission(None, Permission.CCO_VIEW))

    def test_role_permissions_matrix_consistency(self):
        """Verifica se todas as roles definidas no Enum estão na matriz."""
        for role in Role:
            self.assertIn(role, ROLE_PERMISSIONS, f"Role {role} esquecida na ROLE_PERMISSIONS")

if __name__ == '__main__':
    unittest.main()