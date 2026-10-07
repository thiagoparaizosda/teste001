# Massa de Testes — Módulo de Correção IPCA/IGPM (`/ipca-correcao/`)

**Gerado em:** 2026-08-22  
**Módulo:** `app/services/ipca_gap_analyzer.py` + `app/services/ipca_correcao_orquestrador.py`  
**Diretório dos arquivos:** `tests/fixtures/`

---

## Visão Geral

O módulo de Correção IPCA/IGPM analisa um registro de CCO (Conta Custo Óleo) e detecta
inconsistências na aplicação de correção monetária (IPCA ou IGPM). A lógica central é a
**regra do aniversário**: exatamente 1 ano após o `dataReconhecimento` da CCO (mais precisamente
no mês seguinte ao mês de reconhecimento, no ano + 1), deve existir uma entrada `tipo: IPCA`
ou `tipo: IGPM` em `correcoesMonetarias`. Se a entrada está ausente ou foi calculada sobre
uma base incorreta, o sistema gera propostas de correção.

A taxa aplicada usa **offset de -1 mês**: para o aniversário no mês M, usa-se a taxa do
mês M-1 (ex: aniversário em abril usa taxa de março).

O sistema detecta **4 cenários ativos** (mais 2 sem propostas implementadas):

| Cenário | Arquivo de Fixture | Descrição |
|---|---|---|
| `CENARIO_0` | `cco_cenario0_gap_simples.json` | Gap sem nada posterior |
| `CENARIO_1` | `cco_cenario1_gap_com_correcao_posterior.json` | Gap + correção posterior com base errada |
| `CENARIO_2` | `cco_cenario2_gap_com_recuperacao.json` | Gap + recuperação posterior |
| `CENARIO_DUPLICATAS` | `cco_cenario_duplicatas.json` | Mesmo período corrigido duas vezes |

---

## Como usar as fixtures

Carregar como dict Python nos testes:

```python
import json
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"

def carregar_cco(nome: str) -> dict:
    with open(FIXTURES_DIR / nome, encoding="utf-8") as f:
        return json.load(f)

cco = carregar_cco("cco_cenario0_gap_simples.json")
```

Para injetar no `IPCAGapAnalyzer` sem banco de dados real (seguindo o padrão de
`tests/services/test_ipca_gap_analyzer.py`):

```python
from app.services.ipca_gap_analyzer import IPCAGapAnalyzer

def montar_analyzer():
    anl = IPCAGapAnalyzer.__new__(IPCAGapAnalyzer)
    anl.OFFSET_MES_TAXA_APLICACAO = -1
    return anl
```

---

## Cenário 0 — Gap Simples

**Arquivo:** `cco_cenario0_gap_simples.json`  
**CCO ID:** `CCO_CENARIO0_GAP_SIMPLES`

### Descrição

CCO reconhecida em **março/2022**. Seu primeiro aniversário é em **abril/2023** (mês seguinte
ao reconhecimento, no ano + 1). O histórico de `correcoesMonetarias` contém apenas uma entrada
IPCA de **abril/2024** (segundo aniversário), **faltando** a correção do primeiro aniversário
(abril/2023).

Não há recuperações nem outras correções após o gap. É o cenário mais simples.

### Linha do tempo

```
mar/2022  → Reconhecimento (valorReconhecidoComOH = R$ 385.545.713,96)
abr/2023  → [GAP] — deveria haver IPCA (taxa ref: mar/2023), mas não existe
abr/2024  → IPCA aplicado (taxa: 1,039578) — calculado sobre base INCORRETA
              valorReconhecidoComOhOriginal = 385.545.713,96 (deveria ser o valor pós-gap de 2023)
              valorReconhecidoComOH = R$ 400.806.944,24
```

### Campos-chave

| Campo | Valor |
|---|---|
| `dataReconhecimento` | `2022-03-11` |
| Primeiro aniversário | `04/2023` |
| Taxa ref. esperada para o gap | `03/2023` |
| `valorReconhecidoComOH` (raiz) | `385.545.713,96` |
| Correções em `correcoesMonetarias` | 1 (somente abr/2024) |
| `flgRecuperado` | `false` |

### Comportamento esperado do sistema

- `scenario_detected: "CENARIO_0"`
- `gaps_count: 1`
- Proposta gerada: `IPCA_ADDITION` para o período `04/2023`, usando taxa de `03/2023`
- `valor_base` da proposta = `385.545.713,96` (raiz da CCO, pois não há correção anterior ao gap)

---

## Cenário 1 — Gap com Correção Posterior

**Arquivo:** `cco_cenario1_gap_com_correcao_posterior.json`  
**CCO ID:** `CCO_CENARIO1_GAP_CORRECAO_POSTERIOR`

### Descrição

CCO reconhecida em **agosto/2021**. Primeiro aniversário: **setembro/2022**. Segundo
aniversário: **setembro/2023**.

O histórico contém **apenas** a correção de setembro/2023 (segundo aniversário), mas
**falta** a de setembro/2022 (primeiro aniversário). A correção de 2023 foi calculada
sobre a base original `202.000.000,00`, quando deveria ter usado um valor maior (base
já corrigida pelo IPCA de 2022 que estava em falta).

### Linha do tempo

```
ago/2021  → Reconhecimento (valorReconhecidoComOH = R$ 202.000.000,00)
set/2022  → [GAP] — deveria haver IPCA (taxa ref: ago/2022), mas não existe
set/2023  → IPCA aplicado (taxa: 1,042001) sobre base INCORRETA (202.000.000)
              valorReconhecidoComOhOriginal = 202.000.000,00
              valorReconhecidoComOH = R$ 210.484.200,00
              ← deveria ter sido calculado sobre o valor pós-correção de 2022
```

### Campos-chave

| Campo | Valor |
|---|---|
| `dataReconhecimento` | `2021-08-20` |
| Primeiro aniversário (gap) | `09/2022` |
| Taxa ref. esperada para o gap | `08/2022` |
| Segundo aniversário (correção existente) | `09/2023` |
| Taxa ref. da correção existente | `08/2023` |
| `valorReconhecidoComOH` (raiz) | `202.000.000,00` |
| `flgRecuperado` | `false` |

### Comportamento esperado do sistema

- `scenario_detected: "CENARIO_1"`
- `gaps_count: 1` (gap de set/2022)
- Propostas geradas:
  - `IPCA_ADDITION` para `09/2022`, `taxa_referencia: "08/2022"`, `valor_base: 202.000.000`
  - `IPCA_UPDATE` para a correção de `09/2023`, recalculando-a sobre a base corrigida
    (`valor_base_correto = 202.000.000 × taxa_agosto_2022`)
- O `IPCA_UPDATE` tem dependência do `IPCA_ADDITION` (cascade)

---

## Cenário 2 — Gap com Recuperação

**Arquivo:** `cco_cenario2_gap_com_recuperacao.json`  
**CCO ID:** `CCO_CENARIO2_GAP_COM_RECUPERACAO`

### Descrição

CCO reconhecida em **maio/2021**. Primeiro aniversário: **junho/2022**. Segundo
aniversário: **junho/2023**.

O histórico contém o IPCA de junho/2023 (segundo aniversário), mas **falta** o de
junho/2022 (primeiro). Além disso, em fevereiro/2024 houve uma **recuperação parcial**
de R$ 100.000.000,00 calculada sobre a base incorreta (sem o IPCA de 2022).

A presença da `RECUPERACAO` eleva a complexidade: além de inserir o IPCA faltante,
o sistema deve gerar uma compensação pelo impacto sobre a recuperação que ocorreu
sobre a base errada.

### Linha do tempo

```
mai/2021  → Reconhecimento (valorReconhecidoComOH = R$ 151.500.000,00)
jun/2022  → [GAP] — deveria haver IPCA (taxa ref: mai/2022), mas não existe
jun/2023  → IPCA aplicado sobre base INCORRETA (151.500.000)
              valorReconhecidoComOH = R$ 157.865.700,00
fev/2024  → RECUPERACAO parcial: R$ 100.000.000,00 deduzido
              valorReconhecidoComOH após: R$ 57.865.700,00
              ← valor recuperado calculado sobre base sem o IPCA de 2022
```

### Campos-chave

| Campo | Valor |
|---|---|
| `dataReconhecimento` | `2021-05-18` |
| Primeiro aniversário (gap) | `06/2022` |
| Taxa ref. esperada para o gap | `05/2022` |
| `valorReconhecidoComOH` atual (última correção ativa) | `57.865.700,00` |
| `flgRecuperado` | `false` (recuperação parcial) |
| `valorRecuperado` na RECUPERACAO | `100.000.000,00` |
| `valorRecuperadoTotal` | `100.000.000,00` |

### Comportamento esperado do sistema

- `scenario_detected: "CENARIO_2"`
- `gaps_count: 1`
- Propostas geradas:
  - `IPCA_ADDITION` para `06/2022`, `taxa_referencia: "05/2022"`, `valor_base: 151.500.000`
  - `COMPENSATION` — compensação pelo impacto do gap não aplicado sobre a recuperação posterior
- Se após a compensação o saldo for positivo e `flgRecuperado = true`: proposta adicional
  `REACTIVATION` (não se aplica aqui pois `flgRecuperado = false`)

---

## Cenário Duplicatas — Correção Duplicada

**Arquivo:** `cco_cenario_duplicatas.json`  
**CCO ID:** `CCO_CENARIO_DUPLICATAS`

### Descrição

CCO reconhecida em **março/2022** (mesmo base do exemplo de referência da documentação).
Primeiro aniversário: **abril/2023**. Segundo aniversário: **abril/2024**.

O problema: o aniversário de **abril/2023** foi corrigido **duas vezes**:
- Entrada 1: `dataCorrecao: 2023-04-16` — taxa `1,046500`
- Entrada 2: `dataCorrecao: 2023-04-30` — taxa `1,045567` (lançamento duplicado no mesmo mês/ano)

A entrada de abril/2024 foi calculada em cascata sobre a segunda duplicata, inflando o saldo.

O sistema deve detectar duplicatas com **prioridade** sobre outros cenários: mesmo que
existam gaps, o cenário `CENARIO_DUPLICATAS` é ativado primeiro.

### Linha do tempo

```
mar/2022  → Reconhecimento (valorReconhecidoComOH = R$ 385.545.713,96)
abr/2023  → IPCA 1ª vez (taxa: 1,046500) → saldo: R$ 403.473.589,66  ← VÁLIDO
abr/2023  → IPCA 2ª vez (taxa: 1,045567) → saldo: R$ 421.857.498,05  ← DUPLICATA
              mesmo mês/ano — segunda entrada infla o saldo incorretamente
abr/2024  → IPCA calculado sobre saldo inflado (421.857.498,05)
              taxa: 1,039593 → valorReconhecidoComOH: R$ 438.565.046,35
```

### Campos-chave

| Campo | Valor |
|---|---|
| `dataReconhecimento` | `2022-03-11` |
| Período duplicado | `04/2023` |
| Entradas IPCA em abr/2023 | 2 (duplicata) |
| `valorReconhecidoComOH` atual (última correção ativa) | `438.565.046,35` |
| `flgRecuperado` | `false` |

### Comportamento esperado do sistema

- `scenario_detected: "CENARIO_DUPLICATAS"` (prioridade — detectado antes de qualquer gap)
- Propostas geradas:
  - `DUPLICATA_REMOVAL`: remoção da segunda entrada IPCA de abril/2023 (a mais recente)
  - `DUPLICATA_ADJUSTMENT`: RETIFICACAO compensatória que ajusta o efeito cascata na correção
    de abril/2024 (recalculada sobre a base sem a duplicata)
- Após remoção, `valorReconhecidoComOH` esperado é menor que o atual

---

## Notas de Implementação

### Regra do aniversário (implementada em `ipca_gap_analyzer.py`)

```
primeiro_aniversario.mes = dataReconhecimento.mes + 1
primeiro_aniversario.ano = dataReconhecimento.ano + 1
# exceto: se mes == 12 → mes = 1, ano = ano + 2
```

### Offset da taxa

```
taxa_referencia.mes = aniversario.mes - 1
# ex: aniversário abr/2023 → taxa de mar/2023
# ex: aniversário jan/2023 → taxa de dez/2022 (cruza virada de ano)
```

### Guard de valor_base (BUG-1 — já corrigido)

```python
if valor_base == 0:
    # gap sempre ignorado — sem base financeira
if valor_base < 0 and IGNORAR_CORECAO_MONETARIA_VALOR_NEGATIVO:
    # gap ignorado apenas quando flag = True (padrão: False)
```

### Determinação de cenário (em `ipca_correcao_orquestrador.py`)

| Condição | Cenário |
|---|---|
| `duplicatas` detectadas | `CENARIO_DUPLICATAS` (prioridade máxima) |
| `gaps` + sem correção posterior + sem RECUPERACAO | `CENARIO_0` |
| `gaps` + correção IPCA/IGPM posterior ao gap | `CENARIO_1` |
| `gaps` + entrada `RECUPERACAO` em `correcoesMonetarias` | `CENARIO_2` |
| Apenas correções fora do prazo (sem gaps) | `CENARIO_CORRECAO_FORA_APENAS` (sem propostas implementadas) |
| Demais casos | `CENARIO_COMPLEXO` (análise manual) |
