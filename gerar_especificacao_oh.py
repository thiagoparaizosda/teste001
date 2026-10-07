#!/usr/bin/env python3
"""
Script para gerar o documento de especificação técnica do Módulo de Análise e Correção de OH.
Requisito US-21700: Entregar ao cliente um documento de escopo (.docx) do Módulo de Análise e Correção de OH
"""

from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import datetime

def add_heading_with_style(doc, text, level=1):
    """Add a heading with consistent styling."""
    heading = doc.add_heading(text, level=level)
    heading.style = f'Heading {level}'
    return heading

def add_placeholder_for_screenshot(doc, title, caption):
    """Add a placeholder for a screenshot with title and caption."""
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(12)

    # Add a bordered rectangle as placeholder
    run = p.add_run('[ESPAÇO RESERVADO PARA IMAGEM/PROTÓTIPO]')
    run.italic = True
    run.font.size = Pt(10)
    run.font.color.rgb = RGBColor(128, 128, 128)

    # Add title below
    p_title = doc.add_paragraph()
    r_title = p_title.add_run(title)
    r_title.bold = True
    r_title.font.size = Pt(11)

    # Add caption below
    p_caption = doc.add_paragraph()
    r_caption = p_caption.add_run(caption)
    r_caption.italic = True
    r_caption.font.size = Pt(9)

    return p

def shade_cell(cell, color):
    """Shade a table cell with a background color."""
    shading_elm = OxmlElement('w:shd')
    shading_elm.set(qn('w:fill'), color)
    cell._element.get_or_add_tcPr().append(shading_elm)

def create_specification_document():
    """Create the OH Correction Module specification document."""

    doc = Document()

    # ========== DOCUMENT TITLE ==========
    title = doc.add_heading('Especificação Técnica - Módulo de Análise e Correção de Overhead (OH)', 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    subtitle = doc.add_paragraph('Contas de Custo de Óleo (CCOs) - SGPP')
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitle_run = subtitle.runs[0]
    subtitle_run.font.size = Pt(12)
    subtitle_run.italic = True

    # Document metadata
    meta_para = doc.add_paragraph()
    meta_para.add_run(f'Data: {datetime.date.today().strftime("%d de %B de %Y")}').font.size = Pt(10)
    meta_para.alignment = WD_ALIGN_PARAGRAPH.CENTER

    doc.add_paragraph()  # Blank line

    # ========== SEÇÃO 1: VISÃO GERAL E OBJETIVOS ==========
    add_heading_with_style(doc, '1. Visão Geral e Objetivos', 1)

    add_heading_with_style(doc, '1.1 Objetivo de Negócio', 2)
    doc.add_paragraph(
        'O Módulo de Análise e Correção de Overhead (OH) resolve um problema crítico no sistema de gestão de '
        'Contas de Custo de Óleo (CCOs): valores de overhead calculados incorretamente não podiam ser corrigidos de forma segura, '
        'e as correções não se refletiam automaticamente nos valores que dependem delas (correções monetárias IPCA/IGPM e recuperações).'
    )

    doc.add_paragraph(
        'Este módulo oferece ao cliente a capacidade de:'
    )

    benefits = [
        'Identificar automaticamente quais CCOs possuem overhead incorreto, classificando cada uma como "OK", "Atenção" ou "Erro"',
        'Analisar o cálculo de overhead por faixas progressivas, compreendendo como cada CCO é enquadrada',
        'Corrigir valores de overhead com segurança, visualizando o impacto antes da aplicação',
        'Reprocessar automaticamente todas as correções monetárias subsequentes, garantindo consistência em cascata',
        'Revisar as correções em uma área temporária antes de promover para produção',
        'Exportar relatórios detalhados das análises e correções realizadas'
    ]
    for benefit in benefits:
        doc.add_paragraph(benefit, style='List Bullet')

    add_heading_with_style(doc, '1.2 Público-alvo / Atores', 2)

    actors_table = doc.add_table(rows=3, cols=2)
    actors_table.style = 'Light Grid Accent 1'

    # Header
    hdr_cells = actors_table.rows[0].cells
    hdr_cells[0].text = 'Ator'
    hdr_cells[1].text = 'Responsabilidade'

    # Analyst row
    row_cells = actors_table.rows[1].cells
    row_cells[0].text = 'Analista de Conformidade (PPSA)'
    row_cells[1].text = 'Utiliza o módulo para identificar overhead incorreto, simular correções e revisar antes de aprovar'

    # Manager row
    row_cells = actors_table.rows[2].cells
    row_cells[0].text = 'Gestor/Gestor de Projeto'
    row_cells[1].text = 'Aprova as correções simuladas e as promove para produção'

    doc.add_paragraph()  # Blank line

    # ========== SEÇÃO 2: DEFINIÇÃO DO ESCOPO ==========
    add_heading_with_style(doc, '2. Definição do Escopo', 1)

    add_heading_with_style(doc, '2.1 Dentro do Escopo', 2)
    in_scope = [
        'Análise automática de overhead em CCOs: verificação de conformidade com as regras de cálculo',
        'Classificação de status: OK (conforme as regras), Atenção (base negativa) ou Erro (valores fora da tolerância)',
        'Tela de análise por faixas progressivas: visualização detalhada de como o overhead de exploração é distribuído nas faixas',
        'Correção manual de overhead com recálculo em cascata: propagação automática da alteração para CCOs derivadas da mesma remessa (cascata horizontal)',
        'Reprocessamento completo do histórico de correções monetárias (IPCA/IGPM) da CCO corrigida (cascata temporal)',
        'Simulação obrigatória antes da aplicação: tela mostrando valores anteriores, valores corrigidos e diferenças',
        'Área temporária para correções: gravação segura das correções em `conta_custo_oleo_corrigida_entity` antes da promoção',
        'Revisão e aprovação: etapa de validação antes de promover para produção',
        'Promoção para produção: integração com o fluxo existente de promoção de correções',
        'Exportação de relatório: documento detalhado com todas as CCOs analisadas, status, ajustes realizados e impactos financeiros'
    ]
    for item in in_scope:
        doc.add_paragraph(item, style='List Bullet')

    add_heading_with_style(doc, '2.2 Fora do Escopo', 2)
    out_of_scope = [
        'Alteração das regras de cálculo de overhead: este módulo implementa as regras tal como definidas; propostas de mudança nas alíquotas (1%, 3%, 2%) '
        'ou nas faixas (R$5M, R$15M) devem ser feitas em projeto separado com aprovação de negócio',
        'Correção de overhead em massa sem revisão: todas as correções passam por simulação e revisão, não há aplicação em lote direto',
        'Integração com sistemas externos de BI ou auditoria: o módulo gera relatórios internos; exportação para sistemas terceirizados fica para fase posterior'
    ]
    for item in out_of_scope:
        doc.add_paragraph(item, style='List Bullet')

    doc.add_paragraph()  # Blank line

    # ========== SEÇÃO 3: REGRAS DE NEGÓCIO E REQUISITOS ==========
    add_heading_with_style(doc, '3. Regras de Negócio e Requisitos', 1)

    add_heading_with_style(doc, '3.1 Regras de Cálculo de Overhead', 2)

    doc.add_paragraph(
        'O overhead (OH) é um percentual aplicado aos valores reconhecidos em gastos de exploração e produção. '
        'O cálculo diferencia-se por fase, usa faixas progressivas e é acumulado por contrato em cada ano-calendário:'
    )

    # OH Production Rule
    doc.add_heading('OH de Produção', level=3)
    doc.add_paragraph(
        'Taxa fixa de 1% sobre o `valorReconhecidoProducao`',
        style='List Bullet'
    )
    doc.add_paragraph(
        'Tolerância permitida: ±0,005% do valor calculado (margem para arredondamentos de sistema)',
        style='List Bullet'
    )
    doc.add_paragraph(
        'Fórmula: OH_Produção = valorReconhecidoProducao × 0,01',
        style='List Bullet'
    )

    # OH Exploration Rule
    doc.add_heading('OH de Exploração (Faixas Progressivas)', level=3)
    doc.add_paragraph(
        'O cálculo usa faixas progressivas baseadas no acumulado de valores reconhecidos em exploração por contrato e ano-calendário:'
    )

    # Create bands table
    bands_table = doc.add_table(rows=4, cols=3)
    bands_table.style = 'Light Grid Accent 1'

    hdr_cells = bands_table.rows[0].cells
    hdr_cells[0].text = 'Faixa de Acumulado'
    hdr_cells[1].text = 'Taxa de OH'
    hdr_cells[2].text = 'Aplicação'

    row_cells = bands_table.rows[1].cells
    row_cells[0].text = 'R$ 0 até R$ 5.000.000'
    row_cells[1].text = '3%'
    row_cells[2].text = 'Aplicada a valores na faixa'

    row_cells = bands_table.rows[2].cells
    row_cells[0].text = 'R$ 5.000.001 até R$ 15.000.000'
    row_cells[1].text = '2%'
    row_cells[2].text = 'Aplicada a valores na faixa'

    row_cells = bands_table.rows[3].cells
    row_cells[0].text = 'Acima de R$ 15.000.000'
    row_cells[1].text = '1%'
    row_cells[2].text = 'Aplicada a valores na faixa'

    doc.add_paragraph(
        'Exemplo: Uma CCO com `valorReconhecidoExploracao` de R$ 12.000.000 é enquadrada nas faixas como:',
        style='List Bullet'
    )
    doc.add_paragraph(
        'R$ 5.000.000 × 3% = R$ 150.000 (primeira faixa)',
        style='List Number'
    )
    doc.add_paragraph(
        'R$ 7.000.000 × 2% = R$ 140.000 (segunda faixa)',
        style='List Number'
    )
    doc.add_paragraph(
        'OH_Exploração Total = R$ 150.000 + R$ 140.000 = R$ 290.000',
        style='List Number'
    )

    # Accumulation rules
    doc.add_heading('Acumulação e Reinício Anual', level=3)
    doc.add_paragraph(
        'As CCOs de um mesmo contrato no mesmo ano-calendário são somadas (apenas valores positivos da raiz) em ordem de data de reconhecimento'
    )
    doc.add_paragraph(
        'O acumulado reinicia a cada ano-calendário (01/01 de cada ano)'
    )
    doc.add_paragraph(
        'Se uma CCO cruza duas faixas diferentes (exemplo: acumulado anterior era R$ 4.500.000 e a nova CCO adiciona R$ 2.000.000, '
        'totalizando R$ 6.500.000), o cálculo é proporcional: '
        'R$ 500.000 (até completar R$ 5M) × 3% + R$ 1.500.000 (acima de R$ 5M) × 2%'
    )

    # OH Total
    doc.add_heading('OH Total', level=3)
    doc.add_paragraph(
        'OH_Total = OH_Exploração + OH_Produção'
    )
    doc.add_paragraph(
        'O OH total é somado ao `valorReconhecido` para compor o `valorReconhecidoComOH`'
    )

    # Special Cases
    doc.add_heading('Casos Especiais', level=3)
    special_cases = [
        'Base zero (`valorReconhecidoExploracao` = 0 ou `valorReconhecidoProducao` = 0): overhead correspondente é zero',
        'Base negativa (`valorReconhecidoExploracao < 0` ou `valorReconhecidoProducao < 0`): '
        'a CCO é marcada com status "Atenção" (não "Erro"), pois bases negativas podem ocorrer em compensações',
        'Origem AEGV (Associação de Empresas Gestoras da Atividade de Exploração e Produção de Petróleo): '
        'overhead total é sempre zero, independentemente dos valores reconhecidos'
    ]
    for case in special_cases:
        doc.add_paragraph(case, style='List Bullet')

    # Classificação de Status
    add_heading_with_style(doc, '3.2 Classificação de Status da CCO', 2)

    status_table = doc.add_table(rows=4, cols=3)
    status_table.style = 'Light Grid Accent 1'

    hdr_cells = status_table.rows[0].cells
    hdr_cells[0].text = 'Status'
    hdr_cells[1].text = 'Condição'
    hdr_cells[2].text = 'Ação Recomendada'
    shade_cell(hdr_cells[0], 'D3D3D3')
    shade_cell(hdr_cells[1], 'D3D3D3')
    shade_cell(hdr_cells[2], 'D3D3D3')

    row_cells = status_table.rows[1].cells
    row_cells[0].text = 'OK'
    row_cells[1].text = 'O overhead calculado está dentro da tolerância permitida (±0,005%)'
    row_cells[2].text = 'Nenhuma ação necessária'

    row_cells = status_table.rows[2].cells
    row_cells[0].text = 'Atenção'
    row_cells[1].text = 'Base negativa ou situação que requer revisão, mas não é erro'
    row_cells[2].text = 'Revisar contexto; avaliar se há compensação esperada'

    row_cells = status_table.rows[3].cells
    row_cells[0].text = 'Erro'
    row_cells[1].text = 'O overhead está fora da tolerância ou valores são inconsistentes'
    row_cells[2].text = 'Corrigir via simulação e promoção'

    doc.add_paragraph()  # Blank line

    # Requisitos Não-Funcionais
    add_heading_with_style(doc, '3.3 Requisitos Não-Funcionais', 2)

    nfr = [
        'Desempenho: análise de até 500 CCOs por consulta deve completar em menos de 30 segundos',
        'Integridade de dados: todas as correções aplicadas à área temporária devem ser auditadas (usuário, timestamp, valores anteriores/posteriores)',
        'Segurança: acesso ao módulo requer permissões explícitas (CCO_VIEW para análise, CCO_EDIT para simulação, CORRECAO_PROMOTE para promoção)',
        'Consistência de cascata: quando uma CCO é corrigida, todas as CCOs derivadas da mesma remessa devem ser reprocessadas automaticamente',
        'Rastreabilidade: histórico de todas as correções deve ficar gravado no MongoDB com referência às sessões de análise'
    ]
    for req in nfr:
        doc.add_paragraph(req, style='List Bullet')

    # Dependências Mapeadas
    add_heading_with_style(doc, '3.4 Dependências Mapeadas', 2)

    deps = [
        'Módulo existente de Correção IPCA/IGPM (`IPCACorrectionOrchestrator`, `IPCACorrectionEngine`, `IPCAGapAnalyzer`): '
        'O módulo de OH reusa o mesmo motor de orquestração, máquina de estados de 5 etapas e padrão de sessão para garantir consistência',
        'Fluxo existente de promoção de correções (`IPCAPromocaoService`, rotas `ipca_promocao`): '
        'As correções de OH devem ser promovidas usando o mesmo fluxo, que já controla validação, timeline comparativa e permissões',
        'Tabelas de índices IPCA/IGPM (`ipca_entity`, `igpm_entity`): '
        'Necessárias para reprocessar correções monetárias após uma correção de OH',
        'Matriz de permissões de acesso (`CCO_VIEW`, `CCO_EDIT`, `CORRECAO_PROMOTE` em `app/models/permission.py` e `docs/rbac_matrix.md`): '
        'Controla quem pode visualizar, editar e promover correções',
        'Serviço de auditoria (`AuditService`): '
        'Registra todas as ações de análise e correção para rastreabilidade',
        'Serviço de comparação de CCO (`CCOComparatorService`): '
        'Usado para exibir lado-a-lado a CCO antes e depois da correção',
        'Tela de análise existente por faixas (`/sgpp-cco-tools/verificacao-oh/analise-exp`): '
        'Já implementa a lógica de cálculo por faixas; será reutilizada como referência visual'
    ]
    for dep in deps:
        doc.add_paragraph(dep, style='List Bullet')

    doc.add_paragraph()  # Blank line

    # ========== SEÇÃO 4: ENTREGÁVEIS E CRITÉRIOS DE ACEITE ==========
    add_heading_with_style(doc, '4. Entregáveis e Critérios de Aceite', 1)

    add_heading_with_style(doc, '4.1 Artefatos Entregáveis', 2)

    deliverables = [
        'Componente de análise de overhead: serviço backend para verificar conformidade com as regras',
        'Tela de análise visual: exibição das CCOs com status (OK/Atenção/Erro) e detalhamento por faixas',
        'Tela de simulação de correção: mostra valores anteriores, valores corrigidos e impacto financeiro',
        'Tela de revisão e aprovação: etapa antes da promoção para produção',
        'Integração com promoção: correções de OH promovidas via fluxo existente',
        'Exportação de relatório: arquivo com análises, ajustes e impactos',
        'Documentação técnica: guia de uso para analistas e administradores',
        'Testes de aceitação: validação de todas as regras de cálculo e cascatas'
    ]
    for deliverable in deliverables:
        doc.add_paragraph(deliverable, style='List Bullet')

    # ========== SEÇÃO 4.2: DETALHAMENTO DOS COMPONENTES ==========
    add_heading_with_style(doc, '4.2 Detalhamento dos Componentes', 1)

    # Subseção 4.2.1: Análise e Verificação de OH
    add_heading_with_style(doc, '4.2.1 Análise e Verificação de OH', 2)

    # Telas - Análise
    add_heading_with_style(doc, 'Telas', 3)
    telas_analise_table = doc.add_table(rows=3, cols=4)
    telas_analise_table.style = 'Light Grid Accent 1'

    hdr_cells = telas_analise_table.rows[0].cells
    hdr_cells[0].text = 'ID'
    hdr_cells[1].text = 'Tela'
    hdr_cells[2].text = 'Arquivo'
    hdr_cells[3].text = 'Descrição'
    for cell in hdr_cells:
        shade_cell(cell, 'D3D3D3')

    row_cells = telas_analise_table.rows[1].cells
    row_cells[0].text = 'T-6.1'
    row_cells[1].text = 'Verificação Geral de OH'
    row_cells[2].text = 'verificacao_oh/index.html'
    row_cells[3].text = 'Exibe lista de CCOs com status (OK, Atenção, Erro), valores reconhecidos de exploração e produção, overhead calculado e verificado. Permite filtrar por contrato, campo e fase. Acesso para análise de detalhes por faixas.'

    row_cells = telas_analise_table.rows[2].cells
    row_cells[0].text = 'T-6.2'
    row_cells[1].text = 'Análise de OH Exploração por Faixas'
    row_cells[2].text = 'verificacao_oh/analise_exp.html'
    row_cells[3].text = 'Mostra o cálculo progressivo do overhead de exploração, indicando qual faixa cada valor se enquadra (exemplo: "R$ 5M × 3% = R$150k (Faixa 1)", "R$ 7M × 2% = R$140k (Faixa 2)"). Identifica quando uma CCO cruza limites de faixa e mostra cálculo proporcional.'

    # Componentes - Análise
    add_heading_with_style(doc, 'Componentes de Interface', 3)
    comp_analise_table = doc.add_table(rows=7, cols=4)
    comp_analise_table.style = 'Light Grid Accent 1'

    hdr_cells = comp_analise_table.rows[0].cells
    hdr_cells[0].text = 'ID'
    hdr_cells[1].text = 'Componente'
    hdr_cells[2].text = 'Localização'
    hdr_cells[3].text = 'Descrição'
    for cell in hdr_cells:
        shade_cell(cell, 'D3D3D3')

    row_data = [
        ('C-6.1', 'Filtros de Pesquisa', 'T-6.1', 'Filtros para contrato, campo, fase e período (ano-calendário)'),
        ('C-6.2', 'Cartões de Indicadores', 'T-6.1', 'Resumo de CCOs por status: OK, Atenção, Erro, e totais financeiros'),
        ('C-6.3', 'Tabela de Resultados de Verificação', 'T-6.1', 'Grid com resultados: ID CCO, contrato, campo, valorReconhecidoExploracao, valorReconhecidoProducao, OH verificado, OH calculado, status, diferença, motivo do status'),
        ('C-6.4', 'Botão Análise de Faixas', 'T-6.1', 'Ação para drill-down em uma CCO específica'),
        ('C-6.5', 'Barra de Faixas Progressivas', 'T-6.2', 'Visualização das 3 faixas (≤5M @ 3%, 5-15M @ 2%, >15M @ 1%) com acumulado'),
        ('C-6.6', 'Tabela de Detalhamento por Faixa', 'T-6.2', 'Linhas para cada faixa atravessada: valor na faixa, taxa aplicada, OH contribuído'),
    ]

    for i, (id_comp, nome, local, desc) in enumerate(row_data, 1):
        row_cells = comp_analise_table.rows[i].cells
        row_cells[0].text = id_comp
        row_cells[1].text = nome
        row_cells[2].text = local
        row_cells[3].text = desc

    # Rotas - Análise
    add_heading_with_style(doc, 'Rotas/Endpoints', 3)
    rotas_analise_table = doc.add_table(rows=9, cols=5)
    rotas_analise_table.style = 'Light Grid Accent 1'

    hdr_cells = rotas_analise_table.rows[0].cells
    hdr_cells[0].text = 'ID'
    hdr_cells[1].text = 'Endpoint'
    hdr_cells[2].text = 'Método'
    hdr_cells[3].text = 'Blueprint'
    hdr_cells[4].text = 'Descrição'
    for cell in hdr_cells:
        shade_cell(cell, 'D3D3D3')

    rotas_data = [
        ('E-6.1', '/sgpp-cco-tools/verificacao-oh/', 'GET', 'verificacao_oh_bp', 'Página principal'),
        ('E-6.2', '/sgpp-cco-tools/verificacao-oh/analise-exp', 'GET', 'verificacao_oh_bp', 'Página de análise por faixas'),
        ('E-6.3', '/sgpp-cco-tools/verificacao-oh/api/contratos', 'GET', 'verificacao_oh_bp', 'Lista contratos disponíveis'),
        ('E-6.4', '/sgpp-cco-tools/verificacao-oh/api/campos', 'GET', 'verificacao_oh_bp', 'Lista campos por contrato'),
        ('E-6.5', '/sgpp-cco-tools/verificacao-oh/api/fases', 'GET', 'verificacao_oh_bp', 'Lista fases disponíveis'),
        ('E-6.6', '/sgpp-cco-tools/verificacao-oh/api/verificar', 'POST', 'verificacao_oh_bp', 'Busca CCOs e verifica OH conforme filtros'),
        ('E-6.7', '/sgpp-cco-tools/verificacao-oh/api/analise-exp', 'GET', 'verificacao_oh_bp', 'Análise de faixas exploração de uma CCO específica'),
        ('E-6.8', '/sgpp-cco-tools/verificacao-oh/download-csv', 'GET', 'verificacao_oh_bp', 'Download CSV do último resultado de verificação'),
    ]

    for i, (id_rota, endpoint, metodo, blueprint, desc) in enumerate(rotas_data, 1):
        row_cells = rotas_analise_table.rows[i].cells
        row_cells[0].text = id_rota
        row_cells[1].text = endpoint
        row_cells[2].text = metodo
        row_cells[3].text = blueprint
        row_cells[4].text = desc

    # Serviços - Análise
    add_heading_with_style(doc, 'Serviços', 3)
    servicos_analise_table = doc.add_table(rows=9, cols=4)
    servicos_analise_table.style = 'Light Grid Accent 1'

    hdr_cells = servicos_analise_table.rows[0].cells
    hdr_cells[0].text = 'ID'
    hdr_cells[1].text = 'Serviço'
    hdr_cells[2].text = 'Método'
    hdr_cells[3].text = 'Descrição'
    for cell in hdr_cells:
        shade_cell(cell, 'D3D3D3')

    servicos_data = [
        ('S-6.1', 'VerificacaoOHService', 'listar_contratos()', 'Retorna lista de contratos com CCOs'),
        ('S-6.2', 'VerificacaoOHService', 'listar_campos(contrato)', 'Retorna campos de um contrato'),
        ('S-6.3', 'VerificacaoOHService', 'listar_fases()', 'Retorna lista de fases (Exploração, Produção, etc.)'),
        ('S-6.4', 'VerificacaoOHService', 'buscar_ccos(filtros)', 'Busca CCOs conforme filtros (contrato, campo, fase)'),
        ('S-6.5', 'VerificacaoOHService', 'verificar_oh(ccos_raw)', 'Verifica OH de cada CCO: compara valor com regras e retorna status'),
        ('S-6.6', 'VerificacaoOHService', 'calcular_estatisticas(resultados)', 'Computa totalizações por status e impactos financeiros'),
        ('S-6.7', 'VerificacaoOHService', 'analisar_faixas_exploracao(cco_id)', 'Detalha cálculo de OH exploração por faixa para uma CCO'),
        ('S-6.8', 'VerificacaoOHService', 'gerar_csv(resultados)', 'Gera CSV com resultado da verificação'),
    ]

    for i, (id_srv, servico, metodo, desc) in enumerate(servicos_data, 1):
        row_cells = servicos_analise_table.rows[i].cells
        row_cells[0].text = id_srv
        row_cells[1].text = servico
        row_cells[2].text = metodo
        row_cells[3].text = desc

    # Repositórios - Análise
    add_heading_with_style(doc, 'Repositórios', 3)
    repos_analise_table = doc.add_table(rows=2, cols=4)
    repos_analise_table.style = 'Light Grid Accent 1'

    hdr_cells = repos_analise_table.rows[0].cells
    hdr_cells[0].text = 'ID'
    hdr_cells[1].text = 'Repositório'
    hdr_cells[2].text = 'Collection'
    hdr_cells[3].text = 'Descrição'
    for cell in hdr_cells:
        shade_cell(cell, 'D3D3D3')

    row_cells = repos_analise_table.rows[1].cells
    row_cells[0].text = 'R-6.1'
    row_cells[1].text = 'CCO Repository'
    row_cells[2].text = 'conta_custo_oleo_entity'
    row_cells[3].text = 'CCOs com valores de OH a serem verificados'

    doc.add_paragraph()  # Blank line

    # Subseção 4.2.2: Correção de OH
    add_heading_with_style(doc, '4.2.2 Correção de OH', 2)

    # Telas - Correção
    add_heading_with_style(doc, 'Telas', 3)
    telas_correcao_table = doc.add_table(rows=4, cols=4)
    telas_correcao_table.style = 'Light Grid Accent 1'

    hdr_cells = telas_correcao_table.rows[0].cells
    hdr_cells[0].text = 'ID'
    hdr_cells[1].text = 'Tela'
    hdr_cells[2].text = 'Arquivo'
    hdr_cells[3].text = 'Descrição'
    for cell in hdr_cells:
        shade_cell(cell, 'D3D3D3')

    row_cells = telas_correcao_table.rows[1].cells
    row_cells[0].text = 'T-6.3'
    row_cells[1].text = 'Simulação e Resultado da Correção'
    row_cells[2].text = 'verificacao_oh/simulacao_correcao.html'
    row_cells[3].text = 'Exibe lado-a-lado a CCO antes (valores originais) e depois (valores corrigidos), com destaque das diferenças. Mostra o impacto em cascata: quais CCOs subsequentes serão recalculadas, qual será o reprocessamento de IPCA/IGPM. Botão "Confirmar" após revisão.'

    row_cells = telas_correcao_table.rows[2].cells
    row_cells[0].text = 'T-6.4'
    row_cells[1].text = 'Sessão de Revisão da Correção'
    row_cells[2].text = 'verificacao_oh/revisar_correcao.html'
    row_cells[3].text = 'Tela de revisão em área temporária antes da promoção: detalhes das correções, histórico de mudanças, validações realizadas, com opções de aprovar ou rejeitar.'

    row_cells = telas_correcao_table.rows[3].cells
    row_cells[0].text = 'T-6.5'
    row_cells[1].text = 'Promoção para Produção'
    row_cells[2].text = 'verificacao_oh/promover_correcao.html'
    row_cells[3].text = 'Resumo da correção antes de promover: quais CCOs foram afetadas, valores totais alterados, timeline de impactos financeiros. Campo de aprovação com data/hora, usuário e comentário obrigatório.'

    # Componentes - Correção
    add_heading_with_style(doc, 'Componentes de Interface', 3)
    comp_correcao_table = doc.add_table(rows=11, cols=4)
    comp_correcao_table.style = 'Light Grid Accent 1'

    hdr_cells = comp_correcao_table.rows[0].cells
    hdr_cells[0].text = 'ID'
    hdr_cells[1].text = 'Componente'
    hdr_cells[2].text = 'Localização'
    hdr_cells[3].text = 'Descrição'
    for cell in hdr_cells:
        shade_cell(cell, 'D3D3D3')

    comp_correcao_data = [
        ('C-6.7', 'Botão Corrigir', 'T-6.1', 'Ação para iniciar simulação de correção de um OH incorreto'),
        ('C-6.8', 'Formulário de Entrada de Valor Corrigido', 'T-6.3', 'Campo para entrada do novo valor de overhead a ser aplicado'),
        ('C-6.9', 'Tabela Comparativa Antes/Depois', 'T-6.3', 'Grid mostrando valores anteriores e posteriores para CCO raiz e derivadas'),
        ('C-6.10', 'Resumo de Impacto em Cascata', 'T-6.3', 'Cards com: CCOs afetadas (horizontal), reprocessamento IPCA/IGPM (temporal), valores totais alterados'),
        ('C-6.11', 'Timeline de Impactos Financeiros', 'T-6.3', 'Gráfico/tabela mostrando ao longo do tempo como as correções monetárias serão recalculadas'),
        ('C-6.12', 'Detalhamento de Cada Ajuste', 'T-6.3', 'Linhas com: campo da CCO, valor anterior, valor novo, diferença, motivo (correção de OH)'),
        ('C-6.13', 'Cards de Estatísticas de Revisão', 'T-6.4', 'Resumo: número de CCOs afetadas, impacto financeiro total, número de correções monetárias a reprocessar'),
        ('C-6.14', 'Histórico de Mudanças', 'T-6.4', 'Tabela com cronologia de alterações na sessão'),
        ('C-6.15', 'Validações e Alertas', 'T-6.4', 'Sinalização de inconsistências, se houver'),
        ('C-6.16', 'Botão Aprovar/Rejeitar', 'T-6.4', 'Ações para finalizar revisão e prosseguir para promoção'),
    ]

    for i, (id_comp, nome, local, desc) in enumerate(comp_correcao_data, 1):
        row_cells = comp_correcao_table.rows[i].cells
        row_cells[0].text = id_comp
        row_cells[1].text = nome
        row_cells[2].text = local
        row_cells[3].text = desc

    # Rotas - Correção
    add_heading_with_style(doc, 'Rotas/Endpoints', 3)
    rotas_correcao_table = doc.add_table(rows=8, cols=5)
    rotas_correcao_table.style = 'Light Grid Accent 1'

    hdr_cells = rotas_correcao_table.rows[0].cells
    hdr_cells[0].text = 'ID'
    hdr_cells[1].text = 'Endpoint'
    hdr_cells[2].text = 'Método'
    hdr_cells[3].text = 'Blueprint'
    hdr_cells[4].text = 'Descrição'
    for cell in hdr_cells:
        shade_cell(cell, 'D3D3D3')

    rotas_correcao_data = [
        ('E-6.9', '/sgpp-cco-tools/verificacao-oh/simular-correcao', 'POST', 'verificacao_oh_bp', 'Inicia simulação de correção de OH'),
        ('E-6.10', '/sgpp-cco-tools/verificacao-oh/api/calcular-impacto-cascata', 'POST', 'verificacao_oh_bp', 'Calcula impacto em cascata (horizontal e temporal)'),
        ('E-6.11', '/sgpp-cco-tools/verificacao-oh/revisar-correcao/<session_id>', 'GET', 'verificacao_oh_bp', 'Página de revisão em área temporária'),
        ('E-6.12', '/sgpp-cco-tools/verificacao-oh/api/salvar-correcao-temporaria', 'POST', 'verificacao_oh_bp', 'Salva correção na área temporária conta_custo_oleo_corrigida_entity'),
        ('E-6.13', '/sgpp-cco-tools/verificacao-oh/api/validar-correcao', 'POST', 'verificacao_oh_bp', 'Valida correção antes de confirmar'),
        ('E-6.14', '/sgpp-cco-tools/verificacao-oh/promover-correcao/<session_id>', 'GET', 'verificacao_oh_bp', 'Página de promoção (integração com fluxo existente)'),
        ('E-6.15', '/sgpp-cco-tools/verificacao-oh/api/promover-correcao', 'POST', 'verificacao_oh_bp', 'Executa promoção da correção para produção'),
    ]

    for i, (id_rota, endpoint, metodo, blueprint, desc) in enumerate(rotas_correcao_data, 1):
        row_cells = rotas_correcao_table.rows[i].cells
        row_cells[0].text = id_rota
        row_cells[1].text = endpoint
        row_cells[2].text = metodo
        row_cells[3].text = blueprint
        row_cells[4].text = desc

    # Serviços - Correção
    add_heading_with_style(doc, 'Serviços', 3)
    servicos_correcao_table = doc.add_table(rows=12, cols=4)
    servicos_correcao_table.style = 'Light Grid Accent 1'

    hdr_cells = servicos_correcao_table.rows[0].cells
    hdr_cells[0].text = 'ID'
    hdr_cells[1].text = 'Serviço'
    hdr_cells[2].text = 'Método'
    hdr_cells[3].text = 'Descrição'
    for cell in hdr_cells:
        shade_cell(cell, 'D3D3D3')

    servicos_correcao_data = [
        ('S-6.9', 'CorrecaoOHService', 'iniciar_simulacao_correcao(cco_id, novo_oh)', 'Inicia sessão de simulação de correção'),
        ('S-6.10', 'CorrecaoOHService', 'calcular_impacto_cascata_horizontal(cco_id, novo_oh)', 'Identifica CCOs derivadas da mesma remessa e calcula impacto'),
        ('S-6.11', 'CorrecaoOHService', 'calcular_impacto_cascata_temporal(cco_id, novo_oh)', 'Reprocessa correções monetárias IPCA/IGPM posteriores'),
        ('S-6.12', 'CorrecaoOHService', 'gerar_preview_correcao(cco_id, novo_oh)', 'Retorna dados para visualização side-by-side antes/depois'),
        ('S-6.13', 'CorrecaoOHService', 'validar_correcao(session_id)', 'Valida consistência da correção (regras de negócio, integridade)'),
        ('S-6.14', 'CorrecaoOHService', 'salvar_correcao_temporaria(session_id)', 'Persiste correção na área temporária conta_custo_oleo_corrigida_entity'),
        ('S-6.15', 'CorrecaoOHService', 'obter_sessao_correcao(session_id)', 'Recupera detalhes de uma sessão de correção'),
        ('S-6.16', 'CorrecaoOHService', 'listar_sessoes_pendentes()', 'Lista sessões de correção em revisão'),
        ('S-6.17', 'CorrecaoOHService', 'promover_correcao(session_id)', 'Aplica correção de OH da área temporária para produção'),
        ('S-6.18', 'CorrecaoOHService', 'exportar_relatorio_correcao(session_id)', 'Gera relatório detalhado da correção (PDF/CSV)'),
        ('S-6.19', 'AuditService', 'registrar_correcao_oh(usuario, cco_id, valores_anteriores, valores_posteriores)', 'Audita correção realizada'),
    ]

    for i, (id_srv, servico, metodo, desc) in enumerate(servicos_correcao_data, 1):
        row_cells = servicos_correcao_table.rows[i].cells
        row_cells[0].text = id_srv
        row_cells[1].text = servico
        row_cells[2].text = metodo
        row_cells[3].text = desc

    # Repositórios - Correção
    add_heading_with_style(doc, 'Repositórios', 3)
    repos_correcao_table = doc.add_table(rows=3, cols=4)
    repos_correcao_table.style = 'Light Grid Accent 1'

    hdr_cells = repos_correcao_table.rows[0].cells
    hdr_cells[0].text = 'ID'
    hdr_cells[1].text = 'Repositório'
    hdr_cells[2].text = 'Collection'
    hdr_cells[3].text = 'Descrição'
    for cell in hdr_cells:
        shade_cell(cell, 'D3D3D3')

    repos_correcao_data = [
        ('R-6.2', 'CCO Repository', 'conta_custo_oleo_entity', 'CCOs em produção (alvo das correções)'),
        ('R-6.3', 'CCO Corrigida Repository', 'conta_custo_oleo_corrigida_entity', 'Área temporária: CCOs com OH corrigido, aguardando promoção'),
    ]

    for i, (id_rep, repo, col, desc) in enumerate(repos_correcao_data, 1):
        row_cells = repos_correcao_table.rows[i].cells
        row_cells[0].text = id_rep
        row_cells[1].text = repo
        row_cells[2].text = col
        row_cells[3].text = desc

    doc.add_paragraph()  # Blank line

    # Prototype/Screenshot Placeholders
    add_heading_with_style(doc, '4.3 Telas e Protótipos', 2)

    add_placeholder_for_screenshot(
        doc,
        'Tela 1: Verificação Geral de Overhead',
        'Exibe lista de CCOs com status (OK, Atenção, Erro), valores reconhecidos e overhead calculado. '
        'Permite filtrar por contrato, período e status. Botão "Corrigir" ao lado de cada CCO com erro.'
    )

    add_placeholder_for_screenshot(
        doc,
        'Tela 2: Análise Detalhada por Faixas de Exploração',
        'Mostra o cálculo progressivo do overhead de exploração, indicando qual faixa cada valor se enquadra '
        '(exemplo: "R$ 5M × 3% = R$150k (Faixa 1)", "R$ 7M × 2% = R$140k (Faixa 2)"). '
        'Identifica quando uma CCO cruza limites de faixa e mostra cálculo proporcional.'
    )

    add_placeholder_for_screenshot(
        doc,
        'Tela 3: Simulação e Resultado da Correção',
        'Exibe lado-a-lado a CCO antes (valores originais) e depois (valores corrigidos), '
        'com destaque das diferenças. Mostra o impacto em cascata: quais CCOs subsequentes serão recalculadas, '
        'qual será o reprocessamento de IPCA/IGPM. Botão "Confirmar" após revisão.'
    )

    add_placeholder_for_screenshot(
        doc,
        'Tela 4: Promoção para Produção',
        'Resumo da correção antes de promover: quais CCOs foram afetadas, valores totais alterados, '
        'timeline de impactos financeiros. Campo de aprovação com data/hora, usuário e comentário obrigatório. '
        'Integra-se ao fluxo existente de promoção de correções.'
    )

    doc.add_paragraph()  # Blank line

    # Definition of Done
    add_heading_with_style(doc, '4.4 Definition of Done (Checklist de Aceite)', 2)

    doc.add_paragraph(
        'A entrega do Módulo de Análise e Correção de OH é considerada completa quando todos os itens abaixo estão marcados como concluído:'
    )

    dod_items = [
        '☐ Todas as regras de cálculo de OH estão implementadas (1% produção, faixas 3%/2%/1% exploração, '
        'casos especiais de base zero/negativa/AEGV)',
        '☐ A análise identifica corretamente o status de cada CCO (OK, Atenção, Erro) com tolerância de ±0,005%',
        '☐ A tela de análise por faixas mostra o enquadramento progressivo e o cálculo proporcional quando CCO cruza faixas',
        '☐ A simulação de correção executa recálculo em cascata (horizontal para mesma remessa, temporal para IPCA/IGPM)',
        '☐ Os valores da área temporária (`conta_custo_oleo_corrigida_entity`) são corretamente preenchidos',
        '☐ A promoção de correções segue o fluxo existente e requer aprovação com permissão `CORRECAO_PROMOTE`',
        '☐ O relatório de exportação inclui: lista de CCOs analisadas, status, ajustes, impactos financeiros totais',
        '☐ Auditoria registra todas as operações (usuário, timestamp, valores anteriores e posteriores)',
        '☐ Testes automatizados cobrem: cálculo correto de OH, cascata horizontal, cascata temporal, casos especiais',
        '☐ Documentação de usuário está completa e aprovada (screenshots das 4 telas devem estar inclusos)',
        '☐ Teste de aceitação com o cliente: validação de um caso de uso completo (análise → simulação → revisão → promoção)',
        '☐ Performance: análise de até 500 CCOs completa em menos de 30 segundos'
    ]

    for item in dod_items:
        doc.add_paragraph(item, style='List Bullet')

    # ========== RODAPÉ ==========
    doc.add_paragraph()
    doc.add_paragraph()

    footer_para = doc.add_paragraph()
    footer_para.paragraph_format.border_top = True
    footer_run = footer_para.add_run(
        'Documento de Escopo - Módulo de Análise e Correção de OH\n'
        f'Versão 1.0 — {datetime.date.today().strftime("%d de %B de %Y")}\n'
        'Referência: US-21700 (Azure DevOps)'
    )
    footer_run.font.size = Pt(9)
    footer_run.italic = True
    footer_para.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Save document
    output_path = '/workspace/repo/docs/Especificacao_Modulo_Analise_Correcao_OH.docx'
    doc.save(output_path)

    print(f'✓ Documento criado com sucesso em: {output_path}')
    return output_path

if __name__ == '__main__':
    try:
        create_specification_document()
        print('\n✓ Todas as seções foram geradas com sucesso:')
        print('  1. Visão Geral e Objetivos')
        print('  2. Definição do Escopo')
        print('  3. Regras de Negócio e Requisitos')
        print('  4. Entregáveis e Critérios de Aceite')
        print('     4.2 Detalhamento dos Componentes')
        print('        4.2.1 Análise e Verificação de OH (Tabelas: Telas, Componentes, Rotas, Serviços, Repositórios)')
        print('        4.2.2 Correção de OH (Tabelas: Telas, Componentes, Rotas, Serviços, Repositórios)')
        print('     4.3 Telas e Protótipos')
        print('     4.4 Definition of Done')
        print('\n✓ Detalhamento completo de componentes implementados (análise) e planejados (correção)')
        print('✓ Tabelas seguem padrão de outros módulos (Portal PPSA)')
        print('✓ Placeholders para 4 protótipos/telas inclusos')
        print('✓ Todas as regras de cálculo de OH descritas')
        print('✓ Processo de correção em etapas detalhado')
        print('✓ Fora do Escopo e Dependências Mapeadas preenchidos')
    except Exception as e:
        print(f'✗ Erro ao gerar documento: {e}')
        import traceback
        traceback.print_exc()
