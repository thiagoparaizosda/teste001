"""
app/routes/verificacao_ipca_routes.py
======================================
Blueprint para verificação de correções IPCA/IGPM em lote (várias CCOs de uma vez).

Rotas:
  GET  /verificacao-ipca/                 → página principal
  GET  /verificacao-ipca/api/contratos    → lista contratos
  GET  /verificacao-ipca/api/campos       → lista campos por contrato
  GET  /verificacao-ipca/api/fases        → lista fases
  POST /verificacao-ipca/api/buscar       → busca CCOs por filtros
  POST /verificacao-ipca/api/analisar     → roda a análise IPCA/IGPM das CCOs selecionadas
  GET  /verificacao-ipca/download-csv     → download CSV do último resultado

Nota: cada CCO analisada reaproveita o mesmo fluxo de duas etapas da tela
individual (/ipca-correcao/): iniciar_analise_cco + gerar_propostas_correcao.
Esta tela é somente leitura/relatório — aprovar e aplicar correções continua
sendo feito CCO a CCO na tela individual (link "Ver detalhes").
"""

import json
import logging
import os
import tempfile
import uuid

from flask import Blueprint, Response, jsonify, render_template, request, session
from pymongo import MongoClient

from app.config import MONGO_URI, MONGO_URI_PRD
from app.middleware.auth_middleware import require_permission, deny_client, get_current_user_id
from app.models.permission import Permission
from app.services.ipca_correcao_engine import IPCACorrectionEngine
from app.services.ipca_correcao_orquestrador import IPCACorrectionOrchestrator
from app.services.ipca_gap_analyzer import IPCAGapAnalyzer
from app.services.verificacao_ipca_service import LIMITE_MAXIMO_LOTE, VerificacaoIpcaService

logger = logging.getLogger(__name__)

verificacao_ipca_bp = Blueprint("verificacao_ipca", __name__, url_prefix="/verificacao-ipca")

_TEMP_DIR = os.path.join(tempfile.gettempdir(), "ppsa_ipca_lote")
os.makedirs(_TEMP_DIR, exist_ok=True)


def _get_service() -> VerificacaoIpcaService:
    """Monta a cadeia de serviços IPCA (gap analyzer → engine → orchestrator) UMA
    ÚNICA VEZ por requisição — reaproveitada por todo o loop de `analisar_lote`,
    ao contrário de recriar conexões/objetos a cada CCO."""
    client = MongoClient(MONGO_URI)
    db = client.sgppServices
    client_prd = MongoClient(MONGO_URI_PRD)
    db_prd = client_prd.sgppServices

    gap_analyzer = IPCAGapAnalyzer(db, db_prd)
    correction_engine = IPCACorrectionEngine(db, db_prd, gap_analyzer)
    orchestrator = IPCACorrectionOrchestrator(db, db_prd, gap_analyzer, correction_engine)

    return VerificacaoIpcaService(db, db_prd, gap_analyzer, correction_engine, orchestrator)


def _json(data, status=200):
    r = jsonify(data)
    r.status_code = status
    return r


def _salvar(dados: list) -> str:
    sid = str(uuid.uuid4())
    payload = {"resultados": dados}
    with open(os.path.join(_TEMP_DIR, f"{sid}.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, default=str)
    return sid


def _carregar(sid: str) -> list:
    if not sid:
        return []
    path = os.path.join(_TEMP_DIR, f"{sid}.json")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    return payload.get("resultados", [])


# ---------------------------------------------------------------------------
# Página
# ---------------------------------------------------------------------------

@verificacao_ipca_bp.route("/")
@require_permission(Permission.CORRECAO_CREATE)
@deny_client()
def index():
    return render_template(
        "verificacao_ipca/index.html",
        titulo="Verificação de IPCA/IGPM em Lote",
        limite_maximo=LIMITE_MAXIMO_LOTE,
    )


# ---------------------------------------------------------------------------
# APIs de suporte
# ---------------------------------------------------------------------------

@verificacao_ipca_bp.route("/api/contratos")
@require_permission(Permission.CORRECAO_CREATE)
@deny_client()
def api_contratos():
    try:
        return _json({"success": True, "contratos": _get_service().listar_contratos()})
    except Exception as e:
        logger.error(f"Erro ao listar contratos (verificação IPCA em lote): {e}", exc_info=True)
        return _json({"success": False, "error": str(e)}, 500)


@verificacao_ipca_bp.route("/api/campos")
@require_permission(Permission.CORRECAO_CREATE)
@deny_client()
def api_campos():
    try:
        campos = _get_service().listar_campos(request.args.get("contrato", ""))
        return _json({"success": True, "campos": campos})
    except Exception as e:
        logger.error(f"Erro ao listar campos (verificação IPCA em lote): {e}", exc_info=True)
        return _json({"success": False, "error": str(e)}, 500)


@verificacao_ipca_bp.route("/api/fases")
@require_permission(Permission.CORRECAO_CREATE)
@deny_client()
def api_fases():
    try:
        return _json({"success": True, "fases": _get_service().listar_fases()})
    except Exception as e:
        logger.error(f"Erro ao listar fases (verificação IPCA em lote): {e}", exc_info=True)
        return _json({"success": False, "error": str(e)}, 500)


# ---------------------------------------------------------------------------
# Busca de CCOs
# ---------------------------------------------------------------------------

@verificacao_ipca_bp.route("/api/buscar", methods=["POST"])
@require_permission(Permission.CORRECAO_CREATE)
@deny_client()
def api_buscar():
    try:
        filtros = request.get_json() or {}
        svc = _get_service()
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
        logger.error(f"Erro ao buscar CCOs para verificação IPCA em lote: {e}", exc_info=True)
        return _json({"success": False, "error": str(e)}, 500)


# ---------------------------------------------------------------------------
# Análise em lote
# ---------------------------------------------------------------------------

@verificacao_ipca_bp.route("/api/analisar", methods=["POST"])
@require_permission(Permission.CORRECAO_CREATE)
@deny_client()
def api_analisar():
    try:
        dados = request.get_json() or {}
        cco_ids = dados.get("cco_ids", [])

        if not cco_ids:
            return _json({"success": False, "error": "Nenhuma CCO selecionada"}, 400)

        if len(cco_ids) > LIMITE_MAXIMO_LOTE:
            return _json({
                "success": False,
                "error": f"Selecione no máximo {LIMITE_MAXIMO_LOTE} CCOs por análise em lote"
            }, 400)

        user_id = get_current_user_id()

        svc = _get_service()
        resultados = svc.analisar_lote(cco_ids, user_id)

        sid = _salvar(resultados)
        session["ipca_lote_sid"] = sid

        total = len(resultados)
        ok = sum(1 for r in resultados if r.get("status") == "OK")
        sem_propostas = sum(1 for r in resultados if r.get("status") == "SEM_PROPOSTAS")
        erro = sum(1 for r in resultados if r.get("status") == "ERRO")
        erro_propostas = sum(1 for r in resultados if r.get("status") == "ERRO_PROPOSTAS")

        por_cenario = {}
        por_tipo_proposta = {}
        for r in resultados:
            cenario = r.get("scenario_detected") or "N/A"
            tipo = r.get("tipo_proposta_usada") or "N/A"
            por_cenario[cenario] = por_cenario.get(cenario, 0) + 1
            por_tipo_proposta[tipo] = por_tipo_proposta.get(tipo, 0) + 1

        return _json({
            "success": True,
            "sid": sid,
            "resultados": resultados,
            "estatisticas": {
                "total": total,
                "ok": ok,
                "sem_propostas": sem_propostas,
                "erro": erro,
                "erro_propostas": erro_propostas,
                "por_cenario": por_cenario,
                "por_tipo_proposta": por_tipo_proposta,
            },
        })

    except Exception as e:
        logger.error(f"Erro na análise em lote de IPCA/IGPM: {e}", exc_info=True)
        return _json({"success": False, "error": str(e)}, 500)


# ---------------------------------------------------------------------------
# Download CSV
# ---------------------------------------------------------------------------

@verificacao_ipca_bp.route("/download-csv")
@require_permission(Permission.CORRECAO_CREATE)
@deny_client()
def download_csv():
    sid = request.args.get("sid") or session.get("ipca_lote_sid")
    resultados = _carregar(sid)
    if not resultados:
        return "Nenhum resultado disponível. Execute a análise primeiro.", 400

    svc = _get_service()
    conteudo = svc.gerar_csv(resultados)

    return Response(
        conteudo.encode("utf-8-sig"),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=verificacao_ipca_lote.csv"},
    )
