# Guia de QA — Portal PPSA (CCO Tools)

**Versão:** 1.1  
**Data:** Junho 2026  
**Projeto:** sgpp-cco-tools  
**Audiência:** Equipe de QA  

---

## Sumário

1. [Visão Geral do Sistema](#1-visão-geral-do-sistema)
2. [Arquitetura e Stack](#2-arquitetura-e-stack)
3. [Ambiente de Testes](#3-ambiente-de-testes)
4. [Controle de Acesso e Perfis](#4-controle-de-acesso-e-perfis)
5. [Módulo 1 — Autenticação e Acesso](#5-módulo-1--autenticação-e-acesso)
6. [Módulo 2 — CCO Timeline](#6-módulo-2--cco-timeline)
7. [Módulo 3 — Recálculo TP](#7-módulo-3--recálculo-tp)
8. [Módulo 4 — Correção IPCA/IGPM](#8-módulo-4--correção-ipcaigpm)
9. [Módulo 5 — Edição de CCO](#9-módulo-5--edição-de-cco)
10. [Convenções de Reporte de Bugs](#10-convenções-de-reporte-de-bugs)
11. [Glossário](#11-glossário)

---

## 1. Visão Geral do Sistema

O **CCO Tools da PPSA** é um sistema web de análise e gestão de dados financeiros do setor pré-sal brasileiro. Seu objetivo central é permitir que analistas da PPSA  (Pré-Sal Petróleo S.A.) e usuários de suporte (Stefanini) visualizem, analisem e corrijam os dados de reconhecimento de gastos enviados pelos operadores de campos petrolíferos, garantindo a integridade e precisão dos dados.

### 1.1 Conceitos de Negócio Essenciais

**CCO (Conta Custo Óleo):** Entidade que representa uma entrada em conta-corrente de gastos reconhecidos. Funciona como um saldo acumulativo — valores são modificados ao longo do tempo por correções monetárias (IPCA/IGPM), recuperações e ajustes (retificações).

**Remessa:** Conjunto de gastos enviados mensalmente pelos operadores. Uma remessa passa por até 5 fases sequenciais: MEN → ROP → RAD → REC → REV. Cada fase representa uma nova oportunidade de ajustar e reconhecer gastos rejeitados em fases anteriores.

**Recálculo TP (Track Participation):** Processo de recalcular os valores de uma CCO aplicando um novo fator de participação (TP), que altera proporcionalmente os valores reconhecidos.

**Correção IPCA/IGPM:** Processo de atualização monetária anual das CCOs, aplicado automaticamente 1 ano após a data de reconhecimento. Existem 4 cenários distintos de correção conforme a condição da CCO (gap simples, gap com correção posterior, gap com recuperação, duplicatas).

**Correções Monetárias (array `correcoesMonetarias`):** Cada CCO possui um array que registra todas as alterações ao longo do tempo. A **última entrada (ativa e observando a data da correção) sempre representa o estado atual** da CCO. Tipos: IPCA, IGPM, RECUPERACAO, RETIFICACAO, INVALIDACAO_RECONHECIMENTO_PARCIAL.

### 1.2 Status dos Módulos

| # | Módulo | Status de QA |
|---|--------|-------------|
| 1 | Autenticação e Acesso | **Pronto para QA - falta ROLES** |
| 2 | CCO Timeline | **Pronto para QA** |
| 3 | Recálculo TP | **Pronto para QA** |
| 4 | Correção IPCA/IGPM | Na fila — não testar ainda |
| 5 | Edição de CCO | Em implementação — testes exploratórios permitidos |
| 6 | Promoção IPCA/IGPM | Na fila — não testar ainda |

---

## 2. Arquitetura e Stack

| Camada | Tecnologia |
|--------|-----------|
| Backend | Python 3.11 + Flask 3.0 |
| Banco de Dados | MongoDB |
| Frontend | HTML5 + Bootstrap 5 + JavaScript |
| Visualização | Chart.js |
| Cache | Flask-Caching (FileSystem) |
| Deploy Local | Gunicorn / Flask dev server |
| Porta Padrão | **5006** |

### 2.1 Blueprints Registrados

| Blueprint | Prefixo de URL | Módulo |
|-----------|---------------|--------|
| `auth_bp` | `/` (login/logout) | Autenticação |
| `portal_bp` | `/` | Portal + CCO Timeline |
| `analise_bp` | `/` | Análise de Remessas |
| `recalculo_bp` | `/recalculo` | Recálculo TP |
| `ipca_correcao_bp` | `/ipca-correcao` | Correção IPCA/IGPM |
| `ipca_promocao_bp` | `/ipca-promocao` | Promoção |
| `cco_editor_bp` | `/cco-editor` | Edição de CCO |

---

## 3. Ambiente de Testes

### 3.1 Inicialização da Aplicação

```bash
#Clonar repositório 
git clone https://github.com/SGPP-PPSA/sgpp-cco-tools

# Navegar até a pasta do projeto
cd ..\sgpp-cco-tools\

#clonar arquivo .env.example
cp .env.example .env

# configurar variáveis de ambiente no arquivo .env

# Ativar ambiente virtual (Windows)
.\venv\Scripts\activate

# instalar dependências
pip install -r requirements.txt

# Iniciar servidor
python run.py
```

A aplicação estará disponível em: **http://localhost:5006**

### 3.2 Configuração de Ambiente

O arquivo `.env` na raiz do projeto controla as conexões. Para QA, utilizar o ambiente HML (homologação):

- `MONGO_URI` — banco HML
- `MONGO_URI_PROD` — deve ser apontado para o banco de HML também
- `PESQUISA_AMBINTE_PRODUCAO=True` — habilita acesso ao banco configurado (HML)
- `DISABLE_AUTH=True` — desabilita autenticação (para testes sem gateway)

> **Atenção:** confirmar com o responsável técnico quais variáveis devem estar ativas no ambiente de QA antes de iniciar.

### 3.3 Execução dos Testes Automatizados

```bash
# Todos os testes
pytest

# Apenas testes unitários (rápido)
pytest tests/services/ tests/utils/ tests/models/ tests/middleware/

# Apenas testes E2E
pytest tests/e2e/

# Com relatório de cobertura
pytest --cov=app --cov-report=html
```

---

## 4. Controle de Acesso e Perfis

> 📖 **Documento de referência completo:** [rbac_matrix.md](rbac_matrix.md) — matriz detalhada de
> roles × permissões, mapeamento de cada tela/endpoint com a permissão exigida, como as roles são
> carregadas (JWT vs. banco), como montar contas de teste por perfil, e achados relevantes para
> teste (ex.: módulos sem controle de acesso, inconsistências entre visibilidade de botão e
> permissão exigida na ação). A tabela resumida abaixo é só um panorama rápido — para casos de
> teste de RBAC, usar o documento completo como fonte.

O sistema possui 3 perfis de usuário com permissões distintas:

| Perfil | Código | Permissões |
|--------|--------|-----------|
| **Visualizador** | `VIEWER` | `CCO_VIEW`, `CORRECAO_VIEW` |
| **Analista** | `ANALYST` | `CCO_VIEW`, `CCO_EDIT`, `CORRECAO_VIEW`, `CORRECAO_CREATE`, `REPORT_EXPORT` |
| **Admin** | `ADMIN` | Todas as permissões |

### 4.1 Permissões Granulares

| Permissão | Descrição |
|-----------|-----------|
| `CCO_VIEW` | Visualizar CCOs e timelines |
| `CCO_EDIT` | Editar CCOs manualmente |
| `CCO_DELETE` | Excluir CCOs |
| `CORRECAO_VIEW` | Visualizar recálculos e correções |
| `CORRECAO_CREATE` | Executar recálculos e correções |
| `CORRECAO_PROMOTE` | Promover correções para produção |
| `USER_VIEW` | Visualizar usuários |
| `USER_MANAGE` | Gerenciar usuários |
| `REPORT_EXPORT` | Exportar relatórios |

### 4.2 Casos de Teste de Controle de Acesso (transversais)

Estes testes se aplicam a **todos os módulos**:

| ID | Cenário | Perfil Testado | Resultado Esperado |
|----|---------|---------------|-------------------|
| AUTH-T01 | Acessar rota protegida sem autenticação | Não autenticado | Redirecionar para `/login` |
| AUTH-T02 | Acessar rota de ANALYST com perfil VIEWER | VIEWER | Retornar 403 ou redirecionar para "Acesso Negado" |
| AUTH-T03 | Acessar rota de ADMIN com perfil ANALYST | ANALYST | Retornar 403 |
| AUTH-T04 | Logout limpa sessão | Qualquer | Sessão encerrada, redireciona para login |
| AUTH-T05 | Acessar rota permitida com perfil correto | ANALYST | Acesso normal, conteúdo exibido |

---

## 5. Módulo 1 — Autenticação e Acesso

### 5.1 Objetivo

Garantir que somente usuários autenticados acessem o sistema, e que cada usuário acesse apenas as funcionalidades permitidas pelo seu perfil. A autenticação é delegada ao API Gateway Java/JHipster via token JWT.

### 5.2 Funcionamento

1. Usuário acessa qualquer rota protegida
2. Se não autenticado, é redirecionado para `/login`
3. Na tela de login, insere credenciais
4. O sistema valida as credenciais junto ao API Gateway (`URL_AUTH_GATEWAY`)
5. O Gateway retorna um token JWT
6. O token é armazenado em sessão Flask
7. Cada requisição subsequente valida o token (middleware `before_request`)
8. O logout limpa o token da sessão e o cache do usuário

> **Nota:** com `DISABLE_AUTH=True` no `.env`, o fluxo de autenticação é desativado para facilitar testes locais.

### 5.3 Endpoints

| Método | URL | Descrição |
|--------|-----|-----------|
| GET/POST | `/login` | Formulário de login |
| GET | `/logout` | Encerra sessão |

### 5.4 Casos de Teste

#### TC-AUTH-001 — Login com credenciais válidas
- **Pré-condição:** Usuário cadastrado no Gateway com perfil ANALYST
- **Passos:**
  1. Acessar `http://localhost:5006/login`
  2. Inserir usuário e senha válidos
  3. Clicar em "Entrar"
- **Resultado esperado:** Redirecionado para a home (`/`), nome do usuário exibido no cabeçalho

#### TC-AUTH-002 — Login com credenciais inválidas
- **Passos:**
  1. Acessar `/login`
  2. Inserir senha incorreta
  3. Clicar em "Entrar"
- **Resultado esperado:** Mensagem de erro exibida na tela, usuário permanece na página de login

#### TC-AUTH-003 — Login com usuário inexistente
- **Passos:**
  1. Inserir usuário que não existe no Gateway
- **Resultado esperado:** Mensagem de erro clara (não expor detalhes técnicos do Gateway)

#### TC-AUTH-004 — Logout
- **Pré-condição:** Usuário autenticado
- **Passos:**
  1. Clicar no menu do usuário → "Sair"
  2. Tentar acessar `http://localhost:5006/` diretamente
- **Resultado esperado:** Após logout, acesso à home redireciona para `/login`

#### TC-AUTH-005 — Acesso direto sem autenticação
- **Passos:**
  1. Com `DISABLE_AUTH=False`, abrir nova aba em modo anônimo
  2. Tentar acessar `http://localhost:5006/pesquisa-ccos`
- **Resultado esperado:** Redirecionado para `/login`

#### TC-AUTH-006 — Acesso a recurso sem permissão
- **Pré-condição:** Usuário com perfil VIEWER autenticado
- **Passos:**
  1. Tentar acessar `http://localhost:5006/recalculo/`
- **Resultado esperado:** Página de "Acesso Negado" ou redirecionamento adequado (não exibir erro 500)

#### TC-AUTH-007 — Menu dinâmico por perfil
- **Passos:**
  1. Fazer login com perfil VIEWER
  2. Observar itens do menu lateral/superior
  3. Fazer logout; fazer login com ADMIN
  4. Observar itens do menu
- **Resultado esperado:** Menu VIEWER exibe apenas módulos de visualização; menu ADMIN exibe todos os módulos

#### TC-AUTH-008 — Expiração de sessão
- **Passos:**
  1. Autenticar no sistema
  2. Aguardar expiração do token (ou forçar expiração via configuração)
  3. Tentar realizar uma ação
- **Resultado esperado:** Redirecionado para `/login` com mensagem de "sessão expirada"

---

## 6. Módulo 2 — CCO Timeline

### 6.1 Objetivo

Fornecer visualização detalhada do ciclo de vida de uma CCO, incluindo: valores financeiros atuais, cronologia de todos os eventos (correções monetárias, recuperações, retificações), filtro temporal e exportação de dados.

### 6.2 Funcionamento

O módulo possui dois fluxos principais:

**Fluxo A — Via Pesquisa de CCOs:**
1. Usuário acessa `/pesquisa-ccos`
2. Filtra por contrato, campo, remessa, fase, status de recuperação
3. Seleciona uma CCO na tabela de resultados
4. É redirecionado para `/cco-timeline/<cco_id>`

**Fluxo B — Via Dashboard:**
1. Usuário acessa o dashboard de análise
2. Visualiza gráficos de distribuição de remessas e CCOs
3. Clica em uma CCO específica nos gráficos
4. Acessa a timeline diretamente

**Na página de timeline:**
- Painel de valores consolidados (valorReconhecidoComOH, IPCA acumulado, IGPM acumulado, etc.)
- Linha do tempo cronológica de todos os eventos da CCO
- Card de detalhes de cada evento (correção, recuperação, retificação)
- Filtro por data de corte (visualizar estado da CCO em momento específico)
- Botão de exportação para Excel (.xlsx)
- Botão para executar recálculo TP diretamente da timeline

### 6.3 Endpoints

| Método | URL | Descrição |
|--------|-----|-----------|
| GET | `/pesquisa-ccos` | Página de pesquisa |
| POST | `/api/pesquisar-ccos` | API de pesquisa com filtros |
| GET | `/cco-timeline/<cco_id>` | Página de timeline |
| GET | `/api/cco-timeline/<cco_id>` | API timeline com `?data_corte=YYYY-MM-DD` |
| POST | `/api/ccos/export` | Exportação Excel lista de CCOs |
| GET | `/api/cco-timeline/<cco_id>/export` | Exportação Excel da timeline |
| GET | `/api/contratos-disponiveis` | Lista contratos disponíveis |
| GET | `/api/campos-por-contrato/<contrato>` | Campos de um contrato |

### 6.4 Casos de Teste — Pesquisa de CCOs

#### TC-TL-001 — Pesquisa sem filtros
- **Passos:**
  1. Acessar `/pesquisa-ccos`
  2. Clicar em "Pesquisar" sem preencher nenhum filtro
- **Resultado esperado:** Lista de CCOs retornada (com paginação), nenhum erro

#### TC-TL-002 — Pesquisa por contrato
- **Passos:**
  1. Selecionar um contrato no dropdown "Contrato"
  2. Verificar se o dropdown "Campo" é atualizado dinamicamente
  3. Clicar em "Pesquisar"
- **Resultado esperado:** Apenas CCOs do contrato selecionado são exibidas; dropdown de campo populado corretamente

#### TC-TL-003 — Pesquisa com múltiplos filtros
- **Filtros combinados:** Contrato + Campo + Fase = "MEN" + Recuperado = "Não"
- **Resultado esperado:** Resultados filtrados corretamente; se nenhum resultado, exibir mensagem adequada (não exibir tabela vazia sem aviso)

#### TC-TL-004 — Pesquisa retornando zero resultados
- **Passos:**
  1. Combinar filtros que não correspondam a nenhuma CCO (ex: campo inexistente)
- **Resultado esperado:** Mensagem "Nenhuma CCO encontrada" (não exibir erro 500 ou tela em branco)

#### TC-TL-005 — Exportação da lista de CCOs (Excel)
- **Pré-condição:** Pesquisa com resultados (pelo menos 1 CCO)
- **Passos:**
  1. Realizar pesquisa com resultados
  2. Clicar em "Exportar" / "Baixar Excel"
- **Resultado esperado:** Arquivo `.xlsx` gerado e iniciado o download; arquivo abre no Excel sem erros; colunas com valores financeiros formatados corretamente em moeda BRL

### 6.5 Casos de Teste — Página de Timeline

#### TC-TL-006 — Carregamento da timeline
- **Passos:**
  1. A partir da pesquisa, clicar em uma CCO com histórico de correções
- **Resultado esperado:**
  - Painel de valores exibido com todos os campos: `valorReconhecidoComOH`, overhead, IPCA acumulado, IGPM acumulado
  - Linha do tempo com todos os eventos ordenados cronologicamente
  - Cada evento exibe: data, tipo (IPCA/IGPM/RECUPERACAO/RETIFICACAO), valores aplicados, observações

#### TC-TL-007 — Timeline de CCO sem correções
- **Passos:**
  1. Acessar timeline de uma CCO recém-criada (sem `correcoesMonetarias`)
- **Resultado esperado:** Painel de valores exibido com dados da raiz; linha do tempo com apenas o evento de "Reconhecimento"; sem erros JavaScript no console

#### TC-TL-008 — Filtro por data de corte
- **Passos:**
  1. Abrir timeline de CCO com múltiplos eventos (ex: 5+ correções de anos diferentes)
  2. Usar o seletor de data para definir uma data no passado (ex: 2 anos atrás)
  3. Confirmar o filtro
- **Resultado esperado:**
  - Badge "Visualização até DD/MM/YYYY" exibido
  - Apenas eventos anteriores à data selecionada são mostrados na timeline
  - Valores do painel refletem o estado da CCO **naquela data** (não o valor atual)
  - Eventos posteriores ocultados

#### TC-TL-009 — Filtro data de corte: data futura
- **Passos:**
  1. Definir data de corte com data futura
- **Resultado esperado:** Todos os eventos exibidos (equivalente a não filtrar) ou mensagem de aviso

#### TC-TL-010 — Exportação da timeline individual (Excel)
- **Passos:**
  1. Abrir qualquer timeline
  2. Clicar em "Exportar Excel" / ícone de download
- **Resultado esperado:**
  - Download iniciado em até 5 segundos
  - Arquivo `.xlsx` contém múltiplas abas: Resumo, Timeline de Eventos, Valores Financeiros
  - Dados numéricos formatados como valores monetários (R$)
  - Datas no formato brasileiro (DD/MM/AAAA)

#### TC-TL-011 — Rate limit na exportação
- **Passos:**
  1. Clicar em "Exportar Excel" 3+ vezes rapidamente na mesma timeline
- **Resultado esperado:** A partir da 2ª ou 3ª tentativa, exibir mensagem de "aguarde antes de exportar novamente" (rate limit ativo)

#### TC-TL-012 — Botão "Executar Recálculo" na timeline
- **Pré-condição:** Usuário com permissão `CORRECAO_CREATE`
- **Passos:**
  1. Abrir qualquer timeline
  2. Localizar e clicar no botão "Recálculo TP"
- **Resultado esperado:** Modal de recálculo abre com dados da CCO pré-preenchidos (ID, contrato, campo); usuário pode prosseguir para o fluxo de recálculo

#### TC-TL-013 — Botão "Recálculo" não visível sem permissão
- **Pré-condição:** Usuário com perfil VIEWER (sem `CORRECAO_CREATE`)
- **Passos:**
  1. Abrir qualquer timeline
- **Resultado esperado:** Botão de recálculo não aparece na interface (não apenas desabilitado — deve estar oculto)

### 6.6 Casos de Teste — Dashboard e Análise

#### TC-TL-014 — Carregamento do dashboard
- **Passos:**
  1. Acessar `/dashboard`
- **Resultado esperado:** Gráficos carregados (distribuição de fases, valores por remessa, timeline de reconhecimento); sem erros no console; cards de resumo com totais

#### TC-TL-015 — Análise Remessas vs CCOs
- **Passos:**
  1. Acessar `/analise-remessas`
  2. Selecionar um contrato e período
  3. Clicar em "Analisar"
- **Resultado esperado:** Tabela comparando remessas x CCOs geradas; indicadores de consistência (valores que batem vs divergências)

#### TC-TL-016 — Verificação Remessas x CCOs
- **Passos:**
  1. Acessar `/verificacao-remessas-ccos`
  2. Selecionar filtros e executar verificação
- **Resultado esperado:** Relatório de inconsistências exibido (remessas sem CCO, CCOs sem remessa correspondente, divergências de valor)

---

## 7. Módulo 3 — Recálculo TP

### 7.1 Objetivo

Permitir que analistas recalculem os valores de uma CCO aplicando um novo fator de Track Participation (TP). O recálculo gera um resultado temporário que pode ser revisado e, se aprovado, aplicado definitivamente na CCO.

### 7.2 Funcionamento

O fluxo de recálculo segue estas etapas:

```
Pesquisar CCO → Abrir formulário → Configurar parâmetros →
Executar recálculo → Revisar resultado → [Salvar temporário | Aplicar definitivo | Descartar]
```

**Tipos de recálculo disponíveis:**
- **Recálculo TP Completo:** Recalcula todos os valores com novo fator TP
- **Recálculo Monetário:** Recalcula apenas as correções monetárias (IPCA/IGPM)

**Resultado temporário:** O resultado é salvo em cache e pode ser acessado por um período. O usuário pode:
- **Salvar como temporário:** Persiste no MongoDB para revisão posterior
- **Aplicar definitivamente:** Atualiza a CCO em produção (requer permissão `CORRECAO_PROMOTE`)
- **Descartar:** Cancela o recálculo

### 7.3 Endpoints

| Método | URL | Descrição |
|--------|-----|-----------|
| GET | `/recalculo/` | Home do módulo |
| GET | `/recalculo/pesquisar-ccos` | Pesquisa CCOs para recálculo |
| POST | `/recalculo/api/pesquisar-ccos` | API de pesquisa |
| GET | `/recalculo/executar/<cco_id>` | Página de configuração |
| POST | `/recalculo/api/executar-recalculo` | Executa o recálculo |
| GET | `/recalculo/resultado/<cache_key>` | Resultado do recálculo |
| POST | `/recalculo/api/salvar-temporario` | Salva resultado temporário |
| POST | `/recalculo/api/aplicar-definitivo` | Aplica definitivamente |
| GET | `/recalculo/temporarios` | Lista recálculos temporários |
| GET | `/recalculo/api/listar-temporarios` | API lista temporários |
| DELETE | `/recalculo/api/excluir-temporario/<id>` | Exclui temporário |
| DELETE | `/recalculo/api/limpar-temporarios` | Limpa todos temporários |
| GET | `/recalculo/api/exportar-csv/<cache_key>` | Exporta resultado CSV |

### 7.4 Casos de Teste — Pesquisa e Navegação

#### TC-REC-001 — Pesquisa de CCOs para recálculo
- **Passos:**
  1. Acessar `/recalculo/pesquisar-ccos`
  2. Pesquisar sem filtros
- **Resultado esperado:** Lista de CCOs elegíveis para recálculo exibida

#### TC-REC-002 — Pesquisa com filtros combinados
- **Filtros:** Contrato + Campo + Fase
- **Resultado esperado:** Resultados filtrados; link "Executar Recálculo" disponível para cada CCO listada

#### TC-REC-003 — Acesso à página de execução via link direto
- **Passos:**
  1. Acessar `http://localhost:5006/recalculo/executar/<cco_id>` com um ID válido
- **Resultado esperado:** Formulário de parâmetros carregado com dados da CCO (ID, contrato, campo, valores atuais)

### 7.5 Casos de Teste — Execução do Recálculo

#### TC-REC-004 — Recálculo TP com fator válido
- **Pré-condição:** CCO com `valorReconhecido > 0`
- **Passos:**
  1. Acessar formulário de recálculo de uma CCO
  2. Selecionar tipo "Recálculo TP Completo"
  3. Informar novo fator TP (ex: 0.45)
  4. Clicar em "Executar"
- **Resultado esperado:**
  - Redirecionado para `/recalculo/resultado/<cache_key>`
  - Tabela comparativa exibida: coluna "Original" vs coluna "Recalculado"
  - Delta percentual calculado e exibido
  - Gráfico comparativo (barras) visível

#### TC-REC-005 — Recálculo com fator TP inválido (fora do range)
- **Passos:**
  1. Informar fator TP = 0 ou negativo
  2. Clicar em "Executar"
- **Resultado esperado:** Validação de formulário impede o envio; mensagem de erro descritiva exibida (ex: "O fator TP deve ser maior que 0")

#### TC-REC-006 — Recálculo monetário
- **Passos:**
  1. Selecionar tipo "Recálculo Monetário" no formulário
  2. Executar
- **Resultado esperado:** Resultado exibe comparativo das correções IPCA/IGPM recalculadas vs originais

#### TC-REC-007 — Campos obrigatórios em branco
- **Passos:**
  1. Deixar campo obrigatório em branco (ex: fator TP)
  2. Tentar enviar
- **Resultado esperado:** Formulário não é submetido; campo destacado com mensagem de erro

#### TC-REC-008 — Resultado com campos pré-preenchidos ao voltar da timeline
- **Pré-condição:** Abrir recálculo a partir do botão na timeline da CCO
- **Resultado esperado:** ID da CCO, contrato e campo pré-preenchidos no formulário; dados consistentes com a CCO da timeline

### 7.6 Casos de Teste — Resultado e Persistência

#### TC-REC-009 — Salvar resultado como temporário
- **Pré-condição:** Recálculo executado com sucesso
- **Passos:**
  1. Na página de resultado, clicar em "Salvar como Temporário"
- **Resultado esperado:** Confirmação de sucesso; item aparece na lista `/recalculo/temporarios`

#### TC-REC-010 — Listar e acessar recálculos temporários
- **Passos:**
  1. Acessar `/recalculo/temporarios`
- **Resultado esperado:** Lista de recálculos salvos com: CCO ID, data de criação, tipo, status; link para visualizar cada resultado

#### TC-REC-011 — Excluir um recálculo temporário
- **Passos:**
  1. Na lista de temporários, clicar em "Excluir" em um item
  2. Confirmar a exclusão
- **Resultado esperado:** Item removido da lista; confirmação exibida; **não exibir erro** (bug corrigido na feature/tp001: a API de exclusão real foi implementada substituindo um placeholder)

#### TC-REC-012 — Aplicar recálculo definitivamente
- **Pré-condição:** Usuário com permissão `CORRECAO_PROMOTE`; recálculo temporário salvo
- **Passos:**
  1. Acessar resultado do recálculo temporário
  2. Clicar em "Aplicar Definitivamente"
  3. Confirmar no modal
- **Resultado esperado:**
  - CCO atualizada no banco com os novos valores
  - Evento de auditoria registrado em `correcoesMonetarias`
  - Redirecionado para a timeline da CCO atualizada

#### TC-REC-013 — Aplicar definitivo sem permissão (ANALYST sem PROMOTE)
- **Pré-condição:** Usuário ANALYST (sem `CORRECAO_PROMOTE`)
- **Passos:**
  1. Visualizar resultado de recálculo
- **Resultado esperado:** Botão "Aplicar Definitivamente" não visível ou desabilitado; usuário não consegue promover

#### TC-REC-014 — Exportação do resultado em CSV
- **Pré-condição:** Resultado de recálculo disponível
- **Passos:**
  1. Na página de resultado, clicar em "Exportar CSV"
- **Resultado esperado:** Arquivo `.csv` com colunas de campos originais e recalculados; valores numéricos sem formatação de moeda (apenas números)

#### TC-REC-015 — Consistência de valores: Original → Recalculado → Aplicado
- **Passos:**
  1. Anotar os valores do resultado do recálculo (ex: `valorReconhecidoComOH` recalculado)
  2. Aplicar definitivamente
  3. Abrir a timeline da CCO
- **Resultado esperado:** Valores na timeline correspondem exatamente aos valores recalculados anotados; evento de recálculo registrado na timeline

#### TC-REC-016 — Remessa derivada atualizada após aplicação
- **Passos:**
  1. Executar e aplicar recálculo em uma CCO que possua remessa derivada associada
  2. Verificar as remessas derivadas
- **Resultado esperado:** Valores das remessas derivadas atualizados de forma consistente com o recálculo aplicado à CCO original (funcionalidade implementada na feature/tp001)

---

## 8. Módulo 4 — Correção IPCA/IGPM

### 8.1 Objetivo

Identificar e corrigir falhas nas correções monetárias (IPCA ou IGPM) de uma CCO. As falhas mais comuns são: **gaps** (aniversários que deveriam ter recebido correção mas não receberam), **correções com valor base errado** (porque houve um gap anterior que não foi corrigido na época) e **correções duplicadas** (mesmo período lançado mais de uma vez).

Este é o módulo de maior complexidade do sistema — envolve regras de negócio específicas, múltiplos cenários de correção, efeito cascata entre correções e um fluxo em etapas (wizard) com sessão persistida no MongoDB.

---

### 8.2 Conceito: Regra do Aniversário

A correção monetária IPCA/IGPM é aplicada **1 ano após a data de reconhecimento da CCO** (mês e ano de reconhecimento). A cada ano subsequente, uma nova correção deve ser aplicada sobre o **saldo mais recente**.

**Exemplo:**
- CCO reconhecida em Janeiro/2020
- Aniversário 1: Janeiro/2021 → aplica IPCA de Dezembro/2020 no mês posterior, Fevereiro/2021
- Aniversário 2: Janeiro/2022 → aplica IPCA de Dezembro/2021 sobre o saldo corrigido no mês posterior, Fevereiro/2022
- Se o aniversário de Janeiro/2021 **não ocorreu** (gap), então o aniversário de Janeiro/2022 também calculou sobre a **base errada** → precisa ser recalculado (Cenário 1)

> A taxa IPCA aplicada usa **offset de -1 mês**: para o aniversário em mês M, usa-se a taxa do mês M-1. Exemplo: aniversário em Janeiro usa a taxa de Dezembro do ano anterior.

---

### 8.3 Os 5 Cenários de Correção

O sistema detecta automaticamente qual cenário se aplica à CCO analisada:

#### Cenário 0 — Gap Simples
**Condição:** Existe ao menos um aniversário sem correção, e **não há** correções posteriores ao gap nem recuperações.  
**Ação:** Inserir a(s) correção(ões) faltante(s) na data correta, com a taxa do período correspondente.  
**Complexidade:** Baixa.

```
Histórico atual:  [Reconhec.] → [IPCA 2022] → [IPCA 2023]
Esperado:         [Reconhec.] → [IPCA 2021] → [IPCA 2022] → [IPCA 2023]
                                      ↑
                               GAP a inserir
```

#### Cenário 1 — Gap com Correção Posterior
**Condição:** Existe um gap, mas há correções IPCA/IGPM **posteriores ao gap** que foram calculadas sobre a **base errada** (sem o IPCA do gap).  
**Ação:** Inserir o IPCA do gap E recalcular as correções posteriores que usaram base incorreta.  
**Complexidade:** Alta — requer recalcular o valor base de cada correção posterior em cascata.

```
Situação incorreta:
  Valor base: R$ 1.000.000
  IPCA 2022 (sobre 1M):       + R$ 46.200  → saldo: R$ 1.046.200
  
Correção (inserindo gap de 2021):
  IPCA 2021 (sobre 1M):       + R$ 62.000  → saldo: R$ 1.062.000  ← novo
  IPCA 2022 (sobre 1.062.000): + R$ 49.062  → saldo: R$ 1.111.062  ← recalculado
```

#### Cenário 2 — Gap com Recuperação
**Condição:** Existe um gap e a CCO possui correções do tipo `RECUPERACAO` (ou `flgRecuperado = true`).  
**Ação:** Inserir o IPCA do gap + criar uma compensação pelo impacto sobre a recuperação que ocorreu com base errada. Se a CCO estava zerada (`flgRecuperado = true`), pode ser necessário **reativá-la**.  
**Complexidade:** Muito alta — envolve compensações, possível reativação e reconciliação de saldos.

#### Cenário Duplicatas — Correções Duplicadas
**Condição:** Existe mais de uma correção IPCA/IGPM para o **mesmo período** (mês/ano de referência).  
**Ação:** Remover a duplicata e criar um ajuste compensatório para corrigir o efeito cascata que a duplicata causou nas correções subsequentes. Se a CCO foi zerada por conta disto, reativá-la.  
**Complexidade:** Alta — duplicatas têm **prioridade** sobre outros cenários; devem ser resolvidas primeiro.

#### Cenário IPCA Vigente
**Condição:** A CCO completou um novo aniversário **no ano corrente** e ainda não recebeu a correção.  
**Ação:** Proposta de aplicação da correção do ano vigente.  
**Observação:** Acionado via botão específico na interface (`avaliar-ipca-vigente`), não pelo fluxo principal de análise de gaps.

---

### 8.4 Fluxo do Wizard (4 Steps)

O módulo funciona como um **wizard multi-step** com sessão persistida no MongoDB (`ipca_correction_sessions`). Cada step corresponde a uma chamada de API:

```
Step 1: Informar CCO ID
        → POST /api/iniciar-analise
        → Cria sessão (UUID), detecta cenário, conta gaps
        
Step 2: Visualizar resultados da análise
        → POST /api/gerar-propostas
        → Calcula e exibe as propostas de correção (valor atual vs proposto, impacto)
        
Step 3: Aprovar/selecionar correções
        → POST /api/aprovar-correcoes
        → Usuário confirma quais propostas aceitar (pode ser seleção parcial)
        
Step 4: Aplicar correções
        → POST /api/aplicar-correcoes
        → Engine aplica as correções aprovadas na CCO em staging
```

**Estados da sessão (`CorrectionStatus`):**
`ANALYZING` → `PREVIEW` → `APPROVED` → `APPLIED`  
(ou `ERROR` em caso de falha)

---

### 8.5 Tipos de Proposta Gerados

| Tipo | Descrição |
|------|-----------|
| `IPCA_ADDITION` | Adicionar correção IPCA faltante (gap) |
| `IPCA_UPDATE` | Recalcular correção IPCA existente (base estava errada) |
| `COMPENSATION` | Compensação pelo impacto sobre recuperação |
| `REACTIVATION` | Reativar CCO que estava marcada como recuperada |
| `DUPLICATA_REMOVAL` | Remover entrada duplicada |
| `DUPLICATA_ADJUSTMENT` | Ajuste compensatório pelo efeito cascata da duplicata |
| `CORRECTION_DATE_CHANGE` | Reordenar data de retificação para manter ordenação cronológica correta |

---

### 8.6 Endpoints

| Método | URL | Permissão | Descrição |
|--------|-----|-----------|-----------|
| GET | `/ipca-correcao/` | `CORRECAO_CREATE` | Página principal (wizard) |
| POST | `/ipca-correcao/api/iniciar-analise` | `CORRECAO_CREATE` | Step 1: inicia análise, cria sessão |
| POST | `/ipca-correcao/api/gerar-propostas` | `CORRECAO_CREATE` | Step 2: gera propostas |
| POST | `/ipca-correcao/api/aprovar-correcoes` | `CORRECAO_PROMOTE` | Step 3: aprova selecionadas |
| POST | `/ipca-correcao/api/aplicar-correcoes` | `CORRECAO_CREATE` | Step 4: aplica na CCO |
| GET | `/ipca-correcao/api/status-sessao/<session_id>` | `CORRECAO_CREATE` | Consulta status da sessão |
| POST | `/ipca-correcao/api/avaliar-ipca-vigente` | `CORRECAO_CREATE` | Avalia IPCA do ano vigente |

> **Atenção de permissões:** O Step 3 (aprovar) exige `CORRECAO_PROMOTE`, enquanto os demais steps exigem apenas `CORRECAO_CREATE`. Um ANALYST pode analisar e propor, mas **não pode aprovar** — apenas ADMIN pode.

---

### 8.7 Casos de Teste — Fluxo Geral do Wizard

#### TC-IPCA-001 — Acesso à página principal
- **Pré-condição:** Usuário com `CORRECAO_CREATE`
- **Passos:** Acessar `/ipca-correcao/`
- **Resultado esperado:** Wizard carregado com Step 1 ativo (campo de CCO ID); sem erros JavaScript

#### TC-IPCA-002 — Acesso sem permissão
- **Pré-condição:** Usuário VIEWER (sem `CORRECAO_CREATE`)
- **Resultado esperado:** Redirecionado para "Acesso Negado"; não exibir a página do wizard

#### TC-IPCA-003 — Análise de CCO inexistente (Step 1)
- **Passos:**
  1. No campo de CCO ID, digitar um ID que não existe no banco
  2. Clicar em "Analisar"
- **Resultado esperado:** Mensagem de erro clara: "CCO não encontrada"; wizard permanece no Step 1

#### TC-IPCA-004 — Análise de CCO sem gaps
- **Passos:**
  1. Inserir ID de uma CCO que está **correta** (todas as correções no lugar)
  2. Clicar em "Analisar"
- **Resultado esperado:** Mensagem informativa "CCO está correta — nenhum gap identificado"; wizard não avança para Step 2 com propostas de correção

#### TC-IPCA-005 — Análise de CCO com gap simples (Cenário 0)
- **Passos:**
  1. Inserir ID de CCO com 1 aniversário sem correção (sem recuperações, sem IPCA posterior ao gap)
  2. Clicar em "Analisar"
- **Resultado esperado (Step 1 → Step 2):**
  - `scenario_detected: "CENARIO_0"`
  - Número de gaps identificados = 1
  - Wizard avança para Step 2
- **Resultado esperado (Step 2 — Propostas):**
  - 1 proposta do tipo `IPCA_ADDITION`
  - Exibe: período do gap, taxa IPCA aplicada, valor atual, valor proposto, impacto (R$)
  - Impacto calculado corretamente: `valor_atual × taxa = valor_proposto`

#### TC-IPCA-006 — Análise com múltiplos gaps (Cenário 0)
- **Passos:**
  1. Inserir CCO com 3 aniversários sem correção (ex: 2021, 2022, 2023)
- **Resultado esperado:**
  - 3 propostas do tipo `IPCA_ADDITION`
  - As propostas são **ordenadas cronologicamente** (2021 → 2022 → 2023)
  - O valor base de cada proposta parte do resultado da anterior (efeito acumulado)
  - Impacto total = soma dos três impactos individuais (exibido no resumo)

#### TC-IPCA-007 — Análise com gap e correção posterior (Cenário 1)
- **Passos:**
  1. Inserir CCO onde há um gap de 2021, mas existe uma correção IPCA de 2022 que foi calculada sobre a base incorreta
- **Resultado esperado:**
  - `scenario_detected: "CENARIO_1"`
  - Propostas geradas: ao menos 1 `IPCA_ADDITION` (para o gap) + 1 `IPCA_UPDATE` (recalcular 2022)
  - A proposta `IPCA_UPDATE` deve indicar a **dependência** da proposta `IPCA_ADDITION`
  - Valor da proposta `IPCA_UPDATE` usa como base o saldo **após a inserção do gap**
  - Interface indica claramente quais correções são novas e quais são atualizações

#### TC-IPCA-008 — Análise com gap e recuperação (Cenário 2)
- **Passos:**
  1. Inserir CCO com gap de IPCA, mas que possui uma `RECUPERACAO` posterior
- **Resultado esperado:**
  - `scenario_detected: "CENARIO_2"`
  - Propostas incluem `IPCA_ADDITION` + `COMPENSATION`
  - A `COMPENSATION` compensa o impacto que a recuperação teve sobre a base incorreta
  - Se CCO está com `flgRecuperado = true` e o saldo final estimado ≠ 0: proposta de `REACTIVATION` também presente

#### TC-IPCA-009 — Análise com duplicata (Cenário Duplicatas)
- **Passos:**
  1. Inserir CCO que possui 2 correções IPCA para o mesmo período (ex: 2 registros com `dataCorrecao` de Janeiro/2022)
- **Resultado esperado:**
  - `scenario_detected: "CENARIO_DUPLICATAS"` (prioridade sobre outros cenários, mesmo se houver gaps)
  - Propostas incluem:
    - `DUPLICATA_REMOVAL`: remoção da entrada duplicada
    - `DUPLICATA_ADJUSTMENT`: ajuste compensatório (considera efeito cascata nas correções posteriores)
  - Interface exibe o valor que será removido e o ajuste resultante
  - Se há correções IPCA posteriores à duplicata, exibe o **efeito cascata** calculado

---

### 8.8 Casos de Teste — Step 3: Aprovação

#### TC-IPCA-010 — Aprovar todas as propostas
- **Pré-condição:** Sessão em status PREVIEW com propostas geradas; usuário com `CORRECAO_PROMOTE`
- **Passos:**
  1. No Step 3, selecionar todas as propostas
  2. Clicar em "Aprovar"
- **Resultado esperado:**
  - Sessão atualiza para status `APPROVED`
  - Preview final exibido: lista de correções aprovadas + impacto financeiro total
  - Botão "Aplicar" habilitado

#### TC-IPCA-011 — Aprovação parcial (Cenário 1 ou Duplicatas)
- **Passos:**
  1. No Step 3, desmarcar uma das propostas que tem **dependente** (ex: selecionar `IPCA_UPDATE` sem selecionar o `IPCA_ADDITION` do qual depende)
- **Resultado esperado:** Validação impede aprovação inconsistente; mensagem explica que a dependência precisa ser incluída

#### TC-IPCA-012 — Tentativa de aprovação sem permissão (ANALYST)
- **Pré-condição:** Usuário ANALYST (sem `CORRECAO_PROMOTE`)
- **Passos:**
  1. Chegar ao Step 3 (análise e propostas visíveis)
  2. Tentar aprovar
- **Resultado esperado:** Botão de aprovação não disponível ou API retorna 403; mensagem de "permissão insuficiente"

---

### 8.9 Casos de Teste — Step 4: Aplicação

#### TC-IPCA-013 — Aplicar correções aprovadas (Cenário 0)
- **Pré-condição:** Sessão em status APPROVED com 1 proposta `IPCA_ADDITION`
- **Passos:**
  1. Clicar em "Aplicar Correções"
  2. Confirmar no modal
- **Resultado esperado:**
  - API `/api/aplicar-correcoes` retorna sucesso
  - Sessão atualiza para status `APPLIED`
  - CCO no banco de dados (staging ou produção, conforme config) possui nova entrada em `correcoesMonetarias` com:
    - `tipo: "IPCA"`
    - `taxaCorrecao` = taxa do período
    - `diferencaValor` = impacto calculado
    - `dataCorrecao` = data do aniversário corrigido
  - Interface exibe confirmação de sucesso e opção de ver a timeline da CCO atualizada

#### TC-IPCA-014 — Verificar CCO após aplicação (Cenário 0)
- **Passos:**
  1. Após aplicar correção do Cenário 0, abrir a timeline da CCO em `/cco-timeline/<cco_id>`
- **Resultado esperado:**
  - Nova entrada de IPCA visível na timeline, **na posição cronológica correta**
  - Valores do painel (valorReconhecidoComOH, IPCA acumulado) atualizados
  - Sem entradas duplicadas

#### TC-IPCA-015 — Aplicar correções (Cenário 1) e verificar cascata
- **Passos:**
  1. Aplicar correção do Cenário 1 (gap + atualização posterior)
  2. Abrir timeline da CCO
- **Resultado esperado:**
  - Correção do gap inserida na posição correta
  - Correção posterior (`IPCA_UPDATE`) com valor recalculado (base maior)
  - O valor acumulado final é maior do que antes da correção (pois a base estava incorreta)

#### TC-IPCA-016 — Aplicar e verificar Cenário 2 (com compensação)
- **Passos:**
  1. Aplicar correção do Cenário 2
  2. Verificar `correcoesMonetarias` da CCO
- **Resultado esperado:**
  - Correção do gap inserida
  - Entrada de compensação registrada (com observação explicando o motivo)
  - Se havia `REACTIVATION`: `flgRecuperado = false` na CCO; `valorReconhecidoComOH` reflete o saldo reativado

#### TC-IPCA-017 — Aplicar Cenário Duplicatas e verificar remoção
- **Resultado esperado:**
  - A entrada duplicada **não existe mais** em `correcoesMonetarias`
  - Ajuste compensatório registrado
  - Valor acumulado da CCO é menor do que antes (duplicata inflava o saldo)
  - Se CCO estava recuperada por conta da duplicata: `flgRecuperado = false` após reativação

#### TC-IPCA-018 — Tentar aplicar sem aprovação prévia
- **Passos:**
  1. Chamar diretamente `POST /api/aplicar-correcoes` com `session_id` de uma sessão em status `PREVIEW` (não `APPROVED`)
- **Resultado esperado:** API retorna erro: "Sessão inválida ou não aprovada" (status 400 ou 422); CCO **não é alterada**

---

### 8.10 Casos de Teste — Sessão e Persistência

#### TC-IPCA-019 — Retomada de sessão existente
- **Passos:**
  1. Iniciar análise, gerar propostas (sessão em PREVIEW)
  2. Fechar o browser / navegar para outra página
  3. Voltar para `/ipca-correcao/` e inserir o mesmo `session_id`
- **Resultado esperado:** Sessão recuperada do MongoDB; wizard retorna ao step correto com as propostas já geradas

#### TC-IPCA-020 — Consulta de status da sessão
- **Passos:**
  1. Após iniciar análise, chamar `GET /api/status-sessao/<session_id>`
- **Resultado esperado:** JSON com dados completos da sessão, incluindo `status`, `scenario_detected`, `gaps_identified`, `corrections_proposed`

#### TC-IPCA-021 — Sessão inexistente
- **Passos:**
  1. Chamar `/api/gerar-propostas` com `session_id` inválido ou expirado
- **Resultado esperado:** Resposta: `{"success": false, "error": "Sessão não encontrada"}` (não erro 500)

---

### 8.11 Casos de Teste — IPCA do Ano Vigente

#### TC-IPCA-022 — CCO elegível para IPCA vigente
- **Pré-condição:** CCO cujo aniversário do ano corrente já passou e ainda não recebeu correção
- **Passos:**
  1. Chamar `POST /api/avaliar-ipca-vigente` com o `cco_id`
- **Resultado esperado:**
  - `aplicavel: true`
  - Proposta com taxa do período e valor proposto calculado
  - `session_id` gerado no status `PREVIEW` (pronto para aprovação direta)

#### TC-IPCA-023 — CCO com aniversário ainda no futuro
- **Resultado esperado:** `aplicavel: false`; motivo: "Aniversário MM/AAAA ainda não atingido"; data do próximo aniversário exibida

#### TC-IPCA-024 — CCO que já recebeu IPCA vigente
- **Resultado esperado:** `aplicavel: false`; motivo: "Correção IPCA para MM/AAAA já existe"

#### TC-IPCA-025 — CCO com saldo zero ou negativo
- **Resultado esperado:** `aplicavel: false`; motivo: "CCO com saldo zero ou negativo" (não aplica IPCA em CCO sem saldo)

---

### 8.12 Casos de Teste — Cálculos e Integridade

#### TC-IPCA-026 — Validação matemática da taxa IPCA (Cenário 0)
- **Objetivo:** Garantir que o cálculo está matematicamente correto
- **Passos:**
  1. Identificar uma CCO com gap em período X
  2. Consultar manualmente a taxa IPCA do mês anterior ao aniversário (na coleção `ipca_entity`)
  3. Calcular manualmente: `valor_atual × taxa = valor_esperado`
  4. Comparar com o `proposed_value` retornado pela API
- **Resultado esperado:** Valor proposto pelo sistema = valor calculado manualmente (margem de erro < R$ 0,02 por arredondamento)

#### TC-IPCA-027 — Offset do mês da taxa (-1 mês)
- **Objetivo:** Confirmar que o sistema usa a taxa do mês **anterior** ao aniversário
- **Passos:**
  1. CCO com aniversário em Março/2023
  2. Verificar qual taxa é usada: deve ser `ipca_entity` com referência Fevereiro/2023
- **Resultado esperado:** `taxa_referencia = "02/2023"` na proposta gerada

#### TC-IPCA-028 — Aniversário em Janeiro (offset cruza virada de ano)
- **Passos:**
  1. Usar CCO com reconhecimento em Janeiro de algum ano (aniversário = Janeiro do próximo ano)
  2. Verificar taxa usada
- **Resultado esperado:** Taxa buscada em Dezembro do ano anterior (mês 1 - 1 = 0 → Dezembro do ano anterior); sem erro de índice ou mês inválido

#### TC-IPCA-029 — Taxa IPCA não encontrada para o período
- **Passos:**
  1. Tentar analisar CCO cujo gap aponta para período sem taxa cadastrada em `ipca_entity`
- **Resultado esperado:** Mensagem de erro descritiva: "Taxa IPCA não encontrada para MM/AAAA"; wizard não avança; CCO **não é alterada**

---

### 8.13 Matriz de Cenários vs Propostas Esperadas (Resumo)

| Cenário | Tipos de Proposta Esperados | Exige CORRECAO_PROMOTE |
|---------|----------------------------|------------------------|
| CENARIO_0 | `IPCA_ADDITION` (1+) | Sim (Step 3) |
| CENARIO_1 | `IPCA_ADDITION` + `IPCA_UPDATE` (1+) | Sim (Step 3) |
| CENARIO_2 | `IPCA_ADDITION` + `COMPENSATION` [+ `REACTIVATION`] | Sim (Step 3) |
| CENARIO_DUPLICATAS | `DUPLICATA_REMOVAL` + `DUPLICATA_ADJUSTMENT` [+ `REACTIVATION`] | Sim (Step 3) |
| CENARIO_IPCA_VIGENTE | `IPCA_ADDITION` [+ `CORRECTION_DATE_CHANGE`] | Sim (Step 3) |

> **Nota sobre `CORRECTION_DATE_CHANGE`:** Aparece no Cenário IPCA Vigente quando a última correção da CCO é do tipo `RETIFICACAO`. Serve para garantir que a nova correção IPCA fique **após** a retificação na ordenação cronológica interna.

---

## 9. Módulo 5 — Edição de CCO

> **Status:** Em implementação. Testes exploratórios são permitidos, mas não espere que todos os fluxos estejam completos. Reporte comportamentos inesperados.

### 8.1 Objetivo

Permitir edição manual controlada dos atributos de uma CCO e de suas correções monetárias, com validação automática das regras de negócio antes de salvar.

### 8.2 Funcionamento (parcialmente implementado)

```
Home Edição → Pesquisar CCO → Editar Atributos/Correções →
Validar → Revisar (diff) → [Salvar | Cancelar | Descartar]
```

**Abas de edição previstas:**
- Atributos raiz da CCO (contratoCpp, campo, faseRemessa, origemDosGastos)
- Edição de correções monetárias existentes
- Inclusão de novas correções monetárias
- Aba de validação com alertas e inconsistências

### 8.3 Endpoints

| Método | URL | Descrição |
|--------|-----|-----------|
| GET | `/cco-editor/` | Home |
| GET | `/cco-editor/pesquisar` | Pesquisa avançada |
| GET | `/cco-editor/editar/<cco_id>` | Editor |
| GET | `/cco-editor/revisar/<cco_id>` | Revisão/diff |
| POST | `/cco-editor/api/pesquisar` | API pesquisa |
| GET | `/cco-editor/api/carregar/<cco_id>` | Carrega dados da CCO |
| POST | `/cco-editor/api/salvar` | Salva edição |
| POST | `/cco-editor/api/preview` | Preview sem salvar |
| GET | `/cco-editor/api/edicoes-pendentes` | Edições pendentes |
| DELETE | `/cco-editor/api/descartar/<cco_id>` | Descarta edição |

### 8.4 Casos de Teste Exploratórios

#### TC-ED-001 — Carregamento da página de edição
- **Passos:**
  1. Acessar `/cco-editor/`
  2. Pesquisar uma CCO e abrir para edição
- **Verificar:** Campos carregados corretamente; abas presentes

#### TC-ED-002 — Preview de edição
- **Passos:**
  1. Alterar um atributo (ex: `faseRemessa`)
  2. Clicar em "Preview" ou "Visualizar alterações"
- **Verificar:** Diff exibido (de → para); sem salvar no banco

#### TC-ED-003 — Validação de campos obrigatórios
- **Passos:**
  1. Limpar campo obrigatório
  2. Tentar salvar
- **Verificar:** Mensagem de erro de validação (não erro 500)

#### TC-ED-004 — Descartar edição
- **Passos:**
  1. Fazer edições na CCO
  2. Clicar em "Descartar"
- **Verificar:** CCO volta ao estado original; item some da lista de edições pendentes

#### TC-ED-005 — Lista de edições pendentes
- **Passos:**
  1. Salvar uma edição como pendente
  2. Voltar para a home `/cco-editor/`
- **Verificar:** Edição pendente listada com ações (revisar, editar novamente, excluir)

---

## 10. Convenções de Reporte de Bugs

### 9.1 Severidades

| Severidade | Critério | Exemplo |
|-----------|----------|---------|
| **Crítico** | Sistema inoperante ou perda de dados | Erro 500 ao aplicar recálculo; dados corrompidos |
| **Alto** | Funcionalidade principal quebrada | Pesquisa não retorna resultados válidos; exportação falha |
| **Médio** | Funcionalidade degradada com workaround | Filtro de data não funciona; gráfico não carrega |
| **Baixo** | Problema de UX ou cosmético | Alinhamento incorreto; texto de botão errado |

### 9.2 Template de Bug Report

```
**Título:** [Módulo] Descrição curta do problema

**Severidade:** Crítico / Alto / Médio / Baixo

**Módulo:** Auth / CCO Timeline / Recálculo TP / Edição CCO

**Ambiente:**
- URL: http://localhost:5006/...
- Perfil do usuário: VIEWER / ANALYST / ADMIN
- Data/hora:

**Passos para reproduzir:**
1.
2.
3.

**Resultado obtido:**
(descrever o que aconteceu)

**Resultado esperado:**
(descrever o que deveria acontecer)

**Evidências:**
- Screenshot / vídeo
- Mensagem de erro completa (incluindo console do browser se aplicável)
- Request/Response da API (F12 → Network) se relevante

**Frequência:** Sempre / Intermitente / Uma vez
```

### 9.3 Checklist de Regressão (Smoke Test)

Executar este checklist após qualquer deploy ou merge significativo:

- [ ] `/login` carrega e aceita credenciais válidas
- [ ] Home (`/`) carrega sem erros
- [ ] `/pesquisa-ccos` retorna resultados
- [ ] Timeline de pelo menos 1 CCO carrega corretamente
- [ ] `/recalculo/pesquisar-ccos` lista CCOs
- [ ] Execução de recálculo básico completa sem erro 500
- [ ] Lista de temporários (`/recalculo/temporarios`) carrega
- [ ] Logout funciona e bloqueia acesso subsequente

---

## 11. Glossário

| Termo | Definição |
|-------|-----------|
| **CCO** | Conta Custo Óleo — entidade de saldo de gastos reconhecidos |
| **Remessa** | Conjunto de gastos mensais enviados por um operador |
| **TP (Track Participation)** | Fator de participação usado no cálculo dos valores reconhecidos |
| **IPCA** | Índice de Preços ao Consumidor Amplo — índice oficial de inflação |
| **IGPM** | Índice Geral de Preços do Mercado — índice alternativo de inflação |
| **correcoesMonetarias** | Array dentro da CCO que registra todas as alterações históricas |
| **Gap** | Ausência de correção monetária em um aniversário que deveria ter ocorrido |
| **Staging** | Ambiente intermediário onde CCOs corrigidas aguardam promoção para produção |
| **Promoção** | Ato de mover uma correção de staging para o banco de produção |
| **MEN/ROP/RAD/REC/REV** | Fases sequenciais do processo de reconhecimento de remessa |
| **flgRecuperado** | Flag booleano que indica se a CCO foi totalmente recuperada (saldo = 0) |
| **valorReconhecidoComOH** | Valor principal da CCO: valor reconhecido + overhead aplicado |
| **Overhead (OH)** | Percentual adicional aplicado sobre valores reconhecidos (exploração ou produção) |
| **CORRECAO_PROMOTE** | Permissão necessária para aplicar recálculos e promover correções definitivamente |
| **Rate Limit** | Limitação de requisições por período (ex: exportação Excel máximo 1x/minuto) |
| **Gap** | Aniversário de correção monetária que deveria ter ocorrido mas não ocorreu |
| **Cenário 0** | Gap simples — apenas inserir a correção faltante |
| **Cenário 1** | Gap com correção posterior calculada sobre base errada — requer recalcular em cascata |
| **Cenário 2** | Gap com recuperação posterior — requer compensação e possível reativação da CCO |
| **Cenário Duplicatas** | Mesma correção IPCA/IGPM lançada mais de uma vez no mesmo período |
| **Efeito Cascata** | Impacto de um erro em uma correção sobre todas as correções subsequentes, pois cada uma usa o saldo acumulado da anterior |
| **CorrectionSession** | Objeto de sessão persistido no MongoDB que guarda o estado do wizard em andamento |
| **IPCA_ADDITION** | Tipo de proposta: adicionar nova correção IPCA em período sem correção |
| **IPCA_UPDATE** | Tipo de proposta: recalcular correção IPCA existente (base estava incorreta) |
| **COMPENSATION** | Tipo de proposta: compensar impacto sobre recuperação feita com base errada |
| **REACTIVATION** | Tipo de proposta: reativar CCO que estava marcada como totalmente recuperada |
| **Offset mês taxa** | Regra de que a taxa IPCA usada no aniversário do mês M é a taxa do mês M-1 |

---

*Documento gerado para uso interno da equipe de QA. Não compartilhar externamente.*

*Versão 1.0 — Junho 2026*
