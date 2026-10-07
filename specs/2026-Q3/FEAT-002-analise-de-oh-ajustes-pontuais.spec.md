---
spec_id: FEAT-002
title: "Analise de OH - Ajustes Pontuais"
status: Approved
type: feature
created_at: 2026-09-03
created_by: "Thiago Paraizo"
approved_by: ""
approved_at: ""
sprint: "2026-Q3"
stack: "python"
---


# FEAT-002: Analise de OH - Ajustes Pontuais

## 1. Contexto e Motivação

O módulo de Análise de OH já está implementado em produção (documentado em FEAT-001). Uma
investigação de código comparando a implementação atual com o documento de escopo técnico
(`docs/PPSA - SD-3720 - Estimativa Escopo - Aditivo (Modulo_OH).pdf`) identificou 3 gaps pontuais.
O Tech Lead decidiu corrigir os 3:

1. CCOs de origem `GASTO_AEGV` devem ter o OH validado como realmente zero — hoje o sistema apenas
   marca `ATENÇÃO` sem checar o valor real, mascarando um possível erro real.
2. A exportação CSV da análise por faixas (hoje client-side) deve seguir o padrão arquitetural do
   projeto, sendo gerada server-side.
3. O acesso à coleção `conta_custo_oleo_entity` dentro do service deve ser extraído para uma camada
   de repositório dedicada, seguindo o padrão já usado por `CCORepository` (`app/repositories/
   cco_repository.py`) e `remessa_repository.py`.

Esta spec depende de FEAT-001 (documenta o baseline sobre o qual esses 3 ajustes são aplicados) e
deve ser concluída antes de FEAT-003 (Correção de OH), para que o motor de verificação/cálculo usado
pela correção parta de uma base 100% aderente ao escopo.

## 2. Escopo

### 2.1 Está no escopo
- Corrigir a verificação de CCOs `GASTO_AEGV`: se `overHeadExploracao`, `overHeadProducao` ou
  `overHeadTotal` forem diferentes de `0`, o bloco deve ser classificado como **ERRO** (não mais
  `ATENÇÃO` incondicional). Isso vale tanto na verificação em lote (`verificar_oh`) quanto na análise
  por faixas (`analisar_faixas_exploracao`).
- Criar endpoint de backend para exportação CSV da análise por faixas, no padrão dos demais CSVs do
  módulo (`Response` server-side, mesma formatação BR/UTF-8 BOM já usada em `gerar_csv()`), mantendo
  o detalhamento por faixa (3%/2%/1%) hoje gerado no client-side.
- Substituir a exportação client-side (JS/Blob) do template `analise_exp.html` pela chamada ao novo
  endpoint de backend.
- Criar `app/repositories/oh_verificacao_repository.py` seguindo o padrão de `CCORepository`,
  movendo o acesso direto a `db.conta_custo_oleo_entity` (hoje em `verificacao_oh_service.py:276`)
  para essa nova camada.
- Ajustar `VerificacaoOHService` para receber o novo repositório via injeção de dependência no
  construtor, em vez de acessar `pymongo`/`Database` diretamente.

### 2.2 NÃO está no escopo (decisão consciente)
- Qualquer outra regra de cálculo de OH além da checagem de zero para `GASTO_AEGV` — as taxas,
  faixas e tolerâncias permanecem inalteradas (fora de escopo conforme documento original).
- Alterações na tela de busca, filtros, KPIs ou tabela principal de resultados — não fazem parte dos
  3 gaps identificados.
- O motor de correção de OH e suas telas — tratado em FEAT-003.

## 3. Definição da Solução

### 3.1 Arquitetura

```
verificacao_oh_bp (routes)
        │
        ▼
VerificacaoOHService (recebe OHVerificacaoRepository via __init__)
        │
        ▼
OHVerificacaoRepository (NOVO) — app/repositories/oh_verificacao_repository.py
        │  encapsula: db.conta_custo_oleo_entity
        ▼
MongoDB
```

Novo endpoint: `GET /verificacao-oh/api/analise-exp/download-csv` — gera CSV server-side reutilizando
o resultado já calculado por `analisar_faixas_exploracao()`.

### 3.2 Contrato de API (novo endpoint)

```yaml
GET /verificacao-oh/api/analise-exp/download-csv?cco_id=<string>
Request:
  query:
    cco_id: string (required)
Response:
  200: text/csv (UTF-8 BOM, separador ;) — detalhamento por faixa da CCO informada e das demais
       CCOs do mesmo contrato/ano
  400: ValidationError — cco_id ausente ou inválido
  401: UnauthorizedError
  403: ForbiddenError (sem permissão CCO_VIEW)
  404: NotFoundError — CCO não encontrada
```

### 3.3 Requisitos Funcionais

- FR-001: Ao verificar um bloco (RAIZ ou entrada de `correcoesMonetarias`) de uma CCO com origem
  `GASTO_AEGV`, o sistema deve checar se `overHeadExploracao`, `overHeadProducao` e `overHeadTotal`
  são todos iguais a `0`. Se todos forem `0`, o status permanece `OK`. Se qualquer um for diferente
  de `0`, o status do bloco deve ser `ERRO` (substituindo o comportamento atual de `ATENÇÃO`
  incondicional via `override_atencao`). Aplicar em `_verificar_bloco_oh()`
  (`verificacao_oh_service.py` ~linhas 201-226, 363-366).
- FR-002: A mesma checagem do FR-001 deve ser aplicada em `analisar_faixas_exploracao()`
  (~linhas 517-521), garantindo consistência entre a tabela principal e o drill-down por faixas.
- FR-003: Criar o endpoint `GET /verificacao-oh/api/analise-exp/download-csv`, protegido por
  `@require_permission(Permission.CCO_VIEW)` + `@deny_client()`, que gera o CSV de detalhamento por
  faixa server-side (mesmo conteúdo hoje gerado pela função `exportarCSV()` em
  `analise_exp.html:596-653`), seguindo o padrão de `gerar_csv()` (separador `;`, BOM UTF-8,
  formatação numérica BR).
- FR-004: Atualizar `analise_exp.html` para remover a geração client-side do CSV (função
  `exportarCSV()`) e substituir por uma chamada (link/fetch) ao novo endpoint do FR-003.
- FR-005: Criar `app/repositories/oh_verificacao_repository.py` com uma classe
  `OHVerificacaoRepository(database: Database)`, expondo os métodos de acesso a
  `conta_custo_oleo_entity` hoje embutidos no service (equivalentes a `buscar_ccos`,
  listagens de `distinct` para contratos/campos/fases, e busca cronológica por contrato/ano usada em
  `analisar_faixas_exploracao`), seguindo exatamente o padrão de `CCORepository`
  (`app/repositories/cco_repository.py`): logging via `logger = logging.getLogger(__name__)`,
  tratamento de exceções específico com `logger.error(..., exc_info=True)`, sem bare `except`.
- FR-006: Refatorar `VerificacaoOHService.__init__` para receber o `OHVerificacaoRepository` via
  injeção de dependência (`def __init__(self, repository: OHVerificacaoRepository)` ou equivalente),
  removendo o atributo `self.collection = db.conta_custo_oleo_entity` (linha 276) e todo acesso
  direto a `pymongo`/`Database` do service. O ponto de instanciação nas rotas
  (`verificacao_oh_routes.py`, função `_get_service`) deve ser ajustado para instanciar o repositório
  e injetá-lo no service.

### 3.4 Modelo de Dados

Nenhuma entidade nova. Mesma coleção `conta_custo_oleo_entity` já usada por FEAT-001, apenas
reorganização da camada de acesso (repository).

## 4. Restrições de Implementação

### Stack obrigatória
- [x] Python 3.11 + Flask 3.0
- [x] Logging: `logging` stdlib, `logger = logging.getLogger(__name__)` em todos os módulos novos
- [x] Tratamento de erros: exceções específicas com `logger.error(f"...: {e}", exc_info=True)` —
      nunca bare `except:`
- [x] Sem dependências novas — usa apenas `pymongo` já presente no projeto

### O que NÃO fazer
- Não alterar as regras de cálculo de OH (taxas, faixas, tolerâncias) — apenas a lógica de
  classificação de status para `GASTO_AEGV`.
- Não duplicar a lógica de geração de CSV — reaproveitar o padrão/utilitários já usados em
  `gerar_csv()` sempre que possível.
- Não alterar a tela de busca principal, KPIs ou tabela de resultados (`index.html`) — fora do
  escopo dos 3 gaps.
- Não iniciar o motor de correção de OH (FEAT-003) nesta spec.
- Não remover o array `correcoesMonetarias` nem alterar seu schema.

### LLM a usar
- [x] Ollama local (regras de negócio de cálculo de OH) ou Azure OpenAI conforme política de dados
      do cliente — sem dados de produção reais envolvidos na implementação.

## 5. Critérios de Aceite

### Cenário 1: GASTO_AEGV com OH zerado permanece OK (FR-001)
```gherkin
Dado uma CCO de origem GASTO_AEGV cujos overHeadExploracao, overHeadProducao e overHeadTotal são 0
Quando o bloco RAIZ dessa CCO é verificado
Então o status do bloco é classificado como OK
```

### Cenário 2: GASTO_AEGV com OH diferente de zero é ERRO (FR-001, FR-002)
```gherkin
Dado uma CCO de origem GASTO_AEGV cujo overHeadExploracao é diferente de 0
Quando o bloco RAIZ dessa CCO é verificado na tela de verificação em lote
Então o status do bloco é classificado como ERRO
Quando essa mesma CCO é analisada na tela de faixas (drill-down)
Então o status exibido também é ERRO, de forma consistente
```

### Cenário 3: Exportação CSV de faixas via backend (FR-003, FR-004)
```gherkin
Dado uma CCO de referência com erro no OH de Exploração
Quando o usuário aciona a exportação de CSV na tela de análise por faixas
Então uma requisição é feita ao endpoint GET /verificacao-oh/api/analise-exp/download-csv
E o arquivo CSV retornado é gerado pelo servidor, com o mesmo detalhamento por faixa exibido na tela
E nenhuma geração de CSV ocorre mais no navegador via Blob
```

### Cenário 4: Endpoint de CSV de faixas requer permissão CCO_VIEW (FR-003)
```gherkin
Dado um usuário autenticado sem a permissão CCO_VIEW
Quando esse usuário tenta acessar GET /verificacao-oh/api/analise-exp/download-csv
Então o sistema retorna HTTP 403
```

### Cenário 5: Service não acessa mais o MongoDB diretamente (FR-005, FR-006)
```gherkin
Dado o código-fonte de VerificacaoOHService após a refatoração
Quando o construtor da classe é inspecionado
Então ele recebe uma instância de OHVerificacaoRepository via injeção de dependência
E não existe nenhum atributo self.collection nem acesso direto a db.conta_custo_oleo_entity no service
```

### Cenário 6: Comportamento funcional permanece idêntico após a refatoração do repositório (FR-005, FR-006)
```gherkin
Dado os cenários de aceite já documentados em FEAT-001 (busca, verificação, KPIs, CSV principal)
Quando esses mesmos cenários são executados após a extração do repositório
Então todos continuam passando sem alteração de comportamento observável
```

## 6. Task List

| ID | Descrição | FR | Azure Task ID | Est. | [P] | Status |
|----|-----------|----|---------------|------|-----|--------|
| T01 | Ajustar checagem de GASTO_AEGV em `_verificar_bloco_oh` (verificação em lote) | FR-001 | | 2h | | ⬜ |
| T02 | Ajustar checagem de GASTO_AEGV em `analisar_faixas_exploracao` (drill-down) | FR-002 | | 2h | | ⬜ |
| T03 | Criar `app/repositories/oh_verificacao_repository.py` seguindo padrão de `CCORepository` | FR-005 | | 3h | [P] | ⬜ |
| T04 | Refatorar `VerificacaoOHService` para receber o repositório via injeção de dependência | FR-006 | | 3h | | ⬜ |
| T05 | Ajustar `_get_service` em `verificacao_oh_routes.py` para instanciar e injetar o repositório | FR-006 | | 1h | | ⬜ |
| T06 | Criar endpoint `GET /verificacao-oh/api/analise-exp/download-csv` (server-side) | FR-003 | | 3h | [P] | ⬜ |
| T07 | Atualizar `analise_exp.html` para consumir o novo endpoint em vez do export client-side | FR-004 | | 2h | | ⬜ |
| T08 | Testes de regressão cobrindo os cenários 1-6 (unitários + integração) | FR-001 a FR-006 | | 4h | | ⬜ |

## 7. Questões Abertas

- Nenhuma questão bloqueante. As 3 decisões técnicas já foram confirmadas pelo Tech Lead (ver seção 9).

## 8. Impactos e Dependências

- **Serviços afetados:** `VerificacaoOHService`, novo `OHVerificacaoRepository`,
  `verificacao_oh_routes.py`, template `analise_exp.html`.
- **Migração de banco de dados:** [x] Não
- **Feature flag necessária:** [x] Não
- **Breaking changes na API:** [x] Não — o comportamento de status muda apenas para o caso
  específico de GASTO_AEGV com OH ≠ 0 (que hoje é mascarado como ATENÇÃO); nenhum contrato de
  request/response existente é quebrado; o novo endpoint é aditivo.

## 9. Histórico de Decisões

| Data | Decisão | Motivo |
|------|---------|--------|
| 2026-09-03 | GASTO_AEGV com OH ≠ 0 deve ser ERRO, não ATENÇÃO | Decisão do Tech Lead: o escopo original exige que o OH seja "sempre zero" para essa origem; hoje o sistema mascara esse caso |
| 2026-09-03 | Exportação CSV de faixas deve seguir o padrão server-side do projeto | Decisão do Tech Lead: manter consistência arquitetural com os demais CSVs do módulo |
| 2026-09-03 | Criar repositório dedicado (`oh_verificacao_repository.py`) | Decisão do Tech Lead: manter o padrão de camadas definido no AGENTS.md (routes → services → repositories) |

## 10. Contexto para o Agente de IA

```
Você está implementando FEAT-002 no serviço sgpp-cco-tools (Flask).
Stack: Python 3.11 + Flask 3.0 + pymongo.
Estrutura: app/routes/verificacao_oh_routes.py, app/services/verificacao_oh_service.py,
app/templates/verificacao_oh/analise_exp.html, app/repositories/cco_repository.py (padrão a seguir).
Arquivos existentes a consultar:
  - app/repositories/cco_repository.py (padrão de repositório: __init__(database), métodos com
    try/except + logger.error(..., exc_info=True), sem bare except)
  - app/services/verificacao_oh_service.py (linhas 70-100 faixas, 107-180 checks, 201-239 bloco OH,
    276 acesso direto à collection, 350-405 verificar_oh, 432-477 gerar_csv, 481-575 analisar_faixas)
  - app/templates/verificacao_oh/analise_exp.html (linhas 596-653, exportarCSV client-side a remover)
Arquivos protegidos (não alterar): app/templates/verificacao_oh/index.html (fora do escopo desta spec).
Padrões: ver .devspec/rules/coding-standards.md e AGENTS.md (seção "Services" e "Rotas").
```

## 11. Log de Implementação IA

<!-- Preenchido pelo dev durante e após a implementação -->

| Data | Skill / Modelo | Comando / Prompt resumido | Ajustes manuais |
|------|---------------|--------------------------|-----------------|
| | | | |
