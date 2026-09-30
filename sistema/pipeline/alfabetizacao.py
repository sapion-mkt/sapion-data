"""Bloco 3 — Indicador Criança Alfabetizada (ICA, Inep/MEC), rede municipal, 2023–2025 e metas."""
import sys

import pandas as pd

from common import src, load_municipios, save_json

FILE = src('Alfabetização', 'resultados_e_metas_municipios_2025_3.xlsx')


def build():
    mun = load_municipios()
    df = pd.read_excel(FILE, sheet_name=0, header=1, engine='calamine', dtype={'CO_MUNICIPIO': str})
    df = df[df['SG_UF'] == 'ES'].copy()
    df['ibge'] = df['CO_MUNICIPIO'].astype(str).str[:7]
    df = df.set_index('ibge')

    def v(x):
        return None if pd.isna(x) else float(x)

    out = {}
    for ib in mun['ibge']:
        if ib not in df.index:
            out[ib] = None
            continue
        r = df.loc[ib]
        serie = {str(a): v(r[f'PC_ALUNO_ALFABETIZADO_{a}']) for a in (2023, 2024, 2025)}
        metas = {str(a): v(r[f'META_FINAL_{a}']) for a in range(2024, 2031)}
        out[ib] = {'serie': serie, 'metas': metas, 'nivel': v(r['CO_NIVEL_ALFABETIZACAO']),
                   'participacao': v(r['PC_AVALIADOS_LP'])}
    # ranking estadual 2025
    vals = {ib: (o['serie']['2025'] if o else None) for ib, o in out.items()}
    for ib, o in out.items():
        if o and o['serie']['2025'] is not None:
            o['ranking_2025'] = 1 + sum(1 for x in vals.values() if x is not None and x > o['serie']['2025'])
            o['bateu_meta_2025'] = o['serie']['2025'] >= (o['metas']['2025'] or 0)
            o['gap_meta_2025'] = o['serie']['2025'] - (o['metas']['2025'] or 0)
    es = [x for x in vals.values() if x is not None]
    meta = {'fonte': 'Inep/MEC – Indicador Criança Alfabetizada (resultados e metas por município, rede municipal)',
            'referencias': {'brasil': {'2023': 56, '2024': 59.2, '2025': 66}, 'es': {'2023': 68, '2024': 71.7, '2025': 77},
                            'meta_nacional_2030': 80},
            'media_municipios_es_2025': round(sum(es) / len(es), 1), 'n': len(es),
            'nota': 'Percentual de alunos do 2º ano com pelo menos 743 pontos na escala Saeb.'}
    save_json('alfabetizacao.json', {'meta': meta, 'municipios': out})
    return out


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    build()
    print('ok')
