"""
app/services/verificacao_oh_service.py
=======================================
Serviço de verificação dos valores de OverHead (OH) calculados nas CCOs.

Regras de negócio:
  - overHeadExploracao : 1%, 2% ou 3% do valorReconhecidoExploracao
                         (faixas progressivas: ≤5M→3%, 5-15M→2%, >15M→1%)
  - overHeadProducao   : exatamente 1% do valorReconhecidoProducao
  - overHeadTotal      : overHeadExploracao + overHeadProducao

Casos especiais (não geram ERRO, apenas ATENÇÃO):
  - Base negativa (valorReconhecido* < 0): OH não aplicável
  - Origem GASTO_AEGV / AEGV: OH sempre 0 por definição
"""

import csv
import io
import logging
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple

from bson import ObjectId
from pymongo.database import Database

logger = logging.getLogger(__name__)

TAXAS_VALIDAS_EXPLORACAO = {Decimal("1"), Decimal("2"), Decimal("3")}
TAXA_PRODUCAO = Decimal("1")

TOLERANCIA_ZERO = Decimal("0.01")
TOLERANCIA_PCT  = Decimal("0.005")

# Faixas progressivas do OH de Exploração
_FRONTEIRAS_EXP = [Decimal("0"), Decimal("5000000"), Decimal("15000000")]
_TAXAS_EXP      = [Decimal("3"), Decimal("2"), Decimal("1")]

_ORIGENS_AEGV = {"GASTO_AEGV", "AEGV"}


# ---------------------------------------------------------------------------
# Helpers numéricos
# ---------------------------------------------------------------------------

def _dec(value) -> Decimal:
    if value is None:
        return Decimal("0")
    try:
        if hasattr(value, "to_decimal"):
            return value.to_decimal()
        return Decimal(str(value))
    except (InvalidOperation, TypeError):
        return Decimal("0")


def _pct(numerador: Decimal, denominador: Decimal) -> Optional[Decimal]:
    if abs(denominador) < TOLERANCIA_ZERO:
        return None
    return (numerador / denominador * 100).quantize(Decimal("0.0001"))


def _status_label(s: str) -> str:
    return "ATENÇÃO" if s == "ATENCAO" else s


# ---------------------------------------------------------------------------
# Cálculo por faixas progressivas
# ---------------------------------------------------------------------------

def _calcular_oh_exp_por_faixas(
    acumulado: Decimal, valor: Decimal
) -> Tuple[Decimal, List[Dict]]:
    """
    Calcula OH esperado para um valor de exploração dado o acumulado anual anterior.
    Retorna (oh_total, fatias) com a contribuição de cada faixa atravessada.
    """
    if valor <= Decimal("0"):
        return Decimal("0"), []

    total_oh = Decimal("0")
    fatias: List[Dict] = []

    for i, taxa in enumerate(_TAXAS_EXP):
        f_inicio = _FRONTEIRAS_EXP[i]
        f_fim    = _FRONTEIRAS_EXP[i + 1] if i + 1 < len(_FRONTEIRAS_EXP) else None

        overlap_inicio = max(acumulado, f_inicio)
        overlap_fim    = (acumulado + valor) if f_fim is None else min(acumulado + valor, f_fim)
        fatia          = max(Decimal("0"), overlap_fim - overlap_inicio)

        if fatia > Decimal("0"):
            oh_fatia = fatia * taxa / Decimal("100")
            total_oh += oh_fatia
            fatias.append({
                "taxa_pct":       int(taxa),
                "valor_na_faixa": float(fatia),
                "oh_contribuicao": float(oh_fatia),
            })

    return total_oh, fatias


# ---------------------------------------------------------------------------
# Checks individuais
# ---------------------------------------------------------------------------

def _checar_oh_exploracao(oh: Decimal, base: Decimal) -> Dict:
    if base < -TOLERANCIA_ZERO:
        return {
            "status": "ATENCAO", "pct_calculado": None, "taxa_esperada": None,
            "diferenca": Decimal("0"),
            "motivo": "Base de exploração negativa — OH não aplicável",
        }

    if abs(base) < TOLERANCIA_ZERO:
        if abs(oh) < TOLERANCIA_ZERO:
            return {"status": "OK", "pct_calculado": None, "taxa_esperada": None,
                    "diferenca": Decimal("0"), "motivo": "Base e OH ambos zero"}
        return {"status": "ERRO", "pct_calculado": None, "taxa_esperada": Decimal("0"),
                "diferenca": oh, "motivo": f"Base zero mas OH = {oh:.4f}"}

    pct = _pct(oh, base)
    for taxa in sorted(TAXAS_VALIDAS_EXPLORACAO):
        if abs(pct - taxa) <= TOLERANCIA_PCT:
            return {"status": "OK", "pct_calculado": pct, "taxa_esperada": taxa,
                    "diferenca": oh - (base * taxa / 100),
                    "motivo": f"OH = {taxa}% da base"}

    mais_proxima = min(TAXAS_VALIDAS_EXPLORACAO, key=lambda t: abs(pct - t))
    return {
        "status": "ERRO",
        "pct_calculado": pct,
        "taxa_esperada": mais_proxima,
        "diferenca": oh - (base * mais_proxima / 100),
        "motivo": f"Percentual {pct:.4f}% não corresponde a 1%, 2% ou 3%",
    }


def _checar_oh_producao(oh: Decimal, base: Decimal) -> Dict:
    if base < -TOLERANCIA_ZERO:
        return {
            "status": "ATENCAO", "pct_calculado": None, "taxa_esperada": None,
            "diferenca": Decimal("0"),
            "motivo": "Base de produção negativa — OH não aplicável",
        }

    if abs(base) < TOLERANCIA_ZERO:
        if abs(oh) < TOLERANCIA_ZERO:
            return {"status": "OK", "pct_calculado": None, "taxa_esperada": None,
                    "diferenca": Decimal("0"), "motivo": "Base e OH ambos zero"}
        return {"status": "ERRO", "pct_calculado": None, "taxa_esperada": Decimal("0"),
                "diferenca": oh, "motivo": f"Base zero mas OH = {oh:.4f}"}

    pct = _pct(oh, base)
    if abs(pct - TAXA_PRODUCAO) <= TOLERANCIA_PCT:
        return {"status": "OK", "pct_calculado": pct, "taxa_esperada": TAXA_PRODUCAO,
                "diferenca": oh - (base * TAXA_PRODUCAO / 100),
                "motivo": "OH = 1% da base"}

    return {
        "status": "ERRO",
        "pct_calculado": pct,
        "taxa_esperada": TAXA_PRODUCAO,
        "diferenca": oh - (base * TAXA_PRODUCAO / 100),
        "motivo": f"Percentual {pct:.4f}% ≠ 1%",
    }


def _checar_oh_total(oh_total: Decimal, oh_exp: Decimal, oh_prod: Decimal) -> Dict:
    esperado  = oh_exp + oh_prod
    diferenca = oh_total - esperado
    if abs(diferenca) <= TOLERANCIA_ZERO:
        return {"status": "OK", "esperado": esperado,
                "diferenca": diferenca, "motivo": "Total = Exp + Prod"}
    return {
        "status": "ERRO",
        "esperado": esperado,
        "diferenca": diferenca,
        "motivo": f"Total {oh_total:.4f} ≠ Exp+Prod {esperado:.4f} (Δ {diferenca:+.4f})",
    }


# ---------------------------------------------------------------------------
# Verificação de bloco
# ---------------------------------------------------------------------------

def _verificar_bloco_oh(
    bloco: Dict, origem: str, override_atencao: Optional[str] = None
) -> Dict:
    """
    Aplica as três verificações de OH em um bloco (raiz ou correcoesMonetarias).
    Se override_atencao for fornecido, retorna ATENCAO para todos os checks sem
    executar a matemática (usado para origem AEGV).
    """
    oh_exp    = _dec(bloco.get("overHeadExploracao"))
    oh_prod   = _dec(bloco.get("overHeadProducao"))
    oh_tot    = _dec(bloco.get("overHeadTotal"))
    base_exp  = _dec(bloco.get("valorReconhecidoExploracao"))
    base_prod = _dec(bloco.get("valorReconhecidoProducao"))

    if override_atencao:
        return {
            "origem": origem,
            "oh_exploracao": float(oh_exp),
            "base_exploracao": float(base_exp),
            "pct_exploracao": None,
            "taxa_esperada_exp": None,
            "status_exploracao": "ATENCAO",
            "motivo_exploracao": override_atencao,
            "diferenca_exploracao": 0.0,

            "oh_producao": float(oh_prod),
            "base_producao": float(base_prod),
            "pct_producao": None,
            "status_producao": "ATENCAO",
            "motivo_producao": override_atencao,
            "diferenca_producao": 0.0,

            "oh_total": float(oh_tot),
            "oh_total_esperado": float(oh_exp + oh_prod),
            "status_total": "ATENCAO",
            "motivo_total": override_atencao,
            "diferenca_total": 0.0,

            "status_geral": "ATENCAO",
        }

    check_exp  = _checar_oh_exploracao(oh_exp, base_exp)
    check_prod = _checar_oh_producao(oh_prod, base_prod)
    check_tot  = _checar_oh_total(oh_tot, oh_exp, oh_prod)

    # Hierarquia: ERRO > ATENCAO > OK
    statuses = {check_exp["status"], check_prod["status"], check_tot["status"]}
    if "ERRO" in statuses:
        status_geral = "ERRO"
    elif "ATENCAO" in statuses:
        status_geral = "ATENCAO"
    else:
        status_geral = "OK"

    return {
        "origem": origem,
        "oh_exploracao": float(oh_exp),
        "base_exploracao": float(base_exp),
        "pct_exploracao": float(check_exp["pct_calculado"]) if check_exp["pct_calculado"] is not None else None,
        "taxa_esperada_exp": float(check_exp["taxa_esperada"]) if check_exp["taxa_esperada"] is not None else None,
        "status_exploracao": check_exp["status"],
        "motivo_exploracao": check_exp["motivo"],
        "diferenca_exploracao": float(check_exp["diferenca"]),

        "oh_producao": float(oh_prod),
        "base_producao": float(base_prod),
        "pct_producao": float(check_prod["pct_calculado"]) if check_prod["pct_calculado"] is not None else None,
        "status_producao": check_prod["status"],
        "motivo_producao": check_prod["motivo"],
        "diferenca_producao": float(check_prod["diferenca"]),

        "oh_total": float(oh_tot),
        "oh_total_esperado": float(check_tot["esperado"]),
        "status_total": check_tot["status"],
        "motivo_total": check_tot["motivo"],
        "diferenca_total": float(check_tot["diferenca"]),

        "status_geral": status_geral,
    }


# ---------------------------------------------------------------------------
# Service principal
# ---------------------------------------------------------------------------

class VerificacaoOHService:

    def __init__(self, db: Database):
        self.db = db
        self.collection = db.conta_custo_oleo_entity

    # ── Listagens para os filtros da UI ────────────────────────────────────

    def listar_contratos(self) -> List[str]:
        try:
            return sorted(c for c in self.collection.distinct("contratoCpp") if c)
        except Exception as e:
            logger.error(f"Erro ao listar contratos: {e}")
            return []

    def listar_campos(self, contrato: str) -> List[str]:
        try:
            filtro = {"contratoCpp": contrato} if contrato else {}
            return sorted(c for c in self.collection.distinct("campo", filtro) if c)
        except Exception as e:
            logger.error(f"Erro ao listar campos: {e}")
            return []

    def listar_fases(self) -> List[str]:
        try:
            return sorted(f for f in self.collection.distinct("faseRemessa") if f)
        except Exception as e:
            logger.error(f"Erro ao listar fases: {e}")
            return []

    # ── Busca de CCOs ──────────────────────────────────────────────────────

    def buscar_ccos(self, filtros: Dict) -> List[Dict]:
        query: Dict[str, Any] = {}

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
        if filtros.get("mesAnoReferencia"):
            query["mesAnoReferencia"] = filtros["mesAnoReferencia"]

        for campo_num in ("remessa", "remessaExposicao"):
            val = filtros.get(campo_num, "").strip()
            if val:
                if "-" in val:
                    partes = val.split("-", 1)
                    try:
                        query[campo_num] = {"$gte": int(partes[0]), "$lte": int(partes[1])}
                    except ValueError:
                        pass
                else:
                    try:
                        query[campo_num] = int(val)
                    except ValueError:
                        pass

        limite = min(int(filtros.get("limite") or 200), 500)

        try:
            cursor = (
                self.collection.find(query)
                .sort([("remessa", 1), ("faseRemessa", 1)])
                .limit(limite)
            )
            return list(cursor)
        except Exception as e:
            logger.error(f"Erro ao buscar CCOs para verificação OH: {e}")
            return []

    # ── Verificação de OH ──────────────────────────────────────────────────

    def verificar_oh(self, ccos_raw: List[Dict]) -> List[Dict]:
        resultados = []
        for cco in ccos_raw:
            cco_id   = str(cco.get("_id", ""))
            contrato = cco.get("contratoCpp", "")
            campo    = cco.get("campo", "")
            remessa  = cco.get("remessa", "")
            rem_exp  = cco.get("remessaExposicao", "")
            fase     = cco.get("faseRemessa", "")
            mes_ano  = cco.get("mesAnoReferencia", "")
            data_rec = str(cco.get("dataReconhecimento", ""))[:10]
            flg_rec  = cco.get("flgRecuperado", False)

            origem_raw = cco.get("origemDosGastos") or ""
            origem     = origem_raw.replace("GASTO_", "")
            eh_aegv    = origem_raw in _ORIGENS_AEGV
            override   = "Origem AEGV — não gera OH" if eh_aegv else None

            bloco_raiz = _verificar_bloco_oh(cco, "RAIZ", override_atencao=override)
            resultados.append({
                "cco_id": cco_id,
                "contrato": contrato,
                "campo": campo,
                "remessa": remessa,
                "remessaExposicao": rem_exp,
                "faseRemessa": fase,
                "mesAnoReferencia": mes_ano,
                "dataReconhecimento": data_rec,
                "origemDosGastos": origem,
                "flgRecuperado": flg_rec,
                **bloco_raiz,
            })

            for corr in cco.get("correcoesMonetarias") or []:
                if not any(corr.get(k) for k in
                           ("overHeadExploracao", "overHeadProducao", "overHeadTotal")):
                    continue
                tipo_corr   = f"{corr.get('tipo','?')}/{corr.get('subTipo','?')}"
                data_corr   = str(corr.get("dataCorrecao", ""))[:10]
                origem_corr = f"CORREÇÃO {tipo_corr} {data_corr}"
                bloco_corr  = _verificar_bloco_oh(corr, origem_corr, override_atencao=override)
                resultados.append({
                    "cco_id": cco_id,
                    "contrato": contrato,
                    "campo": campo,
                    "remessa": remessa,
                    "remessaExposicao": rem_exp,
                    "faseRemessa": fase,
                    "mesAnoReferencia": mes_ano,
                    "dataReconhecimento": data_rec,
                    "origemDosGastos": origem,
                    "flgRecuperado": flg_rec,
                    **bloco_corr,
                })

        return resultados

    # ── Estatísticas do resultado ──────────────────────────────────────────

    def calcular_estatisticas(self, resultados: List[Dict]) -> Dict:
        total       = len(resultados)
        erros       = sum(1 for r in resultados if r["status_geral"] == "ERRO")
        atencoes    = sum(1 for r in resultados if r["status_geral"] == "ATENCAO")
        ok          = total - erros - atencoes
        erros_exp   = sum(1 for r in resultados if r["status_exploracao"] == "ERRO")
        erros_prod  = sum(1 for r in resultados if r["status_producao"]   == "ERRO")
        erros_tot   = sum(1 for r in resultados if r["status_total"]      == "ERRO")
        ccos_unicas = len({r["cco_id"] for r in resultados})
        return {
            "total_linhas":    total,
            "ccos_unicas":     ccos_unicas,
            "total_erros":     erros,
            "total_atencao":   atencoes,
            "total_ok":        ok,
            "pct_ok":          round(ok / total * 100, 1) if total else 0,
            "erros_exploracao": erros_exp,
            "erros_producao":   erros_prod,
            "erros_total_oh":   erros_tot,
        }

    # ── Geração de CSV ─────────────────────────────────────────────────────

    def gerar_csv(self, resultados: List[Dict]) -> str:
        def br(v):
            if v is None:
                return ""
            try:
                return f"{float(v):.4f}".replace(".", ",")
            except Exception:
                return str(v)

        output = io.StringIO()
        w = csv.writer(output, delimiter=";")
        w.writerow([
            "ID CCO", "Contrato", "Campo", "Remessa", "Remessa Exp.",
            "Fase", "Mês/Ano Ref.", "Data Reconhec.", "Origem", "Recuperada",
            "Bloco Verificado",
            "Base Exp. (R$)", "OH Exp. (R$)", "% OH Exp. Calculado",
            "% OH Exp. Esperado", "Status OH Exp.", "Diferença Exp. (R$)", "Motivo OH Exp.",
            "Base Prod. (R$)", "OH Prod. (R$)", "% OH Prod. Calculado",
            "Status OH Prod.", "Diferença Prod. (R$)", "Motivo OH Prod.",
            "OH Total (R$)", "OH Total Esperado (R$)",
            "Status OH Total", "Diferença Total (R$)", "Motivo OH Total",
            "Status Geral",
        ])
        for r in resultados:
            w.writerow([
                r["cco_id"], r["contrato"], r["campo"],
                r["remessa"], r["remessaExposicao"],
                r["faseRemessa"], r["mesAnoReferencia"],
                r["dataReconhecimento"],
                r["origemDosGastos"],
                "SIM" if r["flgRecuperado"] else "NÃO",
                r["origem"],
                br(r["base_exploracao"]), br(r["oh_exploracao"]),
                br(r["pct_exploracao"]), br(r["taxa_esperada_exp"]),
                _status_label(r["status_exploracao"]),
                br(r["diferenca_exploracao"]), r["motivo_exploracao"],
                br(r["base_producao"]), br(r["oh_producao"]),
                br(r["pct_producao"]),
                _status_label(r["status_producao"]),
                br(r["diferenca_producao"]), r["motivo_producao"],
                br(r["oh_total"]), br(r["oh_total_esperado"]),
                _status_label(r["status_total"]),
                br(r["diferenca_total"]), r["motivo_total"],
                _status_label(r["status_geral"]),
            ])
        return "﻿" + output.getvalue()

    # ── Análise por faixas de um contrato/ano ─────────────────────────────

    def analisar_faixas_exploracao(self, cco_id: str) -> Dict:
        """
        Retorna análise cronológica de todas as CCOs do mesmo contrato/ano,
        mostrando a contribuição de cada faixa progressiva de OH de Exploração.
        """
        # Busca CCO de referência
        try:
            cco_ref = self.collection.find_one({"_id": ObjectId(cco_id)})
        except Exception:
            cco_ref = self.collection.find_one({"_id": cco_id})

        if not cco_ref:
            raise ValueError(f"CCO não encontrada: {cco_id}")

        contrato = cco_ref.get("contratoCpp", "")
        ano      = cco_ref.get("anoReconhecimento")

        ccos = list(
            self.collection.find({
                "contratoCpp":      contrato,
                "anoReconhecimento": ano,
            }).sort("dataReconhecimento", 1)
        )

        acumulado = Decimal("0")
        linhas: List[Dict] = []

        for cco in ccos:
            cco_id_atual = str(cco.get("_id", ""))
            val_exp      = _dec(cco.get("valorReconhecidoExploracao"))
            oh_real      = _dec(cco.get("overHeadExploracao"))
            origem_raw   = (cco.get("origemDosGastos") or "")
            eh_aegv_cco  = origem_raw in _ORIGENS_AEGV

            acum_antes = acumulado

            if eh_aegv_cco:
                status    = "ATENCAO"
                oh_esp    = Decimal("0")
                fatias    = []
                diferenca = Decimal("0")
                faixa_pred = None
            elif val_exp < -TOLERANCIA_ZERO:
                status    = "ATENCAO"
                oh_esp    = Decimal("0")
                fatias    = []
                diferenca = Decimal("0")
                faixa_pred = None
            elif val_exp <= TOLERANCIA_ZERO:
                # Zero ou quase zero
                oh_esp    = Decimal("0")
                fatias    = []
                diferenca = oh_real - oh_esp
                status    = "OK" if abs(diferenca) <= TOLERANCIA_ZERO else "ERRO"
                faixa_pred = None
            else:
                oh_esp, fatias = _calcular_oh_exp_por_faixas(acumulado, val_exp)
                diferenca      = oh_real - oh_esp
                status         = "OK" if abs(diferenca) <= TOLERANCIA_ZERO else "ERRO"
                if fatias:
                    max_f      = max(fatias, key=lambda f: f["valor_na_faixa"])
                    faixa_pred = {3: 1, 2: 2, 1: 3}.get(max_f["taxa_pct"])
                else:
                    faixa_pred = None

            # Avança acumulado apenas para valores positivos
            if val_exp > Decimal("0"):
                acumulado += val_exp

            linhas.append({
                "cco_id":                   cco_id_atual,
                "campo":                    cco.get("campo", ""),
                "remessa":                  cco.get("remessa", ""),
                "dataReconhecimento":       str(cco.get("dataReconhecimento", ""))[:10],
                "faseRemessa":              cco.get("faseRemessa", ""),
                "origemDosGastos":          origem_raw.replace("GASTO_", ""),
                "valorReconhecidoExploracao": float(val_exp),
                "acumulado_antes":          float(acum_antes),
                "acumulado_depois":         float(acumulado),
                "faixa_predominante":       faixa_pred,
                "fatias":                   fatias,
                "oh_esperado":              float(oh_esp),
                "oh_real":                  float(oh_real),
                "diferenca":                float(diferenca),
                "status":                   status,
                "eh_referencia":            cco_id_atual == cco_id,
            })

        return {
            "contrato":        contrato,
            "ano":             ano,
            "cco_ref_id":      cco_id,
            "acumulado_total": float(acumulado),
            "linhas":          linhas,
        }
