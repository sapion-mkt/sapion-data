"""Relatório de conferência: o que mudou nos indicadores de cada município desde a última atualização.

A cada atualização, guarda uma "fotografia" dos indicadores-chave em ../historico/AAAA-MM-DD_HHMM.json
e compara com a fotografia anterior. O relatório (../relatorios/conferencia-AAAA-MM-DD_HHMM.md) lista as
mudanças que merecem atenção antes de publicar.
"""
import datetime as dt
import json
import os
import sys

from common import APP, OUT, load_municipios

HIST = os.path.join(APP, 'historico')
REL = os.path.join(APP, 'relatorios')

# indicador: (rótulo, tipo, limite) — tipo 'pct' = variação relativa; 'abs' = diferença absoluta; 'cat' = mudou de valor
INDICADORES = {
    'profissionais': ('Profissionais (pessoas)', 'pct', 0.10),
    'professores': ('Professores (pessoas)', 'pct', 0.10),
    'pct_dt': ('% de DTs entre professores', 'abs', 10),
    'ideb_ai': ('IDEB anos iniciais (último)', 'abs', 0.3),
    'ideb_af': ('IDEB anos finais (último)', 'abs', 0.3),
    'ica': ('Alfabetização – ICA (último)', 'abs', 5),
    'flu': ('Leitores fluentes (último)', 'abs', 10),
    'vaar_situacao': ('Situação no VAAR', 'cat', None),
    'vaar_perda': ('VAAR deixado na mesa (ano)', 'pct', 0.15),
    'vaar_recebido': ('VAAR recebido no ano', 'pct', 0.30),
    'vaat_habilitado': ('Habilitação ao VAAT', 'cat', None),
    'icms_bruto': ('ICMS bruto acumulado', 'pct', 0.30),
    'ipm': ('IPM', 'abs', 0.001),
    'escolas_mun': ('Escolas municipais', 'abs', 2),
    'escolas_est': ('Escolas estaduais', 'abs', 2),
}


def _j(n):
    with open(os.path.join(OUT, n), encoding='utf-8') as fh:
        return json.load(fh)


def fotografia():
    prof, idb, alf, fin = _j('profissionais.json'), _j('ideb.json'), _j('alfabetizacao.json'), _j('financiamento.json')
    flu, esc = _j('fluencia.json'), _j('escolas.json')
    ult_ideb = max(idb['estatisticas']['AI'])
    ult_flu = flu['meta']['anos'][-1]
    out = {}
    for _, m in load_municipios().iterrows():
        ib = m['ibge']
        p, i, a, f = prof['municipios'][ib], idb['municipios'][ib], alf['municipios'][ib], fin['municipios'][ib]
        fl, e = flu['municipios'][ib], esc['municipios'][ib]
        out[ib] = {
            'nome': m['nome'],
            'profissionais': p['total']['pessoas'], 'professores': p['professores']['pessoas'],
            'pct_dt': round(100 * p['professores']['dt'] / p['professores']['pessoas']) if p['professores']['pessoas'] else None,
            'ideb_ai': ((i['AI']['municipal'] or {}).get(ult_ideb) or {}).get('ideb'),
            'ideb_af': ((i['AF']['municipal'] or {}).get(ult_ideb) or {}).get('ideb'),
            'ica': (a or {}).get('serie', {}).get(max((a or {}).get('serie', {'0': 0}))) if a else None,
            'flu': fl['municipal'].get(ult_flu, {}).get('flu'),
            'vaar_situacao': f['vaar']['situacao'], 'vaar_perda': f['vaar']['perda_estimada_anual'],
            'vaar_recebido': f['vaar']['recebido_2026'], 'vaat_habilitado': f['vaat']['habilitado'],
            'icms_bruto': f['icms']['bruto_acumulado'], 'ipm': f['icms']['ipm_2026'],
            'escolas_mun': e['resumo']['municipal']['escolas'], 'escolas_est': e['resumo']['estadual']['escolas'],
        }
    return out


def comparar(antes, depois):
    mudancas = []
    for ib, d in depois.items():
        a = antes.get(ib)
        if not a:
            continue
        for k, (rot, tipo, lim) in INDICADORES.items():
            va, vd = a.get(k), d.get(k)
            if va == vd:
                continue
            if va is None or vd is None or tipo == 'cat':
                mudancas.append((d['nome'], rot, va, vd))
            elif tipo == 'pct' and va and abs(vd - va) / abs(va) >= lim:
                mudancas.append((d['nome'], rot, va, vd))
            elif tipo == 'abs' and abs(vd - va) >= lim:
                mudancas.append((d['nome'], rot, va, vd))
    return mudancas


def fmt(v):
    if isinstance(v, float):
        return f'{v:,.3f}'.replace(',', 'X').replace('.', ',').replace('X', '.').rstrip('0').rstrip(',')
    if isinstance(v, int) and not isinstance(v, bool):
        return f'{v:,}'.replace(',', '.')
    return {True: 'sim', False: 'não', None: '—'}.get(v, str(v))


def gerar(fontes_usadas=None):
    """Grava a fotografia atual, compara com a anterior e escreve o relatório. Retorna o caminho do relatório."""
    os.makedirs(HIST, exist_ok=True)
    os.makedirs(REL, exist_ok=True)
    agora = dt.datetime.now()
    tag = agora.strftime('%Y-%m-%d_%H%M')
    atual = fotografia()
    anteriores = sorted(f for f in os.listdir(HIST) if f.endswith('.json'))
    antes = None
    if anteriores:
        with open(os.path.join(HIST, anteriores[-1]), encoding='utf-8') as fh:
            antes = json.load(fh)
    with open(os.path.join(HIST, f'{tag}.json'), 'w', encoding='utf-8') as fh:
        json.dump(atual, fh, ensure_ascii=False, indent=1)

    L = [f'# Relatório de conferência – Sapion Data', '', f'Gerado em {agora.strftime("%d/%m/%Y %H:%M")}.', '']
    if fontes_usadas:
        L += ['## Fontes usadas nesta atualização', '', '| Fonte | Referência | Arquivos | Atualizado em |', '|---|---|---|---|']
        L += [f'| {f["descricao"]} | {f["referencia"] or "—"} | {f["arquivos"]} | {f["atualizado_em"]} |' for f in fontes_usadas.values()]
        L.append('')
    if antes is None:
        L += ['## Mudanças', '', 'Primeira fotografia: ainda não há versão anterior para comparar. Esta passa a ser a base.']
        mudancas = []
    else:
        mudancas = comparar(antes, atual)
        L += [f'## Mudanças desde {anteriores[-1].replace(".json", "").replace("_", " ")}', '']
        if not mudancas:
            L.append('Nenhuma mudança acima dos limites de atenção.')
        else:
            L += [f'{len(mudancas)} mudanças acima dos limites de atenção. Confira as que parecem estranhas antes de publicar.', '',
                  '| Município | Indicador | Antes | Agora |', '|---|---|---|---|']
            L += [f'| {n} | {r} | {fmt(a)} | {fmt(d)} |' for n, r, a, d in sorted(mudancas)]
    L += ['', '## Limites de atenção', '']
    L += [f'- {rot}: ' + ('qualquer mudança' if t == 'cat' else (f'variação de {int(l * 100)}% ou mais' if t == 'pct' else f'diferença de {fmt(l)} ou mais'))
          for rot, t, l in INDICADORES.values()]
    path = os.path.join(REL, f'conferencia-{tag}.md')
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(L) + '\n')
    return path, mudancas, antes is None


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    p, mud, primeira = gerar()
    print(p, 'primeira' if primeira else f'{len(mud)} mudanças')
