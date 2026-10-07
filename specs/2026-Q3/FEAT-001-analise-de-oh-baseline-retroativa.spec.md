---
spec_id: FEAT-001
title: "Analise de OH"
status: Implemented
type: feature
created_at: 2026-09-03
created_by: "Thiago Paraizo"
approved_by: "@thiagoparaizo"
approved_at: "2026-09-27"
sprint: "2026-Q3"
stack: "python"
---


# FEAT-001: Análise de OH

## 1. Contexto e Motivação

Esta spec define a implementação do módulo de Análise e Verificação de Overhead (OH) das CCOs. A
funcionalidade foi removida da aplicação e deverá ser implementada novamente após aprovação desta
spec.

O objetivo de negócio original (documento de escopo técnico `docs/PPSA - SD-3720 - Estimativa Escopo -
Aditivo (Modulo_OH).pdf`, melhoria SD-2242, 11/06/2024) é: o sistema não possuía um mecanismo
estruturado para verificar a consistência dos valores de OH calculados nas CCOs. Erros de OH ficam
acumulados silenciosamente ao longo da cadeia de correções monetárias (IPCA/IGPM), distorcendo saldos
recuperáveis. Este módulo resolve o problema de **verificação/análise** (o segundo problema —
**correção** — é tratado em FEAT-003).

O objetivo desta entrega é disponibilizar a busca e verificação em lote, a análise detalhada por
faixas progressivas e as exportações descritas nesta spec. O módulo também estabelece a base
funcional para FEAT-002 (ajustes pontuais) e FEAT-003 (módulo de Correção, que reutiliza o motor de
cálculo de faixas progressivas definido aqui).

## 2. Escopo

### 2.1 Está no escopo
- Implementar a tela de busca com filtros configuráveis (contrato, campo, fase da remessa, origem dos
  gastos, mês/ano de referência, faixa de remessa, status de recuperação).
- Implementar a verificação automática de OH em lote (bloco RAIZ da CCO + cada entrada do array
  `correcoesMonetarias` que contenha campos de OH).
- Implementar a classificação de cada bloco em três status: OK, ATENÇÃO, ERRO — com taxa calculada,
  taxa esperada e diferença em reais.
- Implementar o painel de KPIs (total de CCOs únicas, % de conformidade, erros por tipo: OH
  Exploração, OH Produção, OH Total).
- Implementar a tabela de resultados com filtros por status e por tipo de bloco (RAIZ/CORREÇÃO).
- Implementar a exportação dos resultados em CSV (30 colunas, UTF-8 BOM, separador `;`).
- Implementar a tela de análise por faixas progressivas (drill-down): para CCOs com erro no OH de
  Exploração, exibe todas as CCOs do mesmo contrato/ano em ordem cronológica, com acumulado anual,
  fatias por faixa e OH esperado vs. real.
- Implementar a exportação em CSV da análise por faixas no client-side.
- Implementar as regras de cálculo de OH Produção (taxa fixa 1%) e OH Exploração (faixas progressivas
  3%/2%/1% com proporcionalidade no cruzamento de faixas).
- Proteger as rotas com a permissão `CCO_VIEW` e bloqueio para usuários `CLIENT`.

### 2.2 NÃO está no escopo (decisão consciente)
- Os ajustes pontuais identificados para o módulo (checagem de OH zero para `GASTO_AEGV`, exportação
  CSV de faixas server-side e extração de repositório dedicado) são tratados em **FEAT-002**, não aqui.
- Correção de OH com propagação em cascata (motor de correção, telas de correção, staging) — tratado
  em **FEAT-003**.
- Alteração das regras de cálculo de OH (taxas, faixas, tolerâncias) — regras fixas, fora de escopo
  em qualquer entrega conforme o documento de escopo original (seção 2.2).
- Recálculo retroativo em massa de todas as CCOs do sistema.
- Integração com o módulo de Recuperação (processo mensal).
- Interface para o operador (módulo exclusivo para usuários internos da PPSA).
- Análise de cálculos de TP (Track Participation) ou Fator de Alocação.

## 3. Definição da Solução

### 3.1 Arquitetura proposta

```
verificacao_oh_bp (Blueprint, prefixo /verificacao-oh)
        │
        ▼
VerificacaoOHService (app/services/verificacao_oh_service.py)
        │  acessa diretamente: db.conta_custo_oleo_entity (via pymongo)
        │  [FEAT-002 prevê a extração de repositório dedicado]
        ▼
MongoDB — coleção conta_custo_oleo_entity
```

Templates planejados: `app/templates/verificacao_oh/index.html` (busca + resultados + KPIs) e
`app/templates/verificacao_oh/analise_exp.html` (drill-down por faixas).

### 3.2 Contrato de API proposto

```yaml
GET /verificacao-oh/
  Response: 200 (HTML) — página principal

GET /verificacao-oh/analise-exp
  Response: 200 (HTML) — página de drill-down

GET /verificacao-oh/api/contratos
  Response: 200: string[] — lista de contratos distintos (contratoCpp)

GET /verificacao-oh/api/campos?contrato=<string>
  Response: 200: string[] — lista de campos cascateados ao contrato

GET /verificacao-oh/api/fases
  Response: 200: string[] — lista de fases de remessa distintas (faseRemessa)

POST /verificacao-oh/api/verificar
  Request:
    body:
      contrato: string (opcional)
      campo: string (opcional)
      fase: string (opcional)
      origem: string (opcional)
      mesAnoReferencia: string (opcional)
      remessa: string (opcional, aceita sintaxe "min-max")
      flgRecuperado: string (opcional)
  Response:
    200:
      resultados: array (cada item = CCO com blocos verificados RAIZ/CORREÇÃO e status)
      estatisticas: objeto com os 9 KPIs calculados
    401: UnauthorizedError (sem JWT válido)
    403: ForbiddenError (sem permissão CCO_VIEW)

GET /verificacao-oh/api/analise-exp?cco_id=<string>
  Response:
    200: array cronológico de CCOs do mesmo contrato/ano com acumulado, fatias por faixa, OH
         esperado/real
    401/403: idem acima

GET /verificacao-oh/download-csv
  Response:
    200: text/csv (30 colunas, UTF-8 BOM, separador ;) — CSV do último resultado da sessão
    401/403: idem acima
```

### 3.3 Requisitos Funcionais

- FR-001: A tela de busca (`GET /verificacao-oh/`) permitirá filtrar CCOs por contrato, campo (
  cascateado ao contrato selecionado), fase da remessa, origem dos gastos, mês/ano de referência,
  faixa de remessa (sintaxe `min-max`, ex: `10-20`) e status de recuperação (`flgRecuperado`).
  O serviço deve limitar a busca a no máximo 500 CCOs.
- FR-002: A verificação em lote (`POST /verificacao-oh/api/verificar`) executa, para cada CCO
  retornada pela busca, a checagem do bloco RAIZ (`overHeadExploracao`, `overHeadProducao`,
  `overHeadTotal`) e de cada entrada do array `correcoesMonetarias` que contenha ao menos um desses
  campos populado.
- FR-003: Cada bloco verificado (RAIZ ou entrada de correção) recebe um dos três status: `OK`
  (verde), `ATENÇÃO` (amarelo) ou `ERRO` (vermelho), com a taxa calculada, a taxa esperada e a
  diferença em reais. A prioridade de status é ERRO > ATENÇÃO > OK.
- FR-004: **Regra de OH Produção**: base de cálculo = `valorReconhecidoProducao`; taxa fixa de 1%
  (`TAXA_PRODUCAO = Decimal("1")`); tolerância de verificação de ±0,005% sobre a base
  (`TOLERANCIA_PCT = Decimal("0.005")`); se a base for `0`, `overHeadProducao` deve ser `0`
  e isso **não** é erro; se a base for negativa, o OH não é calculado (`resultado = 0`) e o bloco é
  classificado como **ATENÇÃO**, não ERRO.
- FR-005: **Regra de OH Exploração — faixas progressivas**: sobre o acumulado anual de
  `valorReconhecidoExploracao` do contrato (todas as CCOs do mesmo contrato no mesmo ano-calendário,
  ordenadas cronologicamente por `dataReconhecimento`, zerado a cada virada de ano), aplicam-se as
  taxas: 3% até R$ 5.000.000,00 de acumulado; 2% de R$ 5.000.000,01 até R$ 15.000.000,00; 1% acima de
  R$ 15.000.000,00. Quando o valor de exploração de uma CCO faz o acumulado cruzar a fronteira entre
  faixas, o cálculo é feito proporcionalmente, fatiando o valor entre as faixas atravessadas (nunca
  aplicando uma taxa única sobre o valor inteiro).
- FR-006: **OH Total**: `overHeadTotal` deve ser igual a `overHeadExploracao + overHeadProducao`;
  qualquer desvio superior a R$ 0,01 é classificado como ERRO.
- FR-007: O painel de KPIs (`calcular_estatisticas()`) exibe:
  total de CCOs únicas analisadas, quantidade/percentual OK, quantidade de ERRO, quantidade de
  ATENÇÃO, e erros por tipo (OH Exploração, OH Produção, OH Total) — 9 KPIs no total.
- FR-008: A tabela de resultados permite filtro de texto livre, filtro por status
  (OK/ERRO/ATENÇÃO) e filtro por tipo de bloco (RAIZ/CORREÇÃO).
- FR-009: A exportação em CSV (`GET /verificacao-oh/download-csv`, `gerar_csv()`) gera um arquivo
  com exatamente 30 colunas, delimitador `;`,
  BOM UTF-8 e formatação numérica BR (vírgula decimal), a partir do último resultado de verificação
  armazenado na sessão do usuário.
- FR-010: A tela de análise por faixas (`GET /verificacao-oh/analise-exp`, drill-down) exibe, para
  uma CCO de referência com erro no OH de Exploração, todas as CCOs do mesmo `contratoCpp` e
  `anoReconhecimento` em ordem cronológica (`sort("dataReconhecimento", 1)`), com o acumulado
  progressivo, as fatias calculadas por faixa (3%/2%/1%), o OH esperado e o OH real, e a diferença.
- FR-011: A exportação CSV da análise por faixas será gerada inteiramente no client-side (JavaScript,
  via `Blob`, função `exportarCSV()`), sem endpoint de backend dedicado.
- FR-012: Todas as rotas do blueprint `verificacao_oh_bp` exigem a permissão `CCO_VIEW` (decorador
  `@require_permission(Permission.CCO_VIEW)`) combinada com `@deny_client()`, e autenticação JWT
  válida (retorna HTTP 401 sem token válido, HTTP 403 sem a permissão).
- FR-013 [GAP CONHECIDO — ajuste tratado em FEAT-002]: para CCOs de origem `GASTO_AEGV`, o bloco
  deve ser marcado como `ATENÇÃO` incondicionalmente, sem verificar se
  `overHeadExploracao`/`overHeadProducao`/`overHeadTotal` são de fato `0`. A verificação real de zero
  para esse caso não faz parte desta entrega.

### 3.4 Modelo de Dados

Nenhuma entidade nova. Leitura da coleção existente `conta_custo_oleo_entity` (MongoDB), campos
relevantes usados pela verificação: `contratoCpp`, `campo`, `faseRemessa`, `origem`,
`mesAnoReferencia`, `remessa`/`remessaExposicao`, `flgRecuperado`, `dataReconhecimento`,
`anoReconhecimento`, `valorReconhecidoExploracao`, `valorReconhecidoProducao`,
`overHeadExploracao`, `overHeadProducao`, `overHeadTotal`, array `correcoesMonetarias` (cada entrada
podendo conter os mesmos três campos de OH).

## 4. Restrições de Implementação

### Stack obrigatória
- [x] Python 3.11 (runtime atual do projeto) + Flask 3.0
- [x] Logging: `logging` stdlib, seguindo o padrão atual do projeto (`structlog` é débito técnico
      registrado)
- [x] Sem dependências novas — usar as dependências já presentes no projeto

### O que NÃO fazer
- Não ampliar ou alterar as funcionalidades e regras descritas nesta spec.
- Não corrigir o gap documentado no FR-013 aqui — os ajustes pontuais são escopo de FEAT-002.
- Não implementar o módulo de Correção de OH aqui — isso é escopo de FEAT-003.

### LLM a usar
- [x] Ollama local / Azure OpenAI conforme política de dados do cliente — seguir a classificação de
      dados e as regras de segurança do projeto durante a implementação.

## 5. Critérios de Aceite

### Cenário 1: Busca retorna apenas CCOs correspondentes aos filtros (FR-001)
```gherkin
Dado que existem CCOs de múltiplos contratos, campos e fases cadastradas
Quando o usuário busca por um contrato, campo e fase específicos via POST /verificacao-oh/api/verificar
Então apenas as CCOs correspondentes a esses critérios são retornadas
E o limite de 500 CCOs por busca é respeitado
```

### Cenário 2: Classificação correta do bloco RAIZ (FR-002, FR-003, FR-004, FR-005, FR-006)
```gherkin
Dado uma CCO cujo overHeadProducao corresponde exatamente a 1% de valorReconhecidoProducao
E cujo overHeadExploracao corresponde à soma das faixas progressivas aplicadas ao acumulado anual
E cujo overHeadTotal é igual à soma de overHeadExploracao e overHeadProducao
Quando o bloco RAIZ dessa CCO é verificado
Então o status do bloco é classificado como OK
```

### Cenário 3: Base de cálculo negativa é ATENÇÃO, não ERRO (FR-004)
```gherkin
Dado uma CCO cujo valorReconhecidoProducao é negativo
Quando o bloco RAIZ dessa CCO é verificado
Então overHeadProducao é considerado 0
E o status do bloco é classificado como ATENÇÃO, não ERRO
```

### Cenário 4: Cruzamento de faixa aplica cálculo proporcional (FR-005)
```gherkin
Dado que o acumulado anual do contrato antes desta CCO é R$ 4.500.000,00
E o valor de exploração desta CCO é R$ 1.000.000,00
Quando o OH de Exploração desta CCO é calculado
Então R$ 500.000,00 são tributados a 3% (R$ 15.000,00)
E R$ 500.000,00 são tributados a 2% (R$ 10.000,00)
E o OH total de Exploração desta CCO é R$ 25.000,00 (não R$ 30.000,00 pela taxa única de 3%)
```

### Cenário 5: Exportação CSV contém os campos esperados (FR-009)
```gherkin
Dado que uma verificação em lote foi executada e possui resultados na sessão
Quando o usuário aciona GET /verificacao-oh/download-csv
Então o arquivo CSV retornado contém exatamente 30 colunas
E os valores são idênticos aos exibidos na tabela de resultados
```

### Cenário 6: Acesso negado sem permissão CCO_VIEW (FR-012)
```gherkin
Dado um usuário autenticado sem a permissão CCO_VIEW
Quando esse usuário tenta acessar qualquer rota do blueprint verificacao_oh_bp
Então o sistema retorna HTTP 403
```

### Cenário 7: Painel de KPIs reflete exatamente o resultado da verificação (FR-007)
```gherkin
Dado um lote de CCOs verificado, contendo CCOs OK, ATENÇÃO e ERRO
Quando o painel de KPIs é calculado por calcular_estatisticas()
Então o total de CCOs únicas, o percentual OK e os erros por tipo (Exp/Prod/Total) correspondem
  exatamente à contagem dos blocos verificados (RAIZ + correções monetárias)
```

### Cenário 8: Tabela de resultados filtra por status e por bloco (FR-008)
```gherkin
Dado uma tabela de resultados com blocos RAIZ e CORREÇÃO em status OK, ATENÇÃO e ERRO
Quando o usuário aplica o filtro de status "ERRO" e o filtro de bloco "CORREÇÃO"
Então apenas as linhas de bloco CORREÇÃO com status ERRO permanecem visíveis
```

### Cenário 9: Drill-down por faixas exibe a CCO de referência e o contrato/ano completos (FR-010)
```gherkin
Dado uma CCO com erro no OH de Exploração, pertencente a um contrato com outras 4 CCOs no mesmo ano
Quando o usuário acessa a tela de análise por faixas para essa CCO
Então as 5 CCOs do contrato/ano são exibidas em ordem cronológica
E a CCO de referência é destacada visualmente
E o OH esperado calculado corresponde ao resultado das regras progressivas com proporcionalidade
```

### Cenário 10: Exportação CSV de faixas é gerada no cliente (FR-011)
```gherkin
Dado a tela de análise por faixas carregada com os dados de um contrato/ano
Quando o usuário aciona o botão de exportar CSV de faixas
Então o arquivo é gerado inteiramente no navegador via Blob (função exportarCSV() em analise_exp.html)
E nenhuma requisição é feita ao backend para essa exportação
```

### Cenário 11: GASTO_AEGV é classificado como ATENÇÃO independentemente do valor real de OH (FR-013)
```gherkin
Dado uma CCO de origem GASTO_AEGV cujo overHeadExploracao é diferente de 0
Quando o bloco RAIZ dessa CCO é verificado
Então o status do bloco é classificado como ATENÇÃO, mesmo com OH diferente de zero
E a verificação real de zero para essa origem não é executada nesta entrega
```

## 6. Task List

As tasks abaixo implementam os requisitos funcionais e validam os critérios de aceite desta spec.

| ID | Descrição | FR | Azure Task ID | Est. | [P] | Status |
|----|-----------|----|---------------|------|-----|--------|
| T01 | Implementar o blueprint, as rotas de páginas e APIs e proteger os endpoints com `CCO_VIEW` e `deny_client()` | FR-001, FR-002, FR-012 | | 4h | [P] | ⬜ |
| T02 | Implementar o serviço de busca, filtros e verificação OH para blocos RAIZ e correções monetárias | FR-001, FR-002, FR-003 | | 6h | [P] | ⬜ |
| T03 | Implementar as regras de OH de Produção, Exploração por faixas progressivas, OH Total e casos especiais | FR-004, FR-005, FR-006, FR-013 | | 6h | | ⬜ |
| T04 | Implementar cálculo e apresentação dos KPIs e tabela de resultados com filtros | FR-007, FR-008 | | 4h | | ⬜ |
| T05 | Implementar a exportação CSV dos resultados da verificação | FR-009 | | 3h | | ⬜ |
| T06 | Implementar a tela e o serviço de análise por faixas para CCOs do mesmo contrato/ano | FR-010 | | 5h | | ⬜ |
| T07 | Implementar a exportação client-side CSV da análise por faixas | FR-011 | | 2h | | ⬜ |
| T08 | Registrar o blueprint na aplicação e disponibilizar a navegação para usuários autorizados | FR-001, FR-012 | | 2h | | ⬜ |
| T09 | Criar testes unitários, de rotas e de interface cobrindo os cenários de aceite | FR-001 a FR-013 | | 8h | | ⬜ |

## 7. Questões Abertas

- Confirmar com o Tech Lead a aprovação desta spec antes de iniciar a implementação, conforme a
  governança do projeto.
- Os ajustes pontuais descritos em FEAT-002 permanecem fora deste escopo e devem ser implementados
  separadamente.

## 8. Impactos e Dependências

- **Serviços/arquivos novos ou alterados:** blueprint de Verificação de OH, serviço de verificação,
  templates das telas, registro do blueprint e item de navegação.
- **Migração de banco de dados:** [x] Não
- **Feature flag necessária:** [x] Não
- **Breaking changes na API:** [x] Não — os endpoints desta funcionalidade serão novos.

## 9. Histórico de Decisões

| Data | Decisão | Motivo |
|------|---------|--------|
| 2026-09-03 | Criar a especificação inicial da funcionalidade | Documentar os requisitos de análise e verificação de OH derivados do escopo SD-3720 |
| 2026-09-27 | Converter a spec de retroativa/descritiva para implementação futura e definir status `Draft` | O módulo de Verificação de OH foi removido da aplicação; sua implementação depende de aprovação desta spec |

## 10. Contexto para o Agente de IA

```
Você está preparando a implementação da FEAT-001 no serviço sgpp-cco-tools (Flask).
Stack: Python 3.11 + Flask 3.0 + pymongo.
Estrutura planejada: app/routes/verificacao_oh_routes.py, app/services/verificacao_oh_service.py,
app/templates/verificacao_oh/{index.html, analise_exp.html}.
O módulo foi removido e ainda não foi reimplementado. Após a aprovação da spec, implemente somente
os requisitos funcionais e critérios de aceite definidos neste documento. A FEAT-002 contém ajustes
adicionais fora do escopo desta entrega; a FEAT-003 descreve o módulo separado de Correção de OH.
Padrões: ver .devspec/rules/coding-standards.md e AGENTS.md.
```

## 11. Log de Implementação IA

<!-- Preenchido pelo dev durante e após a implementação -->

| Data | Skill / Modelo | Comando / Prompt resumido | Ajustes manuais |
|------|---------------|--------------------------|-----------------|
| 2026-09-27 | claude-sonnet-5 (OpenCode) | Verificação remota da aprovação da spec (status/approved_by/approved_at em `origin/ide_feature/verificacao_oh_analise`) seguida de implementação da FEAT-001 | Módulo já havia existido antes (commit `e865e0d` "remoção do módulo de OH") e foi restaurado a partir do histórico git (`app/routes/verificacao_oh_routes.py`, `app/services/verificacao_oh_service.py`, `app/templates/verificacao_oh/index.html`, `app/templates/verificacao_oh/analise_exp.html`), com paridade byte-a-byte confirmada via `git hash-object`. Revisão manual linha a linha do código restaurado contra os 13 FRs e os 11 cenários de aceite da spec confirmou aderência total, incluindo o GAP conhecido do FR-013 (origem `GASTO_AEGV`). Reversão das remoções relacionadas: registro do blueprint em `app/__init__.py`, item de menu "Verificação de OH" em `app/templates/base.html`, e restauração do texto em `app/middleware/auth_middleware.py` e `docs/rbac_matrix.md` (confirmados idênticos ao estado anterior à remoção, exceto diferença de fim-de-arquivo sem conteúdo). Criados os testes automatizados que não existiam antes da remoção: `tests/services/test_verificacao_oh_service.py` (15 casos) e `tests/routes/test_verificacao_oh_routes.py` (12 casos), cobrindo os cenários 1–11 dos critérios de aceite. Suíte completa executada antes/depois via `git stash` para confirmar zero regressões (mesmas 18 falhas pré-existentes em `test_ipca_gap_analyzer.py`, mesmas falhas pré-existentes em `tests/templates/*`, `tests/middleware/test_rbac.py` e `tests/middleware/test_auth_middleware.py` — nenhuma delas relacionada a esta spec). |
