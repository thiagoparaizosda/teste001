# Melhoria CCO - Portal de Análise e Gestão de Reconhecimento de Custos
## Levantamento de Componentes, Esforço e Escopo

**Melhoria**: SD-3720 (Melhoria CCO - Portal de Análise e Gestão de Reconhecimento de Custos)
**Data:** Janeiro/2026  
**Versão:** 2.0  
**Status:** Em análise
**Autor:** Thiago Paraizo

---

## 1. VISÃO GERAL DA ARQUITETURA

### 1.1 Stack Tecnológico

| Camada | Tecnologia |
|--------|------------|
| Backend | Python 3.x + Flask |
| Banco de Dados | MongoDB |
| Frontend | HTML5 + Bootstrap 5 + JavaScript |
| Visualização | Chart.js |
| Cache | FileSystem Cache (Flask-Caching) |
| Containerização | Docker + Gunicorn |

### 1.2 Estrutura de Diretórios

```
app/
├── __init__.py              # Factory da aplicação Flask
├── config.py                # Configurações (MONGO_URI, CACHE)
├── routes/                  # Blueprints e endpoints
│   ├── portal_ui.py
│   ├── analise_ui.py
│   ├── recalculo_ui.py
│   ├── ipca_correcao_routes.py
│   └── ipca_promocao_routes.py
├── services/                # Lógica de negócio
│   ├── remessa_service.py
│   ├── recalculo_service.py
│   ├── ipca_correcao_orquestrador.py
│   ├── ipca_correcao_engine.py
│   └── ipca_gap_analyzer.py
├── repositories/            # Acesso a dados
│   ├── remessa_repository.py
│   └── cco_repository.py
├── templates/               # Templates HTML
│   ├── base.html
│   ├── index.html
│   └── [módulos específicos]/
└── utils/                   # Utilitários
    ├── converters.py
    └── cache_utils.py
```

---

## 2. MÓDULOS FUNCIONAIS

A aplicação está organizada em duas frentes principais:

| Frente | Descrição | Status |
|--------|-----------|--------|
| **FRENTE 1** | Portal: Inteligência e Visibilidade dos Dados | - |
| **FRENTE 2** | Ferramentas de Correção e Gestão | - |

---

## 3. FRENTE 1: PORTAL - INTELIGÊNCIA E VISIBILIDADE

### 3.1 Módulo: Conta Custo Óleo (Pesquisa e Timeline)

#### 3.1.1 Telas

| ID | Tela | Arquivo | Descrição |
|----|------|---------|-----------|
| T-2.1 | Pesquisa de CCOs | `pesquisa_ccos.html` | Filtros para busca de CCOs |
| T-2.2 | Timeline da CCO | `cco_timeline.html` | Visualização cronológica de eventos |

#### 3.1.2 Componentes de Interface

| ID | Componente | Localização | Descrição |
|----|------------|-------------|-----------|
| C-2.1 | Filtros de CCO | T-2.1 | Contrato, Campo, Remessa, Fase, Recuperado |
| C-2.2 | Tabela de CCOs | T-2.1 | Grid com resultados |
| C-2.3 | Timeline Visual | T-2.2 | Linha do tempo centralizada com eventos |
| C-2.4 | Cards de Evento | T-2.2 | Detalhes de cada correção/alteração |
| C-2.5 | Valores Atuais | T-2.2 | Painel com valores consolidados |

#### 3.1.3 Rotas/Endpoints

| ID | Endpoint | Método | Descrição |
|----|----------|--------|-----------|
| E-2.1 | `/api/pesquisar-ccos` | POST | Pesquisar CCOs por filtros |
| E-2.2 | `/cco-timeline/<id>` | GET | Página de timeline da CCO |

#### 3.1.4 Serviços

| ID | Serviço | Função | Descrição |
|----|---------|--------|-----------|
| S-2.1 | CCO Timeline | `cco_timeline()` | Processa dados para timeline |
| S-2.2 | Processar Timeline | `processar_timeline_cco()` | Ordena e formata eventos |
| S-2.3 | Extrair Valores Atuais | `extrair_valores_atuais_cco()` | Obtém valores mais recentes |

#### 3.1.5 Repositórios

| ID | Repositório | Método | Descrição |
|----|-------------|--------|-----------|
| R-2.1 | CCO Repository | `pesquisar_ccos()` | Busca com projeção otimizada |

#### 3.1.6 Collections MongoDB

| Collection | Descrição |
|------------|-----------|
| `conta_custo_oleo_entity` | CCOs consolidadas |

---
## 4. FRENTE 2: FERRAMENTAS DE CORREÇÃO E GESTÃO

### 4.1 Módulo: Correção de Track Participation (TP)

#### 4.1.1 Telas

| ID | Tela | Arquivo | Descrição |
|----|------|---------|-----------|
| T-3.1 | Pesquisar CCOs para Recálculo | `recalculo/pesquisar_ccos.html` | Busca CCOs para recálculo |
| T-3.2 | Executar Recálculo | `recalculo/executar_recalculo.html` | Formulário de parâmetros |
| T-3.3 | Resultado do Recálculo | `recalculo/resultado_recalculo.html` | Comparativo original vs recalculado |
| T-3.4 | Recálculos Temporários | `recalculo/temporarios.html` | Lista de recálculos pendentes |

#### 4.1.2 Componentes de Interface

| ID | Componente | Localização | Descrição |
|----|------------|-------------|-----------|
| C-3.1 | Filtros de Recálculo | T-3.1 | Específicos para TP |
| C-3.2 | Formulário de Parâmetros | T-3.2 | Novo fator TP, modo recálculo |
| C-3.3 | Tabela Comparativa | T-3.3 | Original vs Recalculado |
| C-3.4 | Gráfico Comparativo | T-3.3 | Chart.js - Bar |
| C-3.5 | Botões de Ação | T-3.3 | Salvar, Exportar, Aplicar |

#### 4.1.3 Rotas/Endpoints

| ID | Endpoint | Método | Blueprint | Descrição |
|----|----------|--------|-----------|-----------|
| E-3.1 | `/recalculo/pesquisar-ccos` | GET | `recalculo_bp` | Página de pesquisa |
| E-3.2 | `/recalculo/api/pesquisar-ccos` | POST | `recalculo_bp` | API de pesquisa |
| E-3.3 | `/recalculo/api/executar-recalculo` | POST | `recalculo_bp` | Executa recálculo |
| E-3.4 | `/recalculo/resultado/<id>` | GET | `recalculo_bp` | Página de resultado |
| E-3.5 | `/recalculo/api/exportar-csv/<id>` | GET | `recalculo_bp` | Exporta CSV |
| E-3.6 | `/recalculo/api/salvar-temporario` | POST | `recalculo_bp` | Salva temporário |
| E-3.7 | `/recalculo/api/aplicar-definitivo` | POST | `recalculo_bp` | Aplica definitivo |

#### 4.1.4 Serviços

| ID | Serviço | Classe/Método | Descrição |
|----|---------|---------------|-----------|
| S-3.1 | Recálculo Service | `RecalculoService` | Orquestra recálculo de CCO |
| S-3.2 | Pesquisar CCOs Recálculo | `RecalculoService.pesquisar_ccos_para_recalculo()` | Busca CCOs elegíveis |
| S-3.3 | Executar Recálculo | `RecalculoService.executar_recalculo()` | Processa recálculo |
| S-3.4 | Salvar Temporário | `RecalculoService.salvar_resultado_temporario()` | Persiste resultado |
| S-3.5 | Aplicar Definitivo | `RecalculoService.aplicar_recalculo_definitivo()` | Aplica na CCO |
| S-3.6 | Atualizar CCO | `RecalculoService._atualizar_cco_e_criar_evento()` | Cria evento de auditoria |

#### 4.1.5 Repositórios

| ID | Repositório | Método | Descrição |
|----|-------------|--------|-----------|
| R-3.1 | CCO Repository | `buscar_por_filtros()` | Com filtros específicos TP |
| R-3.2 | Temp Recálculos | Local MongoDB | Armazena recálculos temporários |

---

### 4.2 Módulo: Identificação e Correção IPCA/IGPM

#### 4.2.1 Telas

| ID | Tela | Arquivo | Descrição |
|----|------|---------|-----------|
| T-4.1 | Busca por CCO | `recalculo/ipca_analise_e_recalculo.html` | Filtros para CCO |
| T-4.2 | Fluxo de Correção (Steps) | `recalculo/ipca_analise_e_recalculo.html` | Wizard multi-step |
| T-4.2.1 | Step 1 - Analisar CCO | Seção do template | Início da análise |
| T-4.2.2 | Step 2 - Resultados | Seção do template | Resumo de gaps/cenários |
| T-4.2.3 | Step 3 - Aprovar | Seção do template | Seleção de correções |
| T-4.2.4 | Step 4 - Aplicar | Seção do template | Aplicação final |

#### 4.2.2 Componentes de Interface

| ID | Componente | Localização | Descrição |
|----|------------|-------------|-----------|
| C-4.1 | Wizard Navigation | T-4.2 | Steps indicator |
| C-4.2 | Resultado Análise | T-4.2.2 | Cards com gaps identificados |
| C-4.3 | Tabela de Gaps | T-4.2.2 | Grid com gaps e cenários |
| C-4.4 | Preview Correções | T-4.2.3 | Visualização antes de aplicar |
| C-4.5 | Seletor de Correções | T-4.2.3 | Checkboxes para seleção |
| C-4.6 | Resumo Impacto | T-4.2.4 | Valores antes/depois |

#### 4.2.3 Rotas/Endpoints

| ID | Endpoint | Método | Blueprint | Descrição |
|----|----------|--------|-----------|-----------|
| E-4.1 | `/ipca-correcao/` | GET | `ipca_correcao_bp` | Página principal |
| E-4.2 | `/ipca-correcao/api/iniciar-analise` | POST | `ipca_correcao_bp` | Inicia análise de CCO |
| E-4.3 | `/ipca-correcao/api/gerar-propostas` | POST | `ipca_correcao_bp` | Gera propostas correção |
| E-4.4 | `/ipca-correcao/api/aprovar-correcoes` | POST | `ipca_correcao_bp` | Aprova selecionadas |
| E-4.5 | `/ipca-correcao/api/aplicar-correcoes` | POST | `ipca_correcao_bp` | Aplica correções |
| E-4.6 | `/ipca-correcao/api/avaliar-ipca-vigente` | POST | `ipca_correcao_bp` | Avalia IPCA ano corrente |

#### 4.2.4 Serviços - Orquestrador

| ID | Serviço | Classe/Método | Descrição |
|----|---------|---------------|-----------|
| S-4.1 | Orquestrador IPCA | `IPCACorrectionOrchestrator` | Coordena todo o fluxo |
| S-4.2 | Iniciar Análise | `iniciar_analise_cco()` | Entry point da análise |
| S-4.3 | Gerar Propostas | `gerar_propostas_correcao()` | Gera propostas por cenário |
| S-4.4 | Aprovar Correções | `aprovar_correcoes()` | Valida e persiste aprovação |
| S-4.5 | Aplicar Correções | `aplicar_correcoes()` | Executa aplicação final |
| S-4.6 | Determinar Cenário | `_determinar_cenario()` | Classifica tipo de gap |
| S-4.7 | Save Session | `_save_session()` | Persiste sessão correção |
| S-4.8 | Load Session | `_load_session()` | Recupera sessão correção |

#### 4.2.5 Serviços - Gap Analyzer

| ID | Serviço | Classe/Método | Descrição |
|----|---------|---------------|-----------|
| S-4.9 | Gap Analyzer | `IPCAGapAnalyzer` | Identifica gaps nas CCOs |
| S-4.10 | Analisar Gaps Sistema | `analisar_gaps_sistema()` | Análise completa |
| S-4.11 | Analisar CCO Individual | `_analisar_cco_individual()` | Análise por CCO |
| S-4.12 | Extrair Data Reconhecimento | `_extrair_data_reconhecimento()` | Obtém data base |
| S-4.13 | Mapear Correções IPCA/IGPM | `_mapear_correcoes_ipca_igpm()` | Lista correções existentes |
| S-4.14 | Mapear Correções Cronológicas | `_mapear_todas_correcoes_cronologicas()` | Ordena por data |
| S-4.15 | Calcular Mês Taxa | `_calcular_mes_taxa_aplicacao()` | Determina período taxa |
| S-4.16 | Calcular Data Limite | `_calcular_data_limite_aplicacao()` | Deadline de aplicação |
| S-4.17 | Buscar Correção Aniversário | `_buscar_correcao_para_aniversario()` | Localiza correção devida |
| S-4.18 | Obter Valor Base Gap | `_obter_valor_base_para_gap()` | Valor para cálculo |
| S-4.19 | Calcular Prioridade | `_calcular_prioridade_gap()` | Ordena gaps |
| S-4.20 | Identificar Alterações | `_identificar_alteracoes_entre_datas()` | Detecta mudanças |
| S-4.21 | Obter Taxa Histórica | `_obter_taxa_historica()` | Busca taxa IPCA/IGPM |
| S-4.22 | Obter Valor Base Original | `_obter_valor_base_original_para_correcao()` | Valor original |
| S-4.23 | Identificar Duplicatas | `_identificar_correcoes_duplicadas()` | Detecta duplicidades |
| S-4.24 | Extrair Data Correção | `_extrair_data_correcao()` | Parser de data |
| S-4.25 | Obter Valor Atual | `_obter_valor_atual_cco()` | Valor corrente |

#### 4.2.6 Serviços - Correction Engine

| ID | Serviço | Classe/Método | Descrição |
|----|---------|---------------|-----------|
| S-4.26 | Correction Engine | `IPCACorrectionEngine` | Motor de cálculo |
| S-4.27 | Calcular Cenário 0 | `calcular_correcao_cenario_0()` | Gap simples |
| S-4.28 | Calcular Cenário 1 | `calcular_correcao_cenario_1()` | Gap com correção posterior |
| S-4.29 | Calcular Cenário 2 | `calcular_correcao_cenario_2()` | Gap com recuperação posterior |
| S-4.30 | Calcular Cenário Duplicatas | `calcular_correcao_cenario_duplicatas()` | Remove duplicatas |
| S-4.31 | Calcular Correção Individual | `_calcular_correcao_individual_gap()` | Cálculo unitário |
| S-4.32 | Identificar Correções Posteriores | `_identificar_correcoes_posteriores_cco()` | Busca subsequentes |
| S-4.33 | Recalcular Correção Posterior | `_calcular_recalculo_correcao_posterior()` | Ajusta posterior |
| S-4.34 | Identificar Recuperações | `_identificar_recuperacoes()` | Busca recuperações |
| S-4.35 | Compensar Recuperação C2 | `_calcular_compensacao_recuperacao_cenario2()` | Compensa recuperação |
| S-4.36 | Efeito Cascata | `_calcular_efeito_cascata_gaps()` | Propaga impactos |
| S-4.37 | Observação Cascata | `_gerar_observacao_compensacao_cascata()` | Documenta cascata |
| S-4.38 | Reativação CCO C2 | `_calcular_reativacao_cco_cenario2()` | Reativa CCO zerada |
| S-4.39 | Calcular Impacto | `_calcular_impacto_financeiro()` | Valor total impacto |
| S-4.40 | Gerar Preview | `_gerar_preview_data()` | Dados para visualização |

#### 4.2.7 Serviços - Aplicação

| ID | Serviço | Classe/Método | Descrição |
|----|---------|---------------|-----------|
| S-4.41 | Aplicar Cenário 0 | `aplicar_correcoes_cenario_0()` | Aplica gap simples |
| S-4.42 | Aplicar Cenário 1 | `aplicar_correcoes_cenario_1()` | Aplica com posterior |
| S-4.43 | Aplicar Cenário 2 | `aplicar_correcoes_cenario_2()` | Aplica com recuperação |
| S-4.44 | Aplicar Duplicatas | `aplicar_correcoes_cenario_duplicatas()` | Remove duplicata |
| S-4.45 | Reconstruir Lista | `_reconstruir_lista_correcoes()` | Monta lista final |
| S-4.46 | Reconstruir Lista C2 | `_reconstruir_lista_correcoes_cenario2()` | Lista específica C2 |
| S-4.47 | Ajustar Atributos | `_ajustar_atributos_correcoes_ipca()` | Normaliza dados |
| S-4.48 | Criar Ajuste Duplicata | `_criar_correcao_ajuste_duplicata()` | Gera ajuste |
| S-4.49 | Avaliar IPCA Vigente | `avaliar_ipca_ano_vigente()` | Verifica ano corrente |
| S-4.50 | Proposta IPCA Vigente | `_calcular_proposta_ipca_vigente()` | Gera proposta |

#### 4.2.8 Repositórios

| ID | Repositório | Collection | Descrição |
|----|-------------|------------|-----------|
| R-4.1 | Sessions | `ipca_correction_sessions` | Sessões de correção |
| R-4.2 | IPCA Entity | `ipca_entity` | Taxas IPCA históricas |
| R-4.3 | IGPM Entity | `igpm_entity` | Taxas IGPM históricas |
| R-4.4 | CCO Repository | `conta_custo_oleo_entity` | CCOs |

---

### 4.3 Módulo: Promoção de Correções IPCA/IGPM

#### 4.3.1 Telas

| ID | Tela | Arquivo | Descrição |
|----|------|---------|-----------|
| T-5.1 | Gerenciamento Promoção | `ipca_promocao/index.html` | Lista correções pendentes |
| T-5.2 | Detalhar Correção | `ipca_promocao/detalhar.html` | Detalhes da correção |
| T-5.3 | Timeline Correção | `ipca_promocao/timeline_correcao.html` | Timeline visual |
| T-5.4 | Memória de Cálculo | `ipca_promocao/memoria_calculo.html` | Detalhes do cálculo |

#### 4.3.2 Componentes de Interface

| ID | Componente | Localização | Descrição |
|----|------------|-------------|-----------|
| C-5.1 | Filtros Promoção | T-5.1 | Contrato, Status, Data |
| C-5.2 | Tabela Pendentes | T-5.1 | Grid com correções |
| C-5.3 | Estatísticas Cards | T-5.1 | Resumo por status |
| C-5.4 | Comparativo Original/Corrigido | T-5.2 | Side-by-side |
| C-5.5 | Timeline Centralizada | T-5.3 | Eventos cronológicos |
| C-5.6 | Memória Detalhada | T-5.4 | Fórmulas e cálculos |
| C-5.7 | Botão Promover | T-5.2 | Ação de promoção |

#### 4.3.3 Rotas/Endpoints

| ID | Endpoint | Método | Blueprint | Descrição |
|----|----------|--------|-----------|-----------|
| E-5.1 | `/ipca-promocao/` | GET | `ipca_promocao_bp` | Página principal |
| E-5.2 | `/ipca-promocao/api/estatisticas` | GET | `ipca_promocao_bp` | Cards de resumo |
| E-5.3 | `/ipca-promocao/api/contratos` | GET | `ipca_promocao_bp` | Lista contratos |
| E-5.4 | `/ipca-promocao/api/pesquisar` | POST | `ipca_promocao_bp` | Buscar pendentes |
| E-5.5 | `/ipca-promocao/detalhar/<id>` | GET | `ipca_promocao_bp` | Página de detalhes |
| E-5.6 | `/ipca-promocao/api/promover` | POST | `ipca_promocao_bp` | Executa promoção |
| E-5.7 | `/ipca-promocao/timeline/<id>` | GET | `ipca_promocao_bp` | Página timeline |
| E-5.8 | `/ipca-promocao/memoria-calculo/<id>` | GET | `ipca_promocao_bp` | Página memória |

#### 4.3.4 Serviços

| ID | Serviço | Método | Descrição |
|----|---------|--------|-----------|
| S-5.1 | Detalhar Correção | `detalhar_correcao()` | Carrega detalhes |
| S-5.2 | Promover Correção | `promover_correcao()` | Executa promoção |
| S-5.3 | Validar Promoção | `_validar_promocao()` | Verifica elegibilidade |
| S-5.4 | Atualizar CCO | `_atualizar_cco_e_criar_evento()` | Aplica e audita |

#### 4.3.5 Repositórios

| ID | Repositório | Collection | Descrição |
|----|-------------|------------|-----------|
| R-5.1 | Correções Staging | `ccos_corrigidas_staging` | CCOs pendentes promoção |
| R-5.2 | CCO Repository | `conta_custo_oleo_entity` | CCOs produção |


---

### 4.4 Módulo: Edição de CCOs

#### 4.3.1 Telas

| ID | Tela | Arquivo | Descrição |
|----|------|---------|-----------|
| T-5.1 | Gerenciamento de Edições | `cco_editor/index.html` | Tela inicial de edição, com filtro de pesquisa de CCOs e lista edições pendentes |
| T-5.2 | Pesquisar CCO | `cco_editor/pesquisar.html` | Tela de pesquisa avançada de CCO |
| T-5.3 | Editar CCO | `cco_editor/editar.html` | Tela de Edição de CCO |
| T-5.4 | Revisão de Edição | `cco_editor/revisar.html` | Detalhes da edição para revisão |

#### 4.3.2 Componentes de Interface

| ID | Componente | Localização | Descrição |
|----|------------|-------------|-----------|
| C-5.1 | Filtro Pesquisa | T-5.1 | Filtro de pesquisa por ID |
| C-5.2 | Botão Editar | T-5.1 | Ação de edição |
| C-5.3 | Botão Abrir Pesquisa Avançada | T-5.1 | Ação de pesquisa avançada |
| C-5.4 | Tabela de Edições Pendentes com Ações | T-5.1 | Grid com edições pendentes, com ações (revisar, editar novamente, excluir) |
| C-5.5 | Filtros Pesquisa | T-5.2 | id,Contrato, campo campo, remessa |
| C-5.6 | Tabela Resultados | T-5.2 | Grid com resultados das CCOs |
| C-5.7 | Botão Editar | T-5.2 | Ação de edição |
| C-5.8 | Header de Detalhes da CCO | T-5.3 | Informações gerais da CCO |
| C-5.9 | Botão Timeline | T-5.3 | Botão de timeline |
| C-5.10 | Aba de Edições de CCO | T-5.3 | Aba com campos de edição da raiz da CCO, com cálculos automáticos e sinalização de alterações |
| C-5.11 | Aba de Edições de Correções Monetárias | T-5.3 | Aba com campos de edição nas correções monetárias da CCO, com cálculos automáticos e sinalização de alterações |
| C-5.12 | Aba de inclusão de Correções Monetárias | T-5.3 | Aba para inclusão de novas correções monetárias na CCO, com cálculos automáticos |
| C-5.13 | Aba de validação das edições | T-5.3 | Aba com resultados das validações das edições, com aletas e sinalização de inconsistências |
| C-5.14 | Modal de Ajuda| T-5.3 | Modal com detalhes das regras utilizadas nas validações e cálculos |
| C-5.15 | Botão Salvar| T-5.3 | Botão para salvar edições |
| C-5.16 | Botão Resetar| T-5.3 | Botão para resetar edições |
| C-5.17 | Botão Cancelar| T-5.3 | Botão para cancelar edições |
| C-5.18 | Botão Confirmar Inconsistencias| T-5.3 | Botão para confirmar edições com inconsistências |
| C-5.19 | Header de Detalhes da CCO | T-5.4 | Informações gerais da CCO |
| C-5.21 | Cards de Estatísticas de Edições na CCO | T-5.4 | Resumos de campos alterados, impacto financeiro, novas correções e toal de correções (de -> para) |
| C-5.21 | Detalhalmento de Edições na CCO | T-5.4 | detalhamento de atributos alterados na CCOs (de -> para) |
| C-5.22 | Card de Correções Adicionadas | T-5.4 | Resumo das correções adicionadas na CCO |
| C-5.23 | Histórico de Alterações da CCO | T-5.4 | Tabela com histórico de alterações da CCO |
| C-5.24 | Botão Ir para Promoção | T-5.4 | Ação de ir para promoção |
| C-5.25 | Botão Editar Novamente | T-5.4 | Ação de editar novamente |
| C-5.26 | Botão Descartar Edição | T-5.4 | Ação de descartar edição |
| C-5.27 | Botão Voltar | T-5.4 | Ação de voltar |

#### 4.3.3 Rotas/Endpoints

| ID | Endpoint | Método | Blueprint | Descrição |
|----|----------|--------|-----------|-----------|
| E-5.1 | `/cco-editor/` | GET | `cco_editor_bp` | Página principal |
| E-5.2 | `/cco-editor/api/edicoes-pendentes` | GET | `cco_editor_bp` | Tabeala de edições pendentes |
| E-5.3 | `/cco-editor/editar/<id>` | GET | `cco_editor_bp` | Página de edição |
| E-5.4 | `/cco-editor/revisar/<id>` | GET | `cco_editor_bp` | Página de revisão |
| E-5.5 | `/ipca-promocao/detalhar/<id>` | GET | `ipca_promocao_bp` | Página de detalhes da promocão |
| E-5.6 | `/cco-editor/api/contratos` | GET | `cco_editor_bp` | Lista contratos |
| E-5.7 | `/cco-editor/pesquisar` | POST | `cco_editor_bp` | Buscar pendentes |
| E-5.8 | `/ipca-promocao/api/promover` | POST | `ipca_promocao_bp` | Executa promoção |

#### 4.3.4 Serviços

| ID | Serviço | Método | Descrição |
|----|---------|--------|-----------|
| S-5.1 | Burcar CCO para Edição | | `buscar_cco_para_edicao()` | Carrega detalhes |
| S-5.2 | Aplicar Edição | | `aplicar_edicao()` | aplica edição |
| S-5.3 | Obter Sessão de Edição | | `obter_sessao_edicao` | Obtém detalhes de uma sessão de edição |

#### 4.3.5 Repositórios

| ID | Repositório | Collection | Descrição |
|----|-------------|------------|-----------|
| R-5.1 | Correções Staging | `ccos_corrigidas_staging` | CCOs pendentes promoção |
| R-5.2 | CCO Repository | `conta_custo_oleo_entity` | CCOs produção |

---

## 5. MÓDULO TRANSVERSAL: AUTENTICAÇÃO E CONTROLE DE ACESSO
## Integração API Gateway Java/JHipster

### 5.1 Arquitetura de Integração
```
┌─────────────────────────────────────────────────────────────────┐
│                      USUÁRIO (Browser)                          │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│              API GATEWAY JAVA (JHipster)                        │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  • Login/Logout (Spring Security)                       │    │
│  │  • Gestão de Sessão                                     │    │
│  │  • Geração de Token JWT                                 │    │
│  │  • Proteção contra Brute Force                          │    │
│  │  • Recuperação de Senha                                 │    │
│  └─────────────────────────────────────────────────────────┘    │
└───────────────────────────┬─────────────────────────────────────┘
                            │ Token JWT (Header Authorization)
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│              APLICAÇÃO PYTHON (Flask)                           │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  • Validação de Token JWT                               │    │
│  │  • Mapeamento Roles → Permissões Granulares             │    │
│  │  • Decorators de Autorização                            │    │
│  │  • Auditoria de Ações de Negócio                        │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 Telas (Reduzido)

| ID | Tela | Arquivo | Descrição |
|----|------|---------|-----------|
| T-0.1 | Acesso Negado | `auth/acesso_negado.html` | Mensagem de permissão insuficiente |
| T-0.2 | Sessão Expirada | `auth/sessao_expirada.html` | Redirecionamento para Gateway |
| T-0.3 | Gerenciar Mapeamento de Roles | `auth/admin_roles_mapping.html` | Mapeia roles Gateway → permissões (admin) |
| T-0.4 | Logs de Ações | `auth/logs_acoes.html` | Auditoria de ações de negócio (admin) |

### 5.3 Componentes de Interface

| ID | Componente | Localização | Descrição |
|----|------------|-------------|-----------|
| C-0.1 | Mensagem Acesso Negado | T-0.1 | Card com permissão necessária |
| C-0.2 | Botão Voltar ao Portal | T-0.1, T-0.2 | Link para Gateway Java |
| C-0.3 | Redirect Automático | T-0.2 | JavaScript para redirecionar ao login |
| C-0.4 | Tabela Mapeamento Roles | T-0.3 | Grid roles × permissões |
| C-0.5 | Matriz de Permissões | T-0.3 | Checkboxes por módulo/ação |
| C-0.6 | Filtros Log Ações | T-0.4 | Usuário, data, ação, módulo |
| C-0.7 | Tabela Logs Ações | T-0.4 | Grid com histórico de ações |
| C-0.8 | Header Usuário Logado | `base.html` | Nome do token, dropdown logout (Gateway) |
| C-0.9 | Menu Dinâmico | `base.html` | Itens conforme permissões mapeadas |

### 5.4 Rotas/Endpoints

| ID | Endpoint | Método | Blueprint | Proteção | Descrição |
|----|----------|--------|-----------|----------|-----------|
| E-0.1 | `/auth/acesso-negado` | GET | `auth_bp` | Pública | Página de acesso negado |
| E-0.2 | `/auth/sessao-expirada` | GET | `auth_bp` | Pública | Página sessão expirada |
| E-0.3 | `/auth/logout` | GET | `auth_bp` | Autenticado | Redireciona para logout do Gateway |
| E-0.4 | `/auth/api/usuario-atual` | GET | `auth_bp` | Autenticado | Retorna dados do token decodificado |
| E-0.5 | `/auth/api/minhas-permissoes` | GET | `auth_bp` | Autenticado | Lista permissões do usuário |
| E-0.6 | `/admin/roles-mapping` | GET | `admin_bp` | Admin | Página mapeamento roles |
| E-0.7 | `/admin/api/roles-mapping` | GET | `admin_bp` | Admin | Listar mapeamentos |
| E-0.8 | `/admin/api/roles-mapping` | POST | `admin_bp` | Admin | Criar/atualizar mapeamento |
| E-0.9 | `/admin/api/roles-mapping/<role>` | DELETE | `admin_bp` | Admin | Remover mapeamento |
| E-0.10 | `/admin/logs-acoes` | GET | `admin_bp` | Admin | Página logs de ações |
| E-0.11 | `/admin/api/logs-acoes` | POST | `admin_bp` | Admin | Buscar logs com filtros |
| E-0.12 | `/admin/api/logs-acoes/exportar` | POST | `admin_bp` | Admin | Exportar logs CSV |

### 5.5 Serviços

| ID | Serviço | Classe/Método | Descrição |
|----|---------|---------------|-----------|
| **JWT/Token** |
| S-0.1 | JWT Service | `JWTService` | Validação e decodificação de tokens |
| S-0.2 | Validar Token | `validar_token()` | Verifica assinatura com chave pública |
| S-0.3 | Decodificar Token | `decodificar_token()` | Extrai payload (sub, email, roles) |
| S-0.4 | Verificar Expiração | `verificar_expiracao()` | Checa claim `exp` do token |
| S-0.5 | Extrair Roles | `extrair_roles()` | Obtém roles do claim `auth` |
| **Mapeamento de Roles** |
| S-0.6 | Role Mapping Service | `RoleMappingService` | Mapeia roles Gateway → permissões |
| S-0.7 | Obter Permissões por Role | `obter_permissoes_por_role()` | Consulta mapeamento |
| S-0.8 | Obter Permissões Usuário | `obter_permissoes_usuario()` | Consolida todas as permissões |
| S-0.9 | Criar Mapeamento | `criar_mapeamento()` | Cadastra role → permissões |
| S-0.10 | Atualizar Mapeamento | `atualizar_mapeamento()` | Edita permissões da role |
| S-0.11 | Remover Mapeamento | `remover_mapeamento()` | Exclui mapeamento |
| S-0.12 | Listar Mapeamentos | `listar_mapeamentos()` | Lista todos os mapeamentos |
| **Controle de Acesso** |
| S-0.13 | Acesso Service | `AcessoService` | Verifica permissões |
| S-0.14 | Verificar Permissão | `verificar_permissao()` | Checa se usuário pode acessar |
| S-0.15 | Obter Menu Permitido | `obter_menu_usuario()` | Itens de menu por permissão |
| **Auditoria** |
| S-0.16 | Auditoria Service | `AuditoriaService` | Registro de ações de negócio |
| S-0.17 | Registrar Ação | `registrar_acao()` | Log de ações em módulos |
| S-0.18 | Buscar Logs | `buscar_logs()` | Consulta logs com filtros |
| S-0.19 | Exportar Logs | `exportar_logs_csv()` | Gera CSV de auditoria |

### 5.6 Decorators/Middlewares

| ID | Componente | Arquivo | Descrição |
|----|------------|---------|-----------|
| D-0.1 | `@jwt_required` | `utils/auth_decorators.py` | Valida token JWT do Gateway |
| D-0.2 | `@permission_required(perm)` | `utils/auth_decorators.py` | Exige permissão específica |
| D-0.3 | `@admin_required` | `utils/auth_decorators.py` | Exige role ROLE_ADMIN |
| D-0.4 | `@audit_action(action)` | `utils/auth_decorators.py` | Registra ação em log |
| D-0.5 | `before_request` | `__init__.py` | Valida token em cada request |
| D-0.6 | `inject_user_context` | `utils/auth_decorators.py` | Injeta `g.user` no contexto Flask |

### 5.8 Repositórios

| ID | Repositório | Classe | Métodos Principais |
|----|-------------|--------|-------------------|
| R-0.1 | Role Mapping Repository | `RoleMappingRepository` | `buscar_por_role()`, `listar_todos()`, `inserir()`, `atualizar()`, `remover()` |
| R-0.2 | Log Ação Repository | `LogAcaoRepository` | `inserir()`, `buscar_por_filtros()` |

### 5.9 Collections MongoDB

| Collection | Descrição | Campos Principais |
|------------|-----------|-------------------|
| `roles_mapping` | Mapeamento roles Gateway → permissões | `_id`, `role_gateway`, `permissoes[]`, `descricao`, `ativo` |
| `logs_acoes` | Auditoria de ações de negócio | `_id`, `usuario_id`, `usuario_email`, `acao`, `modulo`, `ip`, `data_hora`, `detalhes`, `entidade_afetada` |

**Nota:** Collections `usuarios`, `sessoes`, `tokens_reset` são **eliminadas** - gerenciadas pelo Gateway Java.

### 5.10 Estrutura de Mapeamento Roles → Permissões

| Role Gateway (JHipster) | Permissões Mapeadas (App Python) |
|-------------------------|----------------------------------|
| `ROLE_ADMIN` | Todas as permissões |
| `ROLE_GESTOR` | `portal.*`, `ferramentas.ipca_correcao.visualizar`, `ferramentas.ipca_correcao.analisar` |
| `ROLE_ANALISTA` | `portal.remessas.*`, `portal.ccos.*`, `portal.saldos.visualizar` |
| `ROLE_OPERADOR` | `portal.remessas.visualizar`, `portal.ccos.visualizar` |
| `ROLE_AUDITOR` | `portal.*`, `admin.logs.visualizar` |

### 5.11 Estrutura de Permissões Granulares

| Módulo | Permissões Disponíveis |
|--------|------------------------|
| `portal.remessas` | `visualizar`, `analisar`, `exportar` |
| `portal.ccos` | `visualizar`, `timeline` |
| `portal.saldos` | `visualizar`, `exportar` |
| `ferramentas.recalculo_tp` | `visualizar`, `executar`, `aplicar` |
| `ferramentas.ipca_correcao` | `visualizar`, `analisar`, `aprovar`, `aplicar` |
| `ferramentas.ipca_promocao` | `visualizar`, `promover` |
| `admin.roles_mapping` | `visualizar`, `editar` |
| `admin.logs` | `visualizar`, `exportar` |

### 5.12 Configurações

| ID | Configuração | Descrição | Default |
|----|--------------|-----------|---------|
| CF-6 | `GATEWAY_PUBLIC_KEY` | Chave pública RSA do Gateway para validar JWT | (obrigatório) |
| CF-7 | `GATEWAY_PUBLIC_KEY_URL` | URL para obter chave pública (JWKS) | `https://gateway/oauth2/jwks` |
| CF-8 | `GATEWAY_LOGIN_URL` | URL de login do Gateway | `https://gateway/login` |
| CF-9 | `GATEWAY_LOGOUT_URL` | URL de logout do Gateway | `https://gateway/logout` |
| CF-10 | `JWT_ALGORITHM` | Algoritmo de assinatura | `RS256` |
| CF-11 | `JWT_AUDIENCE` | Audience esperado no token | `account` |

### 5.13 Fluxo de Autenticação
```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Usuário    │     │   Gateway    │     │  App Python  │
│   Browser    │     │    Java      │     │    Flask     │
└──────┬───────┘     └──────┬───────┘     └──────┬───────┘
       │                    │                    │
       │  1. Acessa /app    │                    │
       │───────────────────►│                    │
       │                    │                    │
       │  2. Sem token?     │                    │
       │     Redireciona    │                    │
       │◄───────────────────│                    │
       │                    │                    │
       │  3. Login no Gateway                    │
       │───────────────────►│                    │
       │                    │                    │
       │  4. Token JWT      │                    │
       │◄───────────────────│                    │
       │                    │                    │
       │  5. Request + Token│                    │
       │────────────────────┼───────────────────►│
       │                    │                    │
       │                    │  6. Valida JWT     │
       │                    │     (chave pública)│
       │                    │                    │
       │                    │  7. Extrai roles   │
       │                    │     Mapeia perms   │
       │                    │                    │
       │  8. Resposta       │                    │
       │◄───────────────────┼────────────────────│
       │                    │                    │
```
---

## 6. UTILITÁRIOS E INFRAESTRUTURA

### 6.1 Conversores (`utils/converters.py`)

| ID | Função | Descrição |
|----|--------|-----------|
| U-1.1 | `converter_decimal128_para_float()` | Converte Decimal128 → float |
| U-1.2 | `formatar_data_brasileira()` | Formata datetime → dd/mm/yyyy |
| U-1.3 | `formatar_data_simples()` | Formata datetime → yyyy-mm-dd |
| U-1.4 | `validar_e_converter_valor_monetario()` | Valida e converte valores |
| U-1.5 | `processar_json_mongodb()` | Processa tipos BSON |

### 6.2 Cache (`utils/cache_utils.py`)

| ID | Componente | Descrição |
|----|------------|-----------|
| U-2.1 | `CacheManager` | Gerenciador de cache |
| U-2.2 | `configure_cache()` | Configura Flask-Caching |
| U-2.3 | `store_data()` | Armazena dados com TTL |
| U-2.4 | `retrieve_data()` | Recupera dados do cache |

### 6.3 Configuração (`config.py`)

| ID | Configuração | Descrição |
|----|--------------|-----------|
| CF-1 | `MONGO_URI` | Conexão MongoDB principal |
| CF-2 | `CA_CERTIFICATE_PATH` | Certificado TLS MongoDB |
| CF-3 | `CACHE_DIR_PATH` | Diretório de cache |
| CF-4 | `SECRET_KEY` | Chave sessão Flask |

---

## 7. RESUMO QUANTITATIVO

### 7.1 Totais por Tipo de Componente

| Tipo | Quantidade (em separado o módulo de autenticação) |
|------|------------|
| **Telas (Templates)** | 16 + 4 |
| **Componentes de UI** | 50 + 9 |
| **Endpoints (APIs)** | 31 + 12 |
| **Serviços** |31 + 4  |
| **Repositórios** | 11 + 2|
| **Utilitários** | 12 |
| **Configurações** | 11 |

### 7.2 Totais por Módulo

| Módulo | Telas | Endpoints | Serviços |
|--------|-------|-----------|----------|
| Autenticação e Controle de Acesso | 4 | 12 | 4 |
| CCO Timeline | 2 | 2 | 3 |
| Recálculo TP | 4 | 7 | 6 |
| Correção IPCA/IGPM | 2 | 6 | 17 |
| Promoção IPCA/IGPM | 4 | 8 | 2 |
| Edição de CCOs | 4 | 8 | 3 |
| **TOTAL ** | **20** | **43** | **35** |


### 7.3 Complexidade por Módulo

| Módulo | Complexidade | Justificativa |
|--------|--------------|---------------|
| Autenticação e Acesso  | Média | Segurança de senhas, gestão de sessões, matriz de permissões, auditoria |
| CCO Timeline | Baixa | Visualização linear |
| Recálculo TP | Média | Cálculos financeiros, persistência |
| Correção IPCA/IGPM | **Alta** | 4 cenários, cascata, regras complexas |
| Promoção | Média | Workflow staging → produção |
| Edição de CCOs | Média | Visualização linear, regras complexas |

---

## 8. DEPENDÊNCIAS ENTRE MÓDULOS

```

┌─────────────────────────────────────────────────────────────────┐
│              AUTENTICAÇÃO E CONTROLE DE ACESSO (cenário B)      │
│   (Transversal - protege todos os módulos abaixo)               │
│   @login_required | @permission_required | @audit_action        │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                    MÓDULO PRINCIPAL                         │
│                      (index.html)                           │
└─────────────────┬───────────────────────────────────────────┘
                  │
    ┌─────────────┴─────────────┐
    │                           │
┌───▼───────────────┐   ┌───────▼───────────────┐
│   FRENTE 1        │   │   FRENTE 2            │
│   (Portal)        │   │   (Ferramentas)       │
└───┬───────────────┘   └───────┬───────────────┘
    │                           │
┌───▼───────────────┐   ┌───────▼────────────────────────────┐
│                   │   │ Recálculo TP                       │
│                   │   │        │                           │
│                   │   │        ▼                           │
│ CCO Timeline ◄────┼───┼── IPCA Correção◄──── Edição de CCOs│
│                   │   │        │                           │
│                   │   │        │                           │
|                   │   │        │                           │
└───────────────────┘   │        ▼                           │
                        │ IPCA Promoção                      │
                        └────────────────────────────────────┘
```

---

## 9. COLLECTIONS MONGODB

| Collection | Módulos que Utilizam | Tipo |
|------------|---------------------|------|
| `conta_custo_oleo_entity` | Todos/Análise Saldos | Leitura/Escrita |
| `ipca_entity` | IPCA Correção | Leitura |
| `igpm_entity` | IPCA Correção | Leitura |
| `ipca_correction_sessions` | IPCA Correção | Leitura/Escrita |
| `ccos_corrigidas_staging` | IPCA Promoção | Leitura/Escrita |
| `temp_recalculos` (local) | Recálculo TP | Leitura/Escrita |
| `usuarios` | Autenticação (penas cenário A) | Leitura/Escrita |
| `perfis` | Autenticação (penas cenário A) | Leitura/Escrita |
| `sessoes` | Autenticação (penas cenário A) | Leitura/Escrita |
| `logs_acesso` | Autenticação (penas cenário A) | Leitura/Escrita |
| `tokens_reset` | Autenticação | Leitura/Escrita |

---

## 10. OBSERVAÇÕES TÉCNICAS

### 10.1 Padrões Identificados

1. **Arquitetura em Camadas**: Routes → Services → Repositories
2. **Blueprint Pattern**: Separação lógica por módulo funcional
3. **Session Management**: Persistência de sessões de correção no MongoDB
4. **Event Sourcing**: Trilha de auditoria em correções
5. **Staging Pattern**: Ambiente intermediário para promoção

### 10.2 Pontos de Atenção

1. **Conversão de Tipos**: Necessário tratamento especial para Decimal128 e datetime
2. **Cache de Sessão**: Análises complexas armazenadas temporariamente
3. **Integridade de Dados**: Correções geram cópias com sufixo (não alteram original)
4. **Cascata de Efeitos**: Cenário 2 requer cálculo de propagação

---

### 11. Status de Implementação por Módulo (Estimativas)

| Módulo | Complexidade | Status | Estimado (h) | Realizado (h) | Realizado (%) |
|--------|--------------|--------|--------------|---------------|---------------|
| **FRENTE 1 - PORTAL** |
| CCO Timeline | Baixa-Média | Em análise | 55h | - | 0% |
| **FRENTE 2 - FERRAMENTAS** |
| Recálculo TP | Média | Em análise | 100h | - | 0% |
| Correção IPCA/IGPM | Alta | Em análise | 360h | - | 0% |
| Promoção IPCA/IGPM | Média | Em análise | 100h | - | 0% |
| Edição de CCOs | Média | Em análise | 120h | - | 0% 
| **TRANSVERSAL** |
| Autenticação -  | Baixa-Média | Previsto | 55h | - | 0% |


### Observação
 - **As estimativas de desenvolvimento foram feitas sem considerar o Wizard, e não devem ser interpretadas como 100%**
---


---

### 11.2 Análise de Risco por Módulo

| Módulo | Risco | Justificativa |
|--------|-------|---------------|
| CCO Timeline | Baixo | escopo bem definido |
| Correção IPCA/IGPM | **Alto** | Módulo mais complexo, 4 cenários, efeito cascata, muitos serviços |
| Recálculo TP | Médio | Cálculos financeiros, integração com timeline |
| Promoção | Baixo | workflow simples |
| Edição de CCO | Médio | Cálculos financeiros, integração com timeline |
| Autenticação | Baixo | Cenário delega complexidade ao Gateway Java |



*Documento gerado para fins de levantamento e estimativa de esforço interno. Não deve ser compartilhado com o cliente*




