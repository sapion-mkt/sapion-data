"""Cria (ou recria do zero) a planilha Fontes/catalogo_fontes.xlsx.

Uso normal: editar a planilha no Excel. Rode este script só para gerar o catálogo pela primeira vez
ou restaurar o modelo — ele sobrescreve a planilha existente.
"""
import os
import sys

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from common import src

COLS = [
    ('id', 'Identificador usado pelo sistema. Não altere.'),
    ('bloco', 'Bloco do painel que usa a fonte.'),
    ('descricao', 'O que é o dado.'),
    ('orgao', 'Órgão que publica.'),
    ('tipo', 'manual = alguém baixa e coloca na pasta; automática = o sistema busca sozinho.'),
    ('pasta', 'Pasta dentro de Fontes/. Cada referência (ano, trimestre, mês ou data de coleta) fica numa subpasta.'),
    ('padrao_arquivo', 'Nome esperado do arquivo (* = qualquer texto).'),
    ('referencia', 'Subpasta a usar. Em branco = a mais recente.'),
    ('periodicidade', 'De quanto em quanto tempo sai dado novo.'),
    ('proxima_atualizacao', 'Quando esperar a próxima publicação.'),
    ('link', 'Onde obter.'),
    ('como_obter', 'Passo a passo resumido.'),
    ('conferencia', 'Textos que precisam aparecer no arquivo (separados por ;). O sistema confere antes de usar.'),
    ('responsavel', 'Quem cuida da fonte.'),
    ('observacoes', ''),
]

FONTES = [
    ['tcees-vinculo', '1. Profissionais', 'Folha de pagamento declarada pelos municípios (arquivo Vínculo)', 'TCE-ES', 'manual',
     '01-profissionais/tcees-vinculo', 'vinculo-*.csv', '', 'Trimestral', 'Fev/2027 (3º tri 2026)',
     'https://dados.es.gov.br', 'Conjunto "[TCEES] Área temática de Pessoal – Controle Externo" > arquivo Vínculo do trimestre. Subpasta: AAAA-Tn.',
     'NomeServidor;CPFServidor;NomeUnidadeGestora;NomeCargo;TipoVinculo;MesReferencia', 'Felipe / Claude',
     'Contém nomes e CPF parcial de servidores: nunca publicar o arquivo.'],
    ['inep-sinopse-censo', '1. Profissionais', 'Sinopse Estatística do Censo Escolar (docentes em regência por etapa)', 'Inep', 'manual',
     '01-profissionais/inep-sinopse-censo', 'Sinopse*.xlsx', '', 'Anual', 'Fev/2027 (Censo 2026)',
     'https://www.gov.br/inep/pt-br/areas-de-atuacao/pesquisas-estatisticas-e-indicadores/censo-escolar/resultados',
     'Baixar a Sinopse Estatística da Educação Básica do ano. Subpasta: ano do Censo.', '', 'Felipe / Claude', ''],
    ['inep-ideb-municipios', '2. IDEB', 'IDEB por município – anos iniciais e anos finais', 'Inep', 'manual',
     '02-ideb/inep-ideb-municipios', 'divulgacao_anos_*_municipios_*.xlsx', '', 'A cada 2 anos', '2028 (IDEB 2027)',
     'https://www.gov.br/inep/pt-br/areas-de-atuacao/pesquisas-estatisticas-e-indicadores/ideb/resultados',
     'Baixar os arquivos de municípios (anos iniciais e anos finais). Subpasta: ano do IDEB.', 'VL_OBSERVADO_', 'Felipe / Claude', ''],
    ['inep-ica', '3. Alfabetização', 'Indicador Criança Alfabetizada – resultados e metas por município', 'Inep/MEC', 'manual',
     '03-alfabetizacao/inep-ica', 'resultados_e_metas_municipios_*.xlsx', '', 'Anual', 'Mar/2027 (ICA 2026)',
     'https://www.gov.br/inep/pt-br/areas-de-atuacao/avaliacao-e-exames-educacionais/avaliacao-da-alfabetizacao/resultados',
     'Baixar a planilha de resultados e metas por município. Subpasta: ano do resultado.', 'PC_ALUNO_ALFABETIZADO', 'Felipe / Claude', ''],
    ['tcees-fluencia', '3. Alfabetização', 'Avaliação da Fluência em Leitura (Sedu/CAEd) por município e escola', 'TCE-ES (dados Sedu)', 'automática',
     '03-alfabetizacao/tcees-fluencia', 'fluencia.json', '', 'Anual', '2º semestre/2026 (edição 2026)',
     'https://paineldecontrole.tcees.tc.br/areasTematicas/educacao/fluencia/2025/todos/todos/null/null/1',
     'Automática: o sistema consulta o painel (Power BI público) do TCE-ES e guarda uma cópia na subpasta com a data da coleta.',
     '', 'Claude', 'Só ES. Traz percentuais; não traz número de alunos avaliados.'],
    ['tcees-escolas-censo', '5. Escolas', 'Escolas municipais e estaduais com matrículas por etapa (Censo Escolar)', 'TCE-ES (dados Inep)', 'automática',
     '05-escolas/tcees-censo-escolas', 'censo_escolas.json', '', 'Anual', 'Fev/2027 (Censo 2026)',
     'https://paineldecontrole.tcees.tc.br/areasTematicas/educacao/escolas',
     'Automática (Power BI público do TCE-ES).', '', 'Claude',
     'Matrículas estaduais não incluem cursos técnicos de educação profissional.'],
    ['tcees-ideb-escolas', '5. Escolas', 'IDEB por escola (municipais e estaduais)', 'TCE-ES (dados Inep)', 'automática',
     '05-escolas/tcees-ideb-escolas', 'ideb_escolas.json', '', 'A cada 2 anos', '2028 (IDEB 2027)',
     'https://paineldecontrole.tcees.tc.br/areasTematicas/educacao/ideb', 'Automática (Power BI público do TCE-ES).', '', 'Claude', ''],
    ['tesouro-fundeb-mensal', '4. Financiamento', 'Transferências do Fundeb por município e origem – ano corrente (um CSV por mês)', 'Tesouro Nacional/FNDE', 'manual',
     '04-financiamento/tesouro-fundeb-mensal', '*.csv', '', 'Mensal', 'Início de cada mês',
     'https://www.gov.br/fnde/pt-br/acesso-a-informacao/acoes-e-programas/financiamento/fundeb/consultas',
     'Consultas Fundeb > Secretaria do Tesouro Nacional > ano, UF=ES, todos os municípios, mês. Salvar como <mês>.csv (ex.: outubro.csv) na subpasta do ano.',
     'Transferência;Valor Consolidado;Código IBGE', 'Felipe / Claude', ''],
    ['tesouro-fundeb-anual', '4. Financiamento', 'Transferências do Fundeb – ano anterior completo', 'Tesouro Nacional/FNDE', 'manual',
     '04-financiamento/tesouro-fundeb-anual', '*.csv', '', 'Anual', 'Jan/2027 (ano 2026)',
     'https://www.gov.br/fnde/pt-br/acesso-a-informacao/acoes-e-programas/financiamento/fundeb/consultas',
     'Mesma consulta, ano inteiro. Subpasta: ano.', 'Transferência;Valor Consolidado;Código IBGE', 'Felipe / Claude', ''],
    ['sapion-vaar-condicionalidades', '4. Financiamento', 'VAAR: situação, condicionalidades e previsto (lista FNDE + Portaria interministerial)', 'FNDE/MEC (planilha Sapion)', 'manual',
     '04-financiamento/sapion-vaar-condicionalidades', 'VAAR_ES_*.xlsx', '', 'Anual + revisões', 'Lista VAAR 2027 (2º semestre/2026)',
     'https://www.gov.br/fnde/pt-br/acesso-a-informacao/acoes-e-programas/financiamento/fundeb',
     'Planilha montada pela Sapion a partir da lista de beneficiários do VAAR e da portaria vigente. Subpasta: ano do ciclo.',
     'Situação VAAR', 'Felipe / Claude', ''],
    ['fnde-vaat-habilitacao', '4. Financiamento', 'Entes habilitados e inabilitados ao VAAT', 'FNDE', 'manual',
     '04-financiamento/fnde-vaat-habilitacao', '*.csv', '', 'Anual', 'Out/2026 (VAAT 2027)',
     'https://www.gov.br/fnde/pt-br/acesso-a-informacao/acoes-e-programas/financiamento/fundeb/vaat',
     'Baixar o CSV da lista final de entes habilitados e inabilitados do ciclo (página do VAAT no FNDE). Subpasta: ano do ciclo.', 'Habilitado', 'Felipe / Claude', ''],
    ['sefaz-icms-repasses', '4. Financiamento', 'Distribuição mensal do ICMS às prefeituras (PDF)', 'Sefaz-ES', 'manual',
     '04-financiamento/sefaz-icms-repasses', '*.pdf', '', 'Mensal', 'Cerca de 4 semanas após cada mês',
     'https://internet.sefaz.es.gov.br/contas/financas/transferencias/',
     'Baixar o PDF "Distribuição de tributos estaduais ICMS e IPVA às prefeituras" do mês. O nome precisa conter o mês por extenso.',
     '', 'Felipe / Claude', ''],
    ['sefaz-ipm', '4. Financiamento', 'Índice de Participação dos Municípios (IPM) definitivo', 'Sefaz-ES', 'manual',
     '04-financiamento/sefaz-ipm', 'IPM_*.xlsx', '', 'Anual', 'Dez/2026 (IPM 2027)',
     'https://s1-internet.sefaz.es.gov.br/site-ipm-internet', 'Planilha com o IPM do decreto. Subpasta: ano de vigência.',
     'IPM', 'Felipe / Claude', ''],
    ['sapion-iqe-reconstruido', '4. Financiamento', 'IQE reconstruído pela metodologia da Sedu (estimativa Sapion)', 'Sapion', 'manual',
     '04-financiamento/sapion-iqe-reconstruido', 'IQE_*.xlsx', '', 'Anual', 'Com os dados do Paebes 2025',
     '', 'Planilha gerada pela Sapion (ver Metodologia). Subpasta: ano de cálculo do IQE.', 'IQE', 'Claude', 'Estimativa Sapion.'],
    ['logo-sapion-data', '0. Referência', 'Logo do Sapion Data', 'Sapion', 'manual',
     '00-referencia/identidade-visual', 'Logo Sapion Data.png', '.', 'Quando mudar', '', '', '', '', 'Felipe', 'Referência "." = arquivo direto na pasta, sem subpasta.'],
]


def main():
    path = src('Fontes', 'catalogo_fontes.xlsx')
    wb = Workbook()
    ws = wb.active
    ws.title = 'Fontes'
    head = PatternFill('solid', fgColor='22256F')
    ws.append([c for c, _ in COLS])
    for cell in ws[1]:
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = head
        cell.alignment = Alignment(vertical='center', wrap_text=True)
    for f in FONTES:
        ws.append(f)
    widths = [26, 18, 48, 20, 12, 40, 34, 14, 16, 26, 50, 60, 40, 16, 40]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(vertical='top', wrap_text=True)
    ws.freeze_panes = 'B2'
    ws.auto_filter.ref = ws.dimensions

    g = wb.create_sheet('Como usar')
    g.column_dimensions['A'].width = 24
    g.column_dimensions['B'].width = 110
    g.append(['Catálogo de fontes do Sapion Data'])
    g['A1'].font = Font(bold=True, size=14, color='22256F')
    g.append([])
    for c, d in COLS:
        g.append([c, d])
    g.append([])
    g.append(['Regras', '1. Nunca edite um arquivo de fonte: coloque o original, como foi baixado, na subpasta da referência.'])
    g.append(['', '2. Uma subpasta por referência (ano, trimestre, mês ou data). As antigas ficam guardadas para formar séries.'])
    g.append(['', '3. Com "referencia" em branco, o sistema usa a subpasta mais recente (ordem alfabética: use AAAA, AAAA-Tn ou AAAA-MM-DD).'])
    g.append(['', '4. Fonte nova? Preencha uma linha nova e a "Ficha de novo indicador" (pasta Fontes/_modelos).'])
    for row in g.iter_rows(min_row=3):
        row[0].font = Font(bold=True)
        for cell in row:
            cell.alignment = Alignment(vertical='top', wrap_text=True)
    wb.save(path)
    print('ok ->', path)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
