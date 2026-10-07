"""
app/routes/verificacao_tp_routes.py
=====================================
Blueprint para verificação do Tract Participation (TP) utilizado na geração de CCOs.

Rotas:
  GET  /verificacao-tp/                  → página principal
  GET  /verificacao-tp/api/contratos     → lista contratos
  GET  /verificacao-tp/api/campos        → lista campos por contrato
  GET  /verificacao-tp/api/fases         → lista fases
  POST /verificacao-tp/api/buscar        → busca CCOs por filtros
  POST /verificacao-tp/api/analisar      → analisa TP das CCOs selecionadas
  POST /verificacao-tp/api/preview       → preview de reconstrução com novo TP
  GET  /verificacao-tp/api/cco/<cco_id>  → análise de TP de uma CCO específica (integração recálculo)
  GET  /verificacao-tp/download-csv      → download CSV do último resultado

Nota: análise depende da coleção 'event' — recomendado usar PRD para resultados completos.
"""

import json
import logging
import os
import tempfile
import uuid

from flask import Blueprint, Response, jsonify, render_template, request, session

from pymongo import MongoClient
from app.config import MONGO_URI, MONGO_URI_PRD
from app.services.verificacao_tp_service import VerificacaoTPService
from app.middleware.auth_middleware import require_permission, deny_client
from app.models.permission import Permission

logger = logging.getLogger(__name__)

verificacao_tp_bp = Blueprint("verificacao_tp", __name__, url_prefix="/verificacao-tp")

_TEMP_DIR = os.path.join(tempfile.gettempdir(), "ppsa_tp")
os.makedirs(_TEMP_DIR, exist_ok=True)


def _get_service(db_env: str = "prd") -> VerificacaoTPService:
    uri = MONGO_URI_PRD if db_env == "prd" else MONGO_URI
    client = MongoClient(uri)
    return VerificacaoTPService(client.sgppServices)


def _json(data, status=200):
    r = jsonify(data)
    r.status_code = status
    return r


def _salvar(dados: list, db_env: str = "prd") -> str:
    sid = str(uuid.uuid4())
    payload = {"resultados": dados, "db_env": db_env}
    with open(os.path.join(_TEMP_DIR, f"{sid}.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, default=str)
    return sid


def _carregar(sid: str):
    """Retorna (lista_resultados, db_env). Retrocompatível com formato antigo (lista pura)."""
    if not sid:
        return [], "prd"
    path = os.path.join(_TEMP_DIR, f"{sid}.json")
    if not os.path.exists(path):
        return [], "prd"
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    if isinstance(payload, list):
        return payload, "prd"
    return payload.get("resultados", []), payload.get("db_env", "prd")


# ---------------------------------------------------------------------------
# Página
# ---------------------------------------------------------------------------

@verificacao_tp_bp.route("/")
@require_permission(Permission.CCO_VIEW)
@deny_client()
def index():
    return render_template(
        "verificacao_tp/index.html",
        titulo="Verificação de Tract Participation (TP)",
    )


# ---------------------------------------------------------------------------
# APIs de suporte
# ---------------------------------------------------------------------------

@verificacao_tp_bp.route("/api/contratos")
@require_permission(Permission.CCO_VIEW)
@deny_client()
def api_contratos():
    try:
        db_env = request.args.get("db", "prd")
        return _json({"success": True, "contratos": _get_service(db_env).listar_contratos()})
    except Exception as e:
        return _json({"success": False, "error": str(e)}, 500)


@verificacao_tp_bp.route("/api/campos")
@require_permission(Permission.CCO_VIEW)
@deny_client()
def api_campos():
    try:
        db_env = request.args.get("db", "prd")
        return _json({"success": True, "campos": _get_service(db_env).listar_campos(request.args.get("contrato", ""))})
    except Exception as e:
        return _json({"success": False, "error": str(e)}, 500)


@verificacao_tp_bp.route("/api/fases")
@require_permission(Permission.CCO_VIEW)
@deny_client()
def api_fases():
    try:
        db_env = request.args.get("db", "prd")
        return _json({"success": True, "fases": _get_service(db_env).listar_fases()})
    except Exception as e:
        return _json({"success": False, "error": str(e)}, 500)


# ---------------------------------------------------------------------------
# Busca de CCOs
# ---------------------------------------------------------------------------

@verificacao_tp_bp.route("/api/buscar", methods=["POST"])
@require_permission(Permission.CCO_VIEW)
@deny_client()
def api_buscar():
    try:
        filtros = request.get_json() or {}
        db_env = filtros.get("db", "prd")
        svc = _get_service(db_env)
        ccos_raw = svc.buscar_ccos(filtros)

        def _limpar(doc):
            resultado = {}
            for k, v in doc.items():
                if k == "correcoesMonetarias":
                    continue
                if k == "_id":
                    resultado[k] = str(v)
                elif hasattr(v, "to_decimal"):
                    resultado[k] = float(v.to_decimal())
                elif hasattr(v, "isoformat"):
                    resultado[k] = str(v)
                else:
                    resultado[k] = v
            return resultado

        ccos = [_limpar(c) for c in ccos_raw]
        return _json({"success": True, "ccos": ccos, "total": len(ccos)})

    except Exception as e:
        logger.error(f"Erro ao buscar CCOs para TP: {e}", exc_info=True)
        return _json({"success": False, "error": str(e)}, 500)


# ---------------------------------------------------------------------------
# Análise de TP
# ---------------------------------------------------------------------------

@verificacao_tp_bp.route("/api/analisar", methods=["POST"])
@require_permission(Permission.CCO_VIEW)
@deny_client()
def api_analisar():
    try:
        dados = request.get_json() or {}
        cco_ids = dados.get("cco_ids", [])
        db_env  = dados.get("db", "prd")

        if not cco_ids:
            return _json({"success": False, "error": "Nenhuma CCO selecionada"}, 400)

        svc = _get_service(db_env)
        resultados = svc.analisar_tp(cco_ids)

        sid = _salvar(resultados, db_env)
        session["tp_sid"] = sid

        total      = len(resultados)
        ok         = sum(1 for r in resultados if r.get("status") == "OK")
        incons     = sum(1 for r in resultados if r.get("status") == "INCONSISTENTE")
        corrigidas = sum(1 for r in resultados if r.get("status") == "CORRIGIDA")
        corrig_inc = sum(1 for r in resultados if r.get("status") == "CORRIGIDA_INCONSISTENTE")
        sem_tp     = sum(1 for r in resultados if r.get("status") == "SEM_TP")

        por_metodo_orig = {}
        por_metodo_efet = {}
        for r in resultados:
            mo = r.get("metodo_original", "NAO_ENCONTRADO")
            me = r.get("metodo_efetivo",  "NAO_ENCONTRADO")
            por_metodo_orig[mo] = por_metodo_orig.get(mo, 0) + 1
            por_metodo_efet[me] = por_metodo_efet.get(me, 0) + 1

        return _json({
            "success": True,
            "sid": sid,
            "resultados": resultados,
            "estatisticas": {
                "total": total,
                "ok": ok,
                "inconsistentes": incons,
                "corrigidas": corrigidas,
                "corrigidas_inconsistentes": corrig_inc,
                "sem_tp": sem_tp,
                "por_metodo_original": por_metodo_orig,
                "por_metodo_efetivo": por_metodo_efet,
            },
        })

    except Exception as e:
        logger.error(f"Erro na análise de TP: {e}", exc_info=True)
        return _json({"success": False, "error": str(e)}, 500)


# ---------------------------------------------------------------------------
# Consulta de CCO individual — integração com recálculo de TP
# ---------------------------------------------------------------------------

@verificacao_tp_bp.route("/api/cco/<cco_id>")
@require_permission(Permission.CCO_VIEW)
@deny_client()
def api_cco(cco_id):
    """
    Retorna a análise completa de TP de uma CCO específica.

    Usado pela tela de recálculo de TP (/recalculo/executar/<id>) para obter:
      - tp_efetivo_percentual  : TP atual implícito nos valores da CCO
      - tp_original_percentual : TP no momento da criação (via evento)
      - tp_contrato_na_data    : TP do contrato cadastrado na data da CCO
      - tp_contrato_atual      : TP do contrato cadastrado atualmente
      - status, alertas        : diagnóstico de consistência
      - campos_alterados_cco   : campos financeiros raiz que foram alterados

    Query params:
      db: "dev" | "prd"  (default: "prd" — recomendado por depender de eventos)
    """
    try:
        db_env = request.args.get("db", "prd")
        svc = _get_service(db_env)
        cco = svc.cco_col.find_one({"_id": cco_id})
        if not cco:
            return _json({"success": False, "error": f"CCO {cco_id} não encontrada"}, 404)
        resultado = svc._analisar_cco(cco)
        return _json({"success": True, "analise": resultado})
    except Exception as e:
        logger.error(f"Erro na consulta de CCO TP {cco_id}: {e}", exc_info=True)
        return _json({"success": False, "error": str(e)}, 500)


# ---------------------------------------------------------------------------
# Preview de reconstrução com novo TP
# ---------------------------------------------------------------------------

@verificacao_tp_bp.route("/api/preview", methods=["POST"])
@require_permission(Permission.CCO_VIEW)
@deny_client()
def api_preview():
    try:
        dados = request.get_json() or {}
        cco_id      = dados.get("cco_id")
        novo_tp     = dados.get("novo_tp_percentual")
        tp_original = dados.get("tp_original_percentual")
        db_env      = dados.get("db", "prd")

        if not cco_id or novo_tp is None:
            return _json({"success": False, "error": "cco_id e novo_tp_percentual são obrigatórios"}, 400)

        svc = _get_service(db_env)
        preview = svc.preview_reconstrucao(cco_id, float(novo_tp))
        preview["tp_original_percentual"] = float(tp_original) if tp_original else None

        return _json({"success": True, "preview": preview})

    except Exception as e:
        logger.error(f"Erro no preview de reconstrução: {e}", exc_info=True)
        return _json({"success": False, "error": str(e)}, 500)


# ---------------------------------------------------------------------------
# Download CSV
# ---------------------------------------------------------------------------

@verificacao_tp_bp.route("/download-csv")
@require_permission(Permission.CCO_VIEW)
@deny_client()
def download_csv():
    sid = request.args.get("sid") or session.get("tp_sid")
    resultados, db_env = _carregar(sid)
    if not resultados:
        return "Nenhum resultado disponível. Execute a análise primeiro.", 400

    svc = _get_service(db_env)
    conteudo = svc.gerar_csv(resultados)

    return Response(
        conteudo.encode("utf-8-sig"),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=verificacao_tp.csv"},
    )
