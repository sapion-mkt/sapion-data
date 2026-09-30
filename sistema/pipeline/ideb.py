"""Bloco 2 — IDEB 2021, 2023 e 2025 (anos iniciais e finais), com ranking estadual."""
import sys

from python_calamine import CalamineWorkbook

from common import src, load_municipios, save_json, rnd

FILES = {
    'AI': src('IDEB', 'divulgacao_anos_iniciais_municipios_2025', 'divulgacao_anos_iniciais_municipios_2025',
              'divulgacao_anos_iniciais_municipios_2025.xlsx'),
    'AF': src('IDEB', 'divulgacao_anos_finais_municipios_2025', 'divulgacao_anos_finais_municipios_2025',
              'divulgacao_anos_finais_municipios_2025.xlsx'),
}
ANOS = [2021, 2023, 2025]
# códigos de coluna do cabeçalho técnico da planilha do Inep
CODES = {'ideb': 'VL_OBSERVADO_{}', 'saeb': 'VL_NOTA_MEDIA_{}', 'mat': 'VL_NOTA_MATEMATICA_{}',
         'lp': 'VL_NOTA_PORTUGUES_{}', 'rend': 'VL_INDICADOR_REND_{}'}
REDES = {'Municipal': 'municipal', 'Estadual': 'estadual', 'Pública': 'publica'}


def num(v):
    if v in ('', '-', '--', None, 'ND', '*'):
        return None
    if isinstance(v, str):
        v = v.replace('.', '').replace(',', '.') if ',' in v else v
        try:
            return float(v)
        except ValueError:
            return None
    return float(v)


def read(etapa):
    wb = CalamineWorkbook.from_path(FILES[etapa])
    rows = wb.get_sheet_by_name(wb.sheet_names[0]).to_python()
    header = next(r for r in rows if r and r[0] == 'SG_UF')
    idx = {h: i for i, h in enumerate(header)}
    data = {}
    for r in rows:
        if not r or r[0] != 'ES' or r[3] not in REDES:
            continue
        ib = str(int(r[1]))
        rec = {}
        for a in ANOS:
            rec[str(a)] = {k: num(r[idx[c.format(a)]]) for k, c in CODES.items()}
        data.setdefault(ib, {})[REDES[r[3]]] = rec
    return data


def rank(values):
    """values: {ibge: valor}. Ranking decrescente com empates (1 = melhor)."""
    vs = sorted({v for v in values.values() if v is not None}, reverse=True)
    out = {}
    for ib, v in values.items():
        if v is None:
            out[ib] = None
        else:
            out[ib] = 1 + sum(1 for x in values.values() if x is not None and x > v)
    return out


def build():
    mun = load_municipios()
    res = {ib: {} for ib in mun['ibge']}
    stats = {}
    for etapa in ['AI', 'AF']:
        d = read(etapa)
        stats[etapa] = {}
        for a in ANOS:
            vals = {ib: (d.get(ib, {}).get('municipal', {}).get(str(a), {}).get('ideb')) for ib in res}
            rk = rank(vals)
            n = sum(1 for v in vals.values() if v is not None)
            valid = sorted(v for v in vals.values() if v is not None)
            stats[etapa][str(a)] = {'n': n, 'media': rnd(sum(valid) / n, 2) if n else None,
                                    'mediana': valid[n // 2] if n else None,
                                    'max': max(valid) if n else None, 'min': min(valid) if n else None}
            for ib in res:
                res[ib].setdefault(etapa, {'municipal': {}, 'publica': {}, 'estadual': {}, 'ranking': {}, 'n_ranking': {}})
                res[ib][etapa]['ranking'][str(a)] = rk[ib]
                res[ib][etapa]['n_ranking'][str(a)] = n
        for ib in res:
            for rede in ['municipal', 'publica', 'estadual']:
                res[ib][etapa][rede] = d.get(ib, {}).get(rede)
    meta = {'fonte': 'Inep – Ideb 2025, resultados por município (divulgação 2026)',
            'rede_principal': 'municipal',
            'nota': 'Ranking entre os municípios capixabas com Ideb divulgado para a rede municipal naquele ano e etapa.'}
    save_json('ideb.json', {'meta': meta, 'estatisticas': stats, 'municipios': res})
    return res


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    build()
    print('ok')
