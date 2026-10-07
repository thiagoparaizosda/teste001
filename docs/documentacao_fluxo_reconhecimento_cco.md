# Documentação Técnica e de Negócio
# Fluxo de Reconhecimento de Custos e Geração de CCO — Sistema SGPP

> **Versão**: 1.0  
> **Referências**: regras_remessas_ccos.md · PPSA_Modelo_de_Dados_BPM_RCO_v2.pdf · registros de exemplo das coleções MongoDB  
> **Escopo**: Processo completo desde o envio da remessa pelo operador até a recuperação total da CCO

---

## Sumário

1. [Visão Geral do Sistema](#1-visão-geral-do-sistema)
2. [Atores e Responsabilidades](#2-atores-e-responsabilidades)
3. [Entidades e Coleções MongoDB](#3-entidades-e-coleções-mongodb)
4. [Fluxo Completo de Reconhecimento](#4-fluxo-completo-de-reconhecimento)
   - 4.1 [Envio da Remessa pelo Operador](#41-envio-da-remessa-pelo-operador)
   - 4.2 [Criação da remessa_entity](#42-criação-da-remessa_entity)
   - 4.3 [Geração da remessa_derivada_campo_entity](#43-geração-da-remessa_derivada_campo_entity)
   - 4.4 [Processo de Reconhecimento por Fases](#44-processo-de-reconhecimento-por-fases)
   - 4.5 [Geração da CCO (conta_custo_oleo_entity)](#45-geração-da-cco-conta_custo_oleo_entity)
5. [Estrutura Detalhada das Entidades](#5-estrutura-detalhada-das-entidades)
   - 5.1 [contrato_entity](#51-contrato_entity)
   - 5.2 [remessa_entity](#52-remessa_entity)
   - 5.3 [remessa_derivada_campo_entity](#53-remessa_derivada_campo_entity)
   - 5.4 [conta_custo_oleo_entity](#54-conta_custo_oleo_entity)
   - 5.5 [Entidades de Relatório](#55-entidades-de-relatório)
6. [Regras de Negócio Críticas](#6-regras-de-negócio-críticas)
   - 6.1 [Numeração de Remessa](#61-numeração-de-remessa)
   - 6.2 [Cálculo do Tract Participation (TP)](#62-cálculo-do-tract-participation-tp)
   - 6.3 [Cálculo de OverHead (OH)](#63-cálculo-de-overhead-oh)
   - 6.4 [Geração e Consolidação da CCO](#64-geração-e-consolidação-da-cco)
   - 6.5 [Correções Monetárias](#65-correções-monetárias)
   - 6.6 [Processo de Recuperação](#66-processo-de-recuperação)
7. [Ciclo de Vida da CCO](#7-ciclo-de-vida-da-cco)
8. [Relacionamentos entre Entidades](#8-relacionamentos-entre-entidades)
9. [Tipos e Classificações de Referência](#9-tipos-e-classificações-de-referência)
10. [Pontos de Atenção e Armadilhas Técnicas](#10-pontos-de-atenção-e-armadilhas-técnicas)

---

## 1. Visão Geral do Sistema

O **SGPP (Sistema de Gestão do Pré-Sal Petróleo)** gerencia o processo de **Reconhecimento de Custo em Óleo (RCO)** para contratos de partilha de produção no Pré-Sal Brasileiro. O processo central é a análise, validação e reconhecimento de gastos enviados pelos operadores, que posteriormente se convertem em créditos recuperáveis pelos operadores a partir da produção de petróleo.

### Conceito de "Custo Óleo"

No regime de partilha de produção, o operador tem direito a recuperar os gastos incorridos nas fases de exploração e produção usando parte do petróleo produzido. O processo de reconhecimento determina **quais gastos são legítimos e em quais valores**, gerando as **Contas de Custo Óleo (CCOs)** que funcionam como um saldo de crédito a ser progressivamente descontado da produção mensal.

### Diagrama de Fluxo Macro

```
Operador
   │
   │ envia planilha de gastos
   ▼
[remessa_entity]  ──── consulta ────► [contrato_entity]
   │                                       (TP, projetos, campos)
   │ gera (1 ou N, por campo/TP)
   ▼
[remessa_derivada_campo_entity]
   │
   │ ao fim do reconhecimento por fase
   ▼
[conta_custo_oleo_entity]  ──────────► [relatorio_consolidacao_sintese_entity]
   │                                   [relatorio_consolidacao_sintese_remessa_entity]
   │ anualmente (IPCA/IGPM)
   │ mensalmente (RECUPERACAO)
   ▼
[correcoesMonetarias] (array dentro da CCO)
```

---

## 2. Atores e Responsabilidades

| Ator | Papel | Ações principais |
|------|-------|-----------------|
| **Operador** | Empresa que opera dentro dos contratos de partilha | Envia remessas de gastos, responde contestações |
| **PPSA** | Gestora do contrato (Pré-Sal Petróleo S.A.) | Analisa, valida e reconhece/rejeita gastos |
| **SGPP (sistema)** | Plataforma BPM | Orquestra todo o fluxo, aplica regras automáticas, gera entidades derivadas |

---

## 3. Entidades e Coleções MongoDB

| Coleção MongoDB | Entidade Java | Papel no fluxo |
|-----------------|---------------|----------------|
| `contrato_entity` | `ContratoEntity` | Cadastro mestre de contratos: campos, TPs, projetos, fases |
| `remessa_entity` | `RemessaEntity` | Remessa original enviada pelo operador com valores brutos |
| `remessa_derivada_campo_entity` | `RemessaDerivadaPorCampoEntity` | Remessa com valores rateados por campo via TP |
| `conta_custo_oleo_entity` | `ContaCustoOleoEntity` | CCO: consolidado de reconhecimento; saldo recuperável |
| `recibo_entity` | `ReciboEntity` | Protocolo emitido a cada envio/mudança de fase |
| `relatorio_consolidacao_sintese_entity` | — | Consolidado anual por contrato/campo |
| `relatorio_consolidacao_sintese_remessa_entity` | — | Consolidado por remessa/fase |
| `dados_relatorio_r_n_p_entity` | — | Indicadores de prazo de análise |
| `dados_grafico_relatorio_n_p_entity` | — | Dados gráficos do relatório RNP |
| `event` | — | Histórico de eventos de auditoria das CCOs (modo antigo) |

---

## 4. Fluxo Completo de Reconhecimento

### 4.1 Envio da Remessa pelo Operador

O operador acessa o SGPP e realiza o upload de uma **planilha Excel** contendo a lista de gastos do período. Ao submeter, informa:

| Campo | Descrição |
|-------|-----------|
| `contratoCPP` | Código do contrato (ex: `"Sépia"`) |
| `campo` | Nome do campo petrolífero (ex: `"Sepia"`) |
| `remessaExposicao` | Número da remessa conforme visão do operador (ex: `1`, `2`, `3`) |
| `origemDosGastos` | Tipo de remessa — define regra de rateio e numeração interna |
| `mesAnoReferencia` | Competência dos gastos (ex: `"05/2022"`) |

O sistema **valida** os dados antes de persistir. Um `recibo_entity` é gerado com número de protocolo.

---

### 4.2 Criação da remessa_entity

Após validação, é criado **um único registro** em `remessa_entity` com:

- **Valores brutos**: os valores dos itens de gasto são idênticos aos da planilha (`valorMoedaOBJReal`, `valorMoedaACC`, etc.)
- **`faseRemessa`**: inicia em `"MEN"` (Mensal)
- **`remessa`**: calculado internamente com base no `origemDosGastos` (vide seção 6.1)
- **`gastos[]`**: array com um objeto por linha da planilha, cada um contendo todos os atributos do item

> **Importante**: O registro de `remessa_entity` é **atualizado** ao longo de todo o processo (mudanças de fase, novos reconhecimentos). O campo `version` controla as revisões.

#### Atributos de controle de cada item de gasto (remessa_entity)

| Campo | Valores possíveis | Significado |
|-------|-------------------|-------------|
| `statusGastoTipo` | `Reconhecido`, `Nao_Reconhecido`, `0` (ainda não analisado) | Status da análise |
| `reconhecido` | `"SIM"`, `"NAO"`, `"0"` | Flag simplificado |
| `reconhecimentoTipo` | `TOTAL`, `PARCIAL`, `TOTAL_POR_DECURSO_DE_PRAZO`, `TOTAL_AUTOMATICO` | Como o reconhecimento foi concedido |
| `faseRemessa` | `MEN`, `ROP`, `RAD`, `REC`, `REV` | Fase em que o gasto foi reconhecido/analisado |
| `faseRespostaGestora` | mesmas siglas | Fase da última resposta da PPSA |
| `statusValidacao` | `Reconhecido`, `Passivel_Reconhecimento`, `correto` | Status de validação |
| `valorReconhecido` | decimal | Valor efetivamente reconhecido |
| `valorNaoReconhecido` | decimal | Valor não reconhecido nessa fase |
| `fase` | `EXP`, `PRD`, `AEGV` | Fase do projeto a que o gasto pertence (Exploração/Produção/AEGV) |
| `transferenciaEmAndamento` | boolean | Indica se há transferência de valor em andamento |

> **`fase` do gasto**: recuperada da entidade `contrato_entity`, correlacionando `numItemOrcamento1` do gasto com o código do projeto no contrato. O campo `projetos[].codigo` do contrato indica a fase (`EXP` ou `PRD`).

---

### 4.3 Geração da remessa_derivada_campo_entity

Imediatamente após a criação da `remessa_entity`, o sistema gera **um ou mais registros** de `remessa_derivada_campo_entity`. O número de registros e o cálculo dos valores dependem do `origemDosGastos`:

#### GASTO_EXCLUSIVO

- **Quantidade**: 1 registro, para o contrato/campo informado pelo operador
- **TP utilizado**: `tractParticipations` do **contrato** (normalmente 100%)
- **Cálculo**: `valorMoedaOBJReal (derivada) = valorMoedaOBJReal (remessa) × (TP / 100)`
- Se TP = 100%, os valores são idênticos à remessa original

#### GASTO_JAZIDA_COMPARTILHADA

- **Quantidade**: 1 registro por **campo** existente no contrato
- **TP utilizado**: `campos[].tractParticipations` de cada campo
- **Cálculo**: `valorMoedaOBJReal (derivada) = valorMoedaOBJReal (remessa) × (TP_campo / 100)`
- `valorMoedaOBJRealOriginal` no item da derivada armazena o valor bruto original da remessa
- `tractParticipationPercentual` registra o percentual aplicado em cada item

> **Exemplo**: TP do campo Sépia = 60,407%. Um gasto de R$ 644.600,00 na remessa resulta em R$ 389.383,52 na remessa derivada.

> **Exemplo com múltiplos campos**: o contrato **Entorno de Sapinhoá** possui 3 campos ativos — **Nordeste de Sapinhoá**, **Noroeste de Sapinhoá** e **Sudoeste de Sapinhoá** — cada um com seu próprio TP. Para uma remessa `GASTO_JAZIDA_COMPARTILHADA` enviada nesse contrato, o sistema gera **3 registros de `remessa_derivada_campo_entity`** (um por campo), cada um rateado pelo TP específico daquele campo. Consequentemente, o reconhecimento gera **3 CCOs distintas e independentes** (uma por campo), cada uma com seus próprios valores, fases e saldo de recuperação — não há mistura de valores entre campos do mesmo contrato.

#### GASTO_ATIVO_COMPARTILHADO

- **Quantidade**: 1 registro para o contrato/campo/UEP selecionada
- **TP utilizado**: **Fator de Alocação** da UEP (unidade estacionária de produção), previamente calculado

#### GASTO_AEGV

- Segue lógica similar ao exclusivo, com numeração diferenciada (+30.000)
- **Não há cálculo de OverHead** para gastos deste tipo: `overHeadExploracao`, `overHeadProducao` e `overHeadTotal` são sempre 0 na CCO resultante, independente do `valorReconhecido`

#### Campos exclusivos da remessa_derivada_campo_entity

| Campo | Descrição |
|-------|-----------|
| `idRemessaOriginal` | `_id` da `remessa_entity` que originou este registro |
| `tractParticipationPercentual` | TP aplicado no item (por item de gasto) |
| `valorMoedaOBJRealOriginal` | Valor bruto na remessa original, antes do rateio |

---

### 4.4 Processo de Reconhecimento por Fases

O reconhecimento acontece em **até 5 fases sequenciais**, cada uma representando uma nova oportunidade de o operador contestar e tentar reconhecer gastos rejeitados anteriormente.

```
MEN ──► ROP ──► RAD ──► REC ──► REV
```

| Fase | Nome completo | Descrição |
|------|--------------|-----------|
| `MEN` | Mensal | Fase inicial; análise da PPSA sobre a remessa enviada |
| `ROP` | Resposta ao Operador | Segunda tentativa; operador responde às contestações |
| `RAD` | Recurso Administrativo | Terceira tentativa; recurso formal |
| `REC` | Recálculo | Quarta tentativa; recálculo de valores |
| `REV` | Revisão | Fase final de revisão |

#### Regras de transição de fase

- Uma CCO é gerada ao **fim de cada fase** que tiver pelo menos 1 gasto reconhecido
- Cada fase pode ter seus próprios reconhecimentos parciais ou totais
- Um gasto pode ser reconhecido em **qualquer fase** (o campo `faseRemessa` no item identifica em qual fase ocorreu)
- Uma CCO é identificada pela tripla: **contrato + campo + remessa + fase**

#### Tipos de Reconhecimento

| `reconhecimentoTipo` | Descrição |
|----------------------|-----------|
| `TOTAL` | 100% do valor do gasto reconhecido |
| `PARCIAL` | Apenas parte do valor reconhecido; `valorNaoReconhecido > 0` |
| `TOTAL_POR_DECURSO_DE_PRAZO` | Reconhecimento automático por decurso de prazo (vide nota abaixo) |
| `TOTAL_AUTOMATICO` | Reconhecimento automático por regra do sistema (ex: valor negativo) |

> **Gastos com valor negativo** (`valorMoedaOBJReal < 0`): são reconhecidos automaticamente com `TOTAL_AUTOMATICO` e a justificativa é `"Reconhecimento Automático: valor do gasto negativo"`.

> **Decurso de prazo**: o sistema possui um parâmetro configurável que define o prazo máximo para análise de um gasto — atualmente **15 dias**. Ao expirar esse prazo sem que a PPSA tenha concluído a análise, o sistema aciona automaticamente um fluxo de reconhecimento automático (`TOTAL_POR_DECURSO_DE_PRAZO`). Este mecanismo é um parâmetro de sistema e **não tem relação com o Acordo de Gestão** entre PPSA e operador — é uma regra de prazo de análise interna.

#### Ciclo do status de um item de gasto

```
Não analisado (statusGastoTipo: "0", reconhecido: "0")
        │
        ▼
Reconhecido (statusGastoTipo: "Reconhecido", reconhecido: "SIM")
        ou
Não Reconhecido (statusGastoTipo: "Nao_Reconhecido", reconhecido: "NAO")
        │
        ▼ (pode ir para próxima fase)
Reconhecido em fase posterior / Recusado definitivamente
```

---

### 4.5 Geração da CCO (conta_custo_oleo_entity)

Ao término das atividades de análise de cada fase, o sistema consolida os resultados e **gera um registro de CCO** para cada `remessa_derivada_campo_entity` que possua pelo menos 1 gasto reconhecido nessa fase.

#### Regra de unicidade da CCO

> Uma CCO é **única** para a combinação: `contratoCpp` + `campo` + `remessa` + `faseRemessa`

Portanto, para uma remessa que passe por 3 fases (MEN, ROP, RAD) com reconhecimentos em cada fase, serão geradas **3 CCOs distintas**.

#### Como os valores da CCO são calculados

Os valores consolidados vêm da soma dos itens **reconhecidos** da `remessa_derivada_campo_entity`, separados por `fase` do projeto (EXP ou PRD):

| Campo CCO | Origem |
|-----------|--------|
| `valorReconhecidoExploracao` | Soma de `valorReconhecido` dos itens com `fase = "EXP"` |
| `valorReconhecidoProducao` | Soma de `valorReconhecido` dos itens com `fase = "PRD"` |
| `valorReconhecido` | `valorReconhecidoExploracao + valorReconhecidoProducao` |
| `overHeadExploracao` | 1%, 2% ou 3% de `valorReconhecidoExploracao` |
| `overHeadProducao` | Exatamente 1% de `valorReconhecidoProducao` |
| `overHeadTotal` | `overHeadExploracao + overHeadProducao` |
| `valorReconhecidoComOH` | `valorReconhecido + overHeadTotal` |
| `valorNaoReconhecido` | Soma de `valorNaoReconhecido` dos itens |
| `valorLancamentoTotal` | Soma de todos os valores lançados (reconhecidos + não reconhecidos) |
| `quantidadeLancamento` | Contagem de itens considerados |

> **Nota sobre o OH**: A taxa de `overHeadExploracao` (1%, 2% ou 3%) depende do montante total do valor produzido no contrato e é definida por regra de faixa. Quando `valorReconhecidoExploracao = 0` ou `valorReconhecidoProducao = 0`, o OH correspondente também deve ser 0. **Valores de base negativos não geram OH** — nesses casos, o OH é tratado como WARNING (não é erro de cálculo, é uma situação válida).

---

## 5. Estrutura Detalhada das Entidades

### 5.1 contrato_entity

Cadastro mestre consultado durante a geração de remessas derivadas.

```json
{
  "_id": "string",
  "tipo": "CPP",
  "nome": "Sépia",
  "numero": "48610226559202149",
  "rodada": "VECO",
  "projetos": [
    {
      "fase": "PRD | EXP | AEGV",
      "nome": "Nome do projeto",
      "codigo": "30",
      "dataValidade": "2057-04-27T04:00:00Z"
    }
  ],
  "campos": [
    {
      "nome": "Sepia",
      "excedenteUniaoContratado": 0.3743,
      "tractParticipations": [
        {
          "percentual": 60.407,
          "dataInicio": "2022-05-01",
          "dataFim": "2022-06-07"
        }
      ],
      "unidadesEstacionariaProducao": [
        {
          "nome": "FPSO Carioca",
          "dataPrimeiroOleo": "2021-08-23",
          "fatoresDeAlocacaoUEP": [{ "percentual": 100.0, ... }]
        }
      ]
    }
  ],
  "tractParticipations": [ ... ],
  "origemDosGastos": ["GASTO_EXCLUSIVO", "GASTO_JAZIDA_COMPARTILHADA", ...],
  "flgAtualizacaoMonetaria": true,
  "dataInicioProducao": "2022-05-02",
  "permiteDecurso": true
}
```

**Campos críticos para o fluxo**:

| Campo | Uso |
|-------|-----|
| `projetos[].codigo` | Correlacionado com `numItemOrcamento1` do gasto para identificar a `fase` (EXP/PRD) |
| `projetos[].fase` | Fase do projeto (`EXP`, `PRD`, `AEGV`) |
| `campos[].tractParticipations` | TP por campo para rateio de GASTO_JAZIDA_COMPARTILHADA |
| `tractParticipations` | TP do contrato para rateio de GASTO_EXCLUSIVO |
| `campos[].unidadesEstacionariaProducao[].fatoresDeAlocacaoUEP` | Fator para GASTO_ATIVO_COMPARTILHADO |
| `flgAtualizacaoMonetaria` | Define se a CCO desse contrato recebe correção IPCA/IGPM |

---

### 5.2 remessa_entity

```json
{
  "_id": "string",
  "exercicio": 2022,
  "periodo": 5,
  "contratoCPP": "Sépia",
  "campo": "",
  "etapa": "ANALISE",
  "processoAdministrativo": "PPSA_SGPP_RCO_SEPIA_0000893",
  "faseRemessa": "RAD",
  "remessa": 10001,
  "remessaExposicao": 1,
  "usuarioResponsavel": "email@operador.com",
  "mesAnoReferencia": "05/2022",
  "gastosCompartilhados": true,
  "origemDoGasto": "GASTO_JAZIDA_COMPARTILHADA",
  "revisaoEmAndamento": false,
  "reconhecimentoFinalizado": false,
  "dataLancamento": "2022-06-24T22:27:41+0000",
  "version": 27,
  "gastos": [ ... ]
}
```

> **Nota**: `campo` fica vazio na `remessa_entity` para `GASTO_JAZIDA_COMPARTILHADA`; o campo é atribuído somente na `remessa_derivada_campo_entity`.

---

### 5.3 remessa_derivada_campo_entity

```json
{
  "_id": "string",
  "idRemessaOriginal": "_id da remessa_entity",
  "contratoCPP": "Sépia",
  "campo": "Sepia",
  "exercicio": 2022,
  "periodo": 5,
  "faseRemessa": "RAD",
  "remessa": 10001,
  "remessaExposicao": 1,
  "mesAnoReferencia": "05/2022",
  "gastosCompartilhados": true,
  "origemDoGasto": "GASTO_JAZIDA_COMPARTILHADA",
  "dataLancamento": "2022-06-24T22:27:43Z",
  "version": 27,
  "gastos": [
    {
      "item": 1,
      "valorMoedaOBJReal": 389383.522,
      "valorMoedaOBJRealOriginal": 644600.0,
      "tractParticipationPercentual": 60.407,
      "fase": "PRD",
      "valorReconhecido": 389383.522,
      "valorNaoReconhecido": 0.0,
      "faseRemessa": "MEN",
      "faseRespostaGestora": "MEN",
      ...
    }
  ]
}
```

---

### 5.4 conta_custo_oleo_entity

Esta é a entidade central do saldo recuperável. Sua estrutura tem dois níveis: **raiz** (valores na criação) e **correcoesMonetarias** (histórico de alterações).

#### Campos raiz

```json
{
  "_id": "string",
  "contratoCpp": "Sépia",
  "campo": "Sepia",
  "remessa": 10001,
  "remessaExposicao": 1,
  "faseRemessa": "MEN",
  "faseRespostaGestora": "MEN",
  "dataReconhecimento": "2022-07-09T18:09:51-0300",
  "mesReconhecimento": 7,
  "anoReconhecimento": 2022,
  "mesAnoReferencia": "05/2022",
  "exercicio": 2022,
  "periodo": 5,
  "dataLancamento": "2022-06-24T21:08:51.653Z",
  "idRemessaGeradora": "_id da remessa_derivada_campo_entity",
  "versionRemessaGeradora": 8,
  "origemDosGastos": "GASTO_JAZIDA_COMPARTILHADA",
  "quantidadeLancamento": 869,

  "valorLancamentoTotal": 154613399.19,
  "valorReconhecivel": 154613399.19,
  "valorReconhecido": 144353758.57,
  "valorNaoReconhecido": 10259640.63,
  "valorNaoPassivelRecuperacao": 0.0,
  "valorRecusado": 0.0,

  "valorReconhecidoExploracao": 0.0,
  "valorReconhecidoProducao": 144353758.57,

  "overHeadExploracao": 0.0,
  "overHeadProducao": 1443537.59,
  "overHeadTotal": 1443537.59,

  "valorReconhecidoComOH": 145797296.15,

  "flgRecuperado": false,
  "version": 6,
  "correcoesMonetarias": [ ... ]
}
```

#### Array correcoesMonetarias

Cada entrada representa uma **modificação de valor** ocorrida após a criação da CCO. A **última entrada ativa** (`ativo: true`) define o estado atual da CCO.

```json
{
  "tipo": "IPCA | IGPM | RECUPERACAO | RETIFICACAO | INVALIDACAO_RECONHECIMENTO_PARCIAL",
  "subTipo": "DEFAULT",
  "contrato": "Sépia",
  "campo": "Sepia",
  "dataCorrecao": "2024-02-05T13:33:24+0000",
  "dataCriacaoCorrecao": "ISODate(...)",
  "ativo": true,
  "transferencia": false,
  "faseRemessa": "MEN",

  "valorReconhecido": 144353758.57,
  "valorReconhecidoComOH": 151614608.27,
  "overHeadExploracao": 0.0,
  "overHeadProducao": 1443537.59,
  "overHeadTotal": 1443537.59,
  "diferencaValor": 5817312.12,
  "valorReconhecidoComOhOriginal": 145797296.15,

  "valorLancamentoTotal": 160782473.82,
  "valorNaoPassivelRecuperacao": 0.0,
  "valorReconhecivel": 160782473.82,
  "valorNaoReconhecido": 0.0,
  "valorReconhecidoExploracao": 0.0,
  "valorReconhecidoProducao": 144353758.57,

  "taxaCorrecao": 1.0399,
  "igpmAcumulado": 2.0399,
  "igpmAcumuladoReais": 5817312.12,

  "idContaCustoOleoCorrigida": "_id da CCO (para RECUPERACAO)",
  "valorRecuperado": null,
  "valorRecuperadoTotal": null,
  "observacao": "texto (para RETIFICACAO)"
}
```

---

### 5.5 Entidades de Relatório

#### relatorio_consolidacao_sintese_entity
- Consolidado **anual** por contrato/campo
- Criado/atualizado ao final de cada fase de reconhecimento
- Agrupa valores reconhecidos por ano de reconhecimento

#### relatorio_consolidacao_sintese_remessa_entity
- Consolidado por **remessa + fase**
- Um novo registro criado ao final de **cada fase**

#### dados_relatorio_r_n_p_entity / dados_grafico_relatorio_n_p_entity
- Indicadores de cumprimento de prazos
- Gerados ao finalizar a tarefa "Enviar Resposta ao Operador" na fase MEN
- Alimentam o painel `RCO_RNP_ETPn` no Portal

---

## 6. Regras de Negócio Críticas

### 6.1 Numeração de Remessa

O campo `remessaExposicao` é o número informado pelo operador. O campo `remessa` é gerado internamente pelo sistema com base no `origemDosGastos`:

| origemDosGastos | Fórmula | Exemplo (exposição = 1) |
|-----------------|---------|------------------------|
| `GASTO_EXCLUSIVO` | `remessaExposicao` (sem alteração) | `remessa = 1` |
| `GASTO_JAZIDA_COMPARTILHADA` | `remessaExposicao + 10.000` | `remessa = 10001` |
| `GASTO_ATIVO_COMPARTILHADO` | `remessaExposicao + 20.000` | `remessa = 20001` |
| `GASTO_AEGV` | `remessaExposicao + 30.000` | `remessa = 30001` |

---

### 6.2 Cálculo do Tract Participation (TP)

O TP é uma taxa de participação que define quanto do gasto bruto é atribuído a cada campo/contrato.

#### Seleção do TP vigente

O TP é **histórico** — cada campo ou contrato tem uma lista de TPs com período de vigência (`dataInicio` / `dataFim`). O sistema seleciona o TP cujo período engloba a `dataLancamento` do item de gasto.

```
tractParticipations: [
  { percentual: 60.407, dataInicio: "2022-05-01", dataFim: "2022-06-07" },
  { percentual: 60.408, dataInicio: "2022-06-08", dataFim: "2057-04-27" }
]
```

#### Aplicação nos valores

```
valorMoedaOBJReal (derivada) = valorMoedaOBJReal (remessa) × (TP / 100)
```

O `valorMoedaOBJRealOriginal` na remessa derivada preserva o valor bruto antes do rateio para rastreabilidade.

---

### 6.3 Cálculo de OverHead (OH)

Os overheads são calculados sobre os valores reconhecidos separados por fase do projeto:

| OH | Base | Taxa válida | Regra especial |
|----|------|-------------|----------------|
| `overHeadExploracao` | `valorReconhecidoExploracao` | **1%, 2% ou 3%** | Base = 0 → OH = 0; base < 0 → OH não calculado (WARNING, não ERRO) |
| `overHeadProducao` | `valorReconhecidoProducao` | **Exatamente 1%** | Base = 0 → OH = 0; base < 0 → OH não calculado (WARNING, não ERRO) |
| `overHeadTotal` | `overHeadExploracao + overHeadProducao` | Soma | Qualquer desvio > R$ 0,01 é ERRO |

#### Faixas de taxa do overHeadExploracao

A taxa de `overHeadExploracao` depende do **acumulado anual** de `valorReconhecidoExploracao` no contrato — ou seja, a soma dos valores reconhecidos na fase EXP de todas as CCOs do contrato, ordenadas por `dataReconhecimento`, dentro do mesmo ano-calendário. As faixas são:

| Faixa (acumulado anual) | Taxa |
|--------------------------|------|
| ≤ R$ 5.000.000,00 | **3%** |
| > R$ 5.000.000,00 e ≤ R$ 15.000.000,00 | **2%** |
| > R$ 15.000.000,00 | **1%** |

> O acumulado é **zerado a cada novo ano** (`anoReconhecimento`). A primeira CCO reconhecida em um novo ano sempre recomeça a contagem a partir de R$ 0,00.

##### Regra de proporcionalidade nas transições de faixa

Quando o `valorReconhecidoExploracao` de uma CCO faz o acumulado anual **cruzar uma ou mais faixas**, o OH dessa CCO é calculado **proporcionalmente**, fatiando o valor entre as faixas atravessadas — nunca aplicando uma taxa única sobre o valor inteiro.

**Exemplo 1** — cruzando uma única fronteira:
- Acumulado do ano antes desta CCO: R$ 4.500.000,00
- Valor de exploração desta CCO: R$ 1.000.000,00
- R$ 500.000,00 (até completar R$ 5.000.000,00) → taxa de **3%**
- R$ 500.000,00 (excedente, entrando na faixa seguinte) → taxa de **2%**

**Exemplo 2** — cruzando duas fronteiras de uma só vez (primeira CCO do ano):
- Acumulado do ano antes desta CCO: R$ 0,00
- Valor de exploração desta CCO: R$ 20.000.000,00
- R$ 5.000.000,00 → taxa de **3%** (preenche a primeira faixa)
- R$ 10.000.000,00 → taxa de **2%** (preenche a segunda faixa, de R$ 5M a R$ 15M)
- R$ 5.000.000,00 (excedente) → taxa de **1%** (entra na terceira faixa)
- A partir desta CCO, o acumulado anual já está acima de R$ 15.000.000,00 — logo, **todas as CCOs seguintes no mesmo ano** são calculadas a 1% sobre o valor integral, até a virada do ano.

```
overHeadExploracao(CCO) = Σ (fatia_na_faixa × taxa_da_faixa)
```

Os mesmos campos de OH existem dentro de cada entrada de `correcoesMonetarias`. A verificação deve ser feita tanto na raiz da CCO quanto em cada correção que contenha campos de OH.

---

### 6.4 Geração e Consolidação da CCO

#### Condições para geração

- Deve existir **pelo menos 1 gasto reconhecido** na fase
- Uma CCO por `contrato + campo + remessa + fase`
- Gerada a partir dos dados da `remessa_derivada_campo_entity`

#### Imutabilidade da raiz

> O **registro raiz da CCO é imutável após criação**. Todas as modificações posteriores são registradas exclusivamente no array `correcoesMonetarias`, com exceção de CCOs mais antigas, que registravam alterações de recuperação no atributo "valorRecuperado" na raz da CCO, e com isso, é preciso recorrer aos eventos (coleção event que armazena todas as alterações dos registros para histórico).

#### Leitura do estado atual

O estado atual da CCO é sempre determinado pela **última entrada ativa** (`ativo: true`) em `correcoesMonetarias`. Se não houver correções, usam-se os valores da raiz.

```
Estado atual = última correção com ativo=true
               OU raiz (se correcoesMonetarias vazio)
```

Se um atributo não existir na última correção, **usa-se o valor da raiz da CCO**.

---

### 6.5 Correções Monetárias

#### IPCA / IGPM

- **Gatilho**: automaticamente, todo início de mês, após 12 meses da `dataReconhecimento` da CCO
- **Condição**: só aplicada se o saldo `valorReconhecidoComOH ≠ 0`
- **Índice**: recuperado de `ipca_entity` ou `igpm_entity` pelo mês/ano de referência
- **Impacto**: atualiza `valorReconhecidoComOH` e `valorLancamentoTotal` pelo fator acumulado

```
valorReconhecidoComOH_novo = valorReconhecidoComOH_anterior × taxaCorrecao
diferencaValor = valorReconhecidoComOH_novo - valorReconhecidoComOH_anterior
igpmAcumulado += (taxaCorrecao - 1)   # acumula o índice
igpmAcumuladoReais += diferencaValor  # acumula o valor em reais
```

> **Nota**: O campo `igpmAcumulado` e `igpmAcumuladoReais` são usados tanto para IPCA quanto IGPM — o nome é legado.

#### RECUPERACAO

- **Gatilho**: processo mensal de recuperação, quando o campo está em produção
- **Impacto**: reduz `valorReconhecidoComOH` progressivamente
- Campos específicos: `valorRecuperado` (desta recuperação), `valorRecuperadoTotal` (total acumulado)
- Quando `valorRecuperadoTotal = valorReconhecidoComOH_original` → CCO totalmente recuperada

#### RETIFICACAO

- **Gatilho**: ajuste manual da PPSA para correção de erros ou reclassificações
- Campo `observacao` descreve o motivo
- Pode alterar qualquer campo financeiro da CCO

#### INVALIDACAO_RECONHECIMENTO_PARCIAL

- **Gatilho**: quando parte do reconhecimento de uma CCO é transferido para outra CCO
- Campo `idContaCustoOleoCorrigida` referencia a CCO receptora
- Mantém rastreabilidade de transferências entre CCOs
- Campo `transferencia: true` nas correções de tipo transferência

#### Regras de Precedência

1. Última correção com `ativo: true` prevalece sobre valores da raiz
2. `dataCorrecao` determina a ordenação cronológica das correções
3. `ativo: false` indica correção desativada — ignorada na leitura do estado atual
4. Campos ausentes na correção herdam o valor da raiz

---

### 6.6 Processo de Recuperação

#### Pré-condições

- Campo em **produção** (`dataInicioProducao` no contrato já passou)
- `flgRecuperado = false`
- `valorReconhecidoComOH ≠ 0` (saldo disponível)
- CCOs com saldo negativo: são incluídas no saldo total para compensação

#### Sequência de recuperação (FIFO por data de reconhecimento)

1. Identifica todas as CCOs elegíveis (`flgRecuperado = false` AND `valorReconhecidoComOH ≠ 0`)
2. Ordena por `dataReconhecimento` (mais antigas primeiro)
3. Calcula o valor máximo recuperável no mês (baseado na produção e NN)
4. Itera nas CCOs, deduzindo valores até esgotar o limite mensal ou recuperar todas
5. Para cada CCO atingida, cria uma entrada `RECUPERACAO` em `correcoesMonetarias`
6. Quando `valorRecuperadoTotal = valorReconhecidoComOH_original`: `flgRecuperado = true`

#### CCOs com saldo negativo

- Incluídas no saldo consolidado do contrato/campo
- Compensadas na recuperação quando necessário
- Ao compensar: `flgRecuperado = true`, `valorReconhecidoComOH = 0`

#### Registro de recuperação em recuperacao_custo_oleo_entity

Cada evento mensal de recuperação gera um registro em `recuperacao_custo_oleo_entity` com:
- `valorRecuperado`: total recuperado no mês
- `contasCustoOleoReferencia[]`: lista de CCOs atingidas com o `valorReconhecidoComOH` usado como base
- `nn`: fator de participação do contratante
- `dataRecuperacao`, `mesReferencia`, `anoReferencia`

---

## 7. Ciclo de Vida da CCO

```
┌─────────────────────────────────────────────────────────────────┐
│                    CICLO DE VIDA DA CCO                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  [CRIADA]                                                       │
│     │  Fim de fase com ≥1 gasto reconhecido                    │
│     │  correcoesMonetarias = []                                 │
│     │  flgRecuperado = false                                    │
│     ▼                                                           │
│  [EM CORREÇÃO MONETÁRIA]                                        │
│     │  A cada 12 meses após dataReconhecimento                 │
│     │  Tipo: IPCA ou IGPM                                      │
│     │  valorReconhecidoComOH aumenta conforme inflação         │
│     │                                                           │
│     │  (pode ocorrer RETIFICACAO a qualquer momento)           │
│     ▼                                                           │
│  [EM RECUPERAÇÃO PARCIAL]                                       │
│     │  Campo entra em produção                                  │
│     │  Recuperações mensais deduzem o saldo                    │
│     │  Tipo: RECUPERACAO (1 ou mais entradas)                  │
│     │  flgRecuperado = false, valorReconhecidoComOH > 0        │
│     ▼                                                           │
│  [RECUPERADA]                                                   │
│     │  valorRecuperadoTotal = valorReconhecidoComOH original   │
│     │  flgRecuperado = true                                     │
│     │  valorReconhecidoComOH = 0                               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Estados possíveis

| Estado | `flgRecuperado` | `valorReconhecidoComOH` | `correcoesMonetarias` |
|--------|-----------------|------------------------|----------------------|
| Criada | `false` | > 0 | Vazio ou sem RECUPERACAO |
| Em Correção | `false` | > 0 (atualizado por IPCA/IGPM) | Com IPCA/IGPM/RETIFICACAO |
| Em Recuperação Parcial | `false` | > 0 (reduzido por RECUPERACAO) | Com RECUPERACAO parcial |
| Recuperada Totalmente | `true` | = 0 | Com RECUPERACAO total |
| Saldo Negativo Compensado | `true` | = 0 | Com RECUPERACAO de compensação |

---

## 8. Relacionamentos entre Entidades

```
contrato_entity (1)
    │
    │ consultado para TP e fase do projeto
    │
    ├──────────────────────────────────────────────────────┐
    │                                                       │
remessa_entity (1)                                         │
    │                                                       │
    │ gera (1 para EXCLUSIVO / N para COMPARTILHADA)       │
    ▼                                                       │
remessa_derivada_campo_entity (1..N)                       │
    │  ← idRemessaOriginal → remessa_entity._id            │
    │                                                       │
    │ gera (1 por fase com reconhecimento)                 │
    ▼                                                       │
conta_custo_oleo_entity (1..N)                             │
    │  ← idRemessaGeradora → remessa_derivada._id          │
    │                                                       │
    │ alimenta                                              │
    ├─► relatorio_consolidacao_sintese_entity               │
    └─► relatorio_consolidacao_sintese_remessa_entity       │
                                                            │
recuperacao_custo_oleo_entity                              │
    └─ contasCustoOleoReferencia[].idContaCustoOleo        │
       └─► conta_custo_oleo_entity._id                     │
```

### Rastreabilidade de uma CCO até a remessa original

```python
cco = conta_custo_oleo_entity.find(_id)
remessa_derivada = remessa_derivada_campo_entity.find(cco.idRemessaGeradora)
remessa_original = remessa_entity.find(remessa_derivada.idRemessaOriginal)
contrato = contrato_entity.find_by_nome(remessa_original.contratoCPP)
```

---

## 9. Tipos e Classificações de Referência

### origemDosGastos

| Valor | Descrição | Derivadas geradas | TP base | OH calculado? |
|-------|-----------|-------------------|---------|----------------|
| `GASTO_EXCLUSIVO` | Gastos de um único campo | 1 (mesmo campo) | TP do contrato | Sim |
| `GASTO_JAZIDA_COMPARTILHADA` | Gastos compartilhados entre campos | 1 por campo do contrato | TP de cada campo | Sim |
| `GASTO_ATIVO_COMPARTILHADO` | Gastos de ativo compartilhado (UEP) | 1 (campo/UEP) | Fator de alocação da UEP | Sim |
| `GASTO_AEGV` | Gastos AEGV (ativo em gestão PPSA) | 1 | TP contrato | **Não** — OH sempre 0 |

### faseRemessa

| Sigla | Nome | Sequência |
|-------|------|-----------|
| `MEN` | Mensal | 1ª fase |
| `ROP` | Resposta ao Operador | 2ª fase |
| `RAD` | Recurso Administrativo | 3ª fase |
| `REC` | Recálculo | 4ª fase |
| `REV` | Revisão | 5ª fase |

### fase do projeto (campo `fase` nos itens de gasto)

| Sigla | Descrição | OH aplicável |
|-------|-----------|--------------|
| `EXP` | Exploração | `overHeadExploracao` (1%, 2% ou 3%) |
| `PRD` | Produção | `overHeadProducao` (1%) |
| `AEGV` | Ativo em Gestão (ex: compensação ACP) | Definido por projeto |

### tipos de correção monetária

| tipo | subTipo | Descrição | Gatilho |
|------|---------|-----------|---------|
| `IPCA` | `DEFAULT` | Correção por inflação (IPCA) | Automático, 12 meses após reconhecimento |
| `IGPM` | `DEFAULT` | Correção por inflação (IGPM) | Automático, 12 meses após reconhecimento |
| `RECUPERACAO` | `DEFAULT` | Dedução mensal do saldo | Processo mensal de recuperação |
| `RETIFICACAO` | `DEFAULT` | Ajuste manual | Manual pela PPSA |
| `INVALIDACAO_RECONHECIMENTO_PARCIAL` | `DEFAULT` | Transferência de valor para outra CCO | Manual/sistema |

---

## 10. Pontos de Atenção e Armadilhas Técnicas

### 10.1 Decimal128 vs Float

Os valores monetários estão armazenados como `Decimal128` (BSON) no MongoDB. Ao ler via pymongo, é necessário converter:

```python
from decimal import Decimal

def to_decimal(value):
    if hasattr(value, 'to_decimal'):
        return value.to_decimal()  # Decimal128
    return Decimal(str(value))
```

### 10.2 Datas com timezone

Datas podem ter formatos variados nas coleções:
- `"2022-07-09T18:09:51-0300"` — com offset
- `"2024-02-05T13:33:24+0000"` — UTC
- `ISODate("2024-02-05T13:33:24.668+0000")` — tipo nativo MongoDB
- `"2022-07-09 18:09:51"` — sem timezone (legado)

Sempre normalizar para naive datetime antes de comparar:

```python
dt.replace(tzinfo=None)
```

### 10.3 Estado atual da CCO

**Nunca ler apenas os campos raiz**. O estado atual é sempre a última entrada ativa de `correcoesMonetarias`. Padrão correto:

```python
def get_estado_atual(cco):
    correcoes_ativas = [c for c in (cco.get('correcoesMonetarias') or [])
                        if c.get('ativo', True)]
    if correcoes_ativas:
        ultima = correcoes_ativas[-1]  # ou ordenar por dataCorrecao
        # fallback para raiz se campo ausente na correção
        return {k: ultima.get(k, cco.get(k)) for k in campos_financeiros}
    return cco
```

### 10.4 Numeração de remessa

Ao filtrar por remessa, atentar para a diferença entre `remessa` (número interno) e `remessaExposicao` (número do operador). Um mesmo operador que enviou a "remessa 1" pode ter `remessa = 10001` no banco se for `GASTO_JAZIDA_COMPARTILHADA`.

### 10.5 CCOs de fases diferentes para a mesma remessa

Uma remessa pode gerar **múltiplas CCOs** — uma por fase reconhecida (MEN, ROP, RAD, etc.). Ao calcular o saldo total de uma remessa, é necessário somar os `valorReconhecidoComOH` de **todas as CCOs** com o mesmo `remessa` + `campo`, e não apenas a última.

### 10.6 Gastos negativos são válidos

Gastos com `valorMoedaOBJReal < 0` são reconhecidos automaticamente (`TOTAL_AUTOMATICO`). Na CCO resultante, `valorReconhecidoProducao` ou `valorReconhecidoExploracao` pode ser negativo — nesses casos **o OH não é calculado** (o resultado é 0, não é um erro).

### 10.7 Leitura do histórico de recuperações (modo antigo vs novo)

Existem dois padrões de rastreamento de recuperações nas CCOs:

| Modo | Identificação | Como recuperar o valor por evento |
|------|--------------|----------------------------------|
| **ANTIGO** | Sem entradas `RECUPERACAO` em `correcoesMonetarias` | Delta do campo `valorRecuperado` entre versões consecutivas da coleção `event` |
| **NOVO** | Com entradas `tipo: "RECUPERACAO"` em `correcoesMonetarias` | Diretamente de `correcoesMonetarias[].valorRecuperado` |

### 10.8 idRemessaGeradora e versionRemessaGeradora

A CCO mantém referência à versão da `remessa_derivada_campo_entity` usada na geração (`versionRemessaGeradora`). Isso permite auditar se houve alterações na remessa derivada após a geração da CCO.

### 10.9 Contratos com múltiplos campos ativos

Nem todo contrato tem apenas 1 campo. O contrato **Entorno de Sapinhoá** é um exemplo real com **3 campos ativos simultâneos**: Nordeste de Sapinhoá, Noroeste de Sapinhoá e Sudoeste de Sapinhoá.

Implicações práticas para qualquer funcionalidade que itere sobre `contrato_entity.campos[]`:

- **Nunca assumir 1 campo por contrato.** Qualquer rotina que busque o TP, gere remessas derivadas ou consolide CCOs deve iterar por todos os campos do array `campos[]`.
- **Uma remessa `GASTO_JAZIDA_COMPARTILHADA` neste tipo de contrato gera N remessas derivadas** (uma por campo) e, consequentemente, **N CCOs distintas** por fase de reconhecimento.
- **O TP de cada campo é independente** — um erro de cadastro no TP de um campo não afeta os demais campos do mesmo contrato.
- Ao consolidar saldo recuperável de um contrato, é necessário **agrupar por campo**, nunca somar CCOs de campos diferentes como se fossem do mesmo saldo.
- Relatórios e telas de busca/filtro devem sempre expor o filtro por `campo`, já que `contrato` sozinho não identifica unicamente o conjunto de CCOs relevante nesses casos.

---

*Documento gerado com base em: regras_remessas_ccos.md, PPSA_Modelo_de_Dados_BPM_RCO_v2.pdf e registros de exemplo das coleções MongoDB.*
