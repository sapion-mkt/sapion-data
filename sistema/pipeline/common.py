"""Utilidades compartilhadas do pipeline do Sapion Data."""
import os
import re
import json
import unicodedata

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
APP = os.path.join(ROOT, 'sapion-data-app')
CACHE = os.path.join(APP, 'pipeline', '.cache')
OUT = os.path.join(APP, 'data')
os.makedirs(CACHE, exist_ok=True)
os.makedirs(OUT, exist_ok=True)


def src(*parts):
    """Caminho de um arquivo-fonte dentro da pasta do projeto."""
    return os.path.join(ROOT, *parts)


def norm(s):
    """MAIÚSCULAS, sem acento, espaços simples — chave de junção por nome."""
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return ''
    s = unicodedata.normalize('NFKD', str(s)).encode('ascii', 'ignore').decode()
    s = re.sub(r'[^A-Za-z0-9 ]+', ' ', s).upper()
    return re.sub(r'\s+', ' ', s).strip()


# Grafias alternativas encontradas nas fontes -> grafia usada no IBGE/FNDE
NAME_FIX = {
    'DIVINO SAO LOURENCO': 'DIVINO DE SAO LOURENCO',
    'GOVERNADOR LINDEMBERG': 'GOVERNADOR LINDENBERG',
    'ATILIO VIVACQUA': 'ATILIO VIVACQUA',
    'MARATAIZES': 'MARATAIZES',
    'CACH ITAPEMIRIM': 'CACHOEIRO DE ITAPEMIRIM',
    'CONC DA BARRA': 'CONCEICAO DA BARRA',
    'CONC CASTELO': 'CONCEICAO DO CASTELO',
    'CONCEICAO CASTELO': 'CONCEICAO DO CASTELO',
    'S DOMINGOS DO NORTE': 'SAO DOMINGOS DO NORTE',
    'S GABRIEL DA PALHA': 'SAO GABRIEL DA PALHA',
    'S JOSE DO CALCADO': 'SAO JOSE DO CALCADO',
    'S ROQUE DO CANAA': 'SAO ROQUE DO CANAA',
    'STA LEOPOLDINA': 'SANTA LEOPOLDINA',
    'STA MARIA DE JETIBA': 'SANTA MARIA DE JETIBA',
    'STA TERESA': 'SANTA TERESA',
    'VENDA NOVA IMIGRANTE': 'VENDA NOVA DO IMIGRANTE',
    'JERONIMO MONTEIRO': 'JERONIMO MONTEIRO',
    'BARRA DE S FRANCISCO': 'BARRA DE SAO FRANCISCO',
    'BARRA S FRANCISCO': 'BARRA DE SAO FRANCISCO',
    'AGUA DOCE NORTE': 'AGUA DOCE DO NORTE',
    'BOM JESUS NORTE': 'BOM JESUS DO NORTE',
}


def key(name):
    k = norm(name)
    return NAME_FIX.get(k, k)


def brl(v):
    """'R$1.754.645,59' -> 1754645.59"""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return 0.0
    s = str(v).replace('R$', '').replace('.', '').replace(',', '.').strip()
    return float(s) if s else 0.0


def load_municipios():
    """Tabela-dimensão: 78 municípios do ES com IBGE (texto), SIAFI e nome."""
    import fontes  # tabela de municípios: IBGE, SIAFI e nome padronizados vêm do CSV do Tesouro
    df = pd.read_csv(fontes.arquivos('tesouro-fundeb-mensal')[0],
                     sep=';', encoding='latin-1', dtype=str)
    d = (df[['Código IBGE', 'Código SIAFI', 'Município']].drop_duplicates()
         .rename(columns={'Código IBGE': 'ibge', 'Código SIAFI': 'siafi', 'Município': 'nome'}))
    d['key'] = d['nome'].map(key)
    d = d.sort_values('key').reset_index(drop=True)
    assert len(d) == 78, len(d)
    return d


def save_json(name, obj):
    path = os.path.join(OUT, name)
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1, default=_default)
    return path


def _default(o):
    if hasattr(o, 'item'):
        return o.item()
    raise TypeError(type(o))


def rnd(x, n=2):
    if x is None or (isinstance(x, float) and (pd.isna(x))):
        return None
    return round(float(x), n)
