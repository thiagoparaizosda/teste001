import os

from flask import current_app, g, session
from flask_caching import Cache

cache = Cache()

class CacheManager:
    def __init__(self, user_id=None, scope='user'):
        """
        Inicializa o CacheManager com suporte a escopo global ou por usuário.
        
        Args:
            user_id: ID do usuário para cache específico (opcional)
            scope: Escopo do cache ('user' ou 'global')
        """
        self.scope = scope.lower()
        
        if self.scope == 'user':
            self.user_id = user_id or session.get('user_id', None) or 'USER_API'
            if not self.user_id:
                raise ValueError("User ID não encontrado. Certifique-se de estar logado.")
            self.prefix = f"user_{self.user_id}:"
        else:
            self.prefix = "global:"
            

    def clear_cache(self, scope='user'):
        """
        Remove todos os dados do cache para o escopo especificado.
        
        Args:
            scope: Se fornecido, sobrescreve o escopo padrão da instância
        """
        original_scope = self.scope
        if scope:
            self.scope = scope
            original_prefix = self.prefix
            self.prefix = "global:" if scope == 'global' else self.prefix

        try:
            cache_dir = os.path.abspath(current_app.config.get('CACHE_DIR', '/tmp/flask_cache'))
            current_app.logger.info(f"Diretório de cache: {cache_dir}")
            
            if not os.path.exists(cache_dir):
                current_app.logger.warning(f"Diretório de cache não encontrado: {cache_dir}")
                return False

            all_files = os.listdir(cache_dir)
            current_app.logger.info(f"Arquivos encontrados no cache: {all_files}")
            
            known_hashes = set()
            if self._get_known_keys():
                for key in self._get_known_keys():
                    full_key = self._get_key(key)
                    hash_value = self._hash_key(full_key)
                    known_hashes.add(hash_value)
                    current_app.logger.info(f"Hash conhecido ({self.scope}) para {full_key}: {hash_value}")
            
            deleted_count = 0
            for filename in all_files:
                if filename in known_hashes:
                    file_path = os.path.join(cache_dir, filename)
                    try:
                        os.remove(file_path)
                        deleted_count += 1
                        current_app.logger.info(f"Arquivo de cache removido ({self.scope}): {filename}")
                    except Exception as e:
                        current_app.logger.error(f"Erro ao remover arquivo {filename}: {e}")

            for key in self._get_known_keys():
                full_key = self._get_key(key)
                try:
                    cache.delete(full_key)
                    current_app.logger.info(f"Cache removido para chave ({self.scope}): {full_key}")
                except Exception as e:
                    current_app.logger.error(f"Erro ao remover cache para chave {full_key}: {e}")

            current_app.logger.info(
                f"Cache limpo para o escopo {self.scope}. {deleted_count} arquivos removidos."
            )
            return True

        except Exception as e:
            current_app.logger.error(f"Erro ao limpar cache: {e}")
            return False
        finally:
            if scope:
                self.scope = original_scope
                self.prefix = original_prefix

    def _get_known_keys(self, scope='user'):
        """
        Retorna uma lista de chaves conhecidas para o escopo especificado.
        
        Args:
            scope: Se fornecido, sobrescreve o escopo padrão da instância
        """
        original_scope = self.scope
        if scope:
            self.scope = scope
            original_prefix = self.prefix
            self.prefix = "global:" if scope == 'global' else self.prefix

        try:
            known_keys = self.get_data('known_keys') or []
            return known_keys
        finally:
            if scope:
                self.scope = original_scope
                self.prefix = original_prefix