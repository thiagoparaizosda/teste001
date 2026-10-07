# QA — Edição Manual de CCO: Regras de Validação, Ações e Botões

**Telas cobertas:** `/cco-editor/editar/<cco_id>` (Edição) e `/cco-editor/revisar/<cco_id>` (Revisão)
**Arquivos-fonte:** `app/templates/cco_editor/editar.html`, `app/templates/cco_editor/revisar.html`,
`app/services/cco_editor_service.py`, `app/routes/cco_editor_routes.py`
**Audiência:** QA
**Objetivo:** documentar, de forma testável, todas as regras de validação, cálculos, botões e fluxos
implementados nessas duas telas, para apoiar a criação de casos de teste.

---

## Sumário

1. [Conceitos-chave](#1-conceitos-chave)
2. [Fluxo de dados e persistência do rascunho](#2-fluxo-de-dados-e-persistência-do-rascunho)
3. [Tela de Edição — estrutura geral](#3-tela-de-edição--estrutura-geral)
4. [Motor de validação — como e quando roda](#4-motor-de-validação--como-e-quando-roda)
5. [Regras de validação — tabela completa](#5-regras-de-validação--tabela-completa)
6. [Pintura de campos e popover de ajuda](#6-pintura-de-campos-e-popover-de-ajuda)
7. [Aba "Validação" e modal de Ajuda](#7-aba-validação-e-modal-de-ajuda)
8. [Aba "Nova Correção"](#8-aba-nova-correção)
9. [Painel de Ações (Salvar / Resetar / Descartar Rascunho / Cancelar)](#9-painel-de-ações-salvar--resetar--descartar-rascunho--cancelar)
10. [Tela de Revisão](#10-tela-de-revisão)
11. [Endpoints envolvidos](#11-endpoints-envolvidos)
12. [Roteiro de casos de teste sugeridos](#12-roteiro-de-casos-de-teste-sugeridos)
13. [Bugs corrigidos recentemente (regressão)](#13-bugs-corrigidos-recentemente-regressão)

---

## 1. Conceitos-chave

- **Raiz:** os campos do documento principal da CCO (`conta_custo_oleo_entity`), fora do array
  `correcoesMonetarias`.
- **Correção monetária:** cada item do array `correcoesMonetarias`. Tipos possíveis na tela: `IPCA`,
  `IGPM`, `RECUPERACAO`, `RETIFICACAO` (mais `INVALIDACAO_RECONHECIMENTO_PARCIAL`, que só existe em dados
  legados e não é criável pela tela).
- **Rascunho pendente:** ao clicar em "Salvar", a tela **não** grava em produção. Ela grava uma cópia
  inteira da CCO editada na coleção `conta_custo_oleo_corrigida_entity`, com `status_promocao: 'PENDENTE'`.
  Só a tela de **Promoção** (fora do escopo deste documento) aplica isso em produção.
- **Encadeamento de correções:** a validação trata as correções em ordem cronológica de `dataCorrecao`
  (a mesma ordem exibida na aba "Correções"). Cada correção `[n]` usa como base o resultado da correção
  `[n-1]` (ou da raiz, se for a primeira).

---

## 2. Fluxo de dados e persistência do rascunho

Este fluxo é o mesmo para qualquer edição feita pela tela (raiz, correções existentes ou Nova Correção).

### 2.1 Coleções e bancos envolvidos

| Nome usado no código | Coleção Mongo | Banco | Papel |
|---|---|---|---|
| `db` (`MONGO_URI`) | `conta_custo_oleo_corrigida_entity` | Banco local/temporário do CCO Tools | Guarda o **rascunho** da CCO editada, com o documento completo (raiz + `correcoesMonetarias`) mais metadados de edição. |
| `db` (`MONGO_URI`) | `cco_edit_sessions` | Banco local/temporário do CCO Tools | Guarda o **histórico da sessão de edição** (quem editou, o que mudou campo a campo, observações) — é o que a tela de Revisão lê para montar a seção "Histórico de Alterações". |
| `db_prd` (`MONGO_URI_PRD`) | `conta_custo_oleo_entity` | Banco de produção | O documento **oficial** da CCO. Só é alterado no momento da promoção. |
| `db_prd` (`MONGO_URI_PRD`) | `event` | Banco de produção | Event store: recebe um novo evento (`ContaCustoOleoEntityUpdatedEvent`) a cada promoção, para manter o histórico de eventos consistente com o restante do sistema. |

O `_id` do documento em `conta_custo_oleo_corrigida_entity` é o **mesmo `_id`** da CCO em produção — não é
um id novo. Por isso é possível checar se existe rascunho pendente simplesmente buscando por
`{'_id': cco_id}` na coleção de rascunho.

### 2.2 Passo a passo do fluxo

```
1) GET /cco-editor/editar/<cco_id>
   └─ buscar_cco_para_edicao(cco_id)
      ├─ Existe conta_custo_oleo_corrigida_entity._id == cco_id ?
      │    SIM → carrega esse documento (rascunho pendente) como base da tela
      │    NÃO → carrega conta_custo_oleo_entity._id == cco_id (produção) como base da tela
      └─ tem_rascunho_pendente (true/false) é enviado ao template
         → controla o banner amarelo, o botão "Descartar Rascunho" e o texto do modal de "Resetar"

2) Usuário edita campos em tela e clica em "Salvar"
   └─ POST /cco-editor/api/salvar  →  aplicar_edicao(cco_id, alteracoes, user_id, observacoes)
      ├─ SEMPRE parte do documento de PRODUÇÃO (conta_custo_oleo_entity), não do rascunho anterior
      │  — ou seja, a cada "Salvar" o rascunho é reconstruído do zero a partir da produção + alterações atuais
      ├─ aplica alteracoes_raiz, alteracoes_correcoes e nova_correcao (se houver) sobre uma cópia em memória
      ├─ remove um rascunho anterior, se existir (delete_one em conta_custo_oleo_corrigida_entity)
      └─ insere o novo rascunho em conta_custo_oleo_corrigida_entity com:
           status_promocao = 'PENDENTE'
           session_id = novo uuid
           tipo_edicao = 'MANUAL'
           usuario_edicao, observacao, registro_alteracoes, data_criacao_correcao
         e grava a sessão de edição em cco_edit_sessions (session_id, cco_id, alterações campo a campo)

3) Redireciona para GET /cco-editor/revisar/<cco_id>
   └─ Lê o rascunho pendente em conta_custo_oleo_corrigida_entity (status ainda PENDENTE)
   └─ Lê o original em conta_custo_oleo_entity (produção, ainda sem a alteração)
   └─ Compara os dois (CCOComparatorService) para montar os cards e a tabela "Campos Alterados"
   └─ Lê cco_edit_sessions (status PENDENTE) para montar "Histórico de Alterações"
   *** Nesse momento (status temporário/pendente), produção NÃO mudou. Qualquer outra tela do sistema
       que leia conta_custo_oleo_entity direto continua vendo os dados antigos. ***

4a) Se o usuário clicar "Editar Novamente" (Revisão) ou "Resetar" (Edição)
    └─ Volta para o passo 1 — como o rascunho ainda existe em conta_custo_oleo_corrigida_entity,
       ele é carregado de novo (nada se perde).

4b) Se o usuário clicar "Descartar Rascunho" (Edição) ou "Descartar Edição" (Revisão)
    └─ POST /cco-editor/api/descartar-rascunho/<cco_id>  (ou DELETE /cco-editor/api/descartar/<cco_id>)
       delete_one em conta_custo_oleo_corrigida_entity — o rascunho deixa de existir.
       Produção nunca foi tocada, nada a desfazer lá.

4c) Se o usuário clicar "Ir para Promoção" (Revisão) e confirmar a promoção
    (tela /promocao-cco/detalhar/<cco_id>, fora do escopo deste documento)
    └─ promover_correcao(cco_id, ...)
       ├─ valida se pode promover
       ├─ aplica os dados do rascunho (menos os metadados de edição/promoção) em
       │  conta_custo_oleo_entity via update_one, incrementando "version"
       ├─ cria um novo documento em event (ContaCustoOleoEntityUpdatedEvent)
       ├─ NÃO apaga o rascunho: atualiza conta_custo_oleo_corrigida_entity com
       │  status_promocao = 'PROMOVIDA', data_promocao, usuario_promocao, versao_promovida
       │  (fica como registro histórico da promoção, não como rascunho ativo)
       └─ apaga o registro correspondente em cco_edit_sessions
```

### 2.3 Onde cada "visão" dos dados aparece

| Momento | O que está em `conta_custo_oleo_entity` (produção) | O que está em `conta_custo_oleo_corrigida_entity` (rascunho) | O que a tela de Edição/Revisão mostra |
|---|---|---|---|
| Antes de qualquer edição | Dado original | Não existe | Tela de Edição mostra o dado original |
| Após "Salvar" (status **PENDENTE**) | Dado original, **inalterado** | Documento completo com as alterações, `status_promocao: PENDENTE` | Tela de Revisão compara produção (coluna "Original") com o rascunho (coluna "Novo"); reabrir a Edição carrega o rascunho |
| Após "Promover" (status **PROMOVIDA**) | Dado **atualizado** com as alterações, `version` incrementada | Continua existindo, agora com `status_promocao: PROMOVIDA` (fica como histórico, não é mais tratado como rascunho ativo) | Reabrir `/cco-editor/editar/<cco_id>` volta a carregar de **produção** (já não há mais rascunho `PENDENTE`, então `buscar_cco_para_edicao` cai no branch de produção — que agora já reflete a alteração promovida) |

**Ponto de atenção para QA:** entre o "Salvar" e a "Promoção", existem **dois documentos divergentes**
para a mesma CCO (produção intacta vs. rascunho pendente). Qualquer tela do sistema fora do fluxo de edição
(ex.: Timeline, relatórios) continua lendo só `conta_custo_oleo_entity` — então não deve refletir a edição
enquanto ela estiver pendente. Isso é o comportamento esperado, não bug.

---

## 3. Tela de Edição — estrutura geral

| Aba | Conteúdo |
|---|---|
| **Campos Raiz** | Todos os campos editáveis da raiz da CCO (campos bloqueados, como `contratoCpp`, `campo`, `remessa`, `faseRemessa`, aparecem com cadeado e não editáveis). |
| **Correções** | Um card por correção monetária existente, ordenados por `dataCorrecao`. Cada card pode ser expandido/recolhido. Campos `tipo`, `subTipo`, `idContaCustoOleoCorrigida` são somente-leitura; `contrato`, `campo`, `faseRemessa` da correção (quando existem no documento) também aparecem como somente-leitura — servem só para comparação com a raiz (ver seção 4). |
| **Nova Correção** | Formulário para incluir **uma** nova correção monetária (`RETIFICACAO` ou `RECUPERACAO`) junto com o salvamento. Ver seção 7. |
| **Validação** | Lista todas as inconsistências encontradas na última validação, com valor atual x esperado x regra. Tem botão "Ajuda" com o modal de regras. |

A tela **nunca sobrescreve automaticamente um valor vindo do banco**. Ela só lê o valor atual de cada campo,
compara com o valor esperado pela regra e **pinta** o campo — nunca substitui o conteúdo do campo sozinha
(exceto os campos que o próprio usuário edita, e os campos de exibição auxiliar tipo "Acumulado (%)" que não
são persistidos).

---

## 4. Motor de validação — como e quando roda

Função central: `validarTudo()`. Ela:
1. Zera a lista de inconsistências.
2. Roda `validarRaiz()` — aplica as 6 regras da raiz.
3. Roda `validarCorrecoes()` — percorre as correções existentes em ordem cronológica, aplicando as regras
   de "igual à raiz", o encadeamento e as regras específicas por tipo.
4. Roda `validarNovaCorrecao()` — se a aba "Nova Correção" estiver marcada (`Incluir nova correção
   monetária`), aplica as mesmas categorias de regra ao formulário de nova correção.
5. Re-renderiza a lista da aba "Validação" e o badge de contagem na aba.
6. Atualiza o card "Resumo" (contagem de alterações e de inconsistências).

**Quando `validarTudo()` roda:**
- Ao carregar a página (estado inicial, sem marcar nada como "alterado").
- A cada `onchange` de qualquer campo editável (raiz ou correção existente).
- A cada alteração de campo na aba "Nova Correção" (inclusive ao marcar/desmarcar o checkbox "Incluir nova
  correção monetária" e ao trocar o Tipo).

**Teste esperado:** qualquer edição de campo deve atualizar a pintura e a aba "Validação" **imediatamente**,
sem precisar trocar de aba ou recarregar.

---

## 5. Regras de validação — tabela completa

Tolerância numérica: diferenças até **R$ 0,01** são consideradas iguais (arredondamento). Campos de texto
(`contrato`, `campo`, `faseRemessa`) são comparados como string exata.

### 5.1 Raiz

| Campo | Regra |
|---|---|
| `valorLancamentoTotal` | = `valorReconhecido + valorNaoReconhecido` |
| `valorReconhecivel` | = `valorLancamentoTotal` |
| `valorReconhecido` | = `valorReconhecidoExploracao + valorReconhecidoProducao` |
| `overHeadProducao` | = `valorReconhecidoProducao × 0,01` |
| `overHeadTotal` | = `overHeadExploracao + overHeadProducao` |
| `valorReconhecidoComOH` | = `valorReconhecido + overHeadTotal` |

### 5.2 Correções — campos que devem repetir o valor da raiz

Aplicado a **toda correção existente** e também à "Nova Correção" (quando os campos existirem em tela),
comparando sempre com o valor **atual** da raiz (não com o valor no momento em que a correção foi criada):

- `contrato` (raiz: `contratoCpp`), `campo`, `faseRemessa` — comparação textual
- `quantidadeLancamento`, `valorReconhecido`, `valorReconhecidoProducao`, `valorReconhecidoExploracao`,
  `overHeadProducao`, `overHeadExploracao`, `overHeadTotal` — comparação numérica

> Se a raiz não tiver input em tela para `contrato`/`campo`/`faseRemessa` (são bloqueados), a comparação usa
> o valor original do documento carregado (`contratoCpp`, `campo`, `faseRemessa` da raiz).

### 5.3 Correções — encadeamento (todos os tipos)

| Campo | Regra |
|---|---|
| `valorReconhecidoComOhOriginal` | = `valorReconhecidoComOH` da correção anterior (ou da raiz, se for a primeira correção) |

### 5.4 Correções do tipo IPCA / IGPM

| Campo | Regra |
|---|---|
| `valorReconhecidoComOH` | = `valorReconhecidoComOhOriginal × taxaCorrecao` |
| `diferencaValor` | = `valorReconhecidoComOH - valorReconhecidoComOhOriginal` |
| `valorLancamentoTotal` | = `valorLancamentoTotal` da correção anterior (ou raiz) `× taxaCorrecao` |
| `valorReconhecivel` | = `valorLancamentoTotal` (da própria correção) |
| `igpmAcumulado` | = soma das `taxaCorrecao` de **todas** as correções IPCA/IGPM até esta (inclusive) |
| `igpmAcumuladoReais` | = soma das `diferencaValor` de **todas** as correções IPCA/IGPM até esta (inclusive) |

Os campos auxiliares somente-leitura "Acumulado (%)" e "Acumulado (R$)" exibidos no card (`calc_<n>_igpmAcumulado`,
`calc_<n>_igpmAcumuladoReais`) mostram o mesmo acumulado calculado — servem de conferência visual rápida, não
são persistidos.

### 5.5 Correções do tipo RECUPERAÇÃO

| Campo | Regra |
|---|---|
| `valorReconhecidoComOH` | = `valorReconhecidoComOhOriginal - valorRecuperado` |
| `diferencaValor` | = `valorRecuperado` (equivalente a `valorReconhecidoComOhOriginal - valorReconhecidoComOH`) |
| `valorLancamentoTotal` | = `valorLancamentoTotal` **da raiz** (não encadeia com a correção anterior — desfaz a indexação nominal bruta) |
| `valorRecuperadoTotal` **(novo)** | = soma das `valorRecuperado` de **todas** as correções RECUPERACAO até esta (inclusive) |

O campo auxiliar somente-leitura "Recuperado Total" (`calc_<n>_valorRecuperadoTotal`) mostra o mesmo
acumulado — conferência visual, não persistido.

> ⚠️ **Atenção QA:** a regra de `valorRecuperadoTotal` só se aplica quando o campo `valorRecuperadoTotal`
> existir de fato naquela correção (nem toda correção RECUPERACAO antiga tem esse campo gravado). Se o campo
> não existir em tela, ele simplesmente não é validado (nenhuma pintura aparece nele).

---

## 6. Pintura de campos e popover de ajuda

Para todo campo coberto por alguma regra das seções 4.1–4.5:

- **Azul** (`.campo-consistente`, ícone ✅): o valor atual bate com o valor esperado.
- **Vermelho** (`.campo-inconsistente`, ícone ⚠️): o valor diverge.
- Campo sem nenhuma regra aplicável: sem pintura, sem ícone.

**Passar o mouse** sobre o campo (ou sobre o ícone ao lado do rótulo) abre um **popover** (balão) mostrando:
- Nome da regra
- Fórmula usada
- Valor atual do campo
- Valor esperado pela regra

Campos do tipo "quantidade" (`quantidadeLancamento`) mostram os valores do popover como **número inteiro**
(sem `R$`), enquanto campos monetários mostram em `R$` formatado em pt-BR. Campos de texto
(`contrato`/`campo`/`faseRemessa`) mostram o texto puro.

**Teste esperado:** o popover deve sempre refletir o estado **atual** da tela — se o usuário edita um campo
relacionado (ex.: `overHeadExploracao`) e isso muda o valor esperado de outro campo (ex.: `overHeadTotal`),
o popover do segundo campo, ao ser reaberto, deve mostrar o novo valor esperado.

---

## 7. Aba "Validação" e modal de Ajuda

- Lista todas as inconsistências atuais no formato: `Local → Campo` / `Atual: X | Esperado: Y` / `Regra: ...`.
- O badge numérico na aba "Validação" (e o ícone vermelho no botão da aba) só aparece quando há pelo menos
  1 inconsistência.
- Botão **"Ajuda"** (dentro da aba Validação) abre um modal com todas as regras das seções 4.1–4.5,
  organizadas por Raiz → campos iguais à raiz → encadeamento → IPCA/IGPM → RECUPERAÇÃO, mais uma explicação
  de como a validação funciona (nunca sobrescreve, pinta azul/vermelho, popover no hover) e uma nota sobre
  máscaras de valores aceitas (formato BR `1.234,56` e US `1234.56`, com auto-conversão ao colar `R$ ...`).

**Teste esperado:** o conteúdo do modal de Ajuda deve bater exatamente com as regras da seção 4 deste
documento — qualquer divergência é bug de documentação.

---

## 8. Aba "Nova Correção"

- Checkbox **"Incluir nova correção monetária"**: enquanto desmarcado, os campos ficam ocultos e **nenhuma**
  validação é aplicada a eles (qualquer pintura anterior é limpa).
- Ao marcar o checkbox, os campos são pré-preenchidos a partir da **última correção existente** (ou da raiz,
  se não houver nenhuma), incluindo agora corretamente `valorReconhecidoComOhOriginal` (bug corrigido nesta
  rodada — antes ficava sempre zerado).
- Campo **Tipo**: `RETIFICACAO` ou `RECUPERACAO`. Ao trocar, os campos específicos de recuperação
  (`Valor Recuperado`, `Valor Recuperado Total`) aparecem/somem.
- **Cálculo automático ao digitar** (isso é intencional e diferente do resto da tela, pois é um registro
  ainda não existente, não um valor já persistido):
  - `Valor Reconhecido` = Exploração + Produção
  - `OH Total` = OH Exploração + OH Produção
  - `Valor Rec. c/ OH` = Valor Reconhecido + OH Total (ou, se RECUPERACAO, `valorReconhecidoComOhOriginal - valorRecuperado`)
  - `Diferença Valor` = diferença entre o original e o `Valor Rec. c/ OH`
- **Validação aplicada em paralelo ao cálculo automático:** os mesmos grupos de regra da seção 4 (campos
  iguais à raiz, encadeamento, regras por tipo, incluindo a nova regra de `valorRecuperadoTotal`) são
  aplicados aos campos `nc_*`, com pintura azul/vermelho e popover, exatamente como nas correções existentes.
  - A base do encadeamento (`valorReconhecidoComOhOriginal` esperado) é recalculada **a cada validação**, a
    partir da última correção existente em tela — então, se o usuário editar uma correção anterior **depois**
    de já ter marcado "Incluir nova correção monetária", a pintura da nova correção deve reagir a essa
    mudança sem precisar desmarcar/marcar o checkbox de novo.
- **Limite de 1 correção nova por salvamento:** o formulário só permite preencher uma única correção; não
  existe "adicionar outra" nesta tela. Esse limite é estrutural (o formulário, o JS e o payload enviado ao
  backend só suportam um objeto `nova_correcao`, não uma lista).

---

## 9. Painel de Ações (Salvar / Resetar / Descartar Rascunho / Cancelar)

| Botão | Comportamento |
|---|---|
| **Salvar** | Envia `alteracoes_raiz`, `alteracoes_correcoes` e `nova_correcao` (se houver) para `POST /cco-editor/api/salvar`. Se não há nenhuma alteração, mostra alerta "Nenhuma alteração realizada" e não envia. Se há inconsistências pendentes, abre o **modal "Inconsistências Detectadas"** antes de permitir salvar (ver abaixo). Ao salvar com sucesso, redireciona para a tela de Revisão (`/cco-editor/revisar/<cco_id>`). |
| **Resetar** | Abre modal de confirmação explicando o que vai acontecer, e só recarrega a página (`window.location.reload()`) após confirmar. Como a tela sempre carrega o **rascunho pendente** quando ele existe (ver seção 9), "Resetar" recarrega esse mesmo rascunho — **não** descarta as alterações já salvas anteriormente, só as feitas nesta sessão (ainda não salvas). Se não existe rascunho pendente, o texto do modal explica que o reset volta para os dados originais de produção. |
| **Descartar Rascunho** | Só aparece quando existe um rascunho pendente para a CCO (também replicado como banner no topo da tela). Abre modal de confirmação — ação **irreversível**. Ao confirmar, chama `POST /cco-editor/api/descartar-rascunho/<cco_id>` (remove o documento de `conta_custo_oleo_corrigida_entity`) e recarrega a tela de edição já forçando a leitura do original de produção (`?forcar_producao=1`). |
| **Cancelar** | Link simples de volta para a home do editor (`/cco-editor/`). Não descarta nada — se havia um rascunho pendente, ele continua existindo. |

### Modal "Inconsistências Detectadas" (ao clicar em Salvar com pendências)

- Mostra a contagem de inconsistências.
- Exige marcar o checkbox "Confirmo que revisei as inconsistências..." **e** preencher uma justificativa com
  pelo menos alguns caracteres para habilitar o botão "Salvar Mesmo Assim".
- Botão "Ver Detalhes" fecha o modal e abre a aba "Validação".
- Ao salvar mesmo assim, a justificativa e a lista de inconsistências ignoradas são enviadas junto no payload
  (`justificativa_inconsistencias`, `inconsistencias_ignoradas`).

---

## 10. Tela de Revisão

Acesso: `/cco-editor/revisar/<cco_id>` (só existe se houver rascunho pendente para aquela CCO; senão mostra
tela de erro "Edição não encontrada").

### 10.1 Cards de resumo (topo)

- **Campos Alterados** — contagem de diferenças na raiz.
- **Impacto Financeiro** — diferença absoluta entre o `valorReconhecidoComOH` final original e o corrigido.
- **Novas Correções** — contagem de correções novas incluídas.
- **Total Correções** — `qtd original → qtd corrigida`.

### 10.2 Tabela "Campos Alterados"

Colunas: **Campo | Original | (seta) | Novo**. A coluna "Diferença" foi **removida** (não tinha propósito —
só era preenchida para campos monetários e duplicava a informação já visível nas colunas Original/Novo).
Valores monetários aparecem formatados em pt-BR (`R$ 86.879.415,95`), não mais em ponto decimal cru
(`R$ 86879415.95`).

### 10.3 Card "Novas Correções"

Lista cada correção nova incluída, com tipo, subtipo, data, `+ diferencaValor` e
`Valor c/ OH (valorReconhecidoComOH)` — o rótulo agora deixa explícito qual atributo está sendo mostrado.

### 10.4 Card "Impacto Financeiro"

Agora com rótulos explícitos do atributo considerado (`valorReconhecidoComOH`) em cada linha:
- Valor Inicial (`raiz.valorReconhecidoComOH` da CCO original)
- Valor Final Original (`valorReconhecidoComOH` da última correção ativa da CCO original, ou da raiz se não
  houver correção)
- Valor Final Corrigido (idem, mas na CCO corrigida)
- Diferença Total (`Valor Final Corrigido - Valor Final Original`)

Todos formatados em pt-BR.

### 10.5 Ações

| Botão | Comportamento |
|---|---|
| **Ir para Promoção** | Vai para a tela de promoção IPCA/IGPM (fora do escopo deste documento). |
| **Editar Novamente** | Volta para `/cco-editor/editar/<cco_id>`. **Corrigido nesta rodada:** antes, sempre recarregava do original de produção e descartava o rascunho; agora a tela de edição detecta o rascunho pendente e carrega ele — as alterações salvas continuam lá. |
| **Descartar Edição** | Confirmação via `confirm()` do navegador (não é um modal Bootstrap, é o confirm nativo). Chama `DELETE /cco-editor/api/descartar/<cco_id>` e redireciona para a home do editor. Equivalente, em efeito, ao botão "Descartar Rascunho" da tela de edição, mas iniciado a partir da tela de Revisão. |
| **Voltar** | Volta para a home do editor sem descartar nada. |

---

## 11. Endpoints envolvidos

| Método | Rota | Uso |
|---|---|---|
| GET | `/cco-editor/editar/<cco_id>` | Carrega a tela de edição. Aceita `?forcar_producao=1` para ignorar rascunho pendente e carregar sempre produção. |
| GET | `/cco-editor/revisar/<cco_id>` | Carrega a tela de revisão a partir do rascunho pendente. |
| POST | `/cco-editor/api/salvar` | Salva (ou atualiza) o rascunho pendente com as alterações feitas na tela de edição. |
| POST | `/cco-editor/api/descartar-rascunho/<cco_id>` | **Novo.** Remove o rascunho pendente. Usado pelo botão "Descartar Rascunho" da tela de edição. |
| DELETE | `/cco-editor/api/descartar/<cco_id>` | Remove o rascunho pendente (com filtro adicional `tipo_edicao=MANUAL`, `status_promocao=PENDENTE`). Usado pelo botão "Descartar Edição" da tela de revisão. |
| POST | `/cco-editor/api/preview` | Preview de diff sem salvar (usado por outros fluxos, não pelo botão Salvar principal). |
| GET | `/promocao-cco/detalhar/<cco_id>` | Tela de promoção (fora do escopo deste documento), acessada pelo botão "Ir para Promoção" da Revisão. |
| POST | `/promocao-cco/api/promover` | Aplica o rascunho em produção (`conta_custo_oleo_entity`) e marca o rascunho como `PROMOVIDA`. Ver seção 2. |

---

## 12. Roteiro de casos de teste sugeridos

#### TC-ED-VAL-001 — Regras da raiz, caminho feliz
Abrir uma CCO consistente (sem inconsistências). Verificar que todos os 6 campos da seção 4.1 aparecem
pintados de **azul** e sem nenhuma entrada na aba "Validação".

#### TC-ED-VAL-002 — Regras da raiz, caminho de erro
Editar `overHeadExploracao` para um valor que quebre a soma de `overHeadTotal`. Verificar: `overHeadTotal`
fica **vermelho**; a aba "Validação" ganha 1 item; o popover de `overHeadTotal` mostra a fórmula, o valor
atual e o esperado corretos; **o valor de `overHeadTotal` não muda sozinho**.

#### TC-ED-VAL-003 — Campos "iguais à raiz" em correção existente
Editar `valorReconhecido` na raiz de forma que passe a divergir do `valorReconhecido` de uma correção
existente. Verificar que o campo correspondente na correção fica vermelho, com popover citando
`Raiz.valorReconhecido`.

#### TC-ED-VAL-004 — Encadeamento entre correções
Em uma CCO com 2+ correções, editar `valorReconhecidoComOH` da primeira correção. Verificar que
`valorReconhecidoComOhOriginal` da segunda correção passa a ficar vermelho (esperado = novo valor da
primeira), sem precisar recarregar a página.

#### TC-ED-VAL-005 — IPCA/IGPM acumulado
Em uma CCO com 2+ correções IPCA/IGPM, conferir que `igpmAcumulado` de cada uma é a soma das `taxaCorrecao`
até ali (não produto) e que `igpmAcumuladoReais` é a soma das `diferencaValor` até ali.

#### TC-ED-VAL-006 — RECUPERACAO — `valorRecuperadoTotal` (regra nova)
Em uma CCO com 2+ correções RECUPERACAO, cada uma com `valorRecuperado` preenchido e um campo
`valorRecuperadoTotal` persistido: conferir que o `valorRecuperadoTotal` de cada correção é a soma dos
`valorRecuperado` de todas as correções RECUPERACAO até ali (inclusive). Editar o `valorRecuperado` de uma
correção anterior e confirmar que o `valorRecuperadoTotal` das correções RECUPERACAO seguintes reage e passa
a ficar vermelho, se aplicável.

#### TC-ED-VAL-007 — quantidadeLancamento não é exibido como moeda
Forçar uma inconsistência em `quantidadeLancamento` (editar a raiz para divergir de uma correção). Verificar
que o popover e a aba "Validação" mostram o valor como número inteiro simples (ex.: `2980`), **sem** `R$` e
sem casas decimais.

#### TC-ED-VAL-008 — Card "Resumo" acompanha inconsistências em tempo real
Gerar uma inconsistência (ex.: editar `overHeadExploracao`). Conferir que o card "Resumo" mostra
"N inconsistência(s)". Corrigir o valor de volta. Conferir que o card "Resumo" **atualiza imediatamente**,
sem precisar de nova interação, para "Nenhuma alteração" (ou removendo a linha de inconsistências).

#### TC-ED-NC-001 — Nova Correção pré-preenche `valorReconhecidoComOhOriginal`
Marcar "Incluir nova correção monetária" em uma CCO que já tem correções. Verificar que o campo
`Valor Original` vem preenchido com o `valorReconhecidoComOH` da última correção existente (não zero).

#### TC-ED-NC-002 — Nova Correção reage a edição de correção anterior
Marcar "Incluir nova correção monetária". Depois, editar um campo da última correção existente que altere
seu `valorReconhecidoComOH`. Verificar que a pintura de `Valor Original` na Nova Correção reage (fica
vermelha se passou a divergir), sem precisar desmarcar/marcar o checkbox de novo.

#### TC-ED-NC-003 — Nova Correção do tipo RECUPERACAO valida `valorRecuperadoTotal`
Com uma ou mais correções RECUPERACAO já existentes, marcar "Incluir nova correção monetária", selecionar
Tipo = RECUPERACAO, preencher `Valor Recuperado`. Verificar que o campo `Valor Recuperado Total` da Nova
Correção é validado contra a soma de todos os `valorRecuperado` (existentes + o novo).

#### TC-ED-ACAO-001 — Resetar mantém rascunho pendente
Com um rascunho pendente já salvo, abrir a tela de edição, fazer uma alteração nova (não salva), clicar em
"Resetar" e confirmar no modal. Verificar que a tela recarrega com os valores do **rascunho pendente**
(inclusive uma correção nova adicionada anteriormente), não com o original de produção puro.

#### TC-ED-ACAO-002 — Descartar Rascunho é destrutivo e volta para produção
Com um rascunho pendente, clicar em "Descartar Rascunho", confirmar no modal. Verificar: o rascunho some do
banco (`conta_custo_oleo_corrigida_entity`); a tela recarrega mostrando os dados originais de produção; o
banner de rascunho pendente e o botão "Descartar Rascunho" desaparecem.

#### TC-ED-ACAO-003 — Editar Novamente não perde alterações salvas
Salvar uma edição (gera rascunho pendente e vai para a tela de Revisão). Clicar em "Editar Novamente".
Verificar que os valores editados anteriormente continuam aparecendo na tela de edição (e não os valores
originais de produção).

#### TC-REV-001 — Formatação BRL na tela de Revisão
Abrir a tela de Revisão de uma CCO com valores grandes (ex.: `R$ 86.879.415,95`). Verificar que **nenhum**
valor monetário aparece no formato cru (`R$ 86879415.95`), em nenhum dos cards ou tabelas.

#### TC-REV-002 — Coluna "Diferença" não existe mais
Conferir que a tabela "Campos Alterados" tem só 4 colunas (Campo, Original, seta, Novo).

#### TC-REV-003 — Impacto Financeiro identifica o atributo
Conferir que o card "Impacto Financeiro" deixa explícito, em cada linha, que o valor considerado é
`valorReconhecidoComOH`.

---

## 13. Bugs corrigidos recentemente (regressão)

Vale reexecutar esses casos como regressão, pois já foram corrigidos nesta rodada de mudanças:

1. **`quantidadeLancamento` exibido como valor monetário** no popover e na aba Validação (ex.: `R$ 2.980,00`
   em vez de `2980`) — corrigido, ver TC-ED-VAL-007.
2. **Card "Resumo" não atualizava a contagem de inconsistências** em tempo real (ficava sempre um passo
   atrasado em relação à validação mais recente) — corrigido, ver TC-ED-VAL-008.
3. **`valorReconhecidoComOhOriginal` da Nova Correção sempre vinha zerado** — corrigido, ver TC-ED-NC-001.
4. **"Editar Novamente" descartava o rascunho pendente**, recarregando sempre do original de produção —
   corrigido, ver TC-ED-ACAO-003.
5. **Faltava a regra de `valorRecuperadoTotal`** em correções RECUPERACAO (não existia validação nenhuma
   para esse campo) — corrigido, ver TC-ED-VAL-006.
