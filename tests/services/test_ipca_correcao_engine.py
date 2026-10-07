"""
Testes unitários para app/services/ipca_correcao_engine.py — foco em
`calcular_ajuste_recuperacao_cenario2` (CENARIO_2, abordagem "Ajuste de
Recuperação").

Cobre especificamente o caso relatado: quando o saldo pós-recuperação é
recalculado (a partir das correções de gap ANTERIORES à recuperação) e passa a
ser positivo, os aniversários posteriores à recuperação que o analisador de
gaps principal nunca chegou a marcar como gap (porque, no momento da análise,
o saldo persistido da recuperação era zero/negativo) devem ser considerados
para correção de IPCA/IGPM — sem reintroduzir a regra permissiva que gerava
correções indevidas em outros cenários.
"""

from datetime import datetime, timezone

import pytest
from freezegun import freeze_time

from app.services.ipca_gap_analyzer import IPCAGapAnalyzer
from app.services.ipca_correcao_engine import IPCACorrectionEngine


# ─── Fakes de coleção Mongo ────────────────────────────────────────────────

class _FakeCCOCollection:
    def __init__(self, cco: dict):
        self._cco = cco

    def find_one(self, filtro):
        if filtro.get("_id") == self._cco["_id"]:
            return self._cco
        return None


class _FakeDbPrd:
    def __init__(self, cco: dict):
        self.conta_custo_oleo_entity = _FakeCCOCollection(cco)


class _FakeTaxaCollection:
    """Retorna sempre a mesma taxa percentual, independente do período pedido."""

    def __init__(self, taxa_percentual: float):
        self._taxa_percentual = taxa_percentual

    def find_one(self, filtro):
        return {"valor": self._taxa_percentual}


class _FakeDb:
    def __init__(self, taxa_percentual: float = 4.0):
        self.ipca_entity = _FakeTaxaCollection(taxa_percentual)
        self.igpm_entity = _FakeTaxaCollection(taxa_percentual)


# ─── Helpers ────────────────────────────────────────────────────────────────

def cco_base(
    cco_id: str = "CCO_TEST",
    data_reconhecimento: str = "2022-01-15T00:00:00+00:00",
    valor_raiz: float = 100_000.0,
    correcoes: list = None,
) -> dict:
    return {
        "_id": cco_id,
        "contratoCpp": "Contrato Teste",
        "campo": "Campo Teste",
        "dataReconhecimento": data_reconhecimento,
        "valorReconhecidoComOH": valor_raiz,
        "correcoesMonetarias": list(correcoes) if correcoes is not None else [],
    }


def correcao_recuperacao(
    data: str,
    valor_com_oh: float,
    valor_recuperado: float,
    valor_com_oh_original: float,
) -> dict:
    return {
        "tipo": "RECUPERACAO",
        "dataCorrecao": data,
        "valorReconhecidoComOH": valor_com_oh,
        "valorReconhecidoComOhOriginal": valor_com_oh_original,
        "valorRecuperado": valor_recuperado,
        "ativo": True,
    }


def montar_engine(cco: dict, taxa_percentual: float = 4.0) -> IPCACorrectionEngine:
    """Monta um IPCACorrectionEngine com gap_analyzer real (reaproveitando toda
    a lógica de datas/aniversário), mas sem conexão real com MongoDB."""
    gap_analyzer = IPCAGapAnalyzer.__new__(IPCAGapAnalyzer)
    gap_analyzer.OFFSET_MES_TAXA_APLICACAO = -1
    gap_analyzer.db = _FakeDb(taxa_percentual)
    gap_analyzer.db_prd = _FakeDbPrd(cco)

    engine = IPCACorrectionEngine.__new__(IPCACorrectionEngine)
    engine.db = gap_analyzer.db
    engine.db_prd = gap_analyzer.db_prd
    engine.gap_analyzer = gap_analyzer
    return engine


def gap_pre_recuperacao(ano: int, mes: int, valor_base: float) -> dict:
    """Gap simples, no formato produzido por IPCAGapAnalyzer, anterior à
    recuperação — é o único gap que o analisador principal já detecta hoje."""
    return {
        "ano": ano,
        "mes": mes,
        "data_aniversario": f"{mes:02d}/{ano}",
        "valor_base": valor_base,
        "data_limite": f"19/{mes+1:02d}/{ano}",
        "prioridade": "media",
    }


# Data de referência fixa para os testes — mesma usada em test_ipca_gap_analyzer.py
DATA_ATUAL = datetime(2025, 4, 1, tzinfo=timezone.utc)


# ═══════════════════════════════════════════════════════════════════════════
# calcular_ajuste_recuperacao_cenario2 — saldo pós-recuperação recalculado
# ═══════════════════════════════════════════════════════════════════════════

@freeze_time("2025-04-01")
class TestSaldoPosRecuperacaoPositivo:
    """
    CCO reconhecida em Jan/2022 (aniversários: Fev/2023, Fev/2024, Fev/2025).

    - Fev/2023: gap (sem correção) — já detectado pelo analisador principal,
      é o que dispara o CENARIO_2.
    - Recuperação em Jun/2023: baseada no valor ORIGINAL (100k, antes da
      correção do gap de Fev/2023), recupera 100k inteiros → saldo persistido
      = 0. Por isso, o analisador principal NUNCA marca Fev/2024 e Fev/2025
      como gap (valor_base == 0 na época da análise).
    - Ao cascatear a correção do gap de Fev/2023 (100k * 1.04 = 104k) sobre a
      recuperação, o saldo pós-recuperação recalculado vira 104k - 100k =
      4k (positivo) — Fev/2024 e Fev/2025 devem passar a receber correção
      IPCA sobre esse novo saldo.

    "Hoje" é congelado em 01/04/2025 (freeze_time) para que a lista de
    aniversários pós-recuperação seja determinística nos asserts abaixo.
    """

    def _montar_cco_e_gaps(self):
        cco = cco_base(
            valor_raiz=100_000.0,
            data_reconhecimento="2022-01-15T00:00:00+00:00",
            correcoes=[
                correcao_recuperacao(
                    "2023-06-01T00:00:00+00:00",
                    valor_com_oh=0.0,
                    valor_recuperado=100_000.0,
                    valor_com_oh_original=100_000.0,
                ),
            ],
        )
        gaps = [{
            "_id": cco["_id"],
            "gaps": [gap_pre_recuperacao(2023, 2, 100_000.0)],
        }]
        return cco, gaps

    def test_saldo_positivo_gera_correcao_ipca_pos_recuperacao(self):
        cco, gaps = self._montar_cco_e_gaps()
        engine = montar_engine(cco, taxa_percentual=4.0)

        resultado = engine.calcular_ajuste_recuperacao_cenario2(cco["_id"], gaps, [])

        tipos = [c["tipo"] for c in resultado]
        assert tipos.count("RECOVERY_ADJUSTMENT") == 1
        # Gap pré-recuperação (Fev/2023) + 2 gaps pós-recuperação (Fev/2024, Fev/2025)
        assert tipos.count("IPCA_ADDITION") == 3, tipos

        recovery = next(c for c in resultado if c["tipo"] == "RECOVERY_ADJUSTMENT")
        assert recovery["valor_corrigido"] == pytest.approx(104_000.0)
        assert recovery["saldo_pos_recuperacao"] == pytest.approx(4_000.0)

        periodos_pos = sorted(
            (c["ano_gap"], c["mes_gap"]) for c in resultado
            if c["tipo"] == "IPCA_ADDITION" and c.get("gap_id", "").startswith("gap_pos_")
        )
        assert periodos_pos == [(2024, 2), (2025, 2)]

    def test_correcao_pos_recuperacao_usa_saldo_recalculado_como_base(self):
        cco, gaps = self._montar_cco_e_gaps()
        engine = montar_engine(cco, taxa_percentual=4.0)

        resultado = engine.calcular_ajuste_recuperacao_cenario2(cco["_id"], gaps, [])

        primeiro_pos = next(
            c for c in resultado
            if c["tipo"] == "IPCA_ADDITION" and c.get("gap_id") == "gap_pos_202402"
        )
        # Base = saldo_pos_recuperacao (4_000.0), não o valor original zerado da recuperação
        assert primeiro_pos["valor_original"] == pytest.approx(4_000.0)
        assert primeiro_pos["valor_corrigido"] == pytest.approx(4_160.0)


@freeze_time("2025-04-01")
class TestSaldoPosRecuperacaoNaoPositivo:
    """
    Casos de controle: o saldo recalculado da recuperação NÃO fica positivo
    mesmo após cascatear o gap pré-recuperação — o guard de valor_base em
    _calcular_correcao_individual_gap (linha 1576, já restaurado ao "modo
    antigo") deve seguir decidindo se gera ou não a correção pós-recuperação,
    exatamente como decide para qualquer outro gap — sem correção indevida
    quando o saldo é exatamente zero, e respeitando a flag
    IGNORAR_CORECAO_MONETARIA_VALOR_NEGATIVO quando o saldo é negativo.
    """

    def _montar_cco_e_gaps(self, valor_recuperado: float):
        cco = cco_base(
            valor_raiz=100_000.0,
            data_reconhecimento="2022-01-15T00:00:00+00:00",
            correcoes=[
                correcao_recuperacao(
                    "2023-06-01T00:00:00+00:00",
                    valor_com_oh=0.0,
                    valor_recuperado=valor_recuperado,
                    valor_com_oh_original=100_000.0,
                ),
            ],
        )
        gaps = [{
            "_id": cco["_id"],
            "gaps": [gap_pre_recuperacao(2023, 2, 100_000.0)],
        }]
        return cco, gaps

    def test_saldo_exatamente_zero_nunca_gera_correcao_pos_recuperacao(self):
        # new_recovery_base (104_000, após cascatear o gap) - valor_recuperado
        # (104_000) = saldo 0 — guard bloqueia sempre, independente da flag.
        cco, gaps = self._montar_cco_e_gaps(valor_recuperado=104_000.0)
        engine = montar_engine(cco, taxa_percentual=4.0)

        resultado = engine.calcular_ajuste_recuperacao_cenario2(cco["_id"], gaps, [])

        tipos = [c["tipo"] for c in resultado]
        assert tipos.count("RECOVERY_ADJUSTMENT") == 1
        assert tipos.count("IPCA_ADDITION") == 1, tipos  # só o gap pré-recuperação
        assert not any(c.get("gap_id", "").startswith("gap_pos_") for c in resultado)

        recovery = next(c for c in resultado if c["tipo"] == "RECOVERY_ADJUSTMENT")
        assert recovery["saldo_pos_recuperacao"] == pytest.approx(0.0)

    def test_saldo_negativo_com_flag_ativa_nao_gera_correcao_indevida(self, monkeypatch):
        monkeypatch.setattr(
            "app.services.ipca_correcao_engine.IGNORAR_CORECAO_MONETARIA_VALOR_NEGATIVO",
            True,
        )
        # saldo_pos_recuperacao = 104_000 - 110_000 = -6_000
        cco, gaps = self._montar_cco_e_gaps(valor_recuperado=110_000.0)
        engine = montar_engine(cco, taxa_percentual=4.0)

        resultado = engine.calcular_ajuste_recuperacao_cenario2(cco["_id"], gaps, [])

        tipos = [c["tipo"] for c in resultado]
        assert tipos.count("IPCA_ADDITION") == 1, tipos  # só o gap pré-recuperação
        assert not any(c.get("gap_id", "").startswith("gap_pos_") for c in resultado)

    def test_saldo_negativo_com_flag_inativa_segue_regra_padrao_do_sistema(self, monkeypatch):
        """
        Com a flag desligada (padrão de app/config.py), valor_base negativo NÃO
        é ignorado — mesmo comportamento hoje já validado para o detector
        principal de gaps (test_valor_base_negativo_flag_false_deve_gerar_gap em
        test_ipca_gap_analyzer.py). Este teste apenas documenta que o novo
        caminho pós-recuperação segue a mesma regra, sem introduzir uma exceção.
        """
        monkeypatch.setattr(
            "app.services.ipca_correcao_engine.IGNORAR_CORECAO_MONETARIA_VALOR_NEGATIVO",
            False,
        )
        cco, gaps = self._montar_cco_e_gaps(valor_recuperado=110_000.0)
        engine = montar_engine(cco, taxa_percentual=4.0)

        resultado = engine.calcular_ajuste_recuperacao_cenario2(cco["_id"], gaps, [])

        tipos = [c["tipo"] for c in resultado]
        assert tipos.count("IPCA_ADDITION") > 1, tipos  # gera correção sobre base negativa


class TestPeriodosAniversarioSemCorrecao:
    """Testes diretos de IPCAGapAnalyzer._gerar_periodos_aniversario_sem_correcao."""

    def _analyzer(self):
        anl = IPCAGapAnalyzer.__new__(IPCAGapAnalyzer)
        anl.OFFSET_MES_TAXA_APLICACAO = -1
        return anl

    def test_retorna_periodos_sem_correcao_apos_data_minima(self):
        anl = self._analyzer()
        cco = cco_base(data_reconhecimento="2022-01-15T00:00:00+00:00")
        periodos = anl._gerar_periodos_aniversario_sem_correcao(
            cco, DATA_ATUAL, data_minima=datetime(2023, 6, 1, tzinfo=timezone.utc)
        )
        chaves = {(p["ano"], p["mes"]) for p in periodos}
        assert (2023, 2) not in chaves  # antes de data_minima
        assert (2024, 2) in chaves
        assert (2025, 2) in chaves

    def test_periodo_com_correcao_real_nao_e_retornado(self):
        anl = self._analyzer()
        cco = cco_base(
            data_reconhecimento="2022-01-15T00:00:00+00:00",
            correcoes=[
                {
                    "tipo": "IPCA",
                    "dataCorrecao": "2024-02-05T00:00:00+00:00",
                    "valorReconhecidoComOH": 104_000.0,
                    "diferencaValor": 4_000.0,
                    "taxaCorrecao": 1.04,
                    "ativo": True,
                },
            ],
        )
        periodos = anl._gerar_periodos_aniversario_sem_correcao(cco, DATA_ATUAL)
        chaves = {(p["ano"], p["mes"]) for p in periodos}
        assert (2024, 2) not in chaves
        assert (2023, 2) in chaves
        assert (2025, 2) in chaves

    def test_sem_data_minima_retorna_todos_os_periodos_sem_correcao(self):
        anl = self._analyzer()
        cco = cco_base(data_reconhecimento="2022-01-15T00:00:00+00:00")
        periodos = anl._gerar_periodos_aniversario_sem_correcao(cco, DATA_ATUAL)
        chaves = {(p["ano"], p["mes"]) for p in periodos}
        assert chaves == {(2023, 2), (2024, 2), (2025, 2)}
