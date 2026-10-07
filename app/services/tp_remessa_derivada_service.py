"""
Serviço para atualização de TP nos gastos da remessa derivada.

Esta rotina é usada no momento da aplicação definitiva de um recálculo de TP,
quando o usuário opta por refletir a alteração também na remessa derivada.
"""

import logging
from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, Optional

from bson import ObjectId
from bson.decimal128 import Decimal128
from bson.int64 import Int64

from app.utils.converters import converter_decimal128_para_float

logger = logging.getLogger(__name__)


class TPRemessaDerivadaService:
    """Serviço responsável por atualizar TP e valores monetários na remessa derivada."""

    CAMPOS_MONETARIOS_GASTO = [
        "valorMoedaOBJReal",
        "valorMoedaOBJRealOriginal",
        "valorMoedaACC",
        "valorMoedaTrans",
        "valorConvertido",
        "valorReconhecido",
        "valorNaoReconhecido",
        "valorReconhecivel",
        "valorNaoPassivelRecuperacao",
        "valorRecusado",
    ]

    # Campo correto de TP dentro de cada item de gasto da remessa derivada.
    # Não criar "tp" e não atualizar campos alternativos.
    CAMPO_TP_GASTO = "tractParticipationPercentual"

    # REGRA IMPORTANTE:
    # A atualização da remessa derivada deve considerar SOMENTE o campo
    # faseRemessa do item de gasto comparado com a faseRemessa da CCO.
    #
    # Não usar campos alternativos como "fase" ou "faseRespostaGestora",
    # pois eles podem representar outra classificação e causar atualização
    # indevida de gastos de fases diferentes, como ROP quando a CCO é MEN.
    CAMPO_FASE_GASTO = "faseRemessa"

    def __init__(self, db_prd):
        self.db_prd = db_prd
        self.collection = db_prd.remessa_derivada_campo_entity

    def atualizar_tp_remessa_derivada(
        self,
        cco_recalculada: Dict[str, Any],
        metadata_recalculo: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Atualiza a remessa derivada vinculada à CCO.

        Regras:
        - usa o idRemessaGeradora da CCO para localizar a remessa derivada;
        - altera apenas gastos cuja fase seja igual à faseRemessa da CCO;
        - ajusta valores monetários pelo fator de correção;
        - atualiza o TP de cada gasto afetado;
        - não altera gastos de outras fases.
        """
        try:
            id_remessa_geradora = cco_recalculada.get("idRemessaGeradora")
            fase_cco = cco_recalculada.get("faseRemessa")
            fator_correcao = metadata_recalculo.get("fator_correcao")
            tp_original = metadata_recalculo.get("tp_original")
            tp_correcao = metadata_recalculo.get("tp_correcao")

            if not id_remessa_geradora:
                return {
                    "success": False,
                    "error": "CCO não possui idRemessaGeradora para localizar a remessa derivada",
                }

            if not fase_cco:
                return {
                    "success": False,
                    "error": "CCO não possui faseRemessa para filtrar os gastos da remessa derivada",
                }

            if fator_correcao is None or tp_correcao is None:
                return {
                    "success": False,
                    "error": "Metadata do recálculo não possui fator_correcao ou tp_correcao",
                }

            filtro_remessa = self._montar_filtro_remessa(id_remessa_geradora)
            remessa = self.collection.find_one(filtro_remessa)

            if not remessa:
                return {
                    "success": False,
                    "error": f"Remessa derivada não encontrada para idRemessaGeradora {id_remessa_geradora}",
                }

            gastos = remessa.get("gastos", [])
            if not isinstance(gastos, list):
                return {
                    "success": False,
                    "error": "Remessa derivada encontrada, mas o campo gastos não é uma lista",
                }

            gastos_atualizados = deepcopy(gastos)
            total_gastos_afetados = 0
            campos_monetarios_alterados = 0

            for gasto in gastos_atualizados:
                if not isinstance(gasto, dict):
                    continue

                if not self._gasto_eh_da_mesma_fase(gasto, fase_cco):
                    continue

                total_gastos_afetados += 1
                campos_monetarios_alterados += self._atualizar_valores_monetarios_gasto(
                    gasto,
                    fator_correcao,
                )
                self._atualizar_tp_gasto(gasto, tp_correcao)
                self._registrar_metadata_atualizacao_gasto(
                    gasto,
                    tp_original,
                    tp_correcao,
                    fator_correcao,
                    cco_recalculada,
                )

            if total_gastos_afetados == 0:
                return {
                    "success": False,
                    "error": f"Nenhum gasto encontrado na remessa derivada para a fase {fase_cco}",
                    "id_remessa_geradora": str(id_remessa_geradora),
                    "fase_cco": fase_cco,
                }

            nova_versao = self._obter_nova_versao(remessa)

            resultado_update = self.collection.update_one(
                filtro_remessa,
                {
                    "$set": {
                        "gastos": gastos_atualizados,
                        "version": Int64(nova_versao),
                        "dataAtualizacaoTP": datetime.now(),
                        "metadataAtualizacaoTP": {
                            "origem": "RECALCULO_TP_CCO",
                            "ccoId": str(cco_recalculada.get("_id", "")),
                            "faseRemessa": fase_cco,
                            "tpOriginal": Decimal128(str(tp_original)) if tp_original is not None else None,
                            "tpCorrecao": Decimal128(str(tp_correcao)),
                            "fatorCorrecao": Decimal128(str(fator_correcao)),
                            "totalGastosAfetados": total_gastos_afetados,
                            "camposMonetariosAlterados": campos_monetarios_alterados,
                            "dataAtualizacao": datetime.now(),
                        },
                    }
                },
            )

            return {
                "success": True,
                "id_remessa_geradora": str(id_remessa_geradora),
                "fase_cco": fase_cco,
                "total_gastos_afetados": total_gastos_afetados,
                "campos_monetarios_alterados": campos_monetarios_alterados,
                "nova_versao_remessa": nova_versao,
                "modified_count": resultado_update.modified_count,
                "message": "TP e valores monetários da remessa derivada atualizados com sucesso",
            }

        except Exception as e:
            logger.error(f"Erro ao atualizar TP da remessa derivada: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def _montar_filtro_remessa(self, id_remessa_geradora: Any) -> Dict[str, Any]:
        """Monta filtro robusto para IDs string ou ObjectId."""
        id_str = str(id_remessa_geradora)

        if isinstance(id_remessa_geradora, ObjectId):
            return {"_id": id_remessa_geradora}

        if len(id_str) == 24:
            try:
                return {"_id": ObjectId(id_str)}
            except Exception:
                return {"_id": id_str}

        return {"_id": id_remessa_geradora}

    def _gasto_eh_da_mesma_fase(self, gasto: Dict[str, Any], fase_cco: Any) -> bool:
        """
        Verifica se o gasto pertence à mesma fase da CCO.

        Regra:
        - comparar exclusivamente gasto.faseRemessa com cco.faseRemessa;
        - não considerar outros campos de fase;
        - se o gasto não tiver faseRemessa, ele não deve ser atualizado.
        """
        fase_cco_normalizada = self._normalizar_fase(fase_cco)
        fase_gasto_normalizada = self._normalizar_fase(gasto.get(self.CAMPO_FASE_GASTO))

        if not fase_gasto_normalizada:
            logger.info(
                "Gasto ignorado na atualização de TP porque não possui faseRemessa. "
                "Item: %s",
                gasto.get("item", gasto.get("_id", "")),
            )
            return False

        mesma_fase = fase_gasto_normalizada == fase_cco_normalizada

        if not mesma_fase:
            logger.info(
                "Gasto ignorado na atualização de TP por fase diferente. "
                "faseRemessa CCO=%s, faseRemessa gasto=%s, item=%s",
                fase_cco_normalizada,
                fase_gasto_normalizada,
                gasto.get("item", gasto.get("_id", "")),
            )

        return mesma_fase

    def _normalizar_fase(self, valor: Any) -> str:
        if valor is None:
            return ""
        return str(valor).strip().upper()

    def _atualizar_valores_monetarios_gasto(
        self,
        gasto: Dict[str, Any],
        fator_correcao: float,
    ) -> int:
        """Multiplica campos monetários existentes no gasto pelo fator de correção."""
        total_alterados = 0

        for campo in self.CAMPOS_MONETARIOS_GASTO:
            if campo not in gasto:
                continue

            valor_original = gasto.get(campo)
            if valor_original is None:
                continue

            try:
                valor_float = converter_decimal128_para_float(valor_original)
                valor_recalculado = valor_float * fator_correcao
                gasto[campo] = Decimal128(str(round(valor_recalculado, 15)))
                total_alterados += 1
            except Exception as e:
                logger.warning(
                    "Não foi possível atualizar campo monetário %s do gasto %s: %s",
                    campo,
                    gasto.get("item", ""),
                    e,
                )

        return total_alterados

    def _atualizar_tp_gasto(self, gasto: Dict[str, Any], tp_correcao: float) -> None:
        """
        Atualiza somente o campo correto de TP do item de gasto.

        Regra:
        - substituir o valor de tractParticipationPercentual;
        - não criar campo "tp";
        - não criar metadataAtualizacaoTP dentro do gasto.
        """
        gasto[self.CAMPO_TP_GASTO] = Decimal128(str(tp_correcao))

    def _registrar_metadata_atualizacao_gasto(
        self,
        gasto: Dict[str, Any],
        tp_original: Optional[float],
        tp_correcao: float,
        fator_correcao: float,
        cco_recalculada: Dict[str, Any],
    ) -> None:
        """Registra metadados da atualização no item de gasto."""

    def _obter_nova_versao(self, remessa: Dict[str, Any]) -> int:
        try:
            versao_atual = remessa.get("version", 0)
            if hasattr(versao_atual, "as_int64"):
                versao_atual = versao_atual.as_int64()
            return int(versao_atual) + 1
        except Exception:
            return 1
