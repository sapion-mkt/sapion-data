"""Acesso às fontes de dados pelo catálogo (Fontes/catalogo_fontes.xlsx).

Nenhum módulo do pipeline usa caminho fixo: todos pedem o arquivo pelo id da fonte.
Estrutura: Fontes/<pasta da fonte>/<referência>/<arquivo>. Sem referência no catálogo,
vale a subpasta mais recente (ordem alfabética: AAAA, AAAA-Tn ou AAAA-MM-DD).
"""
import datetime as dt
import fnmatch
import json
import os

from python_calamine import CalamineWorkbook

from common import src

FONTES = src('Fontes')
CATALOGO = os.path.join(FONTES, 'catalogo_fontes.xlsx')
REGISTRO = os.path.join(FONTES, '_registro_coletas.json')
_cat = None


class FonteError(Exception):
    """Problema com uma fonte, explicado em português para quem está atualizando."""


def catalogo():
    global _cat
    if _cat is None:
        if not os.path.exists(CATALOGO):
            raise FonteError(f'Catálogo não encontrado: {CATALOGO}')
        rows = CalamineWorkbook.from_path(CATALOGO).get_sheet_by_name('Fontes').to_python()
        head = [str(h).strip() for h in rows[0]]
        _cat = {}
        for r in rows[1:]:
            d = {h: (str(v).strip() if v not in (None, '') else '') for h, v in zip(head, r)}
            if d.get('id'):
                _cat[d['id']] = d
    return _cat


def info(fid):
    try:
        return catalogo()[fid]
    except KeyError:
        raise FonteError(f'A fonte "{fid}" não está no catálogo ({CATALOGO}).')


def pasta_referencia(fid):
    f = info(fid)
    base = os.path.join(FONTES, *f['pasta'].split('/'))
    if f.get('referencia') == '.':
        return base
    if f.get('referencia'):
        p = os.path.join(base, f['referencia'])
        if not os.path.isdir(p):
            raise FonteError(f'{fid}: a referência "{f["referencia"]}" indicada no catálogo não existe em {base}.')
        return p
    if not os.path.isdir(base):
        raise FonteError(f'{fid}: a pasta {base} não existe.')
    subs = sorted(d for d in os.listdir(base) if os.path.isdir(os.path.join(base, d)) and not d.startswith('_'))
    if not subs:
        raise FonteError(f'{fid}: nenhuma subpasta de referência em {base}.')
    return os.path.join(base, subs[-1])


def referencia(fid):
    p = pasta_referencia(fid)
    return os.path.basename(p) if info(fid).get('referencia') != '.' else ''


def arquivos(fid):
    """Arquivos da referência em uso que seguem o padrão de nome do catálogo."""
    p = pasta_referencia(fid)
    padrao = info(fid)['padrao_arquivo'] or '*'
    out = sorted(os.path.join(p, n) for n in os.listdir(p) if fnmatch.fnmatch(n, padrao))
    if not out:
        raise FonteError(f'{fid}: nenhum arquivo "{padrao}" em {p}.')
    return out


def arquivo(fid, contendo=None):
    """Um único arquivo da fonte (opcionalmente o que contém um trecho no nome)."""
    arqs = arquivos(fid)
    if contendo:
        arqs = [a for a in arqs if contendo.lower() in os.path.basename(a).lower()]
    if len(arqs) != 1:
        raise FonteError(f'{fid}: esperava 1 arquivo{" com " + repr(contendo) if contendo else ""}, encontrei {len(arqs)}.')
    return arqs[0]


# ---------- fontes automáticas: cada coleta vira uma subpasta com a data ----------
def nova_coleta(fid, nome_arquivo, dados):
    """Grava o resultado de uma coleta automática em Fontes/<pasta>/<AAAA-MM-DD>/<arquivo>."""
    f = info(fid)
    hoje = dt.date.today().isoformat()
    p = os.path.join(FONTES, *f['pasta'].split('/'), hoje)
    os.makedirs(p, exist_ok=True)
    path = os.path.join(p, nome_arquivo)
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(dados, fh, ensure_ascii=False)
    reg = registro()
    reg[fid] = {'referencia': hoje, 'coletado_em': dt.datetime.now().strftime('%d/%m/%Y %H:%M'), 'arquivo': path}
    with open(REGISTRO, 'w', encoding='utf-8') as fh:
        json.dump(reg, fh, ensure_ascii=False, indent=1)
    return path


def ler_coleta(fid):
    with open(arquivo(fid), encoding='utf-8') as fh:
        return json.load(fh)


def registro():
    if os.path.exists(REGISTRO):
        with open(REGISTRO, encoding='utf-8') as fh:
            return json.load(fh)
    return {}


def resumo():
    """Metadados das fontes em uso (para os carimbos 'atualizado em' do painel)."""
    out = {}
    for fid, f in catalogo().items():
        try:
            ref = referencia(fid)
            arqs = arquivos(fid)
            mod = max(os.path.getmtime(a) for a in arqs)
        except FonteError:
            continue
        out[fid] = {'descricao': f['descricao'], 'orgao': f['orgao'], 'tipo': f['tipo'], 'referencia': ref,
                    'arquivos': len(arqs), 'atualizado_em': dt.datetime.fromtimestamp(mod).strftime('%d/%m/%Y'),
                    'periodicidade': f['periodicidade'], 'proxima_atualizacao': f['proxima_atualizacao'], 'link': f['link']}
    return out
