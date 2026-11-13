"""Atualização completa do Sapion Data — o caminho padrão para qualquer dado novo.

Uso:
    python atualizar.py                       # atualização de dados (mantém o número da versão)
    python atualizar.py --sem-coleta          # não consulta as fontes automáticas (usa a última coleta)
    python atualizar.py --versao 1.2 "Novidade 1" "Novidade 2"   # registra uma versão nova com as novidades

Etapas:
  1. confere o catálogo e os arquivos das fontes manuais (existem? têm o conteúdo esperado?)
  2. coleta as fontes automáticas (painel do TCE-ES: fluência e escolas)
  3. recalcula todos os blocos
  4. roda as checagens de totais e coberturas (validar.py)
  5. gera o relatório de conferência (o que mudou desde a última atualização)
  6. registra a data dos dados (e a versão nova, se pedida) e gera o painel e a pasta do GitHub
Se qualquer etapa falhar, nada é publicado e a mensagem explica o que corrigir.
"""
import datetime as dt
import json
import os
import sys
import traceback

from python_calamine import CalamineWorkbook

from common import APP
import fontes


def etapa(n, txt):
    print(f'\n[{n}/6] {txt}', flush=True)


def conferir_manuais():
    problemas = []
    for fid, f in fontes.catalogo().items():
        if f['tipo'] != 'manual':
            continue
        try:
            arqs = fontes.arquivos(fid)
        except fontes.FonteError as e:
            problemas.append(str(e))
            continue
        textos = [t.strip() for t in f.get('conferencia', '').split(';') if t.strip()]
        for a in arqs:
            if not textos:
                continue
            achado = conteudo(a)
            faltam = [t for t in textos if t not in achado]
            if faltam:
                problemas.append(f'{fid}: o arquivo {os.path.basename(a)} não tem o conteúdo esperado ({", ".join(faltam)}). Confira se é o arquivo certo.')
        print(f'   ok  {fid} ({fontes.referencia(fid) or "pasta"}: {len(arqs)} arquivo(s))')
    return problemas


def conteudo(path):
    """Texto do começo do arquivo, para a conferência (cabeçalhos de CSV ou primeiras linhas das planilhas)."""
    ext = os.path.splitext(path)[1].lower()
    if ext == '.csv':
        with open(path, 'rb') as fh:
            raw = fh.read(4000)
        for enc in ('utf-8', 'latin-1'):
            try:
                return raw.decode(enc)
            except UnicodeDecodeError:
                continue
    if ext in ('.xlsx', '.xls', '.ods'):
        wb = CalamineWorkbook.from_path(path)
        partes = []
        for nome in wb.sheet_names[:6]:
            rows = wb.get_sheet_by_name(nome).to_python(nrows=15)
            partes.append(' '.join(str(c) for r in rows for c in r if c not in ('', None)))
        return ' '.join(partes)
    return ''


def main(args):
    coletar = '--sem-coleta' not in args
    nova_versao, notas = None, []
    if '--versao' in args:
        i = args.index('--versao')
        nova_versao, notas = args[i + 1], args[i + 2:]

    etapa(1, 'Conferindo o catálogo e os arquivos das fontes manuais')
    problemas = conferir_manuais()
    if problemas:
        raise fontes.FonteError('Corrija antes de continuar:\n - ' + '\n - '.join(problemas))

    etapa(2, 'Coletando as fontes automáticas' if coletar else 'Usando a última coleta das fontes automáticas')
    import fluencia
    import escolas
    if coletar:
        print('   fluência em leitura (TCE-ES)…', flush=True)
        fluencia.coletar()
        print('   escolas e IDEB por escola (TCE-ES)…', flush=True)
        escolas.coletar()

    etapa(3, 'Recalculando os blocos')
    import build
    for nome, fn in build.BLOCOS.items():
        print('   ' + nome.replace('.json', ''), flush=True)
        fn()

    etapa(4, 'Conferindo totais e coberturas')
    import validar
    if not validar.main():
        raise fontes.FonteError('As checagens acima falharam. O painel não foi gerado. Veja as linhas marcadas com FALHA.')

    etapa(5, 'Gerando o relatório de conferência')
    import conferencia
    rel, mudancas, primeira = conferencia.gerar(fontes.resumo())
    print('   ' + ('primeira fotografia (base para as próximas comparações)' if primeira else f'{len(mudancas)} mudança(s) acima dos limites de atenção'))
    print(f'   relatório: {rel}')

    etapa(6, 'Registrando a versão e gerando o painel')
    vpath = os.path.join(APP, 'versao.json')
    with open(vpath, encoding='utf-8') as fh:
        ver = json.load(fh)
    hoje = dt.date.today().strftime('%d/%m/%Y')
    ver['dados_atualizados_em'] = hoje
    if nova_versao:
        if not notas:
            raise fontes.FonteError('Ao criar uma versão nova, escreva ao menos uma novidade entre aspas depois do número.')
        ver['versao'] = nova_versao
        ver['historico'].insert(0, {'versao': nova_versao, 'data': hoje, 'itens': notas})
    with open(vpath, 'w', encoding='utf-8') as fh:
        json.dump(ver, fh, ensure_ascii=False, indent=1)
    build.main(full=False)

    print(f'\nPronto. Versão {ver["versao"]}, dados de {hoje}.')
    print('Próximos passos: ler o relatório de conferência e publicar (Artifact no claude.ai e pasta publicar-github).')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    try:
        main(sys.argv[1:])
    except fontes.FonteError as e:
        print(f'\nATUALIZAÇÃO INTERROMPIDA\n{e}')
        sys.exit(1)
    except Exception:
        traceback.print_exc()
        print('\nATUALIZAÇÃO INTERROMPIDA por um erro inesperado (detalhes acima).')
        sys.exit(1)
