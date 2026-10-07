# Backlog: Suporte a Múltiplos Cenários Simultâneos — Módulo de Correção IPCA/IGPM

> **Status**: Backlog — Não iniciado  
> **Módulo**: Correção IPCA/IGPM (`feature/ipca-melhorias`)  
> **Criado em**: 2026-06-20  
> **Prioridade**: Média — melhoria de cobertura funcional, sem impacto em funcionalidade atual  
> **Risco estimado**: Alto — alterações em estrutura de dados central, lógica de aplicação e múltiplas camadas

---

## Sumário

1. [Contexto e Motivação](#1-contexto-e-motivação)
2. [Status Atual do Módulo](#2-status-atual-do-módulo)
3. [Objetivo](#3-objetivo)
4. [Justificativa de Negócio](#4-justificativa-de-negócio)
5. [Cenários Existentes — Regras Atuais](#5-cenários-existentes--regras-atuais)
6. [Problema: Exclusividade Forçada dos Cenários](#6-problema-exclusividade-forçada-dos-cenários)
7. [Matriz de Compatibilidade entre Cenários](#7-matriz-de-compatibilidade-entre-cenários)
8. [Arquitetura da Solução Proposta](#8-arquitetura-da-solução-proposta)
9. [Risco Crítico: Dependência de Valor entre Cenários](#9-risco-crítico-dependência-de-valor-entre-cenários)
10. [Mudanças por Camada](#10-mudanças-por-camada)
11. [Plano de Implementação Detalhado](#11-plano-de-implementação-detalhado)
12. [Critérios de Aceitação](#12-critérios-de-aceitação)
13. [Pré-requisitos](#13-pré-requisitos)
14. [Impacto em Funcionalidades Existentes](#14-impacto-em-funcionalidades-existentes)

---

## 1. Contexto e Motivação

O módulo de Correção IPCA/IGPM analisa uma CCO (`conta_custo_oleo_entity`) em busca de problemas relacionados a correções monetárias. O módulo mapeia os problemas encontrados em **cenários de correção**, cada um com sua própria lógica de detecção, geração de propostas e aplicação de correções.

Durante o uso e análise do módulo, identificou-se que uma CCO pode apresentar **mais de um tipo de problema simultaneamente**. Exemplos reais:

- CCO com **duplicatas em `correcoesMonetarias`** E **gaps de período** sem correção
- CCO com **duplicatas** E **correções aplicadas fora do período aniversário**

Atualmente, o sistema detecta apenas **um cenário por sessão**, com prioridade absoluta para `CENARIO_DUPLICATAS`. Isso significa que, na presença de duplicatas, os gaps não são sequer detectados — e o usuário precisaria executar duas análises sequenciais manualmente, o que não é suportado pelo fluxo atual.

---

## 2. Status Atual do Módulo

### Fluxo atual (simplificado)

```
iniciar_analise_cco()
    → gap_analyzer.analisar_gaps_sistema()
    → _determinar_cenario()  ← retorna UMA string
    → CorrectionSession.scenario_detected = str

gerar_propostas_correcao()
    → if/elif por cenário único
    → propostas acumuladas em session.corrections_proposed

aplicar_correcoes()
    → dispatch por cenário único
    → correction_engine.aplicar_correcoes_cenario_X()
```

### Arquivos principais

| Arquivo | Responsabilidade |
|---|---|
| `app/services/ipca_correcao_orquestrador.py` | Coordenação do fluxo, sessão, detecção de cenário |
| `app/services/ipca_correcao_engine.py` | Cálculo e aplicação das correções por cenário |
| `app/services/ipca_gap_analyzer.py` | Detecção de gaps, duplicatas e correções fora do período |
| `app/routes/ipca_correcao_routes.py` | Rotas Flask — exposição da API |
| `app/templates/ipca_correcao/` | Templates de análise, wizard de correção e memória de cálculo |

### Dataclass `CorrectionSession` (estado atual)

```python
@dataclass
class CorrectionSession:
    session_id: str
    cco_id: str
    user_id: str
    status: CorrectionStatus
    gaps_identified: List[Dict[str, Any]]
    corrections_fora_periodo: List[Dict[str, Any]]
    ccos_com_duplicatas: List[Dict[str, Any]]
    corrections_proposed: List[CorrectionProposal]
    corrections_approved: List[str]
    financial_impact: Dict[str, float]
    scenario_detected: str          # ← campo singular, um único cenário
    created_at: datetime
    updated_at: datetime
    applied_at: Optional[datetime] = None
    error_message: Optional[str] = None
```

### Função `_determinar_cenario()` (estado atual)

```python
def _determinar_cenario(self, gaps, correcoes_fora, duplicatas, cco_id) -> str:
    # PRIORIDADE 1: duplicatas engolam tudo
    if tem_duplicatas:
        return "CENARIO_DUPLICATAS"

    # PRIORIDADE 2+: grupo Gap (mutuamente exclusivos)
    if tem_gaps and not tem_correcoes_fora and not tem_recuperacao and not tem_posteriores:
        return "CENARIO_0"
    elif tem_gaps and (tem_correcoes_fora or tem_posteriores) and not tem_recuperacao:
        return "CENARIO_1"
    elif (tem_gaps or tem_correcoes_fora) and tem_recuperacao:
        return "CENARIO_2"
    elif tem_correcoes_fora and not tem_gaps and not tem_recuperacao:
        return "CENARIO_CORRECAO_FORA_APENAS"
    else:
        return "CENARIO_COMPLEXO"
```

### Despacho em `gerar_propostas_correcao()` (estado atual)

```python
if session.scenario_detected == "CENARIO_0":
    propostas = self._gerar_propostas_cenario_0(session)
elif session.scenario_detected == "CENARIO_1":
    propostas = self._gerar_propostas_cenario_1(session)
elif session.scenario_detected == "CENARIO_2":
    propostas = self._gerar_propostas_cenario_2(session)
elif session.scenario_detected == "CENARIO_DUPLICATAS":
    propostas = self._gerar_propostas_cenario_duplicatas(session)
else:
    propostas = []  # cenários não implementados retornam vazio
```

### Despacho em `aplicar_correcoes()` (estado atual)

```python
if session.scenario_detected == "CENARIO_0":
    resultado = self.correction_engine.aplicar_correcoes_cenario_0(...)
elif session.scenario_detected == "CENARIO_1":
    resultado = self.correction_engine.aplicar_correcoes_cenario_1(...)
elif session.scenario_detected == "CENARIO_2":
    resultado = self.correction_engine.aplicar_correcoes_cenario_2(...)
elif session.scenario_detected == "CENARIO_DUPLICATAS":
    resultado = self.correction_engine.aplicar_correcoes_cenario_duplicatas(...)
elif session.scenario_detected == "CENARIO_IPCA_VIGENTE":
    resultado = self.correction_engine.aplicar_correcoes_cenario_ipca_vigente(...)
else:
    return {'success': False, 'error': f'Cenário não implementado'}
```

---

## 3. Objetivo

Permitir que o módulo de Correção IPCA/IGPM:

1. **Detecte todos os problemas presentes em uma CCO simultaneamente**, sem que um cenário mascare a existência de outro.
2. **Gere propostas de correção para todos os cenários detectados** em uma única sessão de análise.
3. **Aplique todas as correções em ordem correta de dependência**, garantindo consistência do valor base entre cenários.
4. **Apresente ao usuário uma visão consolidada e agrupada** de todos os problemas e propostas.

---

## 4. Justificativa de Negócio

- **Completude da análise**: uma CCO analisada hoje pode ter dois problemas distintos. O usuário precisa detectar o segundo problema executando uma nova análise após a primeira correção — o que é ineficiente e sujeito a esquecimento.
- **Confiabilidade**: a ausência de detecção dupla pode levar a CCOs parcialmente corrigidas, com saldo monetário incorreto persistindo indefinidamente.
- **Auditoria**: uma sessão única contendo todos os problemas e correções gera uma memória de cálculo mais completa e rastreável.
- **Experiência do usuário**: o analista vê o quadro completo de problemas da CCO em um único fluxo, sem precisar lembrar de executar análises adicionais.

---

## 5. Cenários Existentes — Regras Atuais

### CENARIO_0 — Gap simples

- **Condição de detecção**: existem períodos aniversário sem correção IPCA/IGPM (`gaps_identified > 0`), sem correções fora do prazo, sem recuperação e sem correções posteriores aos gaps.
- **Proposta gerada**: `IPCA_ADDITION` — adiciona as correções faltantes nos períodos em branco.
- **Engine**: `calcular_correcao_cenario_0()` / `aplicar_correcoes_cenario_0()`

### CENARIO_1 — Gap com correção posterior

- **Condição de detecção**: existem gaps E já existem correções IPCA/IGPM posteriores à data do gap mais antigo (aplicadas sobre base incorreta), sem recuperação.
- **Proposta gerada**: `IPCA_ADDITION` para o gap + `IPCA_UPDATE` para recalcular as correções posteriores sobre a base correta.
- **Engine**: `calcular_correcao_cenario_1()` / `aplicar_correcoes_cenario_1()`

### CENARIO_2 — Gap com recuperação

- **Condição de detecção**: existem gaps OU correções fora do período, E a CCO já possui entradas de `RECUPERACAO` em `correcoesMonetarias`.
- **Proposta gerada**: `IPCA_ADDITION` + `COMPENSATION` (ajuste do saldo já recuperado) + `REACTIVATION` se `flgRecuperado = true`.
- **Engine**: `calcular_correcao_cenario_2()` / `aplicar_correcoes_cenario_2()`

### CENARIO_DUPLICATAS — Correções duplicadas

- **Condição de detecção**: existem entradas duplicadas de IPCA/IGPM em `correcoesMonetarias` para o mesmo período aniversário.
- **Proposta gerada**: `DUPLICATA_REMOVAL` para cada duplicata + `DUPLICATA_ADJUSTMENT` de compensação + `REACTIVATION` se necessário.
- **Engine**: `aplicar_correcoes_cenario_duplicatas()`
- **Prioridade atual**: máxima — quando detectado, nenhum outro cenário é avaliado.

### CENARIO_CORRECAO_FORA_APENAS — Apenas correção fora do prazo

- **Condição de detecção**: existem correções fora do período aniversário, sem gaps e sem recuperação.
- **Proposta gerada**: não implementada ainda (retorna lista vazia).
- **Engine**: não implementado.

### CENARIO_IPCA_VIGENTE — IPCA do ano corrente

- **Condição de detecção**: acionado manualmente via rota separada (`avaliar_ipca_ano_vigente()`), não pelo fluxo padrão de análise.
- **Proposta gerada**: `IPCA_ADDITION` para o período do ano corrente.
- **Engine**: `aplicar_correcoes_cenario_ipca_vigente()`

### CENARIO_COMPLEXO — Fallback

- **Condição**: nenhuma das condições acima correspondeu.
- **Comportamento atual**: retorna lista vazia de propostas, nenhuma correção gerada.

---

## 6. Problema: Exclusividade Forçada dos Cenários

### Exemplos de CCOs que hoje são mal analisadas

**Exemplo 1**: CCO com duplicata E gap de período

```
correcoesMonetarias:
  [0] IPCA  07/2023  ativo=true   ← primeira aplicação
  [1] IPCA  07/2023  ativo=true   ← duplicata (mesmo período)
  [2] IPCA  07/2024  ativo=true   ← período seguinte aplicado sobre base inflada

Período esperado 07/2022 → não existe (gap)
```

Resultado atual: sistema detecta `CENARIO_DUPLICATAS`, ignora o gap de 07/2022.
Resultado esperado: detectar `["CENARIO_DUPLICATAS", "CENARIO_1"]` — a duplicata infla a base, e sobre essa base inflada foram aplicadas as correções posteriores; o gap de 07/2022 também precisa ser preenchido.

**Exemplo 2**: CCO com duplicata E correção aplicada fora do período aniversário

```
dataReconhecimento: 2021-03-15
correcoesMonetarias:
  [0] IPCA  04/2022  ativo=true   ← correto (12 meses após = 04/2022)
  [1] IPCA  04/2022  ativo=true   ← duplicata
  [2] IPCA  06/2023  ativo=true   ← deveria ser 04/2023, aplicado em 06/2023 (fora)
```

Resultado atual: detecta `CENARIO_DUPLICATAS`, ignora a correção fora do período.
Resultado esperado: `["CENARIO_DUPLICATAS", "CENARIO_CORRECAO_FORA_APENAS"]`.

---

## 7. Matriz de Compatibilidade entre Cenários

Os cenários do **Grupo Gap** (CENARIO_0, CENARIO_1, CENARIO_2, CENARIO_CORRECAO_FORA_APENAS) são **mutuamente exclusivos** entre si: descrevem o mesmo tipo de problema (ausência ou erro de correção periódica) com contexto crescente. Apenas um pode ser verdadeiro para uma dada CCO.

`CENARIO_DUPLICATAS` é **ortogonal** ao Grupo Gap: descreve um problema na integridade das entradas existentes, independente de gaps.

| | CENARIO_0 | CENARIO_1 | CENARIO_2 | CENARIO_CORRECAO_FORA | CENARIO_DUPLICATAS |
|---|:---:|:---:|:---:|:---:|:---:|
| **CENARIO_0** | — | ✗ exclusivo | ✗ exclusivo | ✗ exclusivo | **✓ coexiste** |
| **CENARIO_1** | ✗ | — | ✗ exclusivo | ✗ exclusivo | **✓ coexiste** |
| **CENARIO_2** | ✗ | ✗ | — | ✗ exclusivo | **✓ coexiste** |
| **CENARIO_CORRECAO_FORA** | ✗ | ✗ | ✗ | — | **✓ coexiste** |
| **CENARIO_DUPLICATAS** | **✓** | **✓** | **✓** | **✓** | — |

**Combinações válidas esperadas pós-implementação:**

- `["CENARIO_0"]`
- `["CENARIO_1"]`
- `["CENARIO_2"]`
- `["CENARIO_CORRECAO_FORA_APENAS"]`
- `["CENARIO_DUPLICATAS"]`
- `["CENARIO_DUPLICATAS", "CENARIO_0"]`
- `["CENARIO_DUPLICATAS", "CENARIO_1"]`
- `["CENARIO_DUPLICATAS", "CENARIO_2"]`
- `["CENARIO_DUPLICATAS", "CENARIO_CORRECAO_FORA_APENAS"]`
- `["CENARIO_COMPLEXO"]` (nenhuma condição identificada)

---

## 8. Arquitetura da Solução Proposta

### 8.1 Novo campo na sessão

```python
@dataclass
class CorrectionSession:
    # ...
    scenarios_detected: List[str]    # substitui scenario_detected: str
    # ...
```

O campo `scenario` dentro de `CorrectionProposal` **não muda** — continua identificando qual sub-cenário gerou aquela proposta individual.

### 8.2 Nova função de detecção: `_detectar_cenarios()`

Substitui `_determinar_cenario()`. Avalia DUPLICATAS independentemente do Grupo Gap:

```python
def _detectar_cenarios(self, gaps, correcoes_fora, duplicatas, cco_id) -> List[str]:
    cenarios = []

    # DUPLICATAS: detectado de forma independente
    if tem_duplicatas:
        cenarios.append("CENARIO_DUPLICATAS")

    # Grupo Gap: mutuamente exclusivos entre si
    if tem_gaps and not tem_correcoes_fora and not tem_recuperacao and not tem_posteriores:
        cenarios.append("CENARIO_0")
    elif tem_gaps and (tem_correcoes_fora or tem_posteriores) and not tem_recuperacao:
        cenarios.append("CENARIO_1")
    elif (tem_gaps or tem_correcoes_fora) and tem_recuperacao:
        cenarios.append("CENARIO_2")
    elif tem_correcoes_fora and not tem_gaps and not tem_recuperacao:
        cenarios.append("CENARIO_CORRECAO_FORA_APENAS")

    return cenarios if cenarios else ["CENARIO_COMPLEXO"]
```

### 8.3 Geração de propostas em loop

```python
def gerar_propostas_correcao(self, session_id):
    # ...
    all_propostas = []
    for cenario in session.scenarios_detected:
        if cenario == "CENARIO_DUPLICATAS":
            all_propostas.extend(self._gerar_propostas_cenario_duplicatas(session))
        elif cenario == "CENARIO_0":
            all_propostas.extend(self._gerar_propostas_cenario_0(session))
        elif cenario == "CENARIO_1":
            all_propostas.extend(self._gerar_propostas_cenario_1(session))
        elif cenario == "CENARIO_2":
            all_propostas.extend(self._gerar_propostas_cenario_2(session))
        elif cenario == "CENARIO_CORRECAO_FORA_APENAS":
            all_propostas.extend(self._gerar_propostas_cenario_correcao_fora(session))
    session.corrections_proposed = all_propostas
```

### 8.4 Aplicação em dois estágios com recálculo intermediário

Este é o ponto mais crítico da implementação (ver seção 9):

```
ESTÁGIO 1 — Aplicar CENARIO_DUPLICATAS (se presente)
    ↓
    Recarregar CCO do banco (novo estado sem duplicatas)
    ↓
    Recalcular propostas de gap sobre o novo valor base
    ↓
ESTÁGIO 2 — Aplicar cenário de Gap (CENARIO_0/1/2/CORRECAO_FORA)
```

```python
def aplicar_correcoes(self, session_id):
    session = self._load_session(session_id)
    ordem = self._ordenar_cenarios_para_aplicacao(session.scenarios_detected)
    # CENARIO_DUPLICATAS sempre primeiro

    for cenario in ordem:
        propostas_cenario = [
            p for p in correcoes_aprovadas
            if p.scenario == cenario
        ]
        resultado = self._aplicar_cenario(cenario, session, propostas_cenario)

        if not resultado['success']:
            # rollback parcial ou sinalização de erro
            break

        # Se acabou de aplicar DUPLICATAS e há mais cenários:
        if cenario == "CENARIO_DUPLICATAS" and len(ordem) > 1:
            propostas_recalculadas = self._recalcular_propostas_gap(session)
            self._substituir_propostas_gap_na_sessao(session, propostas_recalculadas)
```

### 8.5 Novo método `_recalcular_propostas_gap()`

Após aplicação de CENARIO_DUPLICATAS, relê a CCO do banco e recalcula as propostas de gap sobre o valor limpo:

```python
def _recalcular_propostas_gap(self, session: CorrectionSession) -> List[CorrectionProposal]:
    """
    Relê a CCO após remoção de duplicatas e recalcula propostas de gap
    sobre o valor base atualizado.
    """
    cco_atualizada = self.db.conta_custo_oleo_corrigida_entity.find_one({'_id': session.cco_id})
    # Recalcular usando o engine com a CCO atualizada
    # ...
```

### 8.6 Ordenação de cenários para aplicação

```python
def _ordenar_cenarios_para_aplicacao(self, cenarios: List[str]) -> List[str]:
    """
    Define a ordem de aplicação para garantir consistência de valor base.
    CENARIO_DUPLICATAS sempre antes dos cenários de Gap.
    """
    ORDEM_PRIORIDADE = [
        "CENARIO_DUPLICATAS",
        "CENARIO_0",
        "CENARIO_1",
        "CENARIO_2",
        "CENARIO_CORRECAO_FORA_APENAS",
    ]
    return [c for c in ORDEM_PRIORIDADE if c in cenarios]
```

---

## 9. Risco Crítico: Dependência de Valor entre Cenários

### O problema

As propostas do cenário de Gap são calculadas sobre o `valorReconhecidoComOH` **atual** da CCO. Quando a CCO também tem duplicatas, esse valor atual está inflado pelo valor incorreto das duplicatas.

Se as propostas de gap forem calculadas antes da remoção das duplicatas e aplicadas depois, os valores estarão errados:

```
Estado real da CCO:
  valorReconhecidoComOH = R$ 180.000 (inflado por duplicata de R$ 20.000)
  Valor correto seria = R$ 160.000

Proposta de gap gerada ANTES da remoção:
  Base de cálculo: R$ 180.000
  IPCA 4%: R$ 7.200 de correção

Após remoção da duplicata:
  valorReconhecidoComOH = R$ 160.000

Aplicação do gap com proposta calculada sobre R$ 180.000:
  Resultado: ERRO — base incorreta
```

### Solução: recálculo intermediário obrigatório

Quando `scenarios_detected` contém `CENARIO_DUPLICATAS` junto com qualquer cenário de Gap:

1. **Na geração de propostas**: as propostas de gap são marcadas como `"pendente_recalculo": true` na descrição, com aviso explícito ao usuário.
2. **Na aplicação**: após aplicar `CENARIO_DUPLICATAS`, o sistema relê a CCO e recalcula as propostas de gap antes de aplicá-las.
3. **Na memória de cálculo**: registrar os dois momentos — valor base pré-remoção e valor base pós-remoção.

### Implicação para a UI

Na tela de aprovação de propostas, quando há multi-cenário com duplicatas + gap, exibir aviso:

> "As propostas de correção por gap foram calculadas sobre o saldo atual. Após a remoção das duplicatas, os valores de impacto serão recalculados automaticamente antes da aplicação."

---

## 10. Mudanças por Camada

### 10.1 `app/services/ipca_correcao_orquestrador.py`

| Elemento | Mudança |
|---|---|
| `CorrectionSession.scenario_detected: str` | Renomear para `scenarios_detected: List[str]` |
| `CorrectionSession.to_dict()` | Serializa lista normalmente |
| `_dict_to_session()` | Deserializar lista; retrocompatibilidade com `scenario_detected` (string) de sessões antigas |
| `_determinar_cenario()` | Substituir por `_detectar_cenarios()` retornando `List[str]` |
| `iniciar_analise_cco()` | Usar `_detectar_cenarios()`; campo `scenarios_detected` na sessão; resposta JSON com lista |
| `gerar_propostas_correcao()` | Converter `if/elif` para loop sobre `session.scenarios_detected` |
| `aplicar_correcoes()` | Converter para aplicação em estágios com `_ordenar_cenarios_para_aplicacao()` |
| `_gerar_resumo_analise()` | Adaptar para lista de cenários |
| `_gerar_preview_data()` | Adaptar para lista de cenários |
| `_calcular_impacto_financeiro()` | Agrupar impacto por cenário além de por tipo |
| `_gerar_preview_final()` | Adaptar para multi-cenário |
| Novos métodos | `_detectar_cenarios()`, `_ordenar_cenarios_para_aplicacao()`, `_recalcular_propostas_gap()`, `_substituir_propostas_gap_na_sessao()` |

### 10.2 `app/services/ipca_correcao_engine.py`

| Elemento | Mudança |
|---|---|
| Métodos por cenário | **Sem alteração** — a lógica de cada cenário individual permanece intacta |
| Novo método (opcional) | `aplicar_em_estagios()` — encapsula a lógica de aplicação ordenada se preferir mover para o engine |

### 10.3 `app/services/ipca_gap_analyzer.py`

Sem alterações — a lógica de detecção de gaps, duplicatas e correções fora do período permanece inalterada.

### 10.4 `app/routes/ipca_correcao_routes.py`

| Elemento | Mudança |
|---|---|
| Todas as rotas que retornam `session` | Campo `scenario_detected` (string) → `scenarios_detected` (lista) nas respostas JSON |
| Retrocompatibilidade | Se algum frontend consome `scenario_detected` como string, manter campo adicional de compatibilidade no JSON de resposta durante a transição |

### 10.5 Templates — `app/templates/ipca_correcao/`

| Template | Mudança |
|---|---|
| Tela de análise / wizard | Badge único de cenário → lista de badges (um por cenário detectado) |
| Descrição do problema | Parágrafo por cenário detectado (não mais um texto fixo por cenário único) |
| Lista de propostas | Coluna "Cenário" adicionada; agrupamento por cenário (accordion ou abas) |
| Aviso multi-cenário | Alerta específico quando `CENARIO_DUPLICATAS` coexiste com cenário de Gap |
| `memoria_calculo.html` | Seção "Cenários Detectados" lista todos; tabela de propostas com coluna de cenário; seção "Ordem de Aplicação" quando multi-cenário; impacto financeiro por cenário |

### 10.6 MongoDB — Coleção `ipca_correction_sessions`

| Aspecto | Situação |
|---|---|
| Sessões novas | Campo `scenarios_detected` (array) substitui `scenario_detected` (string) |
| Sessões antigas | Campo `scenario_detected` ainda presente — deserialização deve tratar ambos |
| Índices | Nenhum índice usa `scenario_detected`, nenhuma mudança de índice necessária |

---

## 11. Plano de Implementação Detalhado

### Fase 1 — Estrutura de dados e retrocompatibilidade

**Objetivo**: Mudar o campo da sessão sem quebrar fluxos existentes.

**Tarefas**:

1. Em `CorrectionSession`, renomear `scenario_detected: str` para `scenarios_detected: List[str]`.
2. Em `to_dict()`: serializar como lista (já funciona, `asdict()` converte listas automaticamente).
3. Em `_dict_to_session()`: adicionar lógica de retrocompatibilidade:
   ```python
   # Suporte a documentos antigos com campo singular
   if 'scenario_detected' in session_data and 'scenarios_detected' not in session_data:
       session_data['scenarios_detected'] = [session_data.pop('scenario_detected')]
   elif 'scenarios_detected' not in session_data:
       session_data['scenarios_detected'] = ["CENARIO_COMPLEXO"]
   ```
4. Atualizar `CorrectionProposal.scenario: str` — **sem alteração** (já é string por proposta).
5. Rodar testes manuais de serialização/deserialização com sessão antiga e nova.

**Risco**: Baixo — mudança de estrutura isolada, sem lógica de negócio.

---

### Fase 2 — Detecção multi-cenário

**Objetivo**: Detectar todos os cenários aplicáveis em uma única análise.

**Tarefas**:

1. Criar novo método `_detectar_cenarios()` com a lógica descrita na seção 8.2.
2. Adaptar `iniciar_analise_cco()` para chamar `_detectar_cenarios()` e armazenar `scenarios_detected` (lista).
3. Atualizar resposta JSON de `iniciar_analise_cco()`:
   - Adicionar `scenarios_detected: List[str]` na resposta
   - Manter `scenario_detected: str` como alias do primeiro elemento para retrocompatibilidade de clientes que consumam o campo singular
4. Atualizar `_gerar_resumo_analise()` para listar todos os cenários.
5. Testes: verificar CCOs com duplicata + gap, com duplicata + correção fora do período.

**Risco**: Médio — a lógica de detecção é o núcleo do módulo; regressão pode fazer cenários anteriores pararem de ser detectados. Testar exaustivamente com CCOs de cada cenário individual antes de ativar detecção combinada.

---

### Fase 3 — Geração de propostas multi-cenário

**Objetivo**: Gerar propostas para todos os cenários detectados em uma única sessão.

**Tarefas**:

1. Substituir o `if/elif` em `gerar_propostas_correcao()` pelo loop descrito na seção 8.3.
2. Garantir que cada `CorrectionProposal` gerada tenha o campo `scenario` corretamente preenchido com o cenário que a originou.
3. Atualizar `_calcular_impacto_financeiro()` para retornar breakdown por cenário:
   ```python
   return {
       'total_impact': ...,
       'por_cenario': {
           'CENARIO_DUPLICATAS': {'impacto': ..., 'propostas': n},
           'CENARIO_1': {'impacto': ..., 'propostas': n},
       }
   }
   ```
4. Atualizar `_gerar_preview_data()` para incluir lista de cenários e breakdown.
5. Quando há multi-cenário com DUPLICATAS + Gap: adicionar campo `"pendente_recalculo": true` na descrição das propostas de gap.

**Risco**: Médio — possível duplicação de propostas se condições de cenário se sobrepuserem parcialmente. Verificar que cada proposta pertence a exatamente um cenário.

---

### Fase 4 — Aplicação em estágios com recálculo intermediário

**Objetivo**: Garantir que a aplicação multi-cenário produza valores corretos, respeitando a dependência de valor entre cenários.

**Tarefas**:

1. Implementar `_ordenar_cenarios_para_aplicacao()` (seção 8.6).
2. Implementar `_recalcular_propostas_gap()` — após remoção de duplicatas, relê a CCO e recalcula os valores das propostas de gap já aprovadas pelo usuário.
3. Implementar `_substituir_propostas_gap_na_sessao()` — atualiza a sessão no MongoDB com as propostas recalculadas antes de aplicar o estágio 2.
4. Refatorar `aplicar_correcoes()` para o fluxo em estágios (seção 8.4).
5. Implementar rollback parcial: se o estágio 2 falhar após o estágio 1 já ter sido aplicado, registrar o erro detalhadamente na sessão (`error_message`) e sinalizar quais cenários foram aplicados com sucesso.
6. Adicionar log detalhado de cada estágio de aplicação.

**Risco**: Alto — esta fase mexe na aplicação de correções ao MongoDB de produção. Requer testes com CCOs de homologação com dados reais antes de ativar.

---

### Fase 5 — Atualização de rotas

**Objetivo**: Atualizar as respostas da API para refletir a estrutura multi-cenário.

**Tarefas**:

1. Em todas as rotas de `ipca_correcao_routes.py` que retornam dados de sessão: substituir `scenario_detected` por `scenarios_detected` nas respostas JSON.
2. Manter campo `scenario_detected` como alias do primeiro elemento da lista enquanto houver clientes do frontend que consumam o campo singular (remover após Fase 6 concluída).
3. Atualizar documentação de API (comentários de rotas) para refletir mudança.

**Risco**: Baixo — mudança de resposta JSON, sem lógica de negócio.

---

### Fase 6 — Atualização de templates

**Objetivo**: Refletir visualmente o suporte a múltiplos cenários.

**Tarefas**:

1. **Tela de análise (wizard)**:
   - Substituir badge único de cenário por lista de badges
   - Adicionar seção de descrição por cenário detectado
   - Adicionar aviso específico quando DUPLICATAS + Gap (recálculo intermediário)

2. **Lista de propostas**:
   - Adicionar coluna "Cenário" na tabela de propostas
   - Implementar agrupamento por cenário (accordion: um grupo por cenário)
   - Exibir subtotal de impacto por cenário

3. **`memoria_calculo.html`**:
   - Seção "Cenários Detectados": listar todos com descrição individual
   - Tabela de propostas: coluna cenário
   - Seção "Ordem de Aplicação": exibir quando há mais de um cenário
   - Impacto financeiro: breakdown por cenário além do total

4. Remover alias `scenario_detected` do JavaScript após garantir que nenhum trecho de template ainda o consome.

**Risco**: Baixo — mudanças de apresentação sem lógica de negócio.

---

### Fase 7 — Testes de regressão e validação

**Objetivo**: Garantir que cenários individuais (comportamento atual) continuem funcionando após todas as mudanças.

**Casos de teste obrigatórios**:

| Caso | Cenários esperados | Validação |
|---|---|---|
| CCO com gap simples | `["CENARIO_0"]` | Proposta e aplicação idênticas ao comportamento atual |
| CCO com gap + correção posterior | `["CENARIO_1"]` | Idem |
| CCO com gap + recuperação | `["CENARIO_2"]` | Idem |
| CCO com apenas duplicata | `["CENARIO_DUPLICATAS"]` | Idem |
| CCO com duplicata + gap simples | `["CENARIO_DUPLICATAS", "CENARIO_0"]` | Novo — verificar recálculo intermediário |
| CCO com duplicata + gap + posterior | `["CENARIO_DUPLICATAS", "CENARIO_1"]` | Novo — verificar recálculo intermediário |
| CCO com duplicata + gap + recuperação | `["CENARIO_DUPLICATAS", "CENARIO_2"]` | Novo — verificar recálculo e saldo final |
| CCO sem nenhum problema | `["CENARIO_COMPLEXO"]` | Deve retornar lista vazia de propostas |
| Sessão antiga no MongoDB (campo `scenario_detected: str`) | Retrocompatibilidade na leitura | Não deve quebrar ao carregar sessão |

---

## 12. Critérios de Aceitação

- [ ] Uma CCO com duplicata E gap detecta ambos os cenários em uma única análise
- [ ] Propostas de ambos os cenários são geradas e apresentadas ao usuário na mesma sessão
- [ ] Propostas são agrupadas visualmente por cenário na tela de revisão
- [ ] A aplicação de correções multi-cenário ocorre na ordem correta (DUPLICATAS antes de Gap)
- [ ] Propostas de gap são recalculadas sobre o valor base correto (pós-remoção de duplicatas) antes de serem aplicadas
- [ ] Cenários individuais (fluxo atual com cenário único) continuam funcionando sem regressão
- [ ] Sessões antigas no MongoDB com campo `scenario_detected: str` são lidas sem erro
- [ ] Memória de cálculo exibe todos os cenários detectados e suas propostas agrupadas
- [ ] Quando há recálculo intermediário, a memória de cálculo registra o valor base pré e pós remoção de duplicatas

---

## 13. Pré-requisitos

Antes de iniciar a implementação:

- [ ] **`CENARIO_CORRECAO_FORA_APENAS` implementado**: o gerador de propostas para esse cenário (`_gerar_propostas_cenario_correcao_fora()`) e o método de aplicação correspondente no engine precisam existir antes da Fase 3, pois o loop de geração irá invocá-lo.
- [ ] **Testes de regressão manual documentados**: casos de teste com CCOs reais dos cenários atuais devem ser executados e documentados antes do início, para servir de baseline de comparação pós-implementação.
- [ ] **Ambiente de homologação com dados representativos**: necessário para testar Fase 4 (aplicação em estágios) com segurança.

---

## 14. Impacto em Funcionalidades Existentes

| Funcionalidade | Impacto | Observação |
|---|---|---|
| Fluxo de análise com cenário único | **Nenhum** — comportamento preservado | Loop com lista de 1 elemento é equivalente ao if/elif atual |
| Sessões existentes no MongoDB | **Baixo** — leitura retrocompatível | Campo `scenario_detected` tratado na deserialização |
| Módulo de Promoção IPCA | **Nenhum** — módulo independente | Não consome `scenario_detected` |
| `CENARIO_IPCA_VIGENTE` | **Nenhum** — fluxo separado via `avaliar_ipca_ano_vigente()` | Não passa pelo `_detectar_cenarios()` |
| Memória de cálculo (leitura) | **Baixo** — template precisa de adaptação de exibição | Dados ainda vêm da mesma sessão; apenas apresentação muda |
