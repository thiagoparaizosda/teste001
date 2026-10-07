---
spec_id: FEAT-000
title: "Endpoint GET /api/v1/health com informações do serviço"
status: Draft
# Status possíveis: Draft | In Review | Approved | Implementing | Done | Cancelled
type: feature
created_at: 2026-07-31
created_by: "@tech-lead"
approved_by: ""
approved_at: ""
sprint: "2026-Q3-S1"
related_specs: []
related_adrs: []
---

# FEAT-000: Endpoint GET /api/v1/health com informações do serviço

> Esta é a spec de exemplo copiada por `maestro init` como ponto de partida.
> Ela fica com `status: Draft` propositalmente — sirva-se dela para aprender
> o formato, depois delete ou substitua pela primeira spec real do projeto.

## 1. Contexto e Motivação

O time de infraestrutura precisa de um endpoint simples para verificar,
manualmente ou via monitoramento externo, se um serviço está no ar e qual
versão está rodando em cada ambiente — sem depender de abrir o Actuator cru
(`/actuator/health`), que expõe mais detalhes internos do que o necessário
para esse público.

Hoje, para saber a versão publicada em homologação ou produção, alguém
precisa consultar o pipeline de CI/CD ou perguntar no time. Um endpoint de
health check com metadados básicos resolve isso com uma chamada HTTP.

## 2. Escopo

### 2.1 Está no escopo
- Endpoint `GET /api/v1/health` público (sem autenticação)
- Retornar status do serviço, nome, versão e horário do servidor
- Endpoint leve — sem checar dependências externas (banco, filas, etc.)

### 2.2 NÃO está no escopo (decisão consciente)
- Health checks de liveness/readiness do Kubernetes — já cobertos pelo
  Spring Boot Actuator (`/actuator/health/liveness` e `/readiness`), esta
  spec não substitui isso
- Verificação de dependências externas (banco de dados, filas, serviços
  downstream) — ficaria em uma spec futura de "health check profundo" se a
  necessidade aparecer
- Autenticação/autorização no endpoint — ele é intencionalmente público para
  ser consultado por load balancers e ferramentas de monitoramento externas

## 3. Definição da Solução

### 3.1 Arquitetura

Um novo `HealthController` na camada de apresentação, sem service dedicado
(a lógica é trivial o suficiente para viver no controller — não é violação
do padrão "sem lógica de negócio no controller", pois não há regra de
negócio aqui, apenas leitura de metadados de build).

### 3.2 Contrato de API

```yaml
GET /api/v1/health
Response:
  200:
    status: string      # sempre "UP" se o serviço respondeu
    service: string      # nome do serviço, ex. "pedidos-service"
    version: string       # versão do build, ex. "1.4.2"
    timestamp: ISO8601   # horário do servidor no momento da resposta
```

Exemplo de resposta:
```json
{
  "status": "UP",
  "service": "pedidos-service",
  "version": "1.4.2",
  "timestamp": "2026-07-31T14:32:05Z"
}
```

### 3.3 Regras de Negócio
- RN-001: o endpoint sempre responde `200 OK` com `status: "UP"` enquanto o
  processo da aplicação estiver rodando — não há cenário de erro esperado
  para este endpoint.
- RN-002: o campo `version` reflete a versão de build empacotada na
  aplicação (ex. via `build.gradle`/`pom.xml` ou variável de ambiente
  injetada no deploy), nunca um valor hardcoded no código-fonte.

### 3.4 Modelo de Dados

Nenhuma entidade nova ou persistida. `HealthResponse` é um DTO somente de
saída (`record` em Java / `BaseModel` em Python), sem tabela associada.

## 4. Restrições de Implementação

### Stack obrigatória
- [x] Linguagem/framework: Java 21 + Spring Boot 3.x (adaptar para
      Python 3.12 + FastAPI se o serviço alvo for Python)
- [x] Padrão de logging: conforme `.devspec/rules/coding-standards.md`
- [x] Tratamento de erros: não aplicável — endpoint não tem caminho de erro
- [x] Não criar dependências novas sem aprovação

### O que NÃO fazer
- Não criar abstrações desnecessárias (sem `HealthService`, sem
  `HealthRepository` — a lógica cabe no controller)
- Não duplicar informações já expostas pelo Actuator
- Não adicionar autenticação a este endpoint — é público por design

### LLM a usar
- [x] Ollama local (dados sensíveis / regras de negócio) — mesmo sem dados
      sensíveis aqui, é o padrão do time; usar Ollama por consistência
- [ ] Azure OpenAI (código interno, sem dados críticos)
- [ ] API externa (código genérico, com aprovação)

## 5. Critérios de Aceite

- [ ] `GET /api/v1/health` retorna `200` com `status`, `service`, `version`
      e `timestamp` preenchidos
- [ ] `version` é lido de metadado de build, não hardcoded
- [ ] Teste unitário cobrindo a resposta do endpoint
- [ ] Sem breaking changes em contratos existentes
- [ ] Cobertura de testes ≥ 80% na classe nova
- [ ] SecurityAgent scan sem itens críticos (endpoint público é esperado e
      documentado nesta spec, não deve ser reportado como falha)

## 6. Impactos e Dependências

- **Serviços afetados:** apenas o serviço onde o endpoint for adicionado
- **Migrações de banco:** não
- **Feature flags:** não
- **Breaking changes:** não

## 7. Histórico de Decisões

| Data | Decisão | Motivo |
|------|---------|--------|
| 2026-07-31 | Endpoint público, sem autenticação | Precisa ser consultável por load balancer e monitoramento externo sem credenciais |

## 8. Contexto para o Agente de IA

```
Você está implementando [FEAT-000] no serviço [nome-do-serviço-alvo].
Stack: Java 21 + Spring Boot 3.x
Estrutura do projeto: controller/, service/, repository/, dto/response/
Arquivos existentes relevantes: nenhum — este é um endpoint novo e isolado
Arquivos protegidos (não alterar): GlobalExceptionHandler (não é necessário
  para este endpoint, mas não deve ser modificado por esta spec)
Padrões obrigatórios: ver .devspec/rules/coding-standards.md
```

## 9. Log de Implementação IA

<!-- Spec ainda em Draft — preencher durante a implementação real -->

| Data | Agente/Modelo | Prompt/Comando usado | Ajustes manuais |
|------|--------------|----------------------|-----------------|
| | | | |
