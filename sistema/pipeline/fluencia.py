"""Bloco 3b — Avaliação da Fluência em Leitura (ES), 2º ano, por município e escola.

Fonte: Painel de Controle do TCE-ES (dados da Sedu/CAEd), coletado automaticamente.
Níveis: pré-leitor, leitor iniciante e leitor fluente (percentual dos estudantes avaliados).
"""
import sys

from common import key, load_municipios, save_json
import fontes
import tcees_powerbi

FID = 'tcees-fluencia'
COLS = ['Tipo', 'Edicao', 'DependenciaAdministrativa', 'SuperintendenciaRegionalDeEducacao', 'Municipio', 'CodigoINEP',
        'Escola', 'PreLeitor_Total_Percentual', 'LeitorIniciante_Percentual', 'LeitorFluente_Percentual']
REDE = {'Municipal': 'municipal', 'Estadual': 'estadual'}


def coletar():
    linhas = tcees_powerbi.tabela('Fluencia', COLS)
    if not any(l['Tipo'] == 'Município' for l in linhas):
        raise fontes.FonteError('tcees-fluencia: o painel do TCE-ES não devolveu resultados por município.')
    return fontes.nova_coleta(FID, 'fluencia.json', linhas)


def niveis(l):
    return {'pre': l['PreLeitor_Total_Percentual'], 'ini': l['LeitorIniciante_Percentual'], 'flu': l['LeitorFluente_Percentual']}


def build(coletar_agora=False):
    if coletar_agora:
        coletar()
    try:
        linhas = fontes.ler_coleta(FID)
    except fontes.FonteError:
        coletar()
        linhas = fontes.ler_coleta(FID)
    mun = load_municipios()
    por_key = {k: ib for k, ib in zip(mun['key'], mun['ibge'])}
    anos = sorted({l['Edicao'] for l in linhas})
    out = {ib: {'municipal': {}, 'estadual': {}, 'sre': None} for ib in mun['ibge']}
    estado = {'municipal': {}, 'estadual': {}}
    sem_match = set()
    for l in linhas:
        rede = REDE.get(l['DependenciaAdministrativa'])
        if not rede:
            continue
        ano = str(l['Edicao'])
        if l['Tipo'] == 'Estado':
            estado[rede][ano] = niveis(l)
        elif l['Tipo'] == 'Município':
            ib = por_key.get(key(l['Municipio']))
            if not ib:
                sem_match.add(l['Municipio'])
                continue
            out[ib][rede][ano] = niveis(l)
            out[ib]['sre'] = l['SuperintendenciaRegionalDeEducacao']
    if sem_match:
        raise fontes.FonteError(f'tcees-fluencia: municípios sem correspondência: {sorted(sem_match)}')
    # posição entre os municípios (rede municipal), pelo % de leitores fluentes de cada edição
    for ano in map(str, anos):
        vals = {ib: o['municipal'].get(ano, {}).get('flu') for ib, o in out.items()}
        n = sum(v is not None for v in vals.values())
        for ib, v in vals.items():
            out[ib].setdefault('ranking', {})[ano] = None if v is None else 1 + sum(1 for x in vals.values() if x is not None and x > v)
            out[ib].setdefault('n_ranking', {})[ano] = n
    reg = fontes.registro().get(FID, {})
    meta = {'fonte': 'Sedu/CAEd – Avaliação da Fluência em Leitura, compilado no Painel de Controle do TCE-ES',
            'link': fontes.info(FID)['link'], 'anos': [str(a) for a in anos], 'estado': estado,
            'coletado_em': reg.get('coletado_em') or fontes.referencia(FID), 'etapa': '2º ano do ensino fundamental',
            'nota': 'Percentual dos estudantes avaliados em cada nível. O painel não informa o número de alunos avaliados.'}
    save_json('fluencia.json', {'meta': meta, 'municipios': out})
    return out


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    build(coletar_agora='--coletar' in sys.argv)
    print('ok')
