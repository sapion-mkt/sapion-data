"""Consulta ao painel de Educação do TCE-ES (relatório Power BI publicado na web, acesso público).

O painel (paineldecontrole.tcees.tc.br > Áreas temáticas > Educação) embute um relatório Power BI
"publicar na web". Este módulo consulta o modelo de dados desse relatório pela mesma interface pública
que o navegador usa ao exibir os gráficos, e devolve as linhas como listas de dicionários.
"""
import time

import httpx

RESOURCE_KEY = 'c90802f5-3126-4383-90d6-19071fa2bae1'
API = 'https://wabi-brazil-south-api.analysis.windows.net'
HEADERS = {'X-PowerBI-ResourceKey': RESOURCE_KEY, 'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json',
           'Origin': 'https://app.powerbi.com', 'Referer': 'https://app.powerbi.com/', 'Content-Type': 'application/json'}
_ctx = None


def _context():
    """modelId, dataset e relatório atuais (mudam quando o TCE-ES republica o painel)."""
    global _ctx
    if _ctx is None:
        r = _req('GET', f'{API}/public/reports/{RESOURCE_KEY}/modelsAndExploration?preferReadOnlySession=true')
        d = r.json()
        _ctx = {'model': d['models'][0]['id'], 'dataset': d['models'][0]['dbName'],
                'report': d['exploration']['report']['objectId']}
    return _ctx


def _req(method, url, **kw):
    for tentativa in range(4):
        try:
            r = httpx.request(method, url, headers=HEADERS, timeout=120, **kw)
            r.raise_for_status()
            return r
        except httpx.HTTPError:
            if tentativa == 3:
                raise
            time.sleep(3 * (tentativa + 1))


def _filtro_in(coluna, valores):
    lit = [[{'Literal': {'Value': f'{v}L' if isinstance(v, int) else "'" + str(v).replace("'", "''") + "'"}}] for v in valores]
    return [{'Condition': {'In': {'Expressions': [{'Column': {'Expression': {'SourceRef': {'Source': 't'}}, 'Property': coluna}}],
                                  'Values': lit}}}]


def _query(entity, cols, where, restart=None, count=30000):
    ctx = _context()
    sel = [{'Column': {'Expression': {'SourceRef': {'Source': 't'}}, 'Property': c}, 'Name': f'{entity}.{c}'} for c in cols]
    q = {'Version': 2, 'From': [{'Name': 't', 'Entity': entity, 'Type': 0}], 'Select': sel}
    if where:
        q['Where'] = where
    window = {'Count': count}
    if restart:
        window['RestartTokens'] = restart
    cmd = {'SemanticQueryDataShapeCommand': {'Query': q, 'Binding': {
        'Primary': {'Groupings': [{'Projections': list(range(len(cols)))}]},
        'DataReduction': {'DataVolume': 4, 'Primary': {'Window': window}}, 'Version': 1}, 'ExecutionMetricsKind': 1}}
    body = {'version': '1.0.0', 'cancelQueries': [], 'modelId': ctx['model'],
            'queries': [{'Query': {'Commands': [cmd]}, 'QueryId': '',
                         'ApplicationContext': {'DatasetId': ctx['dataset'], 'Sources': [{'ReportId': ctx['report'], 'VisualId': 'sapion-data'}]}}]}
    return _req('POST', f'{API}/public/reports/querydata?synchronous=true', json=body).json()


def _decode(resp, ncols):
    """Formato DSR do Power BI: linhas comprimidas (R = repete o valor anterior, Ø = nulo, dicionários de texto)."""
    res = resp['results'][0]['result']
    dsr = res['data']['dsr']
    ds = dsr['DS'][0]
    if 'PH' not in ds:
        raise RuntimeError(f'Resposta inesperada do Power BI: {str(ds)[:300]}')
    dicts = ds.get('ValueDicts', {})
    rows = ds['PH'][0].get('DM0', [])
    if not rows:
        return [], None
    schema = rows[0]['S']
    out, prev = [], [None] * ncols
    for row in rows:
        # linhas vêm como lista em 'C' ou, em consultas simples, como chaves nomeadas ('G0', 'G1'...)
        brutos = row['C'] if 'C' in row else [row[s['N']] for s in schema if s['N'] in row]
        rep, nul, vals = row.get('R', 0), row.get('Ø', 0), iter(brutos)
        cur = []
        for i in range(ncols):
            if rep >> i & 1:
                v = prev[i]
            elif nul >> i & 1:
                v = None
            else:
                v = next(vals)
                dn = schema[i].get('DN')
                if dn and isinstance(v, int):
                    v = dicts[dn][v]
            cur.append(v)
        out.append(cur)
        prev = cur
    return out, ds.get('RT')


def tabela(entity, cols, filtros=None):
    """Todas as linhas distintas de `cols` da tabela `entity`, com filtros {coluna: [valores]}."""
    where = []
    for c, vals in (filtros or {}).items():
        where += _filtro_in(c, vals)
    rows, restart = [], None
    while True:
        part, rt = _decode(_query(entity, cols, where or None, restart), len(cols))
        rows += part
        if not rt or not part:
            break
        restart = rt
    return [dict(zip(cols, r)) for r in rows]
