"""Gera o Sapion Data: roda os blocos, junta num pacote único e injeta no HTML.

Uso:
    python build.py            # usa os JSON já gerados em ../data quando existirem
    python build.py --full     # recalcula todos os blocos a partir das fontes
Saída: ../dist/index.html (arquivo único, pronto para publicar)
"""
import base64
import datetime as dt
import json
import os
import sys

from common import APP, OUT, src, load_municipios

import profissionais
import ideb
import alfabetizacao
import financiamento
import fluencia
import escolas
import execucao
import fontes

# ordem importa: escolas usa a coleta de fluência
BLOCOS = {'profissionais.json': profissionais.build, 'ideb.json': ideb.build,
          'alfabetizacao.json': alfabetizacao.build, 'financiamento.json': financiamento.build,
          'fluencia.json': fluencia.build, 'escolas.json': escolas.build}
VERSAO = os.path.join(APP, 'versao.json')


def versao():
    with open(VERSAO, encoding='utf-8') as fh:
        return json.load(fh)


def load(name, full):
    path = os.path.join(OUT, name)
    if full or not os.path.exists(path):
        print('calculando', name, flush=True)
        BLOCOS[name]()
    with open(path, encoding='utf-8') as fh:
        return json.load(fh)


def slim_fin(f):
    """Remove detalhes que a interface não usa, para manter o arquivo leve."""
    f = dict(f)
    f['fundeb_mensal'] = {m: {k: v[k] for k in ('redistribuicao', 'VAAT', 'VAAR', 'fti')}
                          for m, v in f['fundeb_mensal'].items()}
    f['icms'] = dict(f['icms'])
    f['icms']['mensal'] = {m: (None if v is None else {'bruto': v['bruto'], 'liquido': v['liquido']})
                           for m, v in f['icms']['mensal'].items()}
    return f


def slim_esc(e):
    """Escolas: só etapas com matrícula e campos usados pela interface."""
    out = {}
    for rede in ('municipal', 'estadual'):
        lista = []
        for x in e[rede]:
            y = {k: v for k, v in x.items() if k not in ('mat', 'dif') and v not in (None, [], {})}
            y['mat'] = {k: v for k, v in x['mat'].items() if v}
            if x.get('dif'):
                y['dif'] = x['dif']
            lista.append(y)
        out[rede] = lista
    out['resumo'] = e['resumo']
    return out


INKS = {'preto': (0, 0, 0), 'azul': (0x44, 0x4D, 0xF2)}
INKS_DARK = {'preto': (0xFF, 0xFF, 0xFF), 'azul': (0x7C, 0x83, 0xFF)}


def logos_sapion_data(altura=96):
    """Recorta a margem transparente do logo do Sapion Data e gera duas versões:
    cores originais (tema claro) e texto branco + azul clareado (tema escuro)."""
    import io
    import numpy as np
    from PIL import Image
    img = np.asarray(Image.open(fontes.arquivo('logo-sapion-data')).convert('RGBA'))
    alpha = img[..., 3]
    ys, xs = np.where(alpha > 10)
    y0, y1, x0, x1 = max(ys.min() - 4, 0), ys.max() + 5, max(xs.min() - 4, 0), xs.max() + 5
    rgb = img[..., :3].astype(int)
    azul = (rgb[..., 2] - rgb[..., 0]) > 60            # pixels da cor da marca
    out = {}
    for tema, inks in (('claro', None), ('escuro', INKS_DARK)):
        if inks is None:
            cor = rgb
        else:
            cor = np.where(azul[..., None], np.array(inks['azul']), np.array(inks['preto']))
        rgba = np.dstack([cor, alpha]).astype(np.uint8)[y0:y1, x0:x1]
        im = Image.fromarray(rgba, 'RGBA')
        im = im.resize((round(im.width * altura / im.height), altura), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, 'PNG', optimize=True)
        out[tema] = 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()
    return out


# Plano de expansão (Plano de Marketing 2026–2030): Tier 1 ES, CE, PE; Tier 2 SP, MG, PR; Tier 3 GO, MS, SC
ESTADOS = [('ES', 'Espírito Santo', True), ('CE', 'Ceará', False), ('PE', 'Pernambuco', False),
           ('SP', 'São Paulo', False), ('MG', 'Minas Gerais', False), ('PR', 'Paraná', False),
           ('GO', 'Goiás', False), ('MS', 'Mato Grosso do Sul', False), ('SC', 'Santa Catarina', False)]


def main(full=False):
    mun = load_municipios()
    prof, idb, alf, fin, flu, esc = (load(n, full) for n in BLOCOS)
    ver = versao()
    municipios = []
    for _, m in mun.iterrows():
        ib = m['ibge']
        municipios.append({
            'ibge': ib, 'uf': 'ES', 'siafi': m['siafi'], 'nome': m['nome'],
            'prof': prof['municipios'].get(ib), 'ideb': idb['municipios'].get(ib),
            'ica': alf['municipios'].get(ib), 'fin': slim_fin(fin['municipios'][ib]),
            'flu': flu['municipios'].get(ib), 'esc': slim_esc(esc['municipios'][ib]),
        })
    municipios.sort(key=lambda x: x['nome'])
    n_por_uf = {uf: sum(1 for m in municipios if m['uf'] == uf) for uf, _, _ in ESTADOS}
    bundle = {
        'gerado_em': dt.datetime.now().strftime('%d/%m/%Y %H:%M'),
        'versao': 'v' + ver['versao'],
        'versao_info': ver,
        'estados': [{'uf': uf, 'nome': nome, 'ativo': ativo, 'n_municipios': n_por_uf[uf]} for uf, nome, ativo in ESTADOS],
        'meta': {'profissionais': prof['meta'], 'ideb': idb['meta'], 'ideb_stats': idb['estatisticas'],
                 'ica': alf['meta'], 'fin': fin['meta'], 'flu': flu['meta'], 'esc': esc['meta'],
                 'fontes': fontes.resumo()},
        'municipios': municipios,
    }
    tpl_path = os.path.join(APP, 'site', 'index.template.html')
    with open(tpl_path, encoding='utf-8') as fh:
        html = fh.read()
    data = json.dumps(bundle, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    lg = logos_sapion_data()
    html = (html.replace('/*__DATA__*/null', data)
                .replace('__LOGO_LIGHT__', lg['claro'])
                .replace('__LOGO_DARK__', lg['escuro']))
    os.makedirs(os.path.join(APP, 'dist'), exist_ok=True)
    out = os.path.join(APP, 'dist', 'index.html')
    with open(out, 'w', encoding='utf-8') as fh:
        fh.write(html)
    print(f'ok -> {out} ({os.path.getsize(out) / 1024:.0f} KB)')
    pasta_github(html)


# Reset que o claude.ai aplica automaticamente; num site comum (GitHub Pages) precisa vir no próprio arquivo
RESET = (':root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}'
         'body{margin:0}img{max-width:100%}[hidden]{display:none!important}')
PUBLICAR = os.path.join(src(), 'publicar-github')


def standalone(html):
    """Documento HTML completo para hospedagem comum. noindex: o painel não aparece em buscadores."""
    i = html.index('<style>')
    return ('<!doctype html>\n<html lang="pt-BR">\n<head>\n' + html[:i] +
            '<meta name="robots" content="noindex, nofollow">\n'
            f'<style>{RESET}</style>\n</head>\n<body>\n' + html[i:] + '\n</body>\n</html>\n')


def pasta_github(html):
    """Monta a pasta 'publicar-github' com o conteúdo do repositório: o painel na raiz (GitHub Pages)
    e o código-fonte em 'sistema/'. Fontes brutas e o cache (que tem nomes de servidores) ficam de fora."""
    import shutil
    if os.path.exists(PUBLICAR):
        shutil.rmtree(PUBLICAR)
    os.makedirs(PUBLICAR)
    with open(os.path.join(PUBLICAR, 'index.html'), 'w', encoding='utf-8') as fh:
        fh.write(standalone(html))
    open(os.path.join(PUBLICAR, '.nojekyll'), 'w').close()
    sis = os.path.join(PUBLICAR, 'sistema')
    shutil.copytree(os.path.join(APP, 'pipeline'), os.path.join(sis, 'pipeline'),
                    ignore=shutil.ignore_patterns('.cache', '__pycache__', '.claude', '*.parquet', 'execucao.py'))
    shutil.copytree(os.path.join(APP, 'site'), os.path.join(sis, 'site'))
    shutil.copytree(os.path.join(APP, 'data'), os.path.join(sis, 'data'))
    shutil.copy(os.path.join(APP, 'README.md'), os.path.join(sis, 'README.md'))
    shutil.copy(os.path.join(APP, 'PADRAO-DE-ATUALIZACAO.md'), os.path.join(sis, 'PADRAO-DE-ATUALIZACAO.md'))
    shutil.copy(os.path.join(APP, 'versao.json'), os.path.join(sis, 'versao.json'))
    shutil.copy(os.path.join(APP, 'README-repositorio.md'), os.path.join(PUBLICAR, 'README.md'))
    n = sum(len(f) for _, _, f in os.walk(PUBLICAR))
    print(f'ok -> {PUBLICAR} ({n} arquivos)')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main(full='--full' in sys.argv)
