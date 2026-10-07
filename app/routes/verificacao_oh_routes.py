"""
app/routes/verificacao_oh_routes.py
=====================================
Blueprint para verificação de OverHeads das CCOs.

Rotas:
  GET  /verificacao-oh/                  → página principal
  GET  /verificacao-oh/analise-exp       → página drill-down por faixas
  GET  /verificacao-oh/api/contratos     → lista contratos
  GET  /verificacao-oh/api/campos        → lista campos por contrato
  GET  /verificacao-oh/api/fases         → lista fases
  POST /verificacao-oh/api/verificar     → busca + verifica OH → JSON
  GET  /verificacao-oh/api/analise-exp   → análise por faixas de uma CCO
  GET  /verificacao-oh/download-csv      → download CSV do último resultado
"""

import json
import logging
import os
import tempfile
import uuid
from flask import Blueprint, Response, jsonify, render_template, request, session, url_for

from pymongo import MongoClient
from app.config import MONGO_URI, MONGO_URI_PRD
from app.services.verificacao_oh_service import VerificacaoOHService
from app.middleware.auth_middleware import require_permission, deny_client
from app.models.permission import Permission

logger = logging.getLogger(__name__)

verificacao_oh_bp = Blueprint("verificacao_oh", __name__, url_prefix="/verificacao-oh")

_TEMP_DIR = os.path.join(tempfile.gettempdir(), "ppsa_oh")
os.makedirs(_TEMP_DIR, exist_ok=True)


def _get_service(db_env: str = "dev") -> VerificacaoOHService:
    uri    = MONGO_URI_PRD if db_env == "prd" else MONGO_URI
    client = MongoClient(uri)
    return VerificacaoOHService(client.sgppServices)


def _salvar_resultado(resultados: list, db_env: str = "dev") -> str:
    sid = str(uuid.uuid4())
    payload = {"resultados": resultados, "db_env": db_env}
    with open(os.path.join(_TEMP_DIR, f"{sid}.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    return sid


def _carregar_resultado(sid: str):
    """Retorna (lista_resultados, db_env). Se não encontrado, retorna ([], 'dev')."""
    if not sid:
        return [], "dev"
    path = os.path.join(_TEMP_DIR, f"{sid}.json")
    if not os.path.exists(path):
        return [], "dev"
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    if isinstance(payload, list):
        return payload, "dev"
    return payload.get("resultados", []), payload.get("db_env", "dev")


def _json(data, status=200):
    r = jsonify(data)
    r.status_code = status
    return r


# ---------------------------------------------------------------------------
# Páginas
# ---------------------------------------------------------------------------

@verificacao_oh_bp.route("/")
@require_permission(Permission.CCO_VIEW)
@deny_client()
def index():
    return render_template(
        "verificacao_oh/index.html",
        titulo="Verificação de OverHeads (OH)",
        url_analise_exp=url_for("verificacao_oh.analise_exp"),
    )


@verificacao_oh_bp.route("/analise-exp")
@require_permission(Permission.CCO_VIEW)
@deny_client()
def analise_exp():
    return render_template(
        "verificacao_oh/analise_exp.html",
        titulo="Análise de OH Exploração por Faixas",
        cco_id=request.args.get("cco_id", ""),
        db_env=request.args.get("db", "dev"),
        url_api_analise=url_for("verificacao_oh.api_analise_exp"),
        url_voltar=url_for("verificacao_oh.index"),
    )


# ---------------------------------------------------------------------------
# APIs de suporte (filtros)
# ---------------------------------------------------------------------------

@verificacao_oh_bp.route("/api/contratos")
@require_permission(Permission.CCO_VIEW)
@deny_client()
def api_contratos():
    try:
        db_env = request.args.get("db", "dev")
        return _json({"success": True, "contratos": _get_service(db_env).listar_contratos()})
    except Exception as e:
        logger.error(f"Erro ao listar contratos OH: {e}")
        return _json({"success": False, "error": str(e)}, 500)


@verificacao_oh_bp.route("/api/campos")
@require_permission(Permission.CCO_VIEW)
@deny_client()
def api_campos():
    try:
        db_env   = request.args.get("db", "dev")
        contrato = request.args.get("contrato", "")
        return _json({"success": True, "campos": _get_service(db_env).listar_campos(contrato)})
    except Exception as e:
        logger.error(f"Erro ao listar campos OH: {e}")
        return _json({"success": False, "error": str(e)}, 500)


@verificacao_oh_bp.route("/api/fases")
@require_permission(Permission.CCO_VIEW)
@deny_client()
def api_fases():
    try:
        db_env = request.args.get("db", "dev")
        return _json({"success": True, "fases": _get_service(db_env).listar_fases()})
    except Exception as e:
        logger.error(f"Erro ao listar fases OH: {e}")
        return _json({"success": False, "error": str(e)}, 500)


# ---------------------------------------------------------------------------
# Verificação principal
# ---------------------------------------------------------------------------

@verificacao_oh_bp.route("/api/verificar", methods=["POST"])
@require_permission(Permission.CCO_VIEW)
@deny_client()
def api_verificar():
    try:
        filtros  = request.get_json() or {}
        db_env   = filtros.get("db", "dev")
        svc      = _get_service(db_env)

        ccos_raw = svc.buscar_ccos(filtros)
        if not ccos_raw:
            return _json({"success": True, "resultados": [], "estatisticas": {}, "total_encontrados": 0})

        resultados   = svc.verificar_oh(ccos_raw)
        estatisticas = svc.calcular_estatisticas(resultados)

        sid = _salvar_resultado(resultados, db_env)
        session["oh_sid"] = sid

        return _json({
            "success": True,
            "total_encontrados": len(ccos_raw),
            "resultados": resultados,
            "estatisticas": estatisticas,
        })

    except Exception as e:
        logger.error(f"Erro na verificação OH: {e}", exc_info=True)
        return _json({"success": False, "error": str(e)}, 500)


# ---------------------------------------------------------------------------
# Análise de faixas
# ---------------------------------------------------------------------------

@verificacao_oh_bp.route("/api/analise-exp")
@require_permission(Permission.CCO_VIEW)
@deny_client()
def api_analise_exp():
    try:
        cco_id = request.args.get("cco_id", "").strip()
        db_env = request.args.get("db", "dev")
        if not cco_id:
            return _json({"success": False, "error": "cco_id obrigatório"}, 400)
        resultado = _get_service(db_env).analisar_faixas_exploracao(cco_id)
        return _json({"success": True, **resultado})
    except ValueError as e:
        return _json({"success": False, "error": str(e)}, 404)
    except Exception as e:
        logger.error(f"Erro na análise de faixas OH: {e}", exc_info=True)
        return _json({"success": False, "error": str(e)}, 500)


# ---------------------------------------------------------------------------
# Download CSV
# ---------------------------------------------------------------------------

@verificacao_oh_bp.route("/download-csv")
@require_permission(Permission.CCO_VIEW)
@deny_client()
def download_csv():
    sid = request.args.get("sid") or session.get("oh_sid")
    resultados, db_env = _carregar_resultado(sid)
    if not resultados:
        return "Nenhum resultado disponível. Execute a verificação primeiro.", 400

    conteudo = _get_service(db_env).gerar_csv(resultados)

    return Response(
        conteudo.encode("utf-8-sig"),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=verificacao_oh.csv"},
    )
