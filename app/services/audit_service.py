from datetime import datetime, timezone, time
from flask import request, session, g
from pymongo import MongoClient

class AuditAction:
    # CCO actions
    VIEW_CCO = 'VIEW_CCO'
    EDIT_CCO = 'EDIT_CCO'
    DELETE_CCO = 'DELETE_CCO'
    
    # Correção actions
    CREATE_CORRECAO = 'CREATE_CORRECAO'
    PROMOTE_CORRECAO = 'PROMOTE_CORRECAO'
    REJECT_CORRECAO = 'REJECT_CORRECAO'
    
    # Auth actions
    LOGIN = 'LOGIN'
    LOGOUT = 'LOGOUT'
    FAILED_LOGIN = 'FAILED_LOGIN'

class AuditService:
    def __init__(self, mongo_uri):
        self.client = MongoClient(mongo_uri)
        self.db = self.client.sgppServices
        self.collection = self.db.cco_audit_logs
    
    def log_action(self, action, resource_type=None, resource_id=None, 
                    details=None, status='SUCCESS', user_email=None):
        """
        Registra ação no log de auditoria.
        
        Args:
            action: Tipo de ação (AuditAction)
            resource_type: Tipo de recurso (CCO, USER, etc)
            resource_id: ID do recurso
            details: Dict com detalhes adicionais
            status: SUCCESS ou FAILED
        """

        user_id = user_email
        
        audit_log = {
            'user_id': user_id,
            'username': user_email,
            'action': action,
            'resource_type': resource_type,
            'resource_id': resource_id,
            'timestamp': datetime.now(timezone.utc),
            'ip_address': request.remote_addr,
            'user_agent': request.headers.get('User-Agent'),
            'details': details or {},
            'status': status
        }
        
        self.collection.insert_one(audit_log)
    
    def get_user_actions(self, user_id, limit=100):
        """Retorna ações de um usuário específico"""
        return list(self.collection.find(
            {'user_id': user_id}
        ).sort('timestamp', -1).limit(limit))
    
    def get_resource_history(self, resource_type, resource_id):
        """Retorna histórico de um recurso"""
        return list(self.collection.find({
            'resource_type': resource_type,
            'resource_id': resource_id
        }).sort('timestamp', -1))
    
    def get_all(self, start_date=None, end_date=None):
        """Retorna logs de auditoria com filtro opcional por intervalo de datas."""
        query = {}

        if start_date or end_date:
            timestamp_filter = {}

            if start_date:
                timestamp_filter['$gte'] = datetime.combine(start_date, time.min)

            if end_date:
                timestamp_filter['$lte'] = datetime.combine(end_date, time.max)

            query['timestamp'] = timestamp_filter

        return list(self.collection.find(query).sort('timestamp', -1))