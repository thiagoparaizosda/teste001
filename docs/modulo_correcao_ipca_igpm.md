# Módulo de Correção IPCA/IGPM

## Visão Geral

O módulo de Correção IPCA/IGPM é responsável por identificar e corrigir gaps de correção monetária em Contas de Custo de Óleo (CCOs). Ele analisa CCOs individualmente, detecta problemas (gaps, duplicatas, correções fora do prazo), gera propostas de correção e as aplica de forma controlada.

**URL de acesso:** `/sgpp-cco-tools/ipca-correcao/`

---

## Arquitetura

### Rotas (Blueprint: `ipca_correcao`)

Arquivo: [app/routes/ipca_correcao_routes.py](../app/routes/ipca_correcao_routes.py)  
Prefixo URL: `/ipca-correcao`

| Método | Rota | Função | Descrição |
|--------|------|---------|-----------|
| GET | `/` | `index` | Tela principal de análise (wizard 4 steps) |
| GET | `/pesquisar-ccos` | `pesquisar_ccos` | Tela de pesquisa de CCOs para análise |
| POST | `/api/pesquisar-ccos` | `api_pesquisar_ccos` | API de busca de CCOs por filtros |
| POST | `/api/iniciar-analise` | `iniciar_analise` | Inicia análise de uma CCO (Step 1) |
| POST | `/api/gerar-propostas` | `gerar_propostas` | Gera propostas de correção (Step 2) |
| POST | `/api/aprovar-correcoes` | `aprovar_correcoes` | Aprova correções selecionadas (Step 3) |
| POST | `/api/aplicar-correcoes` | `aplicar_correcoes` | Aplica correções aprovadas (Step 4) |
| GET | `/api/status-sessao/<id>` | `status_sessao` | Consulta status de uma sessão |
| POST | `/api/avaliar-ipca-vigente` | `avaliar_ipca_vigente` | Avalia IPCA do ano vigente para uma CCO |

**Permissões:** `CORRECAO_CREATE` para análise/aplicação; `CORRECAO_PROMOTE` para aprovar.

---

## Templates

| Template | Descrição |
|----------|-----------|
| [app/templates/recalculo/ipca_analise_e_recalculo.html](../app/templates/recalculo/ipca_analise_e_recalculo.html) | Tela principal de análise (wizard 4 steps + modo IPCA Vigente) |
| [app/templates/ipca_correcao/pesquisar_ccos.html](../app/templates/ipca_correcao/pesquisar_ccos.html) | Tela de pesquisa de CCOs (busca por filtros) |

---

## Serviços

### IPCACorrectionOrchestrator
Arquivo: [app/services/ipca_correcao_orquestrador.py](../app/services/ipca_correcao_orquestrador.py)

Coordenador principal do fluxo de correção. Gerencia sessões de correção armazenadas no MongoDB (`ipca_correction_sessions`).

**Métodos principais:**
- `iniciar_analise_cco(cco_id, user_id)` → Cria sessão, executa análise de gaps, retorna `session_id`, cenário detectado e contagens
- `gerar_propostas_correcao(session_id)` → Gera propostas baseadas no cenário; retorna lista de `CorrectionProposal` com impacto financeiro
- `aprovar_correcoes(session_id, corrections_approved)` → Marca correções como aprovadas e retorna preview final
- `aplicar_correcoes(session_id)` → Aplica as correções aprovadas no banco de dados (área temporária)
- `avaliar_ipca_ano_vigente(cco_id, user_id)` → Avalia e propõe correção IPCA para ano vigente

**Cenários detectados:**
| Cenário | Condições de Detecção | Propostas Geradas |
|---------|-----------------------|-------------------|
| `CENARIO_0` | Tem gap + sem correção posterior + sem recuperação | `IPCA_ADDITION` por gap |
| `CENARIO_1` | Tem gap + tem correção posterior (fora prazo ou na CCO) + sem recuperação | `IPCA_ADDITION` por gap + `IPCA_UPDATE` para correções que usaram valor base incorreto |
| `CENARIO_2` | Tem gap ou correção fora prazo + tem `RECUPERACAO` na CCO | `IPCA_ADDITION` + `COMPENSATION` (cascata sobre recuperação) + `REACTIVATION` se `flgRecuperado=true` |
| `CENARIO_DUPLICATAS` | Tem correções IPCA/IGPM duplicadas no mesmo mês/ano | `DUPLICATA_REMOVAL` por duplicata + `DUPLICATA_ADJUSTMENT` compensatório |
| `CENARIO_IPCA_VIGENTE` | Fluxo direto via botão "Avaliar IPCA Vigente" — sem gaps, apenas ano corrente | `IPCA_ADDITION` para aniversário do ano vigente |
| `CENARIO_CORRECAO_FORA_APENAS` | Só correções fora do prazo, sem gaps e sem recuperação | **Sem gerador de propostas** (pendência) |
| `CENARIO_COMPLEXO` | Todos os outros casos / CCO não encontrada | Sem propostas — análise manual necessária |

### IPCAGapAnalyzer
Arquivo: [app/services/ipca_gap_analyzer.py](../app/services/ipca_gap_analyzer.py)

Responsável por identificar gaps de correção monetária nas CCOs. Para cada CCO:
1. Extrai `dataReconhecimento` e calcula o primeiro aniversário (mês seguinte ao reconhecimento, no ano + 1)
2. Para cada aniversário até o mês corrente: verifica se existe correção IPCA/IGPM correspondente em `correcoesMonetarias`
3. Se não existe, reporta gap com `valor_base` = última correção anterior ao aniversário (ou `valorReconhecidoComOH` raiz se não houver)
4. Se `valor_base <= 0`, o gap é **ignorado** (não há base financeira para corrigir)
5. Se existe mas foi aplicada após o prazo (dia 19 do mês do aniversário), reporta como `correcao_fora_do_periodo`
6. Identifica duplicatas (duas correções IPCA/IGPM no mesmo mês/ano)

**Taxa aplicada:** índice do mês anterior ao aniversário (`OFFSET_MES_TAXA_APLICACAO = -1`), consultado nas coleções `ipca_entity` ou `igpm_entity`.

### IPCACorrectionEngine
Arquivo: [app/services/ipca_correcao_engine.py](../app/services/ipca_correcao_engine.py)

Motor de cálculo das correções IPCA/IGPM. Recebe os gaps e correções fora do prazo identificados pelo analyzer e calcula os valores propostos. Reconstrói a lista `correcoesMonetarias` em ordem cronológica antes de salvar.

**Regra de encadeamento de gaps:** quando há múltiplos gaps, cada gap usa como `valor_base` o `valor_corrigido` do gap anterior (`correcao_anterior['valor_corrigido']`), garantindo efeito cascata correto.

---

## Modelo de Dados

### CorrectionSession (MongoDB: `ipca_correction_sessions`)

```json
{
  "session_id": "uuid",
  "cco_id": "string",
  "user_id": "string",
  "status": "ANALYZING | PREVIEW | APPROVED | APPLIED | REJECTED | ERROR",
  "gaps_identified": [...],
  "corrections_fora_periodo": [...],
  "ccos_com_duplicatas": {...},
  "corrections_proposed": [...],
  "corrections_approved": ["correction_id", ...],
  "financial_impact": {"total_impact": 0.0, ...},
  "scenario_detected": "CENARIO_X",
  "created_at": "ISO8601",
  "updated_at": "ISO8601",
  "applied_at": "ISO8601 | null"
}
```

### CorrectionProposal

```json
{
  "correction_id": "uuid",
  "type": "IPCA_ADDITION | IPCA_UPDATE | COMPENSATION | REACTIVATION | DUPLICATA_REMOVAL | DUPLICATA_ADJUSTMENT",
  "scenario": "string",
  "target_date": "ISO8601",
  "target_period": "MM/YYYY",
  "current_value": 0.0,
  "proposed_value": 0.0,
  "impact": 0.0,
  "taxa_aplicada": "float",
  "taxa_referencia": "MM/YYYY",
  "description": "string",
  "dependencies": [...],
  "business_rules_applied": [...]
}
```

---

## Fluxo de Uso

```
[Pesquisar CCOs] → seleciona CCO → [Tela de Análise]
                                          ↓
                               Step 1: Informar ID da CCO → "Analisar CCO"
                               Step 2: Resultados da Análise → "Gerar Propostas"
                               Step 3: Propostas (checkbox) → "Aprovar Selecionadas"
                               Step 4: Preview Aprovação → "Aplicar Correções"
                                          ↓
                               [Promoção de Correções] (módulo ipca_promocao)
```

**Modo IPCA Ano Vigente:** Fluxo paralelo simplificado para aplicar correção do ano corrente.

---

## Autenticação e Usuário

- Todas as rotas usam `@require_permission` do [app/middleware/auth_middleware.py](../app/middleware/auth_middleware.py)
- O `user_id` é resolvido pelo helper `get_current_user_id()` no middleware
- Quando `DISABLE_AUTH=True` (.env), o usuário padrão é `"default_user_portal"`
- Quando autenticado, o usuário vem de `session['user_data']['id']` (ou `email` como fallback)

---

## Integração com Outros Módulos

| Módulo | Integração |
|--------|-----------|
| **Portal CCO** (`portal_ui`) | API `/api/contratos-disponiveis` e `/api/campos-remessa/<contrato>` usadas na pesquisa |
| **Recálculo** (`recalculo_ui`) | Padrão de pesquisa de CCOs reutilizado |
| **Promoção IPCA** (`ipca_promocao`) | Destino após aplicação das correções |
| **Timeline CCO** (`portal_ui`) | Link para timeline exibido nos resultados |

---

## Cenários Detalhados

### CENARIO_0 — Gap Simples

**Quando ocorre:** CCO nunca recebeu correção IPCA/IGPM no(s) aniversário(s). Sem recuperações e sem correções posteriores.

**Fluxo de cálculo:**
1. Para cada gap: `valor_base` = última entrada de `correcoesMonetarias` antes do aniversário (ou raiz da CCO)
2. `valor_corrigido = valor_base * taxa_IPCA(mês_anterior_ao_aniversário)`
3. `impacto = valor_corrigido - valor_base`
4. Múltiplos gaps: o `valor_base` do gap N é o `valor_corrigido` do gap N-1 (efeito cascata)

**Condição de skip:** se `valor_base == 0`, o gap é sempre ignorado (sem base financeira para corrigir). Se `valor_base < 0`, o gap é ignorado apenas quando `IGNORAR_CORECAO_MONETARIA_VALOR_NEGATIVO = True` em `config.py`.

---

### CENARIO_1 — Gap com Correção Posterior

**Quando ocorre:** CCO tem gap (falta IPCA no aniversário), mas possui correção IPCA/IGPM posterior que foi aplicada sobre um valor base incorreto (sem considerar o gap anterior).

**Exemplos:**
- Gap em 09/2022, mas IPCA foi aplicado em 03/2023 (fora do prazo de 11 meses)
- Gap em 09/2022, IPCA aplicado em 09/2023 usando valor que deveria ser maior

**Propostas geradas:**
- `IPCA_ADDITION` para o gap faltante
- `IPCA_UPDATE` para recalcular a correção posterior com o valor base correto (`valor_base_correto = valor_base_incorreto + soma_impactos_gaps_anteriores`)

---

### CENARIO_2 — Gap com Recuperação

**Quando ocorre:** CCO tem gap de IPCA/IGPM E também possui entrada `RECUPERACAO` em `correcoesMonetarias`.

**Situações típicas:**
- CCO tinha saldo, perdeu o IPCA de um aniversário, depois foi recuperada parcial/totalmente
- `flgRecuperado = true` e `valorReconhecidoComOH = 0` na última entrada

**Propostas geradas:**
1. `IPCA_ADDITION` por gap (valor que deveria ter sido aplicado antes da recuperação)
2. `COMPENSATION` — compensação cascata: valor dos gaps × taxas das correções posteriores à recuperação
3. `REACTIVATION` — se `flgRecuperado = true` e o saldo final após correções é positivo

---

### CENARIO_DUPLICATAS — Duplicatas de Correção

**Quando ocorre:** Existem duas ou mais correções IPCA/IGPM com datas no mesmo mês/ano em `correcoesMonetarias`.

**Propostas geradas:**
1. `DUPLICATA_REMOVAL` por duplicata identificada (a mais recente é marcada para remoção)
2. `DUPLICATA_ADJUSTMENT` — RETIFICACAO compensatória somando o efeito cascata das correções posteriores
3. `REACTIVATION` se `flgRecuperado = true` após remoção o saldo ficar diferente de zero

---

### CENARIO_IPCA_VIGENTE — Aplicação do Ano Corrente

**Quando ocorre:** Fluxo alternativo acionado pelo botão "Avaliar IPCA Vigente" na tela. Avalia se a CCO (já corrigida na coleção local) precisa receber o IPCA do aniversário do ano vigente.

**Condições para aplicação:**
- CCO encontrada em `conta_custo_oleo_corrigida_entity`
- `valor_atual > 0`
- Aniversário do ano vigente já passou (dia 16 do mês seguinte ao reconhecimento)
- Ainda não existe correção IPCA/IGPM para aquele mês/ano

**Detalhe especial:** se a última correção da CCO for do tipo `RETIFICACAO`, uma proposta adicional `CORRECTION_DATE_CHANGE` é gerada para ajustar a data da retificação (garante ordenação cronológica correta na lista).

---

### CENARIO_CORRECAO_FORA_APENAS — Apenas Fora do Prazo

**Quando ocorre:** Existem correções IPCA/IGPM aplicadas após o prazo (dia 19 do mês do aniversário), mas sem gaps não cobertos e sem recuperações.

**Status atual:** Cenário detectado pelo `_determinar_cenario`, mas **sem gerador de propostas implementado** — retorna lista vazia. Análise e correção manual necessárias.

---

## Bugs Corrigidos (feature/ipca-melhorias)

### BUG-1: `valorReconhecidoComOH <= 0` não impedia identificação de gap

**Sintoma:** Mesmo quando a última correção monetária de uma CCO tinha `valorReconhecidoComOH <= 0`, o sistema continuava identificando gaps de IPCA/IGPM e gerando propostas de correção sobre um valor base zero ou negativo.

**Causa raiz:** O guard original era `if valor_base <= 0 and IGNORAR_CORECAO_MONETARIA_VALOR_NEGATIVO:`, mas a flag estava `False`, tornando a condição nunca verdadeira — inclusive para `valor_base == 0`.

**Correção aplicada:** Guard ajustado para `if valor_base == 0 or (valor_base < 0 and IGNORAR_CORECAO_MONETARIA_VALOR_NEGATIVO):` em ambos os arquivos.

**Regra resultante:**
- `valor_base == 0` → gap sempre ignorado (incondicional — não há base financeira)
- `valor_base < 0` → gap ignorado apenas quando `IGNORAR_CORECAO_MONETARIA_VALOR_NEGATIVO = True` em `config.py` (padrão: `False`, ou seja, valores negativos continuam gerando gaps)

**Arquivos alterados:** `app/config.py:15`, `app/services/ipca_gap_analyzer.py:278`, `app/services/ipca_correcao_engine.py:1339`

---

### BUG-2: `aplicar_correcoes_cenario_ipca_vigente` com assinatura incorreta

**Sintoma:** Ao tentar aplicar correções do cenário IPCA Vigente (Step 4), ocorria `TypeError` por excesso de argumentos.

**Causa raiz:** O orquestrador chamava `aplicar_correcoes_cenario_ipca_vigente(session_id, cco_id, correcoes)` com 3 argumentos, mas o método no engine aceitava apenas `(cco_id, correcoes)`.

**Correção aplicada:** Adicionado `session_id: str` como primeiro parâmetro em `aplicar_correcoes_cenario_ipca_vigente`.

**Arquivo alterado:** `app/services/ipca_correcao_engine.py:1066`

---

## Pendências e Melhorias (feature/ipca-melhorias)

### Implementadas nesta branch:

- [x] **Tela de pesquisa de CCOs** (`/ipca-correcao/pesquisar-ccos`): permite localizar CCOs por filtros (contrato, campo, remessa, fase, origemDosGastos) e iniciar análise diretamente do resultado
- [x] **Identificação da CCO no header da análise**: id, contratoCPP, remessa, faseRemessa e origemDosGastos exibidos em banner fixo visível em todos os steps
- [x] **Usuário da sessão**: campo de usuário removido do formulário; `user_id` resolvido server-side via `session['user_data']` (ou `"default_user_portal"` quando `DISABLE_AUTH=True`)
- [x] **Fix: gap ignorado quando `valor_base <= 0`** — guard agora incondicional (BUG-1)
- [x] **Fix: assinatura de `aplicar_correcoes_cenario_ipca_vigente`** — parâmetro `session_id` adicionado (BUG-2)

### Pendências futuras - fora do escopo desta melhoria:

- [ ] Implementar gerador de propostas para `CENARIO_CORRECAO_FORA_APENAS`
- [ ] Suporte a análise em lote (múltiplas CCOs)
- [ ] Exportação do relatório de correções aplicadas
- [ ] Histórico de sessões por usuário
- [ ] Notificação de conclusão para usuários

---

## Configuração

Variáveis de ambiente relevantes (`.env`):

| Variável | Descrição |
|----------|-----------|
| `MONGO_URI` | URI MongoDB (banco local/dev) |
| `MONGO_URI_PRD` | URI MongoDB produção (CCOs e sessões) |
| `DISABLE_AUTH` | `True` desabilita autenticação (usa usuário padrão) |
| `SECRET_KEY` | Chave para validação de tokens JWT |
