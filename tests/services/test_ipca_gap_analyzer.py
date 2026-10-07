"""
Testes unitários para o módulo de Análise e Correção IPCA/IGPM.

Cobre os seguintes cenários críticos:
  - CCO com gap único (CENARIO_0)
  - CCO com gap e correção posterior incorreta (CENARIO_1)
  - CCO com gap e recuperação (CENARIO_2)
  - CCO com 3 duplicatas consecutivas (CENARIO_DUPLICATAS)
  - CCO com gap + duplicata + recuperação (cenário complexo)
  - CCO recém reconhecida (sem aniversário ainda)
  - CCO recuperada (flgRecuperado = true)
  - CCO com RETIFICACAO manuais
  - Guarda de valor_base zero/negativo (BUG-1)
"""

from datetime import datetime, timezone
import pytest

from app.services.ipca_gap_analyzer import IPCAGapAnalyzer


# ─── Helpers e fixtures ────────────────────────────────────────────────────

def montar_analyzer() -> IPCAGapAnalyzer:
    """Cria IPCAGapAnalyzer sem conexão real com MongoDB."""
    anl = IPCAGapAnalyzer.__new__(IPCAGapAnalyzer)
    anl.OFFSET_MES_TAXA_APLICACAO = -1  # padrão do __init__
    return anl


def cco_base(
    cco_id: str = "CCO_TEST",
    data_reconhecimento="2022-01-15T00:00:00+00:00",
    valor_raiz: float = 100_000.0,
    flg_recuperado: bool = False,
    correcoes: list = None,
) -> dict:
    """Monta documento mínimo de CCO para uso nos testes."""
    return {
        "_id": cco_id,
        "contratoCpp": "Contrato Teste",
        "campo": "Campo Teste",
        "remessa": 1,
        "faseRemessa": "MEN",
        "dataReconhecimento": data_reconhecimento,
        "valorReconhecidoComOH": valor_raiz,
        "flgRecuperado": flg_recuperado,
        "correcoesMonetarias": list(correcoes) if correcoes is not None else [],
    }


def correcao_ipca(
    data: str,
    valor_com_oh: float,
    diferenca: float = 0.0,
    taxa: float = 1.04,
    ativo: bool = True,
) -> dict:
    return {
        "tipo": "IPCA",
        "dataCorrecao": data,
        "valorReconhecidoComOH": valor_com_oh,
        "diferencaValor": diferenca,
        "taxaCorrecao": taxa,
        "ativo": ativo,
    }


def correcao_igpm(data: str, valor_com_oh: float, diferenca: float = 0.0) -> dict:
    return {
        "tipo": "IGPM",
        "dataCorrecao": data,
        "valorReconhecidoComOH": valor_com_oh,
        "diferencaValor": diferenca,
        "taxaCorrecao": 1.035,
        "ativo": True,
    }


def correcao_recuperacao(data: str, valor_com_oh: float, valor_recuperado: float) -> dict:
    return {
        "tipo": "RECUPERACAO",
        "dataCorrecao": data,
        "valorReconhecidoComOH": valor_com_oh,
        "valorRecuperado": valor_recuperado,
        "ativo": True,
    }


def correcao_retificacao(data: str, valor_com_oh: float, observacao: str = "") -> dict:
    return {
        "tipo": "RETIFICACAO",
        "dataCorrecao": data,
        "valorReconhecidoComOH": valor_com_oh,
        "observacao": observacao,
        "ativo": True,
    }


# Data de referência fixa para os testes (1º de abril de 2025)
DATA_ATUAL = datetime(2025, 4, 1, tzinfo=timezone.utc)


# ═══════════════════════════════════════════════════════════════════════════
# 1. Guarda de valor_base zero / negativo (BUG-1)
# ═══════════════════════════════════════════════════════════════════════════

class TestGuardaValorBase:
    """
    Valida a lógica de guard do valor_base nos gaps (correção do BUG-1).

    Regra:
      - valor_base == 0  → gap SEMPRE ignorado (sem olhar para a flag)
      - valor_base < 0 e FLAG=False → gap NÃO ignorado
      - valor_base < 0 e FLAG=True  → gap ignorado
    """

    def test_valor_base_zero_sempre_ignora_gap(self):
        anl = montar_analyzer()
        cco = cco_base(valor_raiz=0.0)
        gaps, _ = anl._analisar_cco_individual(cco, DATA_ATUAL)
        assert gaps == [], "CCO com valor base zero não deve gerar gaps"

    def test_valor_base_negativo_flag_false_deve_gerar_gap(self, monkeypatch):
        monkeypatch.setattr(
            "app.services.ipca_gap_analyzer.IGNORAR_CORECAO_MONETARIA_VALOR_NEGATIVO",
            False,
        )
        anl = montar_analyzer()
        cco = cco_base(valor_raiz=-50_000.0)
        gaps, _ = anl._analisar_cco_individual(cco, DATA_ATUAL)
        assert len(gaps) > 0, "Valor negativo com flag=False deve gerar gaps"

    def test_valor_base_negativo_flag_true_ignora_gap(self, monkeypatch):
        monkeypatch.setattr(
            "app.services.ipca_gap_analyzer.IGNORAR_CORECAO_MONETARIA_VALOR_NEGATIVO",
            True,
        )
        anl = montar_analyzer()
        cco = cco_base(valor_raiz=-50_000.0)
        gaps, _ = anl._analisar_cco_individual(cco, DATA_ATUAL)
        assert gaps == [], "Valor negativo com flag=True deve ignorar gaps"

    def test_valor_base_positivo_gera_gap_para_cada_aniversario_passado(self):
        anl = montar_analyzer()
        cco = cco_base(valor_raiz=100_000.0)
        gaps, _ = anl._analisar_cco_individual(cco, DATA_ATUAL)
        periodos = {(g["ano"], g["mes"]) for g in gaps}
        assert (2023, 2) in periodos
        assert (2024, 2) in periodos
        assert (2025, 2) in periodos


# ═══════════════════════════════════════════════════════════════════════════
# 2. Cenário 0 — Gap único (sem nenhuma correção aplicada)
# ═══════════════════════════════════════════════════════════════════════════

class TestCenario0GapUnico:
    """
    CCO reconhecida em Jan/2022 e com todos os aniversários sem correção.
    Primeiro aniversário: Fev/2023. Seguintes: Fev/2024, Fev/2025.
    """

    def test_tres_aniversarios_passados_geram_tres_gaps(self):
        anl = montar_analyzer()
        cco = cco_base(data_reconhecimento="2022-01-15T00:00:00+00:00")
        gaps, correcoes_fora = anl._analisar_cco_individual(cco, DATA_ATUAL)

        periodos = {(g["ano"], g["mes"]) for g in gaps}
        assert (2023, 2) in periodos
        assert (2024, 2) in periodos
        assert (2025, 2) in periodos
        assert correcoes_fora == []

    def test_gap_usa_valor_raiz_como_base_quando_sem_correcoes_anteriores(self):
        anl = montar_analyzer()
        cco = cco_base(valor_raiz=200_000.0)
        gaps, _ = anl._analisar_cco_individual(cco, DATA_ATUAL)

        assert len(gaps) > 0
        assert gaps[0]["valor_base"] == pytest.approx(200_000.0)

    def test_gap_periodo_taxa_usa_mes_anterior_ao_aniversario(self):
        """
        Aniversário Fev/2023 → taxa referência Jan/2023 (offset = -1).
        """
        anl = montar_analyzer()
        cco = cco_base(data_reconhecimento="2022-01-15T00:00:00+00:00")
        gaps, _ = anl._analisar_cco_individual(cco, DATA_ATUAL)

        gap_fev_2023 = next(g for g in gaps if g["ano"] == 2023)
        assert gap_fev_2023["mes_taxa"] == 1
        assert gap_fev_2023["ano_taxa"] == 2023

    def test_aniversario_futuro_nao_gera_gap(self):
        """
        Aniversário de Abr/2025 (mesmo mês que DATA_ATUAL com dia < 16)
        não deve gerar gap.
        """
        anl = montar_analyzer()
        # Reconhecida em Mar/2024 → primeiro aniversário: Abr/2025
        cco = cco_base(data_reconhecimento="2024-03-10T00:00:00+00:00")
        gaps, _ = anl._analisar_cco_individual(cco, DATA_ATUAL)
        periodos = {(g["ano"], g["mes"]) for g in gaps}
        # Abr/2025: DATA_ATUAL é dia 1 (< 16) → deadline não passou → sem gap
        assert (2025, 4) not in periodos

    def test_reconhecimento_dezembro_primeiro_aniversario_em_janeiro_do_ano_mais_dois(self):
        """
        Regra especial: Dez/2021 → primeiro aniversário Jan/2023 (não Jan/2022).
        """
        anl = montar_analyzer()
        cco = cco_base(data_reconhecimento="2021-12-10T00:00:00+00:00")
        gaps, _ = anl._analisar_cco_individual(cco, DATA_ATUAL)

        periodos = {(g["ano"], g["mes"]) for g in gaps}
        assert (2023, 1) in periodos
        assert (2022, 1) not in periodos


# ═══════════════════════════════════════════════════════════════════════════
# 3. Cenário 1 — Gap com correção posterior incorreta
# ═══════════════════════════════════════════════════════════════════════════

class TestCenario1GapComCorrecaoPosterior:
    """
    Primeiro aniversário (Fev/2023) sem correção = gap.
    Segundo aniversário (Fev/2024) com IPCA corretamente aplicado.
    """

    def test_gap_primeiro_aniversario_persiste_quando_segundo_esta_correto(self):
        anl = montar_analyzer()
        cco = cco_base(
            data_reconhecimento="2022-01-15T00:00:00+00:00",
            correcoes=[
                correcao_ipca("2024-02-10T12:00:00+00:00", 104_000.0, 4_000.0),
            ],
        )
        gaps, _ = anl._analisar_cco_individual(cco, DATA_ATUAL)
        periodos = {(g["ano"], g["mes"]) for g in gaps}

        assert (2023, 2) in periodos, "Fev/2023 deve ser gap (primeiro aniversário ausente)"
        assert (2024, 2) not in periodos, "Fev/2024 não deve ser gap (correção presente)"

    def test_valor_base_gap_usa_raiz_quando_sem_correcao_anterior_ao_gap(self):
        anl = montar_analyzer()
        cco = cco_base(
            valor_raiz=100_000.0,
            data_reconhecimento="2022-01-15T00:00:00+00:00",
            correcoes=[
                correcao_ipca("2024-02-10T12:00:00+00:00", 104_000.0, 4_000.0),
            ],
        )
        valor_base = anl._obter_valor_base_para_gap(cco, 2023, 2)
        assert valor_base == pytest.approx(100_000.0)

    def test_gap_segundo_ano_usa_valor_da_correcao_do_primeiro_como_base(self):
        """
        Quando Fev/2023 foi corrigido (R$ 104k) e Fev/2024 é gap,
        o valor_base do gap de Fev/2025 deve ser o último valor antes de Fev 15/2025.
        """
        anl = montar_analyzer()
        cco = cco_base(
            valor_raiz=100_000.0,
            data_reconhecimento="2022-01-15T00:00:00+00:00",
            correcoes=[
                correcao_ipca("2023-02-05T00:00:00+00:00", 104_000.0, 4_000.0),
                # Fev/2024 ausente (gap)
            ],
        )
        # Para o gap de Fev/2025: última correção anterior = IPCA Fev/2023 → 104k
        valor_base = anl._obter_valor_base_para_gap(cco, 2025, 2)
        assert valor_base == pytest.approx(104_000.0)


# ═══════════════════════════════════════════════════════════════════════════
# 4. Cenário 2 — Gap com recuperação
# ═══════════════════════════════════════════════════════════════════════════

class TestCenario2GapComRecuperacao:
    """CCO com gap e entradas de RECUPERACAO no histórico de correções."""

    def test_gap_persiste_mesmo_com_recuperacao_presente(self):
        anl = montar_analyzer()
        cco = cco_base(
            data_reconhecimento="2022-01-15T00:00:00+00:00",
            valor_raiz=100_000.0,
            correcoes=[
                correcao_recuperacao("2023-06-01T00:00:00+00:00", 80_000.0, 20_000.0),
            ],
        )
        gaps, _ = anl._analisar_cco_individual(cco, DATA_ATUAL)
        periodos = {(g["ano"], g["mes"]) for g in gaps}
        assert (2023, 2) in periodos

    def test_valor_base_gap_apos_recuperacao_usa_valor_da_recuperacao(self):
        """
        Última correção antes do gap = RECUPERACAO → valor_base = saldo pós-recuperação.
        """
        anl = montar_analyzer()
        cco = cco_base(
            data_reconhecimento="2022-01-15T00:00:00+00:00",
            valor_raiz=100_000.0,
            correcoes=[
                correcao_ipca("2023-02-10T00:00:00+00:00", 104_000.0, 4_000.0),
                correcao_recuperacao("2023-06-01T00:00:00+00:00", 84_000.0, 20_000.0),
            ],
        )
        valor_base = anl._obter_valor_base_para_gap(cco, 2024, 2)
        assert valor_base == pytest.approx(84_000.0)

    def test_recuperacao_nao_e_detectada_como_duplicata(self):
        anl = montar_analyzer()
        cco = cco_base(
            correcoes=[
                correcao_ipca("2023-02-05T00:00:00+00:00", 104_000.0, 4_000.0),
                correcao_recuperacao("2023-06-01T00:00:00+00:00", 84_000.0, 20_000.0),
            ]
        )
        duplicatas = anl._identificar_correcoes_duplicadas(cco)
        assert duplicatas == []


# ═══════════════════════════════════════════════════════════════════════════
# 5. Cenário Duplicatas
# ═══════════════════════════════════════════════════════════════════════════

class TestCenarioDuplicatas:
    """Detecção de entradas IPCA/IGPM duplicadas no mesmo período mês/ano."""

    def test_duas_correcoes_no_mesmo_mes_retorna_uma_duplicata(self):
        anl = montar_analyzer()
        cco = cco_base(
            correcoes=[
                correcao_ipca("2023-02-05T12:00:00+00:00", 101_000.0, 1_000.0),
                correcao_ipca("2023-02-10T12:00:00+00:00", 102_000.0, 1_000.0),
            ]
        )
        duplicatas = anl._identificar_correcoes_duplicadas(cco)
        assert len(duplicatas) == 1

    def test_tres_correcoes_no_mesmo_mes_retorna_duas_duplicatas(self):
        anl = montar_analyzer()
        cco = cco_base(
            correcoes=[
                correcao_ipca("2023-02-05T12:00:00+00:00", 101_000.0, 1_000.0),
                correcao_ipca("2023-02-10T12:00:00+00:00", 102_000.0, 1_000.0),
                correcao_ipca("2023-02-15T12:00:00+00:00", 103_000.0, 1_000.0),
            ]
        )
        duplicatas = anl._identificar_correcoes_duplicadas(cco)
        assert len(duplicatas) == 2

    def test_duplicata_contem_indice_da_segunda_ocorrencia(self):
        anl = montar_analyzer()
        cco = cco_base(
            correcoes=[
                correcao_ipca("2023-02-05T12:00:00+00:00", 101_000.0, 1_000.0),
                correcao_ipca("2023-02-10T12:00:00+00:00", 102_000.0, 1_000.0),
            ]
        )
        duplicatas = anl._identificar_correcoes_duplicadas(cco)
        assert duplicatas[0]["indice"] == 1

    def test_sem_duplicatas_retorna_lista_vazia(self):
        anl = montar_analyzer()
        cco = cco_base(
            data_reconhecimento="2022-01-15T00:00:00+00:00",
            correcoes=[
                correcao_ipca("2023-02-05T12:00:00+00:00", 104_000.0, 4_000.0),
                correcao_ipca("2024-02-05T12:00:00+00:00", 108_160.0, 4_160.0),
            ],
        )
        duplicatas = anl._identificar_correcoes_duplicadas(cco)
        assert duplicatas == []

    def test_igpm_duplicado_tambem_e_detectado(self):
        anl = montar_analyzer()
        cco = cco_base(
            correcoes=[
                correcao_igpm("2023-02-05T12:00:00+00:00", 101_000.0, 1_000.0),
                correcao_igpm("2023-02-12T12:00:00+00:00", 102_000.0, 1_000.0),
            ]
        )
        duplicatas = anl._identificar_correcoes_duplicadas(cco)
        assert len(duplicatas) == 1

    def test_correcoes_em_meses_diferentes_nao_sao_duplicatas(self):
        anl = montar_analyzer()
        cco = cco_base(
            correcoes=[
                correcao_ipca("2023-02-05T12:00:00+00:00", 104_000.0, 4_000.0),
                correcao_ipca("2023-03-05T12:00:00+00:00", 108_160.0, 4_160.0),
            ]
        )
        duplicatas = anl._identificar_correcoes_duplicadas(cco)
        assert duplicatas == []

    def test_duplicata_registra_periodo_correto(self):
        anl = montar_analyzer()
        cco = cco_base(
            correcoes=[
                correcao_ipca("2023-02-05T12:00:00+00:00", 101_000.0, 1_000.0),
                correcao_ipca("2023-02-15T12:00:00+00:00", 102_000.0, 1_000.0),
            ]
        )
        duplicatas = anl._identificar_correcoes_duplicadas(cco)
        assert duplicatas[0]["periodo"] == "02/2023"


# ═══════════════════════════════════════════════════════════════════════════
# 6. Cenário complexo — Gap + Duplicata + Recuperação simultâneos
# ═══════════════════════════════════════════════════════════════════════════

class TestCenarioComplexo:
    """
    CCO com múltiplos problemas simultâneos.
    Documenta que o analyzer detecta cada problema de forma independente,
    mesmo que o orquestrador atual só processe um cenário por vez.
    """

    def test_cco_com_duplicata_e_gap_detecta_ambos_independentemente(self):
        anl = montar_analyzer()
        # Fev/2023: IPCA duplicado (problema 1)
        # Fev/2025: sem IPCA (gap — problema 2)
        cco = cco_base(
            data_reconhecimento="2022-01-15T00:00:00+00:00",
            valor_raiz=100_000.0,
            correcoes=[
                correcao_ipca("2023-02-05T12:00:00+00:00", 104_000.0, 4_000.0),
                correcao_ipca("2023-02-15T12:00:00+00:00", 104_000.0, 4_000.0),  # duplicata
                correcao_ipca("2024-02-05T12:00:00+00:00", 108_160.0, 4_160.0),
            ],
        )
        duplicatas = anl._identificar_correcoes_duplicadas(cco)
        gaps, _ = anl._analisar_cco_individual(cco, DATA_ATUAL)

        periodos_gap = {(g["ano"], g["mes"]) for g in gaps}
        assert len(duplicatas) == 1, "Deve detectar 1 duplicata em Fev/2023"
        assert (2025, 2) in periodos_gap, "Deve detectar gap em Fev/2025"

    def test_cco_com_gap_duplicata_e_recuperacao_detecta_todos(self):
        anl = montar_analyzer()
        cco = cco_base(
            data_reconhecimento="2022-01-15T00:00:00+00:00",
            valor_raiz=100_000.0,
            correcoes=[
                correcao_ipca("2023-02-05T12:00:00+00:00", 104_000.0, 4_000.0),
                correcao_ipca("2023-02-15T12:00:00+00:00", 104_000.0, 4_000.0),  # duplicata
                correcao_recuperacao("2024-01-01T00:00:00+00:00", 60_000.0, 44_000.0),
            ],
        )
        duplicatas = anl._identificar_correcoes_duplicadas(cco)
        tem_recuperacao = any(
            c.get("tipo") == "RECUPERACAO" for c in cco["correcoesMonetarias"]
        )
        gaps, _ = anl._analisar_cco_individual(cco, DATA_ATUAL)

        assert len(duplicatas) == 1
        assert tem_recuperacao
        assert len(gaps) > 0


# ═══════════════════════════════════════════════════════════════════════════
# 7. CCO recém reconhecida (sem aniversário ainda)
# ═══════════════════════════════════════════════════════════════════════════

class TestCcoRecemReconhecida:
    """CCO cujo primeiro aniversário ainda está no futuro."""

    def test_sem_aniversario_passado_nao_ha_gaps(self):
        anl = montar_analyzer()
        # Reconhecida Mar/2025 → primeiro aniversário Abr/2026
        cco = cco_base(data_reconhecimento="2025-03-01T00:00:00+00:00")
        gaps, correcoes_fora = anl._analisar_cco_individual(cco, DATA_ATUAL)
        assert gaps == []
        assert correcoes_fora == []

    def test_sem_campo_data_reconhecimento_retorna_vazio(self):
        anl = montar_analyzer()
        cco = cco_base()
        cco.pop("dataReconhecimento")
        gaps, correcoes_fora = anl._analisar_cco_individual(cco, DATA_ATUAL)
        assert gaps == []
        assert correcoes_fora == []

    def test_data_reconhecimento_como_objeto_datetime_nativo(self):
        anl = montar_analyzer()
        cco = cco_base()
        cco["dataReconhecimento"] = datetime(2025, 3, 1, tzinfo=timezone.utc)
        gaps, _ = anl._analisar_cco_individual(cco, DATA_ATUAL)
        assert gaps == []

    def test_aniversario_no_mes_corrente_antes_do_dia_16_nao_gera_gap(self):
        """
        Se DATA_ATUAL.day < 16 e o aniversário é no mesmo mês/ano,
        o prazo limite ainda não passou → sem gap.
        """
        anl = montar_analyzer()
        # Reconhecida Mar/2024 → aniversário Abr/2025
        data_atual_dia_1 = datetime(2025, 4, 1, tzinfo=timezone.utc)
        cco = cco_base(data_reconhecimento="2024-03-15T00:00:00+00:00")
        gaps, _ = anl._analisar_cco_individual(cco, data_atual_dia_1)
        periodos = {(g["ano"], g["mes"]) for g in gaps}
        assert (2025, 4) not in periodos


# ═══════════════════════════════════════════════════════════════════════════
# 8. CCO recuperada (flgRecuperado = true, saldo zero)
# ═══════════════════════════════════════════════════════════════════════════

class TestCcoRecuperada:
    """
    CCO totalmente recuperada: valorReconhecidoComOH = 0 na última correção.
    valor_base == 0 → gaps ignorados.
    """

    def test_cco_com_recuperacao_total_nao_gera_novos_gaps(self):
        anl = montar_analyzer()
        cco = cco_base(
            data_reconhecimento="2022-01-15T00:00:00+00:00",
            valor_raiz=100_000.0,
            flg_recuperado=True,
            correcoes=[
                correcao_ipca("2023-02-05T00:00:00+00:00", 104_000.0, 4_000.0),
                correcao_ipca("2024-02-05T00:00:00+00:00", 108_160.0, 4_160.0),
                # Recuperação total: saldo vai a zero em Dez/2024
                correcao_recuperacao("2024-12-01T00:00:00+00:00", 0.0, 108_160.0),
            ],
        )
        gaps, _ = anl._analisar_cco_individual(cco, DATA_ATUAL)
        # Fev/2025: valor_base = 0 (última correção antes de Fev/2025 = RECUPERACAO com OH=0)
        assert gaps == []

    def test_obter_valor_atual_retorna_zero_apos_recuperacao_total(self):
        anl = montar_analyzer()
        cco = cco_base(
            valor_raiz=100_000.0,
            correcoes=[
                correcao_ipca("2023-02-05T00:00:00+00:00", 104_000.0),
                correcao_recuperacao("2024-12-01T00:00:00+00:00", 0.0, 104_000.0),
            ],
        )
        assert anl._obter_valor_atual_cco(cco) == pytest.approx(0.0)

    def test_obter_valor_atual_sem_correcoes_usa_valor_raiz(self):
        anl = montar_analyzer()
        cco = cco_base(valor_raiz=75_000.0)
        assert anl._obter_valor_atual_cco(cco) == pytest.approx(75_000.0)

    def test_obter_valor_atual_usa_ultima_correcao_monetaria(self):
        """Quando há múltiplas correções, usa a última independente do tipo."""
        anl = montar_analyzer()
        cco = cco_base(
            valor_raiz=100_000.0,
            correcoes=[
                correcao_ipca("2023-02-05T00:00:00+00:00", 104_000.0),
                correcao_recuperacao("2024-06-01T00:00:00+00:00", 54_000.0, 50_000.0),
            ],
        )
        assert anl._obter_valor_atual_cco(cco) == pytest.approx(54_000.0)


# ═══════════════════════════════════════════════════════════════════════════
# 9. CCO com RETIFICACAO manuais
# ═══════════════════════════════════════════════════════════════════════════

class TestCcoComRetificacao:
    """
    RETIFICACAO altera o saldo da CCO e impacta o valor_base dos gaps subsequentes.
    """

    def test_valor_base_gap_usa_retificacao_quando_e_a_correcao_mais_recente(self):
        anl = montar_analyzer()
        cco = cco_base(
            data_reconhecimento="2022-01-15T00:00:00+00:00",
            valor_raiz=100_000.0,
            correcoes=[
                correcao_ipca("2023-02-05T00:00:00+00:00", 104_000.0, 4_000.0),
                # RETIFICACAO posterior ao IPCA → passa a ser o valor base do próximo gap
                correcao_retificacao("2023-06-15T00:00:00+00:00", 98_000.0, "Ajuste manual"),
            ],
        )
        # Gap de Fev/2024: última correção antes de Fev 15/2024 = RETIFICACAO Jun/2023
        valor_base = anl._obter_valor_base_para_gap(cco, 2024, 2)
        assert valor_base == pytest.approx(98_000.0)

    def test_retificacao_nao_e_classificada_como_duplicata_de_ipca(self):
        anl = montar_analyzer()
        cco = cco_base(
            correcoes=[
                correcao_ipca("2023-02-05T00:00:00+00:00", 104_000.0, 4_000.0),
                correcao_retificacao("2023-02-20T00:00:00+00:00", 103_000.0),
            ]
        )
        duplicatas = anl._identificar_correcoes_duplicadas(cco)
        assert duplicatas == [], "RETIFICACAO não deve ser tratada como duplicata de IPCA"

    def test_gap_identificado_mesmo_com_retificacao_na_mesma_janela(self):
        """
        Uma RETIFICACAO não substitui a obrigação de um IPCA no aniversário.
        """
        anl = montar_analyzer()
        cco = cco_base(
            data_reconhecimento="2022-01-15T00:00:00+00:00",
            valor_raiz=100_000.0,
            correcoes=[
                # Fev/2023: sem IPCA (gap)
                correcao_retificacao("2023-06-15T00:00:00+00:00", 95_000.0, "Ajuste"),
                correcao_ipca("2024-02-05T00:00:00+00:00", 98_800.0, 3_800.0),
            ],
        )
        gaps, _ = anl._analisar_cco_individual(cco, DATA_ATUAL)
        periodos = {(g["ano"], g["mes"]) for g in gaps}
        assert (2023, 2) in periodos


# ═══════════════════════════════════════════════════════════════════════════
# 10. Utilitários de data
# ═══════════════════════════════════════════════════════════════════════════

class TestUtilitariosDatas:

    def test_extrair_data_reconhecimento_string_com_offset_brasilia(self):
        anl = montar_analyzer()
        cco = cco_base(data_reconhecimento="2022-07-09T18:09:51-0300")
        dt = anl._extrair_data_reconhecimento(cco)
        assert dt is not None
        assert dt.year == 2022
        assert dt.month == 7
        assert dt.day == 9

    def test_extrair_data_reconhecimento_string_utc_z(self):
        anl = montar_analyzer()
        cco = cco_base(data_reconhecimento="2022-07-09T18:09:51+0000")
        dt = anl._extrair_data_reconhecimento(cco)
        assert dt is not None and dt.year == 2022

    def test_extrair_data_reconhecimento_objeto_datetime(self):
        anl = montar_analyzer()
        cco = cco_base()
        cco["dataReconhecimento"] = datetime(2022, 7, 9, 18, 0, 0, tzinfo=timezone.utc)
        dt = anl._extrair_data_reconhecimento(cco)
        assert dt is not None and dt.month == 7

    def test_extrair_data_correcao_string_com_offset(self):
        anl = montar_analyzer()
        correcao = {"dataCorrecao": "2024-02-05T13:33:24-0300"}
        dt = anl._extrair_data_correcao(correcao)
        assert dt is not None
        assert dt.year == 2024 and dt.month == 2

    def test_extrair_data_correcao_usa_dataCriacaoCorrecao_como_fallback(self):
        anl = montar_analyzer()
        correcao = {"dataCriacaoCorrecao": "2024-03-10T10:00:00+00:00"}
        dt = anl._extrair_data_correcao(correcao)
        assert dt is not None and dt.month == 3

    def test_calcular_mes_taxa_offset_minus_1_retorna_mes_anterior(self):
        anl = montar_analyzer()
        ano_taxa, mes_taxa = anl._calcular_mes_taxa_aplicacao(2023, 2)
        assert ano_taxa == 2023 and mes_taxa == 1

    def test_calcular_mes_taxa_janeiro_com_offset_minus_1_retorna_dezembro_ano_anterior(self):
        anl = montar_analyzer()
        ano_taxa, mes_taxa = anl._calcular_mes_taxa_aplicacao(2023, 1)
        assert ano_taxa == 2022 and mes_taxa == 12

    def test_converter_decimal128_aceita_float(self):
        anl = montar_analyzer()
        assert anl._converter_decimal128_para_float(123.45) == pytest.approx(123.45)

    def test_converter_decimal128_aceita_none(self):
        anl = montar_analyzer()
        assert anl._converter_decimal128_para_float(None) == pytest.approx(0.0)
