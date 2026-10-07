"""
app/services/verificacao_ipca_service.py
=========================================
Serviço de verificação/correção de IPCA/IGPM em lote.

Não reimplementa a lógica de análise: cada CCO é processada reaproveitando
diretamente `IPCACorrectionOrchestrator.iniciar_analise_cco` e
`.gerar_propostas_correcao`, exatamente como a tela individual
(`/ipca-correcao/`) já faz — apenas em loop, para uma lista de CCOs.

Regra de negócio: para CENARIO_2 (gap com recuperação posterior), o orquestrador
(`_gerar_propostas_cenario_2`) já gera exclusivamente propostas de Ajuste de
Recuperação — a abordagem de Compensação foi descontinuada na origem e não chega
mais nem à tela individual nem a este serviço.
"""

import csv
import io
import logging
from typing import Any, Dict, List

from pymongo.database import Database

logger = logging.getLogger(__name__)

LIMITE_MAXIMO_BUSCA = 300
LIMITE_MAXIMO_LOTE = 300


class VerificacaoIpcaService:

    def __init__(self, db: Database, db_prd: Database, gap_analyzer, correction_engine, orchestrator):
        self.db = db
        self.db_prd = db_prd
        self.gap_analyzer = gap_analyzer
        self.correction_engine = correction_engine
        self.orchestrator = orchestrator
        self.cco_col = db_prd["conta_custo_oleo_entity"]

    # ── Busca de CCOs ──────────────────────────────────────────────────────

    def buscar_ccos(self, filtros: Dict) -> List[Dict]:
        if filtros.get("id") or filtros.get("cco_id"):
            doc = self.cco_col.find_one({"_id": filtros.get("id") or filtros.get("cco_id")})
            return [doc] if doc else []

        query: Dict[str, Any] = {}
        if filtros.get("contratoCpp"):
            query["contratoCpp"] = filtros["contratoCpp"]
        if filtros.get("campo"):
            query["campo"] = filtros["campo"]
        if filtros.get("faseRemessa"):
            query["faseRemessa"] = filtros["faseRemessa"]
        if filtros.get("origemDosGastos"):
            query["origemDosGastos"] = filtros["origemDosGastos"]

        for campo_num in ("remessa", "exercicio", "periodo"):
            val = str(filtros.get(campo_num, "")).strip()
            if val:
                try:
                    query[campo_num] = int(val)
                except ValueError:
                    pass

        limite = min(int(filtros.get("limite") or LIMITE_MAXIMO_BUSCA), LIMITE_MAXIMO_BUSCA)
        return list(
            self.cco_col.find(query)
            .sort([("remessa", -1), ("faseRemessa", 1)])
            .limit(limite)
        )

    def listar_contratos(self) -> List[str]:
        return sorted(c for c in self.cco_col.distinct("contratoCpp") if c)

    def listar_campos(self, contrato: str) -> List[str]:
        filtro = {"contratoCpp": contrato} if contrato else {}
        return sorted(c for c in self.cco_col.distinct("campo", filtro) if c)

    def listar_fases(self) -> List[str]:
        return sorted(f for f in self.cco_col.distinct("faseRemessa") if f)

    # ── Análise em lote ────────────────────────────────────────────────────

    def analisar_lote(self, cco_ids: List[str], user_id: str) -> List[Dict]:
        """Roda, para cada CCO, o mesmo fluxo de duas etapas da tela individual
        (iniciar_analise_cco + gerar_propostas_correcao) e monta uma linha de
        resultado consolidada por CCO."""
        resultados = []
        for cco_id in cco_ids:
            resultados.append(self._analisar_cco(cco_id, user_id))
        return resultados

    def _buscar_info_cco(self, cco_id: str) -> Dict:
        cco = self.cco_col.find_one(
            {"_id": cco_id},
            {"_id": 1, "contratoCpp": 1, "campo": 1, "remessa": 1, "faseRemessa": 1, "origemDosGastos": 1},
        )
        if not cco:
            return {}
        return {
            "contratoCpp": cco.get("contratoCpp", ""),
            "campo": cco.get("campo", ""),
            "remessa": cco.get("remessa", ""),
            "faseRemessa": cco.get("faseRemessa", ""),
            "origemDosGastos": cco.get("origemDosGastos", ""),
        }

    def _linha_erro(self, cco_id: str, status: str, erro: str, cco_info: Dict = None) -> Dict:
        base = self._linha_vazia(cco_id, cco_info or {})
        base["status"] = status
        base["erro"] = erro
        return base

    def _linha_vazia(self, cco_id: str, cco_info: Dict) -> Dict:
        return {
            "cco_id": cco_id,
            "contratoCpp": cco_info.get("contratoCpp", ""),
            "campo": cco_info.get("campo", ""),
            "remessa": cco_info.get("remessa", ""),
            "faseRemessa": cco_info.get("faseRemessa", ""),
            "origemDosGastos": cco_info.get("origemDosGastos", ""),
            "session_id": None,
            "scenario_detected": None,
            "gaps_count": 0,
            "corrections_fora_count": 0,
            "duplicates_count": 0,
            "tipo_proposta_usada": None,
            "proposals_count": 0,
            "financial_impact_total": 0.0,
            "financial_impact_additions": 0.0,
            "financial_impact_updates": 0.0,
            "financial_impact_remove": 0.0,
            "status": "OK",
            "erro": None,
            "proposals": [],
        }

    def _analisar_cco(self, cco_id: str, user_id: str) -> Dict:
        cco_info = self._buscar_info_cco(cco_id)
        if not cco_info:
            return self._linha_erro(cco_id, "ERRO", "CCO não encontrada")

        try:
            resultado_inicio = self.orchestrator.iniciar_analise_cco(cco_id, user_id)
        except Exception as e:
            logger.error(f"Erro ao iniciar análise em lote da CCO {cco_id}: {e}", exc_info=True)
            return self._linha_erro(cco_id, "ERRO", str(e), cco_info)

        if not resultado_inicio.get("success"):
            return self._linha_erro(cco_id, "ERRO", resultado_inicio.get("error", "Falha ao iniciar análise"), cco_info)

        session_id = resultado_inicio.get("session_id")
        linha = self._linha_vazia(cco_id, cco_info)
        linha["session_id"] = session_id
        linha["scenario_detected"] = resultado_inicio.get("scenario_detected")
        linha["gaps_count"] = resultado_inicio.get("gaps_count", 0)
        linha["corrections_fora_count"] = resultado_inicio.get("corrections_fora_count", 0)
        linha["duplicates_count"] = resultado_inicio.get("duplicates_count", 0)

        try:
            resultado_propostas = self.orchestrator.gerar_propostas_correcao(session_id)
        except Exception as e:
            logger.error(f"Erro ao gerar propostas em lote da CCO {cco_id}: {e}", exc_info=True)
            linha["status"] = "ERRO_PROPOSTAS"
            linha["erro"] = str(e)
            return linha

        if not resultado_propostas.get("success"):
            linha["status"] = "ERRO_PROPOSTAS"
            linha["erro"] = resultado_propostas.get("error", "Falha ao gerar propostas")
            return linha

        # O orquestrador já entrega uma única lista de propostas por cenário — para
        # CENARIO_2, essa lista é exclusivamente de Ajuste de Recuperação (a
        # abordagem de Compensação foi descontinuada em `_gerar_propostas_cenario_2`).
        proposals_usadas = resultado_propostas.get("proposals") or []
        impacto_usado = resultado_propostas.get("financial_impact") or {}
        tipo_proposta_usada = "AJUSTE_RECUPERACAO" if linha["scenario_detected"] == "CENARIO_2" else "PRIMARIA"

        linha["tipo_proposta_usada"] = tipo_proposta_usada
        linha["proposals_count"] = len(proposals_usadas)
        linha["financial_impact_total"] = impacto_usado.get("total_impact", 0.0)
        linha["financial_impact_additions"] = impacto_usado.get("total_additions", 0.0)
        linha["financial_impact_updates"] = impacto_usado.get("total_updates", 0.0)
        linha["financial_impact_remove"] = impacto_usado.get("total_remove", 0.0)
        linha["proposals"] = proposals_usadas
        linha["status"] = "OK" if proposals_usadas else "SEM_PROPOSTAS"
        return linha

    # ── CSV ────────────────────────────────────────────────────────────────

    def gerar_csv(self, resultados: List[Dict]) -> str:
        def br(v):
            if v is None:
                return ""
            try:
                return f"{float(v):.2f}".replace(".", ",")
            except Exception:
                return str(v)

        output = io.StringIO()
        w = csv.writer(output, delimiter=";")
        w.writerow([
            "ID CCO", "Contrato", "Campo", "Remessa", "Fase", "Origem",
            "Cenário Detectado", "Tipo Proposta Usada",
            "Qtd Gaps", "Qtd Correções Fora Período", "Qtd Duplicatas", "Qtd Propostas",
            "Impacto Total (R$)", "Adições (R$)", "Atualizações (R$)", "Remoções (R$)",
            "Status", "Erro",
        ])
        for r in resultados:
            w.writerow([
                r.get("cco_id", ""), r.get("contratoCpp", ""), r.get("campo", ""),
                r.get("remessa", ""), r.get("faseRemessa", ""), r.get("origemDosGastos", ""),
                r.get("scenario_detected") or "", r.get("tipo_proposta_usada") or "",
                r.get("gaps_count", 0), r.get("corrections_fora_count", 0),
                r.get("duplicates_count", 0), r.get("proposals_count", 0),
                br(r.get("financial_impact_total")), br(r.get("financial_impact_additions")),
                br(r.get("financial_impact_updates")), br(r.get("financial_impact_remove")),
                r.get("status", ""), r.get("erro") or "",
            ])
        return "﻿" + output.getvalue()
