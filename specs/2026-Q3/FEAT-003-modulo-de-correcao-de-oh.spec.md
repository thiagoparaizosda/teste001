---
spec_id: FEAT-003
title: "Modulo de Correcao de OH"
status: Draft
type: feature
created_at: 2026-09-03
created_by: "Thiago Paraizo"
approved_by: ""
approved_at: ""
sprint: "2026-Q3"
stack: "python"
---


# FEAT-003: Módulo de Correção de OH

## 1. Contexto e Motivação

Complementa FEAT-001 (Análise de OH): resolve o segundo problema descrito no documento de escopo
técnico (`docs/PPSA - SD-3720 - Estimativa Escopo - Aditivo (Modulo_OH).pdf`, melhoria SD-2242) —
permitir que usuários autorizados corrijam CCOs com OH inconsistente identificadas na análise, com
simulação completa de propagação em cascata antes de qualquer alteração em produção.

O sistema hoje não possui mecanismo de correção de OH. Erros ficam acumulados silenciosamente ao
longo da cadeia de correções monetárias (IPCA/IGPM), distorcendo o saldo recuperável de cada CCO.
Este módulo introduz um fluxo estruturado de 5 etapas (Análise → Geração de Proposta → Revisão/
Aprovação → Staging → Promoção), reutilizando como base a arquitetura já existente e validada em
produção do módulo de Correção de IPCA/IGPM (`docs/modulo_correcao_ipca_igpm.md`,
`app/services/ipca_correcao_engine.py`, `app/services/ipca_correcao_orquestrador.py`).

Esta spec depende de FEAT-001 (a correção é sempre iniciada a partir de uma CCO identificada como
inconsistente na tela de análise) e recomenda-se que FEAT-002 (ajustes pontuais de Análise) esteja
concluída antes do início desta, para que o motor de verificação/faixas usado aqui parta de uma base
100% aderente ao escopo.

## 2. Escopo

### 2.1 Está no escopo
- Acesso à correção de uma CCO específica a partir da tela de análise de OH (botão "Corrigir" em
  linhas com ERRO — já existente em `verificacao_oh/index.html`, componente C-1.13 do documento de
  escopo).
- Tela de início da correção (T-2.1): exibe a CCO selecionada, valores atuais de OH e OH esperado
  calculado pelo motor de faixas progressivas.
- Motor de cálculo do OH correto pelas regras de faixa progressiva, considerando o acumulado anual
  do contrato (reaproveitando a lógica de `_calcular_oh_exp_por_faixas` documentada em FEAT-001).
- Simulação de cascata temporal: recálculo de `valorReconhecidoComOH` e de toda a cadeia de
  `correcoesMonetarias` (IPCA/IGPM) subsequentes da CCO, reaproveitando o padrão de encadeamento
  `valor_base → valor_corrigido → nova_base` já implementado em
  `IPCACorrectionEngine._calcular_correcao_individual_gap` (`ipca_correcao_engine.py:1578`).
- Simulação de cascata horizontal: identificação e recálculo das demais CCOs do mesmo contrato e ano
  de reconhecimento impactadas pela mudança no acumulado anual.
- Tela de prévia da correção (T-2.2): comparativo lado a lado (atual vs. proposto) para o bloco RAIZ,
  timeline das correções monetárias afetadas, painel de CCOs afetadas (cascata horizontal) e resumo
  de impacto financeiro total.
- Aprovação explícita do usuário antes de qualquer persistência (nenhuma escrita em produção sem
  confirmação).
- Persistência da correção aprovada na coleção de staging `conta_custo_oleo_corrigida_entity`, com
  `status_promocao: 'PENDENTE'`, seguindo exatamente o padrão já usado pelo módulo IPCA/IGPM
  (`ipca_correcao_engine.py`, métodos `aplicar_correcoes_cenario_X`).
- Gerenciamento do ciclo de vida da sessão de correção (ANALYZING → PREVIEW → APPROVED → STAGED/
  APPLIED), reaproveitando o padrão de `CorrectionSession`/`IPCACorrectionOrchestrator`, com
  persistência em uma nova coleção `oh_correction_sessions` (equivalente a `ipca_correction_sessions`).
- Descarte de proposta (sem gravar nada).
- Regra: uma CCO não pode ter mais de uma correção de OH pendente no staging simultaneamente.
- Log de auditoria da criação da proposta e de sua aprovação (reaproveitando `AuditAction`/
  `audit_service.py` já usado pelo módulo IPCA).

### 2.2 NÃO está no escopo (decisão consciente)
- Telas de **Staging (listagem/gerenciamento)** e de **Promoção (execução da promoção para
  produção)** — serão reutilizadas do módulo de Promoção já em fase de implementação
  (`app/routes/ipca_promocao_routes.py`, `app/services/ipca_promocao_service.py`,
  `app/templates/ipca_promocao/`), estendido para também listar/promover correções de origem OH.
  Esta spec entrega apenas a persistência inicial em staging (equivalente a
  `aplicar_correcoes_cenario_X` do módulo IPCA); a listagem e a promoção propriamente dita não são
  contabilizadas neste escopo.
- Alteração das regras de cálculo de OH (taxas, faixas, tolerâncias).
- Recálculo retroativo em massa de todas as CCOs do sistema — a correção é sempre iniciada a partir
  de uma CCO específica identificada como inconsistente.
- Integração com o módulo de Recuperação (processo mensal) — recálculo de recuperações já aplicadas.
- Interface para o operador (módulo exclusivo para usuários internos da PPSA).
- Correção automática sem revisão humana.
- Relatórios executivos em PDF.

## 3. Definição da Solução

### 3.1 Arquitetura

```
verificacao_oh_bp (botão "Corrigir", já existente em FEAT-001)
        │
        ▼
correcao_oh_bp (NOVO blueprint, prefixo /correcao-oh)
        │
        ▼
OHCorrectionOrchestrator (NOVO, app/services/oh_correcao_orquestrador.py)
        │  espelha IPCACorrectionOrchestrator (ipca_correcao_orquestrador.py)
        │  persiste sessões em: oh_correction_sessions (equivalente a ipca_correction_sessions)
        ▼
OHCorrectionEngine (NOVO, app/services/oh_correcao_engine.py)
        │  espelha IPCACorrectionEngine (ipca_correcao_engine.py)
        │  reaproveita: _calcular_correcao_individual_gap (cascata temporal),
        │               _reconstruir_lista_correcoes (reconstrução cronológica),
        │               padrão de _ajustar_atributos_correcoes_ipca
        ▼
conta_custo_oleo_corrigida_entity (staging, banco DEV — MESMA coleção do módulo IPCA)
conta_custo_oleo_entity (leitura da CCO original — banco PRD/origem)
```

> **[NEEDS CLARIFICATION]:** o módulo IPCA usa o padrão de "duas conexões simultâneas no construtor"
> (`db_connection` + `db_prd_connection`), diferente do padrão "parâmetro `db_env` único" usado por
> `verificacao_oh_routes.py`/`verificacao_tp_routes.py`. Como a correção de OH precisa ler a CCO de
> origem (PRD) e gravar em staging (DEV) simultaneamente — igual ao módulo IPCA — recomenda-se seguir
> o padrão do módulo IPCA (duas conexões). Confirmar com o Tech Lead antes de implementar.

> **[NEEDS CLARIFICATION]:** não existe hoje uma `Permission` específica para OH (`app/models/
> permission.py` só tem `CCO_VIEW`, `CCO_EDIT`, `CCO_DELETE`, `CORRECAO_VIEW`, `CORRECAO_CREATE`,
> `CORRECAO_PROMOTE`, `REPORT_EXPORT`, `AUDIT`). O documento de escopo (seção 3.3.5) menciona
> `CCO_VIEW`/`CCO_EDIT`/`CCO_ADMIN` para este módulo, mas esses nomes não existem no enum atual.
> Decidir: (a) reaproveitar `CORRECAO_CREATE`/`CORRECAO_PROMOTE` (já usados pelo módulo IPCA,
> mantendo consistência), ou (b) criar novas permissões específicas (`CORRECAO_OH_CREATE` etc.).
> Esta spec assume a opção (a) até confirmação em contrário — ver FR-012.

### 3.2 Contrato de API

```yaml
GET /correcao-oh/iniciar/<cco_id>
  Response: 200 (HTML) — página T-2.1 com dados da CCO pré-carregados
  401/403: idem padrão do projeto

POST /correcao-oh/api/simular
  Request:
    body:
      cco_id: string (required)
  Response:
    200:
      session_id: string
      proposta:
        raiz: { atual: {...}, proposto: {...} }
        cascata_temporal: array de correções monetárias recalculadas (antes/depois)
        cascata_horizontal: array de CCOs afetadas com Δ
        impacto_financeiro_total: decimal
    400: ValidationError (cco_id inválido, ou CCO já com correção OH pendente no staging)
    401/403: idem
    404: NotFoundError

GET /correcao-oh/previa/<session_id>
  Response: 200 (HTML) — página T-2.2 com a prévia completa

POST /correcao-oh/api/aprovar
  Request:
    body:
      session_id: string (required)
  Response:
    200: { status_promocao: "PENDENTE", cco_id: string }
    400: ConflictError (já existe correção OH pendente para esta CCO)
    401/403: idem

DELETE /correcao-oh/api/descartar/<session_id>
  Response:
    200: { descartado: true }
    401/403: idem
```

### 3.3 Requisitos Funcionais

- FR-001: A partir de uma linha com status ERRO na tela de análise de OH (FEAT-001), um botão
  "Corrigir" (já previsto no componente C-1.13) navega para `GET /correcao-oh/iniciar/<cco_id>`,
  pré-carregando os valores atuais de OH da CCO e o OH esperado calculado pelo motor de faixas.
- FR-002: `OHCorrectionEngine.calcular_oh_correto(cco_id)` determina o acumulado anual do contrato
  até a CCO em questão (mesma lógica cronológica de `analisar_faixas_exploracao`, FEAT-001) e aplica
  as faixas progressivas com proporcionalidade, retornando o valor correto de
  `overHeadExploracao`/`overHeadProducao`/`overHeadTotal`.
- FR-003: `OHCorrectionEngine.simular_cascata_temporal(cco, oh_correto)` reconstrói o encadeamento
  `valor_base → valor_corrigido → nova_base` para cada entrada de `correcoesMonetarias` subsequente
  à mudança de `valorReconhecidoComOH`, reaproveitando o algoritmo de
  `_calcular_correcao_individual_gap` (`ipca_correcao_engine.py:1578`) adaptado para partir da nova
  base de OH em vez de um gap de IPCA. Correções do tipo `RECUPERACAO` e `RETIFICACAO` devem ser
  preservadas e seus efeitos mantidos na proporção correta.
- FR-004: `OHCorrectionEngine.identificar_ccos_afetadas(cco_id)` busca todas as CCOs do mesmo
  `contratoCpp` e `anoReconhecimento` (mesma query cronológica usada em FEAT-001) cujo acumulado
  anual depende da CCO corrigida.
- FR-005: `OHCorrectionEngine.simular_cascata_horizontal(ccos_afetadas, oh_correto)` recalcula o
  acumulado anual a partir da CCO mais antiga afetada, atualizando as faixas progressivas de todas as
  CCOs subsequentes do contrato/ano.
- FR-006: `OHCorrectionEngine.gerar_proposta(cco_id, user_id)` orquestra FR-002 a FR-005 e retorna a
  proposta consolidada (RAIZ + cadeia temporal + CCOs afetadas + impacto financeiro total).
- FR-007: `OHCorrectionOrchestrator` gerencia o ciclo de vida da sessão de correção com os estados
  `ANALYZING → PREVIEW → APPROVED → STAGED` (ou `REJECTED`/`ERROR`), espelhando exatamente o padrão
  de `CorrectionSession`/`CorrectionStatus` de `ipca_correcao_orquestrador.py:15-98`, persistindo em
  `oh_correction_sessions` (MongoDB, banco DEV) via `replace_one(..., upsert=True)`.
- FR-008: A tela de prévia (T-2.2) exibe lado a lado os valores atuais e propostos dos campos
  `valorReconhecidoComOH`, `overHeadExploracao`, `overHeadProducao`, `overHeadTotal`, com destaque
  visual para cada campo alterado; exibe a timeline cronológica de cada entrada de IPCA/IGPM
  recalculada (valores antes/depois, impacto unitário); exibe o painel de CCOs afetadas (cascata
  horizontal) com Δ por CCO; exibe o resumo do impacto financeiro total.
- FR-009: Nenhuma alteração é gravada em produção antes da confirmação explícita do usuário na tela
  de prévia (botão "Confirmar e Enviar para Staging", com modal de confirmação).
- FR-010: `OHCorrectionEngine.persistir_staging(proposta, user_id)` grava o documento de correção em
  `conta_custo_oleo_corrigida_entity` com `status_promocao: 'PENDENTE'`, seguindo o mesmo padrão de
  `aplicar_correcoes_cenario_X` do módulo IPCA (clonar CCO original, sobrescrever `_id`, adicionar
  `session_id`, `data_criacao_correcao`, nova `correcoesMonetarias`).
- FR-011: Antes de `persistir_staging`, o sistema deve validar que a CCO não possui outra correção de
  OH pendente (`status_promocao = 'PENDENTE'`) já existente em `conta_custo_oleo_corrigida_entity`;
  em caso positivo, retornar HTTP 400/ConflictError sem persistir.
- FR-012: Todos os endpoints do blueprint `correcao_oh_bp` exigem autenticação JWT válida (HTTP 401
  sem token) e a permissão apropriada: visualização/início/simulação exige `CORRECAO_CREATE`;
  aprovação (envio para staging) também exige `CORRECAO_CREATE` (a promoção para produção, fora do
  escopo desta spec, já exige `CORRECAO_PROMOTE` no módulo de Promoção existente) — ver
  `[NEEDS CLARIFICATION]` na seção 3.1 sobre nomenclatura de permissões.
- FR-013: O botão "Descartar Proposta" (`DELETE /correcao-oh/api/descartar/<session_id>`) encerra a
  sessão sem gravar nada em `conta_custo_oleo_corrigida_entity`.
- FR-014: Toda operação de escrita (geração de proposta, aprovação, descarte) é registrada em log de
  auditoria (usuário autenticado via JWT, data/hora, ambiente, resumo da alteração), reaproveitando
  `AuditAction`/`audit_service.py` já usado pelo módulo de Promoção.

### 3.4 Modelo de Dados

**Nova coleção `oh_correction_sessions`** (equivalente a `ipca_correction_sessions`):
- `session_id` (string, chave), `cco_id`, `status` (ANALYZING/PREVIEW/APPROVED/STAGED/REJECTED/
  ERROR), `proposta` (objeto com raiz/cascata_temporal/cascata_horizontal/impacto_financeiro_total),
  `user_id`, `created_at`, `updated_at`.

**Coleção `conta_custo_oleo_corrigida_entity`** (já existente, reaproveitada — mesmo schema validado
em `init-scripts/init-mongo.js:51`, campo `status_promocao` com enum `['PENDENTE', 'PROMOVIDA',
'REJEITADA']`): novos documentos de origem OH devem seguir o mesmo shape dos documentos de origem
IPCA (clone da CCO original + campos de controle), sem necessidade de alteração de schema.

## 4. Restrições de Implementação

### Stack obrigatória
- [x] Python 3.11 + Flask 3.0
- [x] Logging: `logging` stdlib, `logger = logging.getLogger(__name__)`
- [x] Tratamento de erros: exceções específicas, `logger.error(f"...: {e}", exc_info=True)`
- [x] Sem dependências novas — reaproveita `pymongo` já presente

### O que NÃO fazer
- Não duplicar a lógica de cascata temporal — reaproveitar/adaptar
  `_calcular_correcao_individual_gap` e `_reconstruir_lista_correcoes` de `ipca_correcao_engine.py`
  em vez de reescrever do zero.
- Não criar uma nova coleção de staging — usar `conta_custo_oleo_corrigida_entity` (mesma do módulo
  IPCA).
- Não implementar as telas de listagem de staging nem de promoção — serão reutilizadas do módulo de
  Promoção já em implementação.
- Não alterar as regras de cálculo de OH (taxas/faixas/tolerâncias) — apenas aplicá-las.
- Não permitir qualquer persistência em produção sem aprovação explícita do usuário.
- Não alterar `app/services/ipca_correcao_engine.py` nem `ipca_correcao_orquestrador.py` — apenas
  consultar/reaproveitar seus padrões; o motor de OH deve ser um módulo novo e independente
  (`oh_correcao_engine.py`, `oh_correcao_orquestrador.py`).

### LLM a usar
- [ ] Ollama local (regras de negócio críticas — cálculo financeiro de OH e cascata) — recomendado
      dado o caráter de "regras de negócio proprietárias" mencionado em `.devspec/rules/
      security-rules.md`.

## 5. Critérios de Aceite

### Cenário 1: Iniciar correção a partir da tela de análise (FR-001)
```gherkin
Dado uma CCO com status ERRO exibida na tela de análise de OH
Quando o usuário clica no botão "Corrigir" dessa linha
Então o sistema navega para /correcao-oh/iniciar/<cco_id>
E exibe os valores atuais de OH e o OH esperado calculado pelo sistema
```

### Cenário 2: Cálculo do OH correto considera o acumulado anual do contrato (FR-002)
```gherkin
Dado uma CCO de Exploração cujo acumulado anual do contrato antes dela é R$ 4.500.000,00
E cujo valor de exploração é R$ 1.000.000,00
Quando o sistema calcula o OH correto para esta CCO
Então o resultado aplica a faixa de 3% sobre R$ 500.000,00 e 2% sobre R$ 500.000,00
E o OH de Exploração correto calculado é R$ 25.000,00
```

### Cenário 3: Simulação de cascata temporal recalcula toda a cadeia de correções monetárias (FR-003)
```gherkin
Dado uma CCO com 5 entradas de correções monetárias IPCA/IGPM subsequentes ao seu reconhecimento
Quando o OH dessa CCO é corrigido e a cascata temporal é simulada
Então cada uma das 5 entradas subsequentes é recalculada a partir do novo valorReconhecidoComOH
E o encadeamento valor_base -> valor_corrigido -> nova_base é preservado entre as entradas
```

### Cenário 4: Simulação de cascata horizontal identifica e recalcula CCOs irmãs (FR-004, FR-005)
```gherkin
Dado três CCOs do mesmo contrato e ano de reconhecimento, ordenadas cronologicamente
E a segunda CCO tem seu OH corrigido, alterando o acumulado anual do contrato
Quando a cascata horizontal é simulada
Então a terceira CCO (subsequente) tem seu OH de Exploração recalculado considerando o novo acumulado
E a primeira CCO (anterior) permanece inalterada
```

### Cenário 5: Nenhuma alteração é persistida sem aprovação explícita (FR-009)
```gherkin
Dado uma proposta de correção gerada e exibida na tela de prévia
Quando o usuário não confirma a aprovação
Então nenhum documento é criado ou alterado em conta_custo_oleo_corrigida_entity
```

### Cenário 6: Aprovação persiste em staging com status PENDENTE (FR-010)
```gherkin
Dado uma proposta de correção revisada na tela de prévia
Quando o usuário confirma "Aprovar e Enviar para Staging"
Então um documento é criado em conta_custo_oleo_corrigida_entity com status_promocao = "PENDENTE"
E o documento contém os valores corrigidos e referência à sessão de correção
```

### Cenário 7: Não permitir mais de uma correção de OH pendente por CCO (FR-011)
```gherkin
Dado uma CCO que já possui uma correção de OH com status_promocao = "PENDENTE" no staging
Quando o usuário tenta aprovar uma nova proposta de correção de OH para essa mesma CCO
Então o sistema rejeita a operação com erro de conflito (HTTP 400)
E nenhum novo documento é criado no staging
```

### Cenário 8: Acesso negado sem a permissão apropriada (FR-012)
```gherkin
Dado um usuário autenticado sem a permissão exigida pelo blueprint correcao_oh_bp
Quando esse usuário tenta acessar qualquer rota de /correcao-oh/
Então o sistema retorna HTTP 403
```

### Cenário 9: Descarte de proposta não grava nada (FR-013)
```gherkin
Dado uma sessão de correção com status PREVIEW
Quando o usuário clica em "Descartar Proposta"
Então a sessão é encerrada
E nenhum documento é criado em conta_custo_oleo_corrigida_entity
```

### Cenário 10: Proposta consolidada reúne raiz, cascata temporal, cascata horizontal e impacto total (FR-006)
```gherkin
Dado o motor de correção executou o cálculo do OH correto, a simulação de cascata temporal e a
  simulação de cascata horizontal para uma CCO
Quando gerar_proposta(cco_id, user_id) é chamado
Então o retorno contém a seção RAIZ (atual vs. proposto), a cadeia temporal recalculada, a lista de
  CCOs afetadas e o impacto financeiro total consolidado em um único objeto de proposta
```

### Cenário 11: Sessão de correção transita corretamente entre os estados do ciclo de vida (FR-007)
```gherkin
Dado uma nova sessão de correção iniciada para uma CCO (status ANALYZING)
Quando a proposta é gerada (status muda para PREVIEW)
E o usuário aprova a proposta (status muda para APPROVED)
E a correção é persistida em staging (status muda para STAGED)
Então cada transição de status é persistida em oh_correction_sessions
E não é possível pular etapas (ex.: aprovar uma sessão ainda em ANALYZING deve falhar)
```

### Cenário 12: Tela de prévia exibe todos os elementos exigidos pelo escopo (FR-008)
```gherkin
Dado uma proposta de correção completa gerada para uma CCO
Quando a tela de prévia (T-2.2) é carregada
Então ela exibe a tabela comparativa RAIZ com destaque visual nos campos alterados
E exibe a timeline cronológica das correções monetárias afetadas com valores antes/depois
E exibe o painel de CCOs afetadas da cascata horizontal com Δ por CCO
E exibe o resumo do impacto financeiro total
```

### Cenário 13: Toda operação de escrita é registrada em log de auditoria (FR-014)
```gherkin
Dado um usuário autenticado via JWT
Quando esse usuário gera uma proposta, aprova uma correção ou descarta uma sessão
Então cada uma dessas ações é registrada no log de auditoria com usuário, data/hora, ambiente e
  resumo da alteração
```

## 6. Task List

| ID | Descrição | FR | Azure Task ID | Est. | [P] | Status |
|----|-----------|----|---------------|------|-----|--------|
| T01 | Criar blueprint `correcao_oh_bp` com rotas E-2.1 a E-2.5 (esqueleto, sem lógica) | FR-001, FR-012 | | 3h | | ⬜ |
| T02 | Implementar `OHCorrectionEngine.calcular_oh_correto` (motor de faixas reaproveitando FEAT-001) | FR-002 | | 4h | [P] | ⬜ |
| T03 | Implementar `OHCorrectionEngine.simular_cascata_temporal` (adaptar de `_calcular_correcao_individual_gap`) | FR-003 | | 6h | | ⬜ |
| T04 | Implementar `OHCorrectionEngine.identificar_ccos_afetadas` + `simular_cascata_horizontal` | FR-004, FR-005 | | 6h | | ⬜ |
| T05 | Implementar `OHCorrectionEngine.gerar_proposta` (orquestra T02-T04) | FR-006 | | 3h | | ⬜ |
| T06 | Implementar `OHCorrectionOrchestrator` (sessões, estados, persistência em `oh_correction_sessions`) | FR-007 | | 6h | [P] | ⬜ |
| T07 | Implementar tela T-2.1 (iniciar correção) | FR-001 | | 3h | [P] | ⬜ |
| T08 | Implementar tela T-2.2 (prévia: comparativo, timeline, painel de CCOs afetadas, impacto total) | FR-008 | | 8h | | ⬜ |
| T09 | Implementar `persistir_staging` + validação de correção pendente única por CCO | FR-009, FR-010, FR-011 | | 4h | | ⬜ |
| T10 | Implementar endpoint de descarte de sessão | FR-013 | | 1h | [P] | ⬜ |
| T11 | Integrar log de auditoria (`AuditAction`) em geração de proposta, aprovação e descarte | FR-014 | | 3h | | ⬜ |
| T12 | Testes de regressão/unitários cobrindo os cenários 1-9 | FR-001 a FR-014 | | 8h | | ⬜ |

## 7. Questões Abertas

- [NEEDS CLARIFICATION]: confirmar o padrão de conexão DEV/PRD a seguir (duas conexões simultâneas
  no construtor, como no módulo IPCA, vs. parâmetro `db_env` único, como em Análise de OH). Ver
  detalhamento na seção 3.1.
- [NEEDS CLARIFICATION]: confirmar se as permissões devem ser `CORRECAO_CREATE`/`CORRECAO_PROMOTE`
  (já existentes, reaproveitadas) ou se devem ser criadas permissões específicas para OH
  (`CORRECAO_OH_CREATE` etc.). O documento de escopo original menciona `CCO_EDIT`/`CCO_ADMIN`, que
  não existem no enum atual — nomenclatura precisa ser reconciliada antes da aprovação desta spec.
- [NEEDS CLARIFICATION]: validar os requisitos não funcionais de desempenho do documento de escopo
  (simulação de cascata completa em até 60 segundos para CCOs com até 20 entradas de correção
  monetária) com a equipe de infraestrutura antes de fechar o design técnico definitivo.
- [NEEDS CLARIFICATION]: confirmar com o time responsável pelo módulo de Promoção (já em
  implementação) se a extensão da listagem/promoção para incluir correções de origem OH está
  planejada e qual é a interface esperada (ex: campo `tipo_correcao: 'IPCA'|'OH'` no documento de
  staging, para diferenciação na listagem).

## 8. Impactos e Dependências

- **Serviços afetados (novos):** `OHCorrectionEngine`, `OHCorrectionOrchestrator`, blueprint
  `correcao_oh_bp`, templates `correcao_oh/iniciar.html` e `correcao_oh/previa.html`.
- **Serviços consultados (não alterados):** `ipca_correcao_engine.py`, `ipca_correcao_orquestrador.py`
  (padrão de referência), `verificacao_oh_service.py` (motor de faixas, ver FEAT-001/FEAT-002),
  `audit_service.py`.
- **Migração de banco de dados:** [x] Sim — criação da nova coleção `oh_correction_sessions`
  (sem schema formal de migração necessário, MongoDB é schemaless; documentar índice por
  `session_id` e `cco_id`).
- **Feature flag necessária:** [ ] A decidir com o Tech Lead (recomendado dado o caráter crítico de
  alterações financeiras).
- **Breaking changes na API:** [x] Não — todos os endpoints são novos (blueprint `correcao_oh_bp`
  inexistente hoje).

## 9. Histórico de Decisões

| Data | Decisão | Motivo |
|------|---------|--------|
| 2026-09-03 | Reaproveitar a arquitetura do módulo de Correção de IPCA/IGPM (Engine + Orchestrator + padrão de sessão) | Evitar duplicação de um padrão já validado em produção para o mesmo tipo de problema (cascata de correções monetárias) |
| 2026-09-03 | Não implementar telas de Staging/Promoção nesta spec | Já estão em desenvolvimento em outro módulo (Promoção), reaproveitado por extensão |

## 10. Contexto para o Agente de IA

```
Você está implementando FEAT-003 no serviço sgpp-cco-tools (Flask).
Stack: Python 3.11 + Flask 3.0 + pymongo.
Estrutura: novo blueprint app/routes/correcao_oh_routes.py, novos services
app/services/oh_correcao_engine.py e app/services/oh_correcao_orquestrador.py.

Arquivos de REFERÊNCIA obrigatória (padrão a espelhar, NÃO alterar):
  - docs/modulo_correcao_ipca_igpm.md (documentação completa do padrão a seguir)
  - app/services/ipca_correcao_orquestrador.py (CorrectionSession, CorrectionStatus, fluxo de sessão)
  - app/services/ipca_correcao_engine.py (linha 1578: _calcular_correcao_individual_gap — cascata
    temporal; linha 271: _reconstruir_lista_correcoes; métodos aplicar_correcoes_cenario_X — padrão
    de persistência em staging)
  - app/models/permission.py (enum Permission e ROLE_PERMISSIONS)
  - app/middleware/auth_middleware.py (decorators require_permission, deny_client)

Arquivos de INTEGRAÇÃO (motor de cálculo de OH a reaproveitar, ver FEAT-001/FEAT-002):
  - app/services/verificacao_oh_service.py (faixas progressivas, cálculo de acumulado anual)

Arquivos protegidos (não alterar nesta spec):
  - app/services/ipca_correcao_engine.py, app/services/ipca_correcao_orquestrador.py
  - app/routes/ipca_promocao_routes.py, app/services/ipca_promocao_service.py

Padrões: ver .devspec/rules/coding-standards.md e AGENTS.md.
Antes de implementar, resolver os itens [NEEDS CLARIFICATION] da seção 7 com o Tech Lead.
```

## 11. Log de Implementação IA

<!-- Preenchido pelo dev durante e após a implementação -->

| Data | Skill / Modelo | Comando / Prompt resumido | Ajustes manuais |
|------|---------------|--------------------------|-----------------|
| | | | |
