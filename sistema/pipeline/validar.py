"""Checagens de consistência dos dados gerados (rodar depois do build)."""
import json
import os
import sys

from common import OUT


def j(n):
    with open(os.path.join(OUT, n), encoding='utf-8') as fh:
        return json.load(fh)


def main():
    ok = True
    fin = j('financiamento.json')
    mf, mu = fin['meta'], fin['municipios']

    def check(nome, cond, det=''):
        nonlocal ok
        ok &= bool(cond)
        print(('OK   ' if cond else 'FALHA') + f' {nome} {det}')

    check('78 municípios no financiamento', len(mu) == 78)
    # ICMS: soma dos 78 = total do PDF em cada mês
    for m, tot in mf['icms']['total_bruto_mensal'].items():
        s = sum((x['icms']['mensal'][m] or {}).get('bruto') or 0 for x in mu.values())
        check(f'ICMS {m}/2026 soma = total do PDF', abs(s - tot) < 1, f'({s:,.2f} × {tot:,.2f})')
    # ICMS Educacional: soma = 12% do total
    s = sum(x['icms']['icms_educ_acumulado_estimado'] or 0 for x in mu.values())
    t = sum(mf['icms']['total_bruto_mensal'].values()) * mf['icms']['peso_iqe']
    check('ICMS Educacional estimado soma 12% do bruto', abs(s - t) < 100, f'({s:,.0f} × {t:,.0f})')
    # VAAR/VAAT jan–ago conferem com o documento de contexto (CSV FNDE/STN)
    s = sum(x['vaar']['recebido_2026'] or 0 for x in mu.values())
    check('VAAR jan–ago = R$ 92.363.052,51', abs(s - 92363052.51) < 1, f'({s:,.2f})')
    s = sum(x['vaat']['recebido_2026'] or 0 for x in mu.values())
    check('VAAT jan–ago = R$ 229.558.346,68', abs(s - 229558346.68) < 1, f'({s:,.2f})')
    n = sum(1 for x in mu.values() if x['vaar']['situacao'] == 'Recebe')
    check('42 municípios recebem VAAR', n == 42, f'({n})')
    s = sum(x['vaar']['perda_estimada_anual'] or 0 for x in mu.values())
    check('Deixado na mesa anual ≈ R$ 166,7 mi (planilha VAAR)', abs(s - 166665426.71) < 100, f'({s:,.0f})')
    # IPM soma 100%
    s = sum(x['icms']['ipm_2026'] or 0 for x in mu.values())
    check('IPM 2026 soma 100%', abs(s - 1) < 1e-4, f'({s:.5f})')
    # profissionais
    pr = j('profissionais.json')['municipios']
    check('78 municípios com profissionais', len(pr) == 78)
    check('todos com professores', all(x['professores']['pessoas'] > 0 for x in pr.values()))
    tot = sum(x['total']['pessoas'] for x in pr.values())
    print(f'     total de profissionais (pessoas) no ES: {tot:,}')
    # ideb / ica
    ideb = j('ideb.json')['municipios']
    check('IDEB AI 2025 para os 78', all(x['AI']['municipal'] and x['AI']['municipal']['2025']['ideb'] for x in ideb.values()))
    ica = j('alfabetizacao.json')['municipios']
    check('ICA 2025 para os 78', all(x and x['serie']['2025'] is not None for x in ica.values()))
    # fluência em leitura
    flu = j('fluencia.json')
    ult = flu['meta']['anos'][-1]
    n = sum(1 for x in flu['municipios'].values() if x['municipal'].get(ult))
    check(f'Fluência {ult}: 78 municípios na rede municipal', n == 78, f'({n})')
    tot = flu['meta']['estado']['municipal'].get(ult, {})
    check(f'Fluência {ult}: total estadual soma ~100%', tot and 98 <= sum(tot.values()) <= 102, f'({tot})')
    # escolas: confere com a Sinopse do Censo (número de escolas e matrículas municipais)
    esc = j('escolas.json')
    sin = sinopse_escolas()
    dif_esc, dif_mat = [], []
    for ib, e in esc['municipios'].items():
        s = sin.get(ib)
        if not s:
            continue
        for rede in ('municipal', 'estadual'):
            if e['resumo'][rede]['escolas'] != s['esc'][rede]:
                dif_esc.append((ib, rede, e['resumo'][rede]['escolas'], s['esc'][rede]))
        if e['resumo']['municipal']['matriculas'] != s['mat']['municipal']:
            dif_mat.append((ib, e['resumo']['municipal']['matriculas'], s['mat']['municipal']))
    check('Escolas por rede iguais à Sinopse do Censo (até 3 municípios com diferença)', len(dif_esc) <= 3, f'({len(dif_esc)}: {dif_esc[:5]})')
    check('Matrículas municipais iguais à Sinopse do Censo (até 3 municípios com diferença)', len(dif_mat) <= 3, f'({len(dif_mat)}: {dif_mat[:5]})')
    print('\nRESULTADO:', 'tudo certo' if ok else 'há falhas')
    return ok


def sinopse_escolas():
    """Escolas (tabela 3.2) e matrículas (tabela 1.2) por rede na Sinopse do Censo, com cache."""
    import fontes
    from python_calamine import CalamineWorkbook
    from common import CACHE
    path = fontes.arquivo('inep-sinopse-censo')
    cache = os.path.join(CACHE, f"sinopse_escolas_{fontes.referencia('inep-sinopse-censo')}.json")
    if os.path.exists(cache):
        with open(cache, encoding='utf-8') as fh:
            return json.load(fh)
    wb = CalamineWorkbook.from_path(path)
    out = {}
    for tab, campo in (('3.2', 'esc'), ('1.2', 'mat')):
        for r in wb.get_sheet_by_name(tab).to_python():
            if len(r) > 8 and str(r[1]).strip() == 'Espírito Santo' and isinstance(r[3], float):
                out.setdefault(str(int(r[3])), {})[campo] = {'estadual': int(r[7] or 0), 'municipal': int(r[8] or 0)}
    with open(cache, 'w', encoding='utf-8') as fh:
        json.dump(out, fh)
    return out


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(0 if main() else 1)
