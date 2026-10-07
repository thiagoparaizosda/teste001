# Matriz de Autenticação, Perfis (Roles) e Permissões — Portal PPSA (CCO Tools)

> Última atualização: 2026-08-11 (inclui a role `CLIENT`, adicionada nesta data)
> Público-alvo: time de QA (validação/testes) e tech leads (configuração de usuários)
> Fonte de verdade: código-fonte em [`app/models/permission.py`](../app/models/permission.py),
> [`app/middleware/auth_middleware.py`](../app/middleware/auth_middleware.py) e
> [`app/models/user.py`](../app/models/user.py). Este documento descreve o comportamento real
> observado no código nesta data — qualquer mudança nesses arquivos pode desatualizar a matriz
> abaixo; revalidar antes de usar como referência definitiva.

Ver também: [guia_qa.md](guia_qa.md) — seção 4 (Controle de Acesso e Perfis) e seção 5 (Módulo de
Autenticação), que remetem a este documento para o detalhamento completo.

---

## 1. Conceitos

O sistema usa dois níveis de controle de acesso, combinados:

- **Role (perfil)** — um papel amplo atribuído ao usuário: `VIEWER`, `ANALYST`, `ADMIN` ou
  `CLIENT` (ver seção 1.2).
- **Permission (permissão granular)** — uma capacidade específica, ex.: `cco.edit`,
  `correcao.promote`. Cada Role concede um conjunto fixo de Permissions (ver seção 3).

O backend **nunca** verifica o Role diretamente nas rotas — todas as rotas protegidas exigem uma
**Permission** (`@require_permission(Permission.X)`). O Role só existe como um agrupamento
conveniente de Permissions — **exceto `CLIENT`**, que é tratada de forma diferente (não concede
Permission nenhuma; ver seção 1.2).

### 1.1 Modelo "duplo" de concessão (importante para QA)

`User.has_permission()` ([`app/models/user.py`](../app/models/user.py)) aceita **duas formas** de
uma "role" do usuário conceder uma permissão:

1. **Baseado em Role** — se `role_name` (string vinda do JWT/DB) corresponder a um dos valores do
   enum `Role` (`ADMIN`, `ANALYST`, `VIEWER`), aplica-se a matriz `ROLE_PERMISSIONS` (seção 3).
2. **Concessão direta (grant)** — se `role_name` for igual ao **nome** (`CCO_EDIT`) ou ao
   **valor** (`cco.edit`) de uma `Permission`, o acesso é concedido diretamente, **sem** passar
   pela Role.

Ou seja: é possível testar cenários de permissão avulsa atribuindo ao usuário, no lugar de
(ou além de) uma Role, uma string como `CCO_EDIT` ou `cco.edit` — o sistema trata isso como grant
direto daquela permissão específica, sem conceder as demais permissões da role `ANALYST`. Isso é
útil para QA testar combinações que não existem como Role padrão (ex.: usuário que só pode
exportar relatórios).

### 1.2 A role `CLIENT` — identificação de usuário externo, não um nível de permissão

O sistema é usado tanto pela equipe interna de suporte quanto por um número menor de usuários
**clientes** (externos). `CLIENT` foi adicionada como uma **role de identificação**, não como mais
um degrau na hierarquia VIEWER→ANALYST→ADMIN:

- `Role.CLIENT` **não aparece** em `ROLE_PERMISSIONS` com nenhuma permissão associada
  (`ROLE_PERMISSIONS[Role.CLIENT] == []`) — ela sozinha não libera nada.
- O restante do acesso do usuário continua vindo normalmente de **outras** roles/permissões que
  ele também possua (ex.: um cliente pode ter as roles `['ANALYST', 'CLIENT']` e manter todas as
  capacidades de `ANALYST`).
- A única função de `CLIENT` é **negar** o acesso a um conjunto fixo de recursos de uso interno,
  **independentemente** de quais outras permissões o usuário tenha — via o método
  `User.is_client()` e o decorator `deny_client()`
  ([`app/middleware/auth_middleware.py`](../app/middleware/auth_middleware.py)).
- `deny_client()` sempre inclui `login_required()` internamente (assim como `require_permission`),
  então as rotas que o usam também passam a exigir autenticação, mesmo se não tivessem antes.

**Recursos hoje bloqueados para `CLIENT`** (ver decorator `@deny_client()` aplicado a cada rota):

| Recurso | Blueprint / rotas |
|---|---|
| Análise de Remessas x CCOs | `analise_ui.*` (todas as rotas do blueprint, incluindo a página `/analise-remessas` e todas as APIs de suporte) |
| Verificação de OH | `verificacao_oh.*` (`/verificacao-oh/*`) |
| Verificação de TP | `verificacao_tp.*` (`/verificacao-tp/*`) |

Para adicionar um novo recurso à lista de bloqueios para `CLIENT` no futuro, basta acrescentar
`@deny_client()` ao(s) decorator(s) da(s) rota(s) correspondente(s) e replicar a mesma condição
`{% if not current_user.is_client() %}` no template do menu/card que a expõe (ver seção 5).

---

## 2. Como os perfis/roles chegam ao usuário

Definido em [`app/routes/auth_routes.py`](../app/routes/auth_routes.py), no login:

1. O usuário informa credenciais em `/login`; elas são validadas contra o **API Gateway externo**
   (`URL_AUTH_GATEWAY`), que retorna um JWT (`id_token`).
2. A lista de roles do usuário é obtida de uma das duas formas, conforme a flag
   `Config.ROLES_FROM_DB` (env var `ROLES_FROM_DB`):
   - **`ROLES_FROM_DB=False`** → as roles vêm do **claim `auth`** dentro do próprio JWT
     (formato `ROLE_ADMIN,ROLE_ANALYST`, com o prefixo `ROLE_` removido antes de guardar).
   - **`ROLES_FROM_DB=True`** (padrão) → as roles são buscadas na coleção MongoDB
     `jhi_user` (banco `sgppGateway`, configurável via `MONGO_URI_GATEWAY` /
     `MONGO_DATABASE_GATEWAY` / `COLECAO_USUARIOS`), no campo `authorities` do documento do
     usuário (busca por `login == email`), também removendo o prefixo `ROLE_` de cada
     `authorities[i]._id`.
3. As roles resultantes (`roles_list`) são gravadas em `session['user_data']['roles']` e usadas
   em todas as requisições seguintes (via `g.current_user` / `current_user`, ver
   [`app/__init__.py`](../app/__init__.py)).

**Para QA:** ao testar um cenário de perfil, confirmar qual modo (`ROLES_FROM_DB`) está ativo no
ambiente de testes — a origem do dado difere completamente (JWT vs. banco `sgppGateway`).

### 2.1 Modo `DISABLE_AUTH=True` (ambiente local/dev)

Quando `Config.DISABLE_AUTH == 'True'` (env var `DISABLE_AUTH`, ver
[`app/config.py`](../app/config.py)):

- `login_required()` deixa passar qualquer requisição, sem checar sessão/token.
- `require_permission(...)` também deixa passar **sempre**, independente de qualquer Role/
  Permission — a checagem de permissão é pulada por completo.
- `get_current_user_id()` retorna sempre o usuário fixo `default_user_portal`.

**Implicação para QA:** testes de controle de acesso (perfil negado, 403, etc.) **exigem**
`DISABLE_AUTH=False` no ambiente de testes. Com `DISABLE_AUTH=True`, todo usuário tem acesso
irrestrito a tudo — é um modo de conveniência para desenvolvimento local, não para validar RBAC.

---

## 3. Perfis (Roles) × Permissões

Matriz definida em `ROLE_PERMISSIONS` ([`app/models/permission.py`](../app/models/permission.py)):

| Permissão | `VIEWER` | `ANALYST` | `ADMIN` | `CLIENT` |
|---|:---:|:---:|:---:|:---:|
| `cco.view` (`CCO_VIEW`) | ✅ | ✅ | ✅ | — |
| `cco.edit` (`CCO_EDIT`) | ❌ | ✅ | ✅ | — |
| `cco.delete` (`CCO_DELETE`) | ❌ | ❌ | ✅ | — |
| `correcao.view` (`CORRECAO_VIEW`) | ✅ | ✅ | ✅ | — |
| `correcao.create` (`CORRECAO_CREATE`) | ❌ | ✅ | ✅ | — |
| `correcao.promote` (`CORRECAO_PROMOTE`) | ❌ | ❌ | ✅ | — |
| `report.export` (`REPORT_EXPORT`) | ❌ | ✅ | ✅ | — |
| `audit.view` (`AUDIT`) | ❌ | ❌ | ✅ | — |

> Coluna `CLIENT` marcada como "—" (não "❌") propositalmente: `CLIENT` não define nenhuma dessas
> permissões por si só — o resultado real depende de quais outras roles o usuário também tiver.
> `CLIENT` apenas **subtrai** o acesso aos 3 recursos da seção 1.2, por cima de qualquer resultado
> desta tabela. Ver seção 1.2.

> **Nota de divergência:** o guia de QA (seção 4.1) menciona `USER_VIEW` e `USER_MANAGE` — essas
> permissões **não existem** no código atual (`app/models/permission.py`). Não usar essas
> permissões em casos de teste; a lista acima é a que está de fato implementada.

### 3.1 Catálogo de permissões (descrição funcional)

| Permissão | O que libera na prática |
|---|---|
| `CCO_VIEW` | Ver CCOs, pesquisar CCOs, abrir timeline, ver dashboards/análises de remessas |
| `CCO_EDIT` | Editar CCOs manualmente (Editor de CCOs) **e** ver o botão "Recalcular" na tela de Timeline |
| `CCO_DELETE` | Excluir CCOs (permissão prevista no modelo; não há rota que a exija hoje — ver seção 6) |
| `CORRECAO_VIEW` | Ver telas de recálculo/correção já existentes (resultado, temporários) |
| `CORRECAO_CREATE` | Executar recálculo de TP, iniciar/rodar o wizard de Correção IPCA/IGPM |
| `CORRECAO_PROMOTE` | Acessar e usar o módulo inteiro de Promoção de Correções IPCA/IGPM |
| `REPORT_EXPORT` | Exportar relatórios/planilhas (Excel/CSV) — ver observação na seção 6 sobre enforcement real |
| `AUDIT` | Ver o menu e a tela de Auditoria (logs de ações do sistema) |

---

## 4. Como o acesso é bloqueado (comportamento observado)

- **Sem login e rota protegida:** redireciona para `/login` (`login_required()`).
- **Logado mas sem a permissão exigida (`require_permission`):**
  - Se a requisição espera JSON (`request.is_json`): resposta `403` com
    `{"success": false, "error": "É necessário a permissão <perm> para acessar essa funcionalidade."}`.
  - Caso contrário (navegação normal): `flash()` com a mesma mensagem (categoria `danger`) e
    **redirecionamento para a Home (`/`)** — não existe uma página dedicada de "Acesso Negado /
    403"; a home volta a exibir normalmente, mas com o flash de erro.
- **Token expirado:** flash "Sessão expirada. Por favor, logue novamente." + redirect para
  `/login`.

## 5. Visibilidade da interface (menu e botões) — atenção especial para QA

A maior parte da interface (menu principal, cards da Home) **não é ocultada por perfil**. Isso é
importante para o time de QA não esperar um "menu dinâmico por perfil" completo — a lógica de
ocultação condicional encontrada no código é:

| Onde | Condição | Efeito |
|---|---|---|
| Menu superior — item "Auditoria" ([`base.html`](../app/templates/base.html)) | `current_user.has_permission(Permission.AUDIT)` | Link só aparece para quem tem `AUDIT` (na prática, só `ADMIN`) |
| Tela de Timeline — botão "Recalcular" ([`cco_timeline.html`](../app/templates/cco_timeline.html)) | `current_user.has_permission(Permission.CCO_EDIT)` | Botão só aparece para quem tem `CCO_EDIT` |
| Menu → "Análises" → item "Análise Remessas x CCOs" ([`base.html`](../app/templates/base.html)) | `not current_user.is_client()` | Item some inteiramente para `CLIENT` |
| Menu → "Ferramentas" → bloco "Qualidade" (Verificação de OH e Verificação de TP) ([`base.html`](../app/templates/base.html)) | `not current_user.is_client()` | Cabeçalho + os 2 itens somem inteiramente para `CLIENT` |
| Home — card "Análise Remessas x CCOs" ([`index.html`](../app/templates/index.html)) | `not current_user.is_client()` | Card some inteiramente para `CLIENT` |

**Todos os demais itens de menu (Pesquisa de CCOs, Recálculo TP, Verificar Correções, Promover
Correções, Editor de CCOs) aparecem para qualquer usuário logado, independentemente do perfil.** O
bloqueio real acontece só ao clicar e a rota backend recusar (flash + redirect para Home, conforme
seção 4). **Caso de teste recomendado:** logar como `VIEWER` e confirmar que o menu mostra
"Promover Correções", mas ao clicar o usuário é redirecionado para a Home com mensagem de
permissão negada — esse é o comportamento correto e esperado hoje, não um bug (mas vale confirmar
com o produto se esse é o UX desejado). Para `CLIENT`, o comportamento é diferente e mais estrito
por design: os 3 recursos da seção 1.2 **não aparecem no menu nem no dashboard**, e tentar acessar
a URL diretamente também é bloqueado no backend (defesa em profundidade, não só ocultação de UI).

### 5.1 Inconsistência entre botão e ação (achado de código)

O botão "Recalcular" na Timeline é exibido para quem tem `CCO_EDIT` (seção 5), mas a submissão
efetiva do recálculo (`POST /recalculo/api/executar-recalculo`) exige `CORRECAO_CREATE`. Como
`ANALYST` e `ADMIN` têm as duas permissões, isso não é perceptível nesses perfis — mas um usuário
com concessão direta de apenas `CCO_EDIT` (ver seção 1.1) veria o botão e receberia 403 ao usá-lo.
Vale um caso de teste específico para essa combinação.

---

## 6. Matriz de módulos, telas e permissão exigida

Prefixos de URL por blueprint: `portal_ui` → `/`, `analise_ui` → `/`, `recalculo_ui` →
`/recalculo`, `ipca_correcao` → `/ipca-correcao`, `ipca_promocao` → `/ipca-promocao`,
`cco_editor` → `/cco-editor`, `audit` → `/audit`, `verificacao_oh` → `/verificacao-oh`,
`verificacao_tp` → `/verificacao-tp`.

| Módulo / Tela | Rota principal | Permissão exigida | `VIEWER` | `ANALYST` | `ADMIN` | `CLIENT` combinado com a role acima |
|---|---|---|:---:|:---:|:---:|:---:|
| Home | `GET /` | `CCO_VIEW` | ✅ | ✅ | ✅ | ✅ |
| Pesquisa de CCOs | `GET /pesquisa-ccos` | `CCO_VIEW` | ✅ | ✅ | ✅ | ✅ |
| Timeline de CCO | `GET /cco-timeline/<id>` | `CCO_VIEW` | ✅ | ✅ | ✅ | ✅ |
| Timeline — botão Recalcular (UI) | — (renderização condicional) | `CCO_EDIT` | ❌ | ✅ | ✅ | ✅ (se a outra role tiver `CCO_EDIT`) |
| Dashboard | `GET /dashboard` | `CCO_VIEW` | ✅ | ✅ | ✅ | ✅ |
| **Análise de Remessas x CCOs** (**todo o módulo**) | `/analise-remessas`, `analise_ui.*` | `CCO_VIEW` **+ bloqueado para `CLIENT`** (`@deny_client()`) | ✅ | ✅ | ✅ | ❌ **sempre** |
| Exportação de listas/timelines (Excel) | `POST /api/ccos/export`, `GET /api/cco-timeline/<id>/export` | `CCO_VIEW` (**não** `REPORT_EXPORT`, ver observação) | ✅ | ✅ | ✅ | ✅ |
| Editor de CCOs (todas as rotas) | `/cco-editor/*` | `CCO_EDIT` | ❌ | ✅ | ✅ | ✅ (se a outra role tiver `CCO_EDIT`) |
| Recálculo de TP — visualizar (index, pesquisar, resultado, temporários) | `/recalculo/`, `/recalculo/pesquisar-ccos`, `/recalculo/resultado/<k>`, `/recalculo/temporarios` | `CORRECAO_VIEW` | ✅ | ✅ | ✅ | ✅ |
| Recálculo de TP — executar / salvar / aplicar | `/recalculo/executar/<id>`, `POST /api/executar-recalculo`, `POST /api/aplicar-definitivo`, etc. | `CORRECAO_CREATE` | ❌ | ✅ | ✅ | ✅ (se a outra role tiver `CORRECAO_CREATE`) |
| Correção IPCA/IGPM (**todo o módulo**, inclusive só visualizar) | `/ipca-correcao/*` | `CORRECAO_CREATE` | ❌ | ✅ | ✅ | ✅ (se a outra role tiver `CORRECAO_CREATE`) |
| Promoção de Correções IPCA/IGPM (**todo o módulo**, inclusive só visualizar) | `/ipca-promocao/*` | `CORRECAO_PROMOTE` | ❌ | ❌ | ✅ | ✅ (na prática só `ADMIN+CLIENT`) |
| Auditoria (logs) | `GET /audit` | `AUDIT` | ❌ | ❌ | ✅ | ✅ (na prática só `ADMIN+CLIENT`) |
| **Verificação de OH** (**todo o módulo**) | `/verificacao-oh/*` | `CCO_VIEW` **+ bloqueado para `CLIENT`** (`@deny_client()`) — ver seção 6.1 | ✅ | ✅ | ✅ | ❌ **sempre** |
| **Verificação de TP** (**todo o módulo**) | `/verificacao-tp/*` | `CCO_VIEW` **+ bloqueado para `CLIENT`** (`@deny_client()`) — ver seção 6.1 | ✅ | ✅ | ✅ | ❌ **sempre** |

> Coluna `CLIENT`: como `CLIENT` não concede nem retira permissões por si só (seção 1.2), o
> resultado depende da(s) outra(s) role(s) do usuário — daí "✅ (se a outra role tiver X)". As 3
> linhas em negrito são exceção: ficam **sempre** bloqueadas para `CLIENT`, mesmo que a outra role
> do usuário seja `ADMIN`.

**Observação sobre exportação (`REPORT_EXPORT`):** apesar de `REPORT_EXPORT` existir no modelo e
constar na permissão do `ANALYST`/`ADMIN`, **nenhuma rota de exportação encontrada no código a
exige de fato** — as exportações de CCO/timeline usam `CCO_VIEW`. Ou seja, hoje um `VIEWER`
também consegue exportar Excel/CSV das telas que consegue visualizar. Vale confirmar com o
produto se isso é intencional antes do time de QA reportar como bug — o comportamento atual do
código é este.

### 6.1 ✅ Gap corrigido em 2026-08-11 — módulos que ficavam sem controle de acesso

Até esta data, ao contrário de todos os outros blueprints, `verificacao_oh` (Verificação de OH) e
`verificacao_tp` (Verificação de TP) não possuíam nenhum decorator `@login_required` ou
`@require_permission` em nenhuma de suas rotas (páginas e APIs) — eram acessíveis **mesmo sem
login**, independentemente de `DISABLE_AUTH`.

Isso foi corrigido como pré-requisito direto para o bloqueio de `CLIENT` funcionar de verdade: sem
exigir autenticação, não haveria usuário/roles para checar `is_client()` contra. Todas as rotas de
`verificacao_oh_routes.py` e `verificacao_tp_routes.py` agora usam
`@require_permission(Permission.CCO_VIEW)` + `@deny_client()`, no mesmo padrão dos demais módulos
de visualização (ex.: Pesquisa de CCOs). Ou seja: hoje exigem login + `CCO_VIEW`, e adicionalmente
bloqueiam `CLIENT`, mesmo que o usuário tenha `CCO_VIEW` por outra role.

**Para QA:** este é um bom caso de teste transversal — confirmar que um usuário `VIEWER`/`ANALYST`/
`ADMIN` **sem** a role `CLIENT` consegue acessar `/verificacao-oh/` e `/verificacao-tp/`
normalmente, e que tentar acessar essas URLs sem login redireciona para `/login` (antes, não
redirecionava).

---

## 7. Como montar cenários de teste (usuários por perfil)

Depende do modo configurado (seção 2):

**Com `ROLES_FROM_DB=True` (padrão):** garantir no MongoDB (`sgppGateway.jhi_user`) um usuário
com `authorities` contendo o(s) `_id` desejado(s), ex.: `{"_id": "ROLE_VIEWER"}`,
`{"_id": "ROLE_ANALYST"}`, `{"_id": "ROLE_ADMIN"}` — o prefixo `ROLE_` é removido automaticamente
ao carregar. Para simular um cliente, adicionar **também** `{"_id": "ROLE_CLIENT"}` junto da role
principal do usuário (ex.: um cliente com acesso de `ANALYST` teria `authorities` com
`ROLE_ANALYST` **e** `ROLE_CLIENT`).

**Com `ROLES_FROM_DB=False`:** o JWT emitido pelo Gateway externo deve conter no claim `auth` uma
string como `ROLE_VIEWER,ROLE_ANALYST` (separada por vírgula); isso depende de configuração no
lado do Gateway/JHipster, fora deste repositório.

**Para testar uma permissão avulsa (fora das 3 roles padrão):** atribuir ao usuário, como se fosse
uma role, o nome (`CCO_EDIT`) ou valor (`cco.edit`) da permissão desejada — ver seção 1.1.

### 7.1 Sugestão de matriz mínima de contas de teste

| Conta de teste | Roles atribuídas | Objetivo do teste |
|---|---|---|
| `qa.viewer` | `VIEWER` | Confirmar que só visualiza; toda ação de escrita/promoção retorna 403/flash |
| `qa.analyst` | `ANALYST` | Confirmar edição de CCO, recálculo de TP e correção IPCA funcionam; promoção e auditoria continuam bloqueadas |
| `qa.admin` | `ADMIN` | Confirmar acesso total, incluindo Promoção e Auditoria |
| `qa.sem_role` | (nenhuma) | Confirmar que usuário autenticado sem nenhuma role só acessa rotas públicas (idealmente nenhuma, exceto os módulos do achado 6.1) |
| `qa.grant_avulso` | grant direto `CCO_EDIT` (sem role) | Validar o caso da seção 5.1 (botão aparece, ação de recálculo pode falhar por faltar `CORRECAO_CREATE`) |
| `qa.client_analyst` | `ANALYST` + `CLIENT` | Confirmar que mantém todas as capacidades de `ANALYST`, **exceto** os 3 recursos da seção 1.2 (menu não mostra, URL direta bloqueia) |
| `qa.client_admin` | `ADMIN` + `CLIENT` | Confirmar que mesmo `ADMIN` perde acesso aos 3 recursos quando tem `CLIENT` — validar que a negação vale mesmo para o perfil mais privilegiado |
| `qa.client_puro` | somente `CLIENT` | Confirmar que sem nenhuma outra role o usuário não acessa nada que exija permissão (já que `CLIENT` não concede nenhuma) além de, obviamente, também não acessar os 3 recursos bloqueados |

---

## 8. Resumo rápido (cola para o time de QA)

- `VIEWER` → só visualiza CCOs e correções já existentes. Nenhuma ação de escrita.
- `ANALYST` → visualiza + edita CCO + executa recálculo/correção IPCA + exporta relatórios. Não
  promove correções, não vê auditoria.
- `ADMIN` → acesso completo, incluindo promoção de correções e auditoria.
- `CLIENT` → **não é um nível de permissão**, é uma marcação combinada com outra role (ex.:
  `ANALYST` + `CLIENT`). Mantém tudo que a outra role permite, **exceto** Análise de Remessas x
  CCOs, Verificação de OH e Verificação de TP — esses 3 ficam bloqueados sempre, mesmo para
  `ADMIN` + `CLIENT`, e somem do menu/dashboard (não só do backend).
- Menu **não** esconde módulos por perfil (exceto Auditoria e os 3 recursos bloqueados para
  `CLIENT`) — o bloqueio dos demais é ao clicar/acessar, não na exibição do menu.
- `DISABLE_AUTH=True` desliga toda a checagem — não usar para testar RBAC.
- Verificação de OH e Verificação de TP passaram a exigir login + `CCO_VIEW` (antes eram abertas
  sem autenticação — corrigido em 2026-08-11 junto com a implementação de `CLIENT`, ver 6.1).
