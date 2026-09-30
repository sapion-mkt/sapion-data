"""Bloco 4b — Execução da despesa com Educação (Função 12), RREO Anexo 2 via API pública do Siconfi.

Fonte: Tesouro Nacional, API de dados abertos do Siconfi (apidatalake.tesouro.gov.br), demonstrativo
RREO – Anexo 2 (despesa por função/subfunção), declarado pelo próprio município.
"""
import json
import os
import sys
import time

import httpx

from common import CACHE, load_municipios, save_json, rnd

API = 'https://apidatalake.tesouro.gov.br/ords/siconfi/tt/rreo'
COLS = {'DOTAÇÃO INICIAL': 'dotacao_inicial', 'DOTAÇÃO ATUALIZADA (a)': 'dotacao_atualizada',
        'DESPESAS EMPENHADAS ATÉ O BIMESTRE (b)': 'empenhado', 'DESPESAS LIQUIDADAS ATÉ O BIMESTRE (d)': 'liquidado'}
# funções de governo (linhas-título do Anexo 2) — delimitam o bloco "Educação"
FUNCOES = {'Legislativa', 'Judiciária', 'Essencial à Justiça', 'Administração', 'Defesa Nacional', 'Segurança Pública',
           'Relações Exteriores', 'Assistência Social', 'Previdência Social', 'Saúde', 'Trabalho', 'Educação', 'Cultura',
           'Direitos da Cidadania', 'Urbanismo', 'Habitação', 'Saneamento', 'Gestão Ambiental', 'Ciência e Tecnologia',
           'Agricultura', 'Organização Agrária', 'Indústria', 'Comércio e Serviços', 'Comunicações', 'Energia',
           'Transporte', 'Desporto e Lazer', 'Encargos Especiais', 'Reserva de Contingência'}


def fetch(ibge, ano, periodo):
    """Municípios com menos de 50 mil habitantes entregam o 'RREO Simplificado'; tenta os dois tipos."""
    for tipo in ('RREO', 'RREO Simplificado'):
        items = _fetch(ibge, ano, periodo, tipo)
        if items:
            return items
    return items


def _fetch(ibge, ano, periodo, tipo):
    tag = 'S' if 'Simpl' in tipo else 'C'
    path = os.path.join(CACHE, f'rreo2{tag}_{ibge}_{ano}_{periodo}.json')
    if os.path.exists(path):
        with open(path, encoding='utf-8') as fh:
            return json.load(fh)
    params = {'an_exercicio': ano, 'nr_periodo': periodo, 'co_tipo_demonstrativo': tipo,
              'no_anexo': 'RREO-Anexo 02', 'id_ente': ibge}
    for tent in range(4):
        try:
            r = httpx.get(API, params=params, timeout=90)
            r.raise_for_status()
            items = r.json().get('items', [])
            break
        except Exception:
            time.sleep(3 * (tent + 1))
    else:
        return None
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(items, fh, ensure_ascii=False)
    return items


def parse(items):
    """Extrai a Função 12 (Educação) e subfunções, só despesas exceto intra-orçamentárias."""
    res = {}
    for col, k in COLS.items():
        rows = [i for i in items if i['coluna'] == col and i['cod_conta'] == 'RREO2TotalDespesas']
        inside = False
        for it in rows:
            conta = it['conta'].strip()
            if conta in FUNCOES:
                inside = conta == 'Educação'
                if inside:
                    res.setdefault('Educação', {})[k] = it['valor']
                continue
            if inside:
                nome = conta.replace('FU12 - ', '')
                res.setdefault(nome, {})[k] = it['valor']
    return res


def latest_period(ibge, ano):
    for per in range(6, 0, -1):
        items = fetch(ibge, ano, per)
        if items:
            return per, items
    return None, None


def build():
    mun = load_municipios()
    out = {}
    for n, ib in enumerate(mun['ibge']):
        rec = {}
        per26, it26 = latest_period(ib, 2026)
        if it26:
            p = parse(it26)
            rec['2026'] = {'bimestre': per26, 'educacao': p.get('Educação'),
                           'subfuncoes': {k: v for k, v in p.items() if k != 'Educação'}}
        it25 = fetch(ib, 2025, 6)
        if it25:
            p = parse(it25)
            rec['2025'] = {'bimestre': 6, 'educacao': p.get('Educação'),
                           'subfuncoes': {k: v for k, v in p.items() if k != 'Educação'}}
        for a in rec.values():
            e = a.get('educacao') or {}
            if e.get('dotacao_atualizada'):
                a['pct_liquidado'] = rnd(e.get('liquidado', 0) / e['dotacao_atualizada'], 4)
                a['pct_empenhado'] = rnd(e.get('empenhado', 0) / e['dotacao_atualizada'], 4)
        out[ib] = rec
        print(f'{n + 1}/78 {ib} 2026-b{per26}', flush=True)
    meta = {'fonte': 'Tesouro Nacional – Siconfi, RREO Anexo 2 (despesa por função/subfunção), API de dados abertos',
            'nota': 'Valores declarados pelo município. 2026 = acumulado até o último bimestre homologado; 2025 = ano fechado (6º bimestre).'}
    save_json('execucao.json', {'meta': meta, 'municipios': out})
    return out


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    build()
