from datetime import datetime

from flask import Blueprint, render_template, request
from bson import ObjectId

from app.config import MONGO_URI_ATIVO
from app.models.permission import Permission
from app.middleware.auth_middleware import require_permission
from app.services.audit_service import AuditService

audit_bp = Blueprint('audit', __name__)

audit_service = AuditService(MONGO_URI_ATIVO)

@audit_bp.context_processor
def inject_today_date():
    return {'today_date': datetime.today().strftime('%Y-%m-%d')}

@audit_bp.route('/audit')
@require_permission(Permission.AUDIT)
def search():
    """Página para exibição dos logs de auditoria"""
    data_inicio_str = (request.args.get('data_inicio') or '').strip()
    data_fim_str = (request.args.get('data_fim') or '').strip()

    data_inicio = None
    data_fim = None

    try:
        if data_inicio_str:
            data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
    except ValueError:
        data_inicio = None

    try:
        if data_fim_str:
            data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date()
    except ValueError:
        data_fim = None

    if data_inicio and data_fim and data_inicio > data_fim:
        data_inicio, data_fim = data_fim, data_inicio

    logs = audit_service.get_all(start_date=data_inicio, end_date=data_fim)
    logs_json = []

    for log in logs:
        item = dict(log)

        for key, value in item.items():
            if isinstance(value, ObjectId):
                item[key] = str(value)
            elif isinstance(value, datetime):
                item[key] = value.isoformat()

        logs_json.append(item)

    return render_template('admin/audit_logs.html',
                         titulo="Logs de Auditoria",
                         logs_json=logs_json,
                         filtro_data_inicio=(data_inicio.isoformat() if data_inicio else ''),
                         filtro_data_fim=(data_fim.isoformat() if data_fim else ''))