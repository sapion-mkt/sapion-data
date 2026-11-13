"""Bloco 5 — Escolas municipais e estaduais de cada município, com IDEB e Fluência por escola.

Fontes (coletadas automaticamente do Painel de Controle do TCE-ES, que reúne dados do Inep):
  tcees-escolas-censo  – escolas do Censo Escolar com matrículas por etapa
  tcees-ideb-escolas   – IDEB por escola (anos iniciais, anos finais, ensino médio)
  tcees-fluencia       – Avaliação da Fluência em Leitura por escola (já coletada pelo bloco de Fluência)
"""
import statistics
import sys

from common import key, load_municipios, save_json
import fontes
import tcees_powerbi

ANOS_IDEB = [2021, 2023, 2025]
CENSO_COLS = ['Ano', 'Municipio', 'CodigoINEP', 'Escola', 'DependenciaAdministrativa', 'Localizacao', 'LocalizacaoDiferenciada',
              'Etapa abreviada', 'QuantidadeDeMatriculasPorEtapa', 'IncluirNaSoma', 'FlagIntegral']
IDEB_COLS = ['Ano', 'Municipio', 'CodigoINEP', 'Escola', 'DependenciaAdministrativa',
             'IDEB_EnsinoFundamental_AnosIniciais', 'IDEB_EnsinoFundamental_AnosFinais', 'IDEB_EnsinoMedio']
ETAPA = {'Ed. Infantil - Creche': 'creche', 'Ed. Infantil - Pré-Escola': 'pre', 'Ensino Fund. - Anos Iniciais': 'ai',
         'Ensino Fund. - Anos Finais': 'af', 'Ensino Médio': 'em', 'EJA - Ensino Fundamental': 'eja',
         'EJA - Ensino Médio': 'eja', 'Educação Especial': 'ee'}
REDE = {'Municipal': 'municipal', 'Estadual': 'estadual'}


def coletar():
    anos = sorted({l['Ano'] for l in tcees_powerbi.tabela('ConsolidadoCenso', ['Ano'])})
    censo = tcees_powerbi.tabela('ConsolidadoCenso', CENSO_COLS, {'Ano': [anos[-1]]})
    fontes.nova_coleta('tcees-escolas-censo', 'censo_escolas.json', censo)
    ideb = tcees_powerbi.tabela('IdebEscola', IDEB_COLS, {'Ano': ANOS_IDEB})
    fontes.nova_coleta('tcees-ideb-escolas', 'ideb_escolas.json', ideb)


def num(v):
    if v in (None, '', '-', '*'):
        return None
    try:
        return round(float(str(v).replace(',', '.')), 1)
    except ValueError:
        return None


def build(coletar_agora=False):
    if coletar_agora:
        coletar()
    try:
        censo, ideb = fontes.ler_coleta('tcees-escolas-censo'), fontes.ler_coleta('tcees-ideb-escolas')
    except fontes.FonteError:
        coletar()
        censo, ideb = fontes.ler_coleta('tcees-escolas-censo'), fontes.ler_coleta('tcees-ideb-escolas')
    try:
        flu_linhas = [l for l in fontes.ler_coleta('tcees-fluencia') if l['Tipo'] == 'Escola']
    except fontes.FonteError:
        flu_linhas = []
    mun = load_municipios()
    por_key = {k: ib for k, ib in zip(mun['key'], mun['ibge'])}
    ano_censo = max(l['Ano'] for l in censo)

    # 1. escolas e matrículas por etapa (IncluirNaSoma evita contar o tempo integral em dobro)
    esc = {}
    sem_match = set()
    for l in censo:
        rede = REDE.get(l['DependenciaAdministrativa'])
        ib = por_key.get(key(l['Municipio']))
        if not rede:
            continue
        if not ib:
            sem_match.add(l['Municipio'])
            continue
        e = esc.setdefault(l['CodigoINEP'], {'inep': l['CodigoINEP'], 'nome': l['Escola'], 'rede': rede, 'ibge': ib,
                                             'loc': l['Localizacao'], 'dif': l['LocalizacaoDiferenciada'],
                                             'mat': {k: 0 for k in ['creche', 'pre', 'ai', 'af', 'em', 'eja', 'ee']}, 'integral': 0})
        q = l['QuantidadeDeMatriculasPorEtapa'] or 0
        if l['FlagIntegral'] == 1:
            e['integral'] += q
        elif l['IncluirNaSoma'] == 1 and l['Etapa abreviada'] in ETAPA:
            e['mat'][ETAPA[l['Etapa abreviada']]] += q
    if sem_match:
        raise fontes.FonteError(f'tcees-escolas-censo: municípios sem correspondência: {sorted(sem_match)}')
    for e in esc.values():
        e['total'] = sum(v for k, v in e['mat'].items() if k != 'ee')  # educação especial já está dentro das etapas
    esc = {k: e for k, e in esc.items() if e['total'] or e['mat']['ee']}

    # 2. IDEB por escola
    for l in ideb:
        e = esc.get(l['CodigoINEP'])
        if not e:
            continue
        ano = str(l['Ano'])
        for et, col in (('ai', 'IDEB_EnsinoFundamental_AnosIniciais'), ('af', 'IDEB_EnsinoFundamental_AnosFinais'), ('em', 'IDEB_EnsinoMedio')):
            v = num(l[col])
            if v is not None:
                e.setdefault('ideb', {}).setdefault(et, {})[ano] = v

    # 3. Fluência por escola (% de leitores fluentes e distribuição)
    for l in flu_linhas:
        e = esc.get(l['CodigoINEP'])
        if e:
            e.setdefault('flu', {})[str(l['Edicao'])] = [l['PreLeitor_Total_Percentual'], l['LeitorIniciante_Percentual'], l['LeitorFluente_Percentual']]

    # 4. por município: lista, resumo e sinalizadores
    out = {ib: {'municipal': [], 'estadual': []} for ib in mun['ibge']}
    for e in esc.values():
        out[e['ibge']][e['rede']].append(e)
    ult = str(ANOS_IDEB[-1]); ant = str(ANOS_IDEB[-2])
    for ib, redes in out.items():
        resumo = {}
        for rede, lista in redes.items():
            lista.sort(key=lambda x: x['nome'])
            meds = {}
            for et in ('ai', 'af', 'em'):
                vals = [x['ideb'][et][ult] for x in lista if ult in x.get('ideb', {}).get(et, {})]
                meds[et] = round(statistics.median(vals), 2) if vals else None
            n_caiu = 0
            for x in lista:
                sinais = []
                for et in ('ai', 'af', 'em'):
                    s = x.get('ideb', {}).get(et, {})
                    if ult in s and ant in s and s[ult] < s[ant]:
                        sinais.append(f'caiu_{et}')
                    if ult in s and meds[et] is not None and s[ult] < meds[et]:
                        sinais.append(f'abaixo_{et}')
                if any(s.startswith('caiu') for s in sinais):
                    n_caiu += 1
                x['sinais'] = sinais
                for k in ('ibge', 'rede'):
                    x.pop(k, None)
            resumo[rede] = {'escolas': len(lista), 'matriculas': sum(x['total'] for x in lista),
                            'urbanas': sum(1 for x in lista if x['loc'] == 'Urbana'),
                            'com_ideb': sum(1 for x in lista if x.get('ideb')), 'mediana_ideb': meds, 'ideb_caiu': n_caiu}
        redes['resumo'] = resumo
    meta = {'fonte_censo': f'Inep – Censo Escolar {ano_censo}, compilado no Painel de Controle do TCE-ES',
            'fonte_ideb': 'Inep – Ideb por escola, compilado no Painel de Controle do TCE-ES',
            'ano_censo': ano_censo, 'anos_ideb': [str(a) for a in ANOS_IDEB],
            'coletado_em': fontes.registro().get('tcees-escolas-censo', {}).get('coletado_em') or fontes.referencia('tcees-escolas-censo'),
            'nota': 'Redes municipal e estadual (escolas federais e privadas fora). Matrículas estaduais não incluem cursos técnicos de educação profissional.'}
    save_json('escolas.json', {'meta': meta, 'municipios': out})
    return out


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    build(coletar_agora='--coletar' in sys.argv)
    print('ok')
