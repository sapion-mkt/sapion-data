"""Cria os modelos em Fontes/_modelos: ficha de novo indicador e planilha-modelo de dados por município."""
import os
import sys

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

from common import src, load_municipios

AZUL = PatternFill('solid', fgColor='22256F')
CLARO = PatternFill('solid', fgColor='EEF0F8')

FICHA = [
    ('Identificação', None),
    ('Nome do indicador', 'Como o indicador vai aparecer no painel. Ex.: "Taxa de abandono nos anos finais".'),
    ('Pergunta comercial que ele responde', 'Por que o time comercial precisa disso? Que decisão ele ajuda a tomar?'),
    ('Bloco do painel', 'Profissionais, IDEB, Alfabetização, Financiamento, Escolas ou um bloco novo.'),
    ('Fonte', None),
    ('Órgão que publica', 'Ex.: Inep, FNDE, Sedu, TCE-ES.'),
    ('Nome oficial da publicação', ''),
    ('Link', 'Página onde o dado é publicado ou baixado.'),
    ('Formato', 'Planilha, CSV, PDF, painel na internet, API.'),
    ('Exemplo de arquivo', 'Coloque um arquivo de exemplo em Fontes/_entrada e escreva o nome aqui.'),
    ('O dado', None),
    ('Nível', 'Por município, por escola, por rede, por estado.'),
    ('Chave de identificação', 'Código IBGE do município (7 dígitos) ou código INEP da escola. Sem chave, o dado não cruza com o resto.'),
    ('Período de referência', 'Ano, trimestre, mês ou edição.'),
    ('Periodicidade', 'Mensal, anual, a cada 2 anos…'),
    ('Próxima publicação esperada', ''),
    ('É dado oficial ou estimativa Sapion?', 'Se for cálculo nosso, descreva a conta e as premissas.'),
    ('Como aparece', None),
    ('Formato de exibição', 'Número, percentual, R$, série no tempo, ranking, lista.'),
    ('Texto do botão "?"', 'Explicação curta para o time comercial, em linguagem simples.'),
    ('Sinal de atenção para o comercial', 'Existe uma regra que deveria virar "ponto de atenção"? Ex.: abaixo da meta.'),
    ('Comparação', 'Comparar com a média do estado? Com a meta? Com o ano anterior?'),
    ('Controle', None),
    ('Quem solicitou', ''),
    ('Data da solicitação', ''),
    ('Observações', ''),
]


def ficha(path):
    wb = Workbook()
    ws = wb.active
    ws.title = 'Ficha'
    ws.column_dimensions['A'].width = 40
    ws.column_dimensions['B'].width = 70
    ws.column_dimensions['C'].width = 60
    ws.append(['Ficha de novo indicador – Sapion Data'])
    ws['A1'].font = Font(bold=True, size=14, color='22256F')
    ws.append(['Preencha a coluna "Resposta" e envie junto com um arquivo de exemplo da fonte.'])
    ws.append([])
    ws.append(['Campo', 'Resposta', 'Orientação'])
    for c in ws[4]:
        c.font = Font(bold=True, color='FFFFFF')
        c.fill = AZUL
    for campo, guia in FICHA:
        if guia is None:
            ws.append([campo])
            ws.cell(ws.max_row, 1).font = Font(bold=True, color='22256F')
            for col in range(1, 4):
                ws.cell(ws.max_row, col).fill = CLARO
        else:
            ws.append([campo, '', guia])
            ws.row_dimensions[ws.max_row].height = 32
    for row in ws.iter_rows(min_row=5):
        for c in row:
            c.alignment = Alignment(vertical='top', wrap_text=True)
    wb.save(path)


def planilha_municipios(path):
    mun = load_municipios()
    wb = Workbook()
    ws = wb.active
    ws.title = 'Dados'
    cols = [('codigo_ibge', 12), ('municipio', 28), ('uf', 5), ('referencia', 12), ('indicador', 30), ('rede', 12),
            ('valor', 12), ('unidade', 12), ('fonte', 30), ('observacao', 40)]
    ws.append([c for c, _ in cols])
    for i, (c, w) in enumerate(cols, start=1):
        ws.cell(1, i).font = Font(bold=True, color='FFFFFF')
        ws.cell(1, i).fill = AZUL
        ws.column_dimensions[ws.cell(1, i).column_letter].width = w
    for _, m in mun.iterrows():
        ws.append([m['ibge'], m['nome'], 'ES', '', '', '', None, '', '', ''])
    for row in ws.iter_rows(min_row=2, max_col=1):
        row[0].number_format = '@'
    ws.freeze_panes = 'A2'
    g = wb.create_sheet('Como preencher')
    g.column_dimensions['A'].width = 16
    g.column_dimensions['B'].width = 100
    linhas = [
        ('codigo_ibge', 'Código IBGE do município, 7 dígitos (já preenchido para os 78 do ES). Obrigatório.'),
        ('referencia', 'Período do dado: 2025, 2026-T2, 2026-08…'),
        ('indicador', 'Nome curto e sempre igual para o mesmo indicador (uma linha por município × indicador × referência × rede).'),
        ('rede', 'municipal, estadual ou total. Deixe em branco se não se aplica.'),
        ('valor', 'Só o número, sem texto. Percentuais: 42,5 para 42,5%.'),
        ('unidade', '%, R$, pessoas, escolas, nota…'),
        ('fonte', 'Órgão e publicação de onde veio o número.'),
        ('', 'Use esta planilha quando o dado não vier num arquivo oficial pronto (ex.: números enviados por uma secretaria). '
             'Salve em Fontes/<pasta da fonte>/<referência>/ e registre a fonte no catálogo.'),
    ]
    for a, b in linhas:
        g.append([a, b])
        g.cell(g.max_row, 1).font = Font(bold=True)
        g.cell(g.max_row, 2).alignment = Alignment(wrap_text=True)
    wb.save(path)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    d = src('Fontes', '_modelos')
    os.makedirs(d, exist_ok=True)
    os.makedirs(src('Fontes', '_entrada'), exist_ok=True)
    ficha(os.path.join(d, 'Ficha de novo indicador.xlsx'))
    planilha_municipios(os.path.join(d, 'Modelo de dados por municipio.xlsx'))
    print('ok ->', d)
