"""
app/services/verificacao_tp_service.py
=======================================
Serviço de verificação do Tract Participation (TP) utilizado na geração de CCOs.

Duas abordagens para descobrir o TP original:

  ABORDAGEM 2 (primária — mais segura):
    Consulta a coleção 'event' para encontrar o estado da remessa_derivada_campo_entity
    imediatamente antes da criação da CCO. O TP está em tractParticipationPercentual
    de cada item de gasto do evento.

  ABORDAGEM 1 (fallback — matemática):
    Reconstrói o TP dividindo valorReconhecido da CCO pelo valorReconhecido bruto
    dos itens da fase correspondente em remessa_entity (valores sem aplicação de TP).
"""

import csv
import io
import logging
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Dict, List, Optional

from pymongo.database import Database

logger = logging.getLogger(__name__)

TOLERANCIA_ZERO = Decimal("0.01")
TOLERANCIA_TP = Decimal("0.000005")          # ±0.005% para considerar TPs iguais


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dec(v) -> Decimal:
    if v is None:
        return Decimal("0")
    try:
        if hasattr(v, "to_decimal"):
            return v.to_decimal()
        return Decimal(str(v))
    except (InvalidOperation, TypeError):
        return Decimal("0")


def _f(v) -> float:
    return float(_dec(v))


def _parse_date(v):
    """Converte ISODate, str ou datetime para datetime naive."""
    from datetime import datetime, timezone
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.replace(tzinfo=None)
    if isinstance(v, str):
        for fmt in (
            "%Y-%m-%dT%H:%M:%S.%f%z",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
        ):
            try:
                dt = datetime.strptime(v, fmt)
                return dt.replace(tzinfo=None)
            except ValueError:
                continue
    return None


def _tp_iguais(tp1: Optional[float], tp2: Optional[float]) -> bool:
    if tp1 is None or tp2 is None:
        return False
    return abs(Decimal(str(tp1)) - Decimal(str(tp2))) <= TOLERANCIA_TP


# ---------------------------------------------------------------------------
# Abordagem 2: via coleção event
# ---------------------------------------------------------------------------

def _tp_via_evento(cco: Dict, db: Database) -> Dict:
    """
    Busca o TP no registro de evento da remessa_derivada imediatamente
    anterior à criação da CCO.

    Retorna dict com:
      tp_percentual, tp_decimal, fonte, gastos_amostra, event_id, event_date
    """
    resultado = {"tp_percentual": None, "tp_decimal": None,
                 "fonte": "EVENTO", "gastos_amostra": [], "detalhe": ""}

    cco_id = str(cco.get("_id", ""))
    id_remessa_geradora = cco.get("idRemessaGeradora")

    # 1. Data de criação da CCO (evento versão 1)
    evento_cco = db["event"].find_one(
        {"aggregateId": cco_id, "version": 1},
        {"eventDate": 1}
    )
    if not evento_cco:
        resultado["detalhe"] = "Evento de criação da CCO (version=1) não encontrado"
        return resultado

    event_date_cco = _parse_date(evento_cco.get("eventDate"))
    if not event_date_cco:
        resultado["detalhe"] = "eventDate da CCO não parseável"
        return resultado

    # 2. Localiza idRemessaGeradora se ausente
    if not id_remessa_geradora:
        derivada = db["remessa_derivada_campo_entity"].find_one(
            {
                "contratoCPP": cco.get("contratoCpp"),
                "campo": cco.get("campo"),
                "remessa": cco.get("remessa"),
                "faseRemessa": cco.get("faseRemessa"),
            },
            {"_id": 1}
        )
        if derivada:
            id_remessa_geradora = str(derivada["_id"])
            resultado["detalhe"] += "[idRemessaGeradora resolvido por chave] "
        else:
            resultado["detalhe"] = "idRemessaGeradora ausente e não resolvido por chave"
            return resultado

    # 3. Evento da remessa_derivada mais recente ANTES da criação da CCO
    evento_derivada = db["event"].find_one(
        {
            "aggregateId": id_remessa_geradora,
            "eventDate": {"$lt": evento_cco["eventDate"]},  # compara em tipo nativo
        },
        sort=[("eventDate", -1)],
    )

    if not evento_derivada:
        resultado["detalhe"] += "Nenhum evento de remessa_derivada anterior à criação da CCO"
        return resultado

    # 4. Extrai TP dos itens de gasto do evento
    remessa_snap = evento_derivada.get("remessaDerivadaPorCampo", {})
    gastos = remessa_snap.get("gastos", [])
    tps = [
        g.get("tractParticipationPercentual")
        for g in gastos
        if g.get("tractParticipationPercentual") is not None
    ]

    if not tps:
        resultado["detalhe"] += "Nenhum tractParticipationPercentual nos itens do evento"
        return resultado

    # Usa o primeiro valor (todos devem ser o mesmo TP naquele momento)
    tp_pct = float(tps[0])
    resultado["tp_percentual"] = tp_pct
    resultado["tp_decimal"] = round(tp_pct / 100, 9)
    resultado["event_id"] = str(evento_derivada["_id"])
    resultado["event_date"] = str(evento_derivada.get("eventDate", ""))
    resultado["gastos_amostra"] = [
        {
            "item": g.get("item"),
            "tractParticipationPercentual": g.get("tractParticipationPercentual"),
            "valorMoedaOBJReal": _f(g.get("valorMoedaOBJReal")),
            "valorMoedaOBJRealOriginal": _f(g.get("valorMoedaOBJRealOriginal")),
        }
        for g in gastos[:3]
    ]
    resultado["detalhe"] += f"TP extraído do evento {str(evento_derivada['_id'])}"
    return resultado


# ---------------------------------------------------------------------------
# Abordagem 1: via remessa_entity (matemática)
# ---------------------------------------------------------------------------

def _tp_via_remessa(cco: Dict, db: Database) -> Dict:
    """
    Deriva o TP matematicamente:
      TP = valorReconhecido(CCO) / Σ valorReconhecido(remessa_entity, fase=cco.faseRemessa)
    """
    resultado = {"tp_percentual": None, "tp_decimal": None,
                 "fonte": "REMESSA", "detalhe": ""}

    id_remessa_geradora = cco.get("idRemessaGeradora")
    fase_cco = cco.get("faseRemessa", "")
    valor_reconhecido_cco = _dec(cco.get("valorReconhecido"))

    if abs(valor_reconhecido_cco) < TOLERANCIA_ZERO:
        resultado["detalhe"] = "valorReconhecido da CCO é zero — TP não calculável"
        return resultado

    # 1. Obtém idRemessaOriginal via remessa_derivada
    id_remessa_original = None
    if id_remessa_geradora:
        derivada = db["remessa_derivada_campo_entity"].find_one(
            {"_id": id_remessa_geradora}, {"idRemessaOriginal": 1}
        )
        if derivada:
            id_remessa_original = derivada.get("idRemessaOriginal")

    if not id_remessa_original:
        # Tenta resolver pela remessa_entity por chave
        remessa_entity = db["remessa_entity"].find_one(
            {
                "contratoCPP": cco.get("contratoCpp"),
                "remessa": cco.get("remessa"),
                "faseRemessa": {"$in": [fase_cco, "MEN", "ROP", "RAD", "REC", "REV"]},
            },
            {"_id": 1}
        )
        if remessa_entity:
            id_remessa_original = str(remessa_entity["_id"])
            resultado["detalhe"] += "[remessa_entity resolvida por chave] "

    if not id_remessa_original:
        resultado["detalhe"] += "remessa_entity não encontrada"
        return resultado

    # 2. Busca a remessa_entity e filtra itens da fase da CCO que foram reconhecidos
    remessa = db["remessa_entity"].find_one({"_id": id_remessa_original})
    if not remessa:
        resultado["detalhe"] += f"remessa_entity {id_remessa_original} não encontrada"
        return resultado

    gastos = remessa.get("gastos", [])
    itens_fase = [
        g for g in gastos
        if g.get("faseRemessa") == fase_cco and g.get("reconhecido") == "SIM"
    ]

    if not itens_fase:
        # Tenta faseRespostaGestora como fallback
        itens_fase = [
            g for g in gastos
            if g.get("faseRespostaGestora") == fase_cco and g.get("reconhecido") == "SIM"
        ]

    if not itens_fase:
        resultado["detalhe"] += (
            f"Nenhum item reconhecido na fase {fase_cco} em remessa_entity"
        )
        return resultado

    soma_sem_tp = sum(_dec(g.get("valorReconhecido", 0)) for g in itens_fase)

    if abs(soma_sem_tp) < TOLERANCIA_ZERO:
        resultado["detalhe"] += "Soma dos valorReconhecido da remessa_entity é zero"
        return resultado

    tp_dec = (valor_reconhecido_cco / soma_sem_tp).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)
    tp_pct = float(tp_dec * 100)

    resultado["tp_percentual"] = tp_pct
    resultado["tp_decimal"] = float(tp_dec)
    resultado["soma_sem_tp"] = float(soma_sem_tp)
    resultado["valor_reconhecido_cco"] = float(valor_reconhecido_cco)
    resultado["qtd_itens_fase"] = len(itens_fase)
    resultado["id_remessa_original"] = id_remessa_original
    resultado["detalhe"] += (
        f"TP calculado: {tp_pct:.6f}% "
        f"({float(valor_reconhecido_cco):.2f} / {float(soma_sem_tp):.2f})"
    )
    return resultado


# ---------------------------------------------------------------------------
# TP do contrato na data
# ---------------------------------------------------------------------------

def _tp_contrato_na_data(contrato: str, campo: str, data_ref, db: Database, origem: str = "") -> Optional[float]:
    """
    Retorna o TP vigente no contrato/campo na data informada.
    Consulta tractParticipations do campo em contrato_entity.
    """
    try:
        contrato_doc = db["contrato_entity"].find_one({"nome": contrato})
        if not contrato_doc:
            return None

        # EXCLUSIVO e AEGV → TP fica na raiz do contrato
        if origem in ("GASTO_EXCLUSIVO", "EXCLUSIVO", "GASTO_AEGV", "AEGV"):
            tps = contrato_doc.get("tractParticipations", [])
        else:
            # JAZIDA_COMPARTILHADA / ATIVO_COMPARTILHADO → TP fica em campos[]
            campos_contrato = contrato_doc.get("campos", [])
            campo_doc = next((c for c in campos_contrato if c.get("nome") == campo), None)
            tps = campo_doc.get("tractParticipations", []) if campo_doc else contrato_doc.get("tractParticipations", [])

        if not tps or data_ref is None:
            return None

        for tp in tps:
            inicio = _parse_date(tp.get("dataInicio"))
            fim = _parse_date(tp.get("dataFim"))
            if inicio and fim and inicio <= data_ref <= fim:
                return float(_dec(tp.get("percentual", 0)))

        # Se não encontrou faixa, retorna o mais recente
        return float(_dec(tps[-1].get("percentual", 0)))
    except Exception as e:
        logger.warning(f"Erro ao consultar TP do contrato: {e}")
        return None

# Campos financeiros raiz que, se mudarem, indicam recalculo de TP ou valor
_CAMPOS_FINANCEIROS_RAIZ = [
    "valorLancamentoTotal",
    "valorReconhecido",
    "valorReconhecivel",
    "valorNaoReconhecido",
    "valorNaoPassivelRecuperacao",
    "valorReconhecidoExploracao",
    "valorReconhecidoProducao",
    "valorRecusado",
    "overHeadExploracao",
    "overHeadProducao",
    "overHeadTotal",
    "valorReconhecidoComOH",
]
_TOLERANCIA_DIFF_VALOR = Decimal("0.01")


def _historico_eventos_cco(cco_id: str, db: Database) -> Dict:
    """
    Detecta se os atributos financeiros raiz da CCO foram alterados
    comparando o evento de criação (version=1) com o estado atual da coleção.
    """
    resultado = {
        "qtd_eventos": 0,
        "teve_modificacoes": False,
        "campos_alterados": [],
        "modificacoes": [],
    }

    try:
        # Conta total de eventos
        resultado["qtd_eventos"] = db["event"].count_documents({"aggregateId": cco_id})

        # Busca apenas o evento de criação (version=1)
        evento_criacao = db["event"].find_one(
            {"aggregateId": cco_id, "version": 1},
            {"contaCustoOleoEntity": 1, "eventDate": 1}
        )
        if not evento_criacao:
            resultado["modificacoes"].append("Evento de criação não encontrado")
            return resultado

        snap = evento_criacao.get("contaCustoOleoEntity") or {}

        # CCO atual (já temos no contexto, mas relemos para garantir)
        cco_atual = db["conta_custo_oleo_entity"].find_one({"_id": cco_id}) or {}

        campos_alterados = []
        for campo in _CAMPOS_FINANCEIROS_RAIZ:
            v_criacao = _dec(snap.get(campo))
            v_atual   = _dec(cco_atual.get(campo))
            diff = abs(v_atual - v_criacao)
            if diff > _TOLERANCIA_DIFF_VALOR:
                campos_alterados.append({
                    "campo": campo,
                    "valor_criacao": float(v_criacao),
                    "valor_atual":   float(v_atual),
                    "diferenca":     float(v_atual - v_criacao),
                })

        resultado["campos_alterados"] = campos_alterados
        resultado["teve_modificacoes"] = len(campos_alterados) > 0

        if campos_alterados:
            data_criacao = str(evento_criacao.get("eventDate", ""))[:19]
            resultado["modificacoes"].append(
                f"Criação em {data_criacao}: "
                + ", ".join(
                    f"{c['campo']} ({c['valor_criacao']:.2f}→{c['valor_atual']:.2f})"
                    for c in campos_alterados
                )
            )

    except Exception as e:
        logger.warning(f"Erro ao verificar histórico da CCO {cco_id}: {e}")

    return resultado
# ---------------------------------------------------------------------------
# Reconstrução simulada de CCO com novo TP (preview)
# ---------------------------------------------------------------------------

def _reconstruir_cco_preview(cco: Dict, novo_tp_percentual: float, db: Database) -> Dict:
    """
    Simula como a CCO ficaria com o novo TP, sem persistir nada.
    Usa a lógica da Abordagem 1 para reconstruir do remessa_entity.
    """
    resultado = {"sucesso": False, "detalhe": ""}
    fase_cco = cco.get("faseRemessa", "")
    id_remessa_geradora = cco.get("idRemessaGeradora")
    novo_tp = Decimal(str(novo_tp_percentual)) / 100

    # Localiza remessa_entity
    id_remessa_original = None
    if id_remessa_geradora:
        derivada = db["remessa_derivada_campo_entity"].find_one(
            {"_id": id_remessa_geradora}, {"idRemessaOriginal": 1}
        )
        if derivada:
            id_remessa_original = derivada.get("idRemessaOriginal")

    if not id_remessa_original:
        resultado["detalhe"] = "remessa_entity não localizável"
        return resultado

    remessa = db["remessa_entity"].find_one({"_id": id_remessa_original})
    if not remessa:
        resultado["detalhe"] = "remessa_entity não encontrada"
        return resultado

    gastos = remessa.get("gastos", [])
    itens_fase = [
        g for g in gastos
        if g.get("faseRemessa") == fase_cco and g.get("reconhecido") == "SIM"
    ]

    if not itens_fase:
        resultado["detalhe"] = f"Sem itens reconhecidos na fase {fase_cco}"
        return resultado

    # Recalcula com novo TP
    val_rec_exp = Decimal("0")
    val_rec_prd = Decimal("0")
    for g in itens_fase:
        val_bruto = _dec(g.get("valorReconhecido", 0))
        val_novo = val_bruto * novo_tp
        if g.get("fase") == "EXP":
            val_rec_exp += val_novo
        else:
            val_rec_prd += val_novo

    val_reconhecido = val_rec_exp + val_rec_prd

    # OH (regras: produção = 1%, exploração = mesmo % que original se > 0)
    oh_prd = val_rec_prd * Decimal("0.01")
    oh_exp = Decimal("0")
    if abs(val_rec_exp) >= TOLERANCIA_ZERO:
        # Mantém a mesma taxa de OH exploração da CCO original
        base_exp_orig = _dec(cco.get("valorReconhecidoExploracao"))
        oh_exp_orig = _dec(cco.get("overHeadExploracao"))
        if abs(base_exp_orig) > TOLERANCIA_ZERO:
            taxa_exp = oh_exp_orig / base_exp_orig
            oh_exp = val_rec_exp * taxa_exp

    oh_total = oh_exp + oh_prd
    val_com_oh = val_reconhecido + oh_total

    # Compara com original
    orig_rec = _dec(cco.get("valorReconhecido"))
    orig_com_oh = _dec(cco.get("valorReconhecidoComOH"))

    resultado.update({
        "sucesso": True,
        "novo_tp_percentual": float(novo_tp_percentual),
        "novo_tp_decimal": float(novo_tp),
        "valorReconhecidoExploracao_novo": float(val_rec_exp),
        "valorReconhecidoProducao_novo": float(val_rec_prd),
        "valorReconhecido_novo": float(val_reconhecido),
        "overHeadExploracao_novo": float(oh_exp),
        "overHeadProducao_novo": float(oh_prd),
        "overHeadTotal_novo": float(oh_total),
        "valorReconhecidoComOH_novo": float(val_com_oh),
        # Diferenças
        "diff_valorReconhecido": float(val_reconhecido - orig_rec),
        "diff_valorReconhecidoComOH": float(val_com_oh - orig_com_oh),
        "diff_percentual": float(
            ((val_com_oh - orig_com_oh) / orig_com_oh * 100)
            if abs(orig_com_oh) > TOLERANCIA_ZERO else Decimal("0")
        ),
        "qtd_itens": len(itens_fase),
        "id_remessa_original": id_remessa_original,
    })
    return resultado


# ---------------------------------------------------------------------------
# Service principal
# ---------------------------------------------------------------------------

class VerificacaoTPService:

    def __init__(self, db: Database):
        self.db = db
        self.cco_col = db["conta_custo_oleo_entity"]

    # ── Busca de CCOs ──────────────────────────────────────────────────────

    def buscar_ccos(self, filtros: Dict) -> List[Dict]:
        query: Dict[str, Any] = {}

        # Busca por ID direto
        if filtros.get("cco_id"):
            doc = self.cco_col.find_one({"_id": filtros["cco_id"]})
            return [doc] if doc else []

        if filtros.get("contratoCpp"):
            query["contratoCpp"] = filtros["contratoCpp"]
        if filtros.get("campo"):
            query["campo"] = filtros["campo"]
        if filtros.get("faseRemessa"):
            query["faseRemessa"] = filtros["faseRemessa"]
        if filtros.get("origemDosGastos"):
            query["origemDosGastos"] = filtros["origemDosGastos"]
        if filtros.get("flgRecuperado") in ("true", "false"):
            query["flgRecuperado"] = filtros["flgRecuperado"] == "true"

        for campo_num in ("remessa", "remessaExposicao"):
            val = str(filtros.get(campo_num, "")).strip()
            if val:
                try:
                    query[campo_num] = int(val)
                except ValueError:
                    pass

        limite = min(int(filtros.get("limite") or 100), 300)
        return list(
            self.cco_col.find(query)
            .sort([("remessa", 1), ("faseRemessa", 1)])
            .limit(limite)
        )

    # ── Análise de TP ──────────────────────────────────────────────────────

    def analisar_tp(self, cco_ids: List[str]) -> List[Dict]:
        """Analisa o TP de cada CCO usando abordagem 2 → 1 como fallback."""
        resultados = []

        for cco_id in cco_ids:
            cco = self.cco_col.find_one({"_id": cco_id})
            if not cco:
                resultados.append({"cco_id": cco_id, "erro": "CCO não encontrada"})
                continue

            resultado = self._analisar_cco(cco)
            resultados.append(resultado)

        return resultados

    def _analisar_cco(self, cco: Dict) -> Dict:
        cco_id = str(cco.get("_id", ""))
        data_rec = _parse_date(cco.get("dataReconhecimento"))
        _origem = cco.get("origemDosGastos", "")

        # ── Sempre executa as DUAS abordagens independentemente ──────────────
        ab2 = _tp_via_evento(cco, self.db)          # TP na criação original
        ab1 = _tp_via_remessa(cco, self.db)          # TP implícito nos valores atuais

        tp_original  = ab2.get("tp_percentual")      # pode ser None
        tp_efetivo   = ab1.get("tp_percentual")      # pode ser None
        metodo_orig  = "EVENTO"   if tp_original is not None else "NAO_ENCONTRADO"
        metodo_efet  = "REMESSA"  if tp_efetivo  is not None else "NAO_ENCONTRADO"

        # ── Histórico de eventos da própria CCO ──────────────────────────────
        historico = _historico_eventos_cco(cco_id, self.db)

        # ── TP do contrato (referência) ──────────────────────────────────────
        tp_contrato_data = _tp_contrato_na_data(
            cco.get("contratoCpp", ""), cco.get("campo", ""), data_rec, self.db, _origem
        )
        tp_contrato_atual = _tp_contrato_na_data(
            cco.get("contratoCpp", ""), cco.get("campo", ""),
            __import__("datetime").datetime(2099, 1, 1), self.db, _origem
        )

        # ── Sinalizadores de comparação ──────────────────────────────────────
        tp_foi_corrigido = (
            tp_original is not None
            and tp_efetivo is not None
            and not _tp_iguais(tp_original, tp_efetivo)
        )
        efetivo_ok_data   = tp_efetivo  is not None and tp_contrato_data  is not None and _tp_iguais(tp_efetivo,  tp_contrato_data)
        efetivo_ok_atual  = tp_efetivo  is not None and tp_contrato_atual is not None and _tp_iguais(tp_efetivo,  tp_contrato_atual)
        original_ok_data  = tp_original is not None and tp_contrato_data  is not None and _tp_iguais(tp_original, tp_contrato_data)

        # ── Status e alertas ─────────────────────────────────────────────────
        alertas = []
        tp_referencia = tp_efetivo if tp_efetivo is not None else tp_original

        if tp_referencia is None:
            status = "SEM_TP"
            alertas.append("Não foi possível determinar o TP usado na geração da CCO")
        else:
            # Alerta: TP efetivo diverge do contrato
            if tp_efetivo is not None and not efetivo_ok_atual:
                alertas.append(
                    f"TP efetivo atual ({tp_efetivo:.6f}%) diverge do TP do contrato "
                    f"({tp_contrato_atual:.6f}%)"
                )
            if tp_efetivo is not None and not efetivo_ok_data and tp_contrato_data != tp_contrato_atual:
                alertas.append(
                    f"TP efetivo atual ({tp_efetivo:.6f}%) diverge do TP do contrato "
                    f"na data da CCO ({tp_contrato_data:.6f}%)"
                )
            # Alerta informativo: CCO foi corrigida
            if tp_foi_corrigido:
                alertas.append(
                    f"TP original na criação ({tp_original:.6f}%) difere do TP atual "
                    f"da CCO ({tp_efetivo:.6f}%) — CCO foi recalculada"
                )
            # Alerta: TP original estava errado (independente de correção)
            if tp_original is not None and not original_ok_data:
                alertas.append(
                    f"TP original na criação ({tp_original:.6f}%) divergia do contrato "
                    f"na data ({tp_contrato_data:.6f}%)"
                )

            # Status prioritário: condição atual da CCO
            efetivo_inconsistente = (
                tp_efetivo is not None
                and tp_contrato_atual is not None
                and not efetivo_ok_atual
            )
            if efetivo_inconsistente and tp_foi_corrigido:
                status = "CORRIGIDA_INCONSISTENTE"   # foi mexida mas ainda errada
            elif efetivo_inconsistente:
                status = "INCONSISTENTE"
            elif tp_foi_corrigido:
                status = "CORRIGIDA"                 # foi corrigida e agora está OK
            else:
                status = "OK"

        return {
            "cco_id": cco_id,
            "contratoCpp": cco.get("contratoCpp", ""),
            "campo": cco.get("campo", ""),
            "remessa": cco.get("remessa"),
            "remessaExposicao": cco.get("remessaExposicao"),
            "faseRemessa": cco.get("faseRemessa", ""),
            "mesAnoReferencia": cco.get("mesAnoReferencia", ""),
            "dataReconhecimento": str(cco.get("dataReconhecimento", ""))[:10],
            "origemDosGastos": (_origem).replace("GASTO_", ""),
            "flgRecuperado": cco.get("flgRecuperado", False),
            "idRemessaGeradora": cco.get("idRemessaGeradora", ""),
            "valorReconhecido": _f(cco.get("valorReconhecido")),
            "valorReconhecidoComOH": _f(cco.get("valorReconhecidoComOH")),
            # TPs
            "tp_original_percentual": tp_original,       # na criação (via evento)
            "tp_efetivo_percentual": tp_efetivo,          # atual (via remessa math)
            "metodo_original": metodo_orig,
            "metodo_efetivo": metodo_efet,
            # TPs do contrato
            "tp_contrato_na_data": tp_contrato_data,
            "tp_contrato_atual": tp_contrato_atual,
            # Sinalizadores
            "tp_foi_corrigido": tp_foi_corrigido,
            "efetivo_alinhado_contrato": efetivo_ok_atual,
            "original_alinhado_contrato": original_ok_data,
            # Histórico da CCO
            "qtd_eventos_cco": historico["qtd_eventos"],
            "cco_teve_modificacoes": historico["teve_modificacoes"],
            "campos_alterados_cco": historico["campos_alterados"],
            "modificacoes_cco": historico["modificacoes"],
            # Status
            "status": status,
            "alertas": alertas,
            # Detalhes brutos
            "detalhe_abordagem2": ab2,
            "detalhe_abordagem1": ab1,
        }

    # ── Preview de reconstrução ────────────────────────────────────────────

    def preview_reconstrucao(self, cco_id: str, novo_tp_percentual: float) -> Dict:
        cco = self.cco_col.find_one({"_id": cco_id})
        if not cco:
            return {"sucesso": False, "detalhe": "CCO não encontrada"}

        preview = _reconstruir_cco_preview(cco, novo_tp_percentual, self.db)
        preview["cco_id"] = cco_id
        preview["tp_original_percentual"] = _f(None)  # será preenchido pelo route
        return preview

    # ── CSV ───────────────────────────────────────────────────────────────

    def gerar_csv(self, resultados: List[Dict]) -> str:
        def br(v):
            if v is None:
                return ""
            try:
                return f"{float(v):.6f}".replace(".", ",")
            except Exception:
                return str(v)

        output = io.StringIO()
        w = csv.writer(output, delimiter=";")
        w.writerow([
            "ID CCO", "Contrato", "Campo", "Remessa", "Remessa Exp.", "Fase",
            "Mês/Ano", "Data Reconhec.", "Origem", "Recuperada",
            "Valor Reconhecido (R$)", "Valor c/OH (R$)",
            # TPs
            "TP Original/Criação (%)", "Método Original",
            "TP Efetivo Atual (%)", "Método Efetivo",
            "TP Contrato na Data (%)", "TP Contrato Atual (%)",
            # Sinalizadores
            "TP Foi Corrigido", "Efetivo Alinhado Contrato", "Original Alinhado Contrato",
            # Histórico
            "Qtd Eventos CCO", "CCO Teve Modificações",
            # Status
            "Status", "Alertas",
            "Detalhe Evento", "Detalhe Remessa",
        ])
        for r in resultados:
            if r.get("erro"):
                w.writerow([r["cco_id"]] + [""] * 25 + [r["erro"]])
                continue
            mods = "; ".join(
                f"v{m['versao']} {m['data']}" for m in (r.get("modificacoes_cco") or [])
            )
            w.writerow([
                r["cco_id"], r["contratoCpp"], r["campo"],
                r["remessa"], r["remessaExposicao"], r["faseRemessa"],
                r["mesAnoReferencia"], r["dataReconhecimento"],
                r["origemDosGastos"], "SIM" if r["flgRecuperado"] else "NÃO",
                br(r["valorReconhecido"]), br(r["valorReconhecidoComOH"]),
                br(r.get("tp_original_percentual")), r.get("metodo_original", ""),
                br(r.get("tp_efetivo_percentual")),  r.get("metodo_efetivo", ""),
                br(r.get("tp_contrato_na_data")),    br(r.get("tp_contrato_atual")),
                "SIM" if r.get("tp_foi_corrigido") else "NÃO",
                "SIM" if r.get("efetivo_alinhado_contrato") else "NÃO",
                "SIM" if r.get("original_alinhado_contrato") else "NÃO",
                r.get("qtd_eventos_cco", 0),
                "SIM" if r.get("cco_teve_modificacoes") else "NÃO",
                r["status"], " | ".join(r.get("alertas", [])),
                r.get("detalhe_abordagem2", {}).get("detalhe", ""),
                r.get("detalhe_abordagem1", {}).get("detalhe", ""),
            ])
        return "\ufeff" + output.getvalue()

    # ── Listagens aux ──────────────────────────────────────────────────────

    def listar_contratos(self) -> List[str]:
        return sorted(c for c in self.cco_col.distinct("contratoCpp") if c)

    def listar_campos(self, contrato: str) -> List[str]:
        filtro = {"contratoCpp": contrato} if contrato else {}
        return sorted(c for c in self.cco_col.distinct("campo", filtro) if c)

    def listar_fases(self) -> List[str]:
        return sorted(f for f in self.cco_col.distinct("faseRemessa") if f)
