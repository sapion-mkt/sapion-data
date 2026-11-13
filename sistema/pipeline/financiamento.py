"""Bloco 4 — Financiamento: Fundeb (VAAF/redistribuição, VAAT, VAAR), ICMS Educacional, saldo e perda.

Camadas:
  OFICIAL   – transferências do Tesouro (FNDE/STN), lista FNDE de habilitação ao VAAR, Portaria 11/2026,
              PDFs mensais da Sefaz-ES, IPM 2026 (Decreto 6.276-R).
  ESTIMADO  – IQE reconstruído, coeficiente do IQE, ICMS Educacional em R$, valores deixados na mesa.
"""
import glob
import os
import re
import sys

import pandas as pd
import pdfplumber

from common import key, brl, load_municipios, save_json, rnd
import fontes
MESES = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro',
         'outubro', 'novembro', 'dezembro']
ORIGENS = ['FPE', 'FPM', 'ICMS', 'IPI-EXP', 'IPVA', 'ITCMD', 'ITR']
PESO_IQE_2026 = 0.12  # Guia Técnico do IQE (Sedu), Tabela 1: repasse 2026 = 12%


# ---------------------------------------------------------------- Fundeb (Tesouro/FNDE)
def rubrica(t):
    t = t.replace('FUNDEB - ', '').replace('FUNDEB - ', '').strip()
    return {'COUN VAAR': 'VAAR', 'COUN VAAT': 'VAAT', 'COUN VAAF': 'VAAF'}.get(t, t)


def read_fundeb_csv(path):
    df = pd.read_csv(path, sep=';', encoding='latin-1', dtype=str)
    df['rub'] = df['Transferência'].map(rubrica)
    df['valor'] = df['Valor Consolidado'].map(brl)
    return df.pivot_table(index='Código IBGE', columns='rub', values='valor', aggfunc='sum', fill_value=0.0)


def load_fundeb():
    mensal = {}
    por_nome = {os.path.splitext(os.path.basename(p))[0].lower(): p for p in fontes.arquivos('tesouro-fundeb-mensal')}
    for i, m in enumerate(MESES, start=1):
        if m in por_nome:
            mensal[i] = read_fundeb_csv(por_nome[m])
    desconhecidos = set(por_nome) - set(MESES)
    if desconhecidos:
        raise fontes.FonteError(f'tesouro-fundeb-mensal: arquivos com nome fora do padrão <mês>.csv: {sorted(desconhecidos)}')
    ano_anterior = read_fundeb_csv(fontes.arquivo('tesouro-fundeb-anual'))
    return mensal, ano_anterior


# ---------------------------------------------------------------- Lista FNDE VAAR + Portaria 11
def load_vaar_sheet():
    path = fontes.arquivo('sapion-vaar-condicionalidades')
    df = pd.read_excel(path, sheet_name=os.path.splitext(os.path.basename(path))[0],
                       engine='calamine', dtype={'Código IBGE': str})
    df['ibge'] = df['Código IBGE'].str[:7]
    return df.set_index('ibge')


VAAT_URL = ('https://www.gov.br/fnde/pt-br/acesso-a-informacao/acoes-e-programas/financiamento/fundeb/vaat/'
            'lista-dos-entes-habilitados-e-inabilitados-ao-vaat-2026-posicao-final-com-ajuste-de-decisao-judicial-edit-csv.csv')


def load_vaat_habilitacao():
    """Lista final FNDE de entes habilitados/inabilitados ao cálculo do VAAT 2026 (cache local)."""
    path = fontes.arquivo('fnde-vaat-habilitacao')
    raw = open(path, 'rb').read()
    try:
        txt = raw.decode('utf-8')
    except UnicodeDecodeError:
        txt = raw.decode('latin-1')
    out = {}
    for line in txt.splitlines():
        p = line.split(';')
        if len(p) > 4 and p[0] == 'ES' and len(p[2]) == 7:
            out[p[2]] = {'status': p[3].strip(), 'pendencia': p[4].strip() or None}
    return out


# ---------------------------------------------------------------- ICMS (PDFs Sefaz)
NUM = re.compile(r'^-?[\d.]+,\d{2}$|^-$')
IDX = re.compile(r'^\d+,\d{3}$')


def parse_icms_pdf(path):
    with pdfplumber.open(path) as pdf:
        text = pdf.pages[0].extract_text()
    rows, total = {}, None
    for line in text.splitlines():
        tok = line.split()
        pos = next((i for i, t in enumerate(tok) if IDX.match(t)), None)
        if pos is None or pos == 0:
            if tok and tok[0].upper() == 'TOTAL':
                nums = [t for t in tok[1:] if NUM.match(t)]
                if len(nums) >= 3:
                    total = [brl(x) if x != '-' else 0.0 for x in nums[:3]]
            continue
        nums = tok[pos + 1:]
        if len(nums) < 3 or not all(NUM.match(x) for x in nums[:3]):
            continue
        name = ' '.join(tok[:pos])
        vals = [brl(x) if x != '-' else 0.0 for x in nums]
        rows[key(name)] = {'indice': float(tok[pos].replace(',', '.')), 'bruto': vals[0], 'fundeb': vals[1],
                           'liquido': vals[2], 'ipva_bruto': vals[3] if len(vals) > 3 else None}
    return rows, total


def load_icms():
    out = {}
    for f in fontes.arquivos('sefaz-icms-repasses'):
        mes = next(i for i, m in enumerate(MESES, start=1) if m.upper() in f.upper())
        rows, total = parse_icms_pdf(f)
        out[mes] = (rows, total)
    return dict(sorted(out.items()))


def load_ipm():
    df = pd.read_excel(fontes.arquivo('sefaz-ipm'), engine='calamine')
    df = df[pd.to_numeric(df['Posição'], errors='coerce').notna()]
    return {key(r['Município']): {'ipm': float(r['IPM 2026 (%)']), 'cod_sefaz': str(r['Código']),
                                  'posicao': int(r['Posição'])} for _, r in df.iterrows()}


def load_iqe():
    df = pd.read_excel(fontes.arquivo('sapion-iqe-reconstruido'), sheet_name='IQE',
                       engine='calamine')
    df = df[pd.to_numeric(df['Código IBGE'], errors='coerce').notna()]
    df['ibge'] = df['Código IBGE'].astype(int).astype(str)
    cols = {'IQ2 (2º ano)': 'iq2', 'IQ5 (5º ano)': 'iq5', 'IQEF (70%)': 'iqef', 'P – taxa de aprovação (15%)': 'p',
            'IMEG – equidade (15%)': 'imeg', 'IQE': 'iqe', 'Posição (1 = maior)': 'posicao'}
    return df.rename(columns=cols).set_index('ibge')[list(cols.values())]


# ---------------------------------------------------------------- build
def build():
    mun = load_municipios()
    mensal, a2025 = load_fundeb()
    vs = load_vaar_sheet()
    icms = load_icms()
    ipm = load_ipm()
    iqe = load_iqe()
    hab_vaat = load_vaat_habilitacao()

    meses_vaar = [m for m in mensal if mensal[m].get('VAAR', pd.Series(dtype=float)).sum() > 0]
    ult_vaar = max(meses_vaar)  # último mês com crédito de complementação
    meses_base = [m for m in mensal if m <= ult_vaar]

    def fb(m, ib, rub):
        t = mensal[m]
        return float(t.loc[ib, rub]) if (ib in t.index and rub in t.columns) else 0.0

    # ---------- VAAR: calibração da estimativa "deixado na mesa"
    base = {ib: sum(fb(m, ib, o) for m in meses_base for o in ORIGENS) for ib in mun['ibge']}
    prev = {ib: float(vs.loc[ib, 'VAAR previsto p/ 2026 – Portaria 11 (R$, 13 parcelas)'] or 0) for ib in mun['ibge']}
    receb_vaar = {ib: sum(fb(m, ib, 'VAAR') for m in meses_base) for ib in mun['ibge']}
    recebe = {ib: vs.loc[ib, 'Situação VAAR 2026'] == 'Recebe' for ib in mun['ibge']}
    n_ind = {ib: (2 if str(vs.loc[ib, 'Indicadores evoluídos']).startswith('2') else 1) for ib in mun['ibge']}

    def kgroup(g, excl=None):
        ibs = [ib for ib in mun['ibge'] if recebe[ib] and n_ind[ib] == g and ib != excl]
        return sum(prev[i] for i in ibs) / sum(base[i] for i in ibs)

    k = {2: kgroup(2), 1: kgroup(1)}
    frac = sum(receb_vaar[i] for i in mun['ibge'] if recebe[i]) / sum(prev[i] for i in mun['ibge'] if recebe[i])
    # validação leave-one-out entre os beneficiários
    errs = []
    for ib in mun['ibge']:
        if recebe[ib] and prev[ib] > 0:
            est = base[ib] * kgroup(n_ind[ib], excl=ib)
            errs.append(abs(est / prev[ib] - 1))
    errs.sort()
    loo = {'mae': sum(errs) / len(errs), 'p90': errs[int(0.9 * (len(errs) - 1))], 'max': errs[-1], 'n': len(errs)}
    faixa = round(loo['p90'], 2)

    # ---------- ICMS: coeficiente estimado do IQE e ICMS Educacional
    soma_iqe = float(iqe['iqe'].sum())
    coef = {ib: float(iqe.loc[ib, 'iqe']) / soma_iqe for ib in iqe.index}
    coefs = sorted(coef.values())
    coef_med = (coefs[38] + coefs[39]) / 2  # mediana dos 78
    icms_tot = {m: (tot[0] if tot else sum(r['bruto'] for r in rows.values())) for m, (rows, tot) in icms.items()}
    meses_icms = list(icms_tot)
    bolo_educ = {m: v * PESO_IQE_2026 for m, v in icms_tot.items()}

    # ---------- por município
    out = {}
    for _, mu in mun.iterrows():
        ib, kk = mu['ibge'], mu['key']
        r = vs.loc[ib]
        # Fundeb mensal 2026
        fundeb_mes = {}
        for m in mensal:
            fundeb_mes[str(m)] = {
                'redistribuicao': rnd(sum(fb(m, ib, o) for o in ORIGENS)),
                'origens': {o: rnd(fb(m, ib, o)) for o in ORIGENS},
                'fti': rnd(fb(m, ib, 'FTI')),
                'VAAT': rnd(fb(m, ib, 'VAAT')), 'VAAR': rnd(fb(m, ib, 'VAAR')), 'VAAF': rnd(fb(m, ib, 'VAAF'))}
        def a25(rub):
            return float(a2025.loc[ib, rub]) if (ib in a2025.index and rub in a2025.columns) else 0.0
        conds = {c: str(r[col]) for c, col in zip(['I', 'II', 'III', 'IV', 'V'],
                 ['Cond. I (gestor escolar)', 'Cond. II (80% Saeb)', 'Cond. III (desigualdades)',
                  'Cond. IV (regime colab.)', 'Cond. V (currículo BNCC)'])}
        est_anual = 0.0 if recebe[ib] else base[ib] * k[n_ind[ib]]
        est_parcial = est_anual * frac
        vaar = {
            'situacao': r['Situação VAAR 2026'],
            'condicionalidades': conds,
            'descumpridas': None if str(r['Condicionantes descumpridas']) in ('—', 'nan') else str(r['Condicionantes descumpridas']),
            'motivo': str(r['Motivo (lista FNDE)']),
            'evoluiu_atendimento': str(r['Evoluiu indicador de atendimento?']),
            'evoluiu_aprendizagem': str(r['Evoluiu indicador de aprendizagem?']),
            'recebido_2025': rnd(a25('VAAR')),
            'recebeu_2025': str(r['Recebeu VAAR em 2025?']),
            'recebido_2026': rnd(receb_vaar[ib]),
            'previsto_2026': rnd(prev[ib]),
            'perda_estimada_anual': rnd(est_anual, 0),
            'perda_estimada_parcial': rnd(est_parcial, 0),
            'perda_faixa': [rnd(est_anual * (1 - faixa), 0), rnd(est_anual * (1 + faixa), 0)] if est_anual else None,
            # insumos da conta, para a ficha explicar o cálculo com os números do próprio município
            'base_fundeb': rnd(base[ib]),
            'indicadores_evoluidos': n_ind[ib],
            'k_aplicado': k[n_ind[ib]],
        }
        vaat_prev = float(r['VAAT previsto p/ 2026 – Portaria 11 (R$, 13 parcelas)'] or 0)
        vaat = {'recebido_2025': rnd(a25('VAAT')), 'recebido_2026': rnd(sum(fb(m, ib, 'VAAT') for m in meses_base)),
                'previsto_2026': rnd(vaat_prev), 'recebe': vaat_prev > 0,
                'habilitacao': hab_vaat.get(ib, {}).get('status'),
                'pendencia': hab_vaat.get(ib, {}).get('pendencia'),
                'habilitado': 'Habilitado' in (hab_vaat.get(ib, {}).get('status') or '')}
        redist_2026 = sum(fb(m, ib, o) for m in mensal for o in ORIGENS)
        vaaf = {'recebe_complementacao': False, 'redistribuicao_2026': rnd(redist_2026),
                'redistribuicao_2025': rnd(sum(a25(o) for o in ORIGENS)),
                'fti_2026': rnd(sum(fb(m, ib, 'FTI') for m in mensal)), 'fti_2025': rnd(a25('FTI'))}

        # ICMS
        ip = ipm.get(kk)
        icms_mes = {}
        for m, (rows, tot) in icms.items():
            x = rows.get(kk)
            icms_mes[str(m)] = None if x is None else {k2: rnd(v) for k2, v in x.items()}
        c = coef.get(ib)
        educ_mes = {str(m): rnd(bolo_educ[m] * c, 0) for m in meses_icms} if c else None
        educ_acum = sum(bolo_educ[m] * c for m in meses_icms) if c else None
        perda_icms = (coef_med - c) * sum(bolo_educ.values()) if c else None
        bruto_acum = sum((icms_mes[str(m)] or {}).get('bruto') or 0 for m in meses_icms)
        iq = iqe.loc[ib] if ib in iqe.index else None
        icms_rec = {
            'ipm_2026': ip['ipm'] if ip else None, 'ipm_posicao': ip['posicao'] if ip else None,
            'cod_sefaz': ip['cod_sefaz'] if ip else None,
            'mensal': icms_mes,
            'bruto_acumulado': rnd(bruto_acum), 'liquido_acumulado': rnd(sum((icms_mes[str(m)] or {}).get('liquido') or 0 for m in meses_icms)),
            'iqe': None if iq is None else {k2: (int(iq[k2]) if k2 == 'posicao' else rnd(iq[k2], 4)) for k2 in iq.index},
            'coef_iqe_estimado': rnd(c, 6) if c else None,
            'contribuicao_ipm_pp': rnd(c * PESO_IQE_2026 * 100, 4) if c else None,
            'icms_educ_mensal_estimado': educ_mes,
            'icms_educ_acumulado_estimado': rnd(educ_acum, 0),
            'dependencia_estimada': rnd((c * PESO_IQE_2026) / ip['ipm'], 4) if (c and ip) else None,
            'diferenca_mediana_estimada': rnd(-perda_icms, 0) if perda_icms is not None else None,
        }
        # saldo x perda (mesmos períodos por mecanismo)
        saldo = {
            'vaar_recebido': vaar['recebido_2026'], 'vaar_perda': rnd(est_parcial, 0),
            'vaat_recebido': vaat['recebido_2026'],
            'icms_educ_recebido': icms_rec['icms_educ_acumulado_estimado'],
            'icms_educ_perda': rnd(max(perda_icms, 0), 0) if perda_icms is not None else None,
        }
        saldo['total_recebido'] = rnd(sum(v or 0 for v in [saldo['vaar_recebido'], saldo['vaat_recebido'], saldo['icms_educ_recebido']]), 0)
        saldo['total_perda'] = rnd((saldo['vaar_perda'] or 0) + (saldo['icms_educ_perda'] or 0), 0)
        out[ib] = {'fundeb_mensal': fundeb_mes, 'vaar': vaar, 'vaat': vaat, 'vaaf': vaaf, 'icms': icms_rec, 'saldo': saldo}

    # ---------- rankings estaduais úteis
    def rk(vals, rev=True):
        return {ib: (None if v is None else 1 + sum(1 for x in vals.values() if x is not None and (x > v if rev else x < v)))
                for ib, v in vals.items()}
    for name, f in {'perda_vaar': lambda o: o['vaar']['perda_estimada_anual'] or None,
                    'vaar_recebido': lambda o: o['vaar']['recebido_2026'] or None,
                    'vaat_recebido': lambda o: o['vaat']['recebido_2026'] or None}.items():
        r_ = rk({ib: f(o) for ib, o in out.items()})
        for ib in out:
            out[ib].setdefault('rankings', {})[name] = r_[ib]

    meta = {
        'fundeb': {'fonte': 'Tesouro Nacional/FNDE – Consultas Fundeb, transferências por município e origem',
                   'meses_2026': sorted(mensal), 'ultimo_mes_complementacao': ult_vaar,
                   'nota': 'Setembro/2026 ainda sem créditos de VAAT e VAAR.'},
        'vaar': {'fonte_situacao': 'FNDE – Lista de entes beneficiários/não beneficiários VAAR 2026; Portaria Interministerial MEC/MF nº 11/2026 (Anexo VI)',
                 'n_recebem': sum(recebe.values()), 'n_nao_recebem': 78 - sum(recebe.values()),
                 'n_recebem_2ind': sum(1 for i in mun['ibge'] if recebe[i] and n_ind[i] == 2),
                 'k_2_indicadores': k[2], 'k_1_indicador': k[1], 'fracao_ano_creditada': frac,
                 'validacao_loo': loo, 'faixa': faixa,
                 'bolo_nacional_2026': 7598794714.82,
                 'versao_metodo': 'VAAR-perda v1.0 (29/09/2026)'},
        'vaat': {'fonte': 'Portaria 11/2026 (Anexo V) e Tesouro; habilitação: FNDE, lista final VAAT 2026 (posição com ajuste de decisão judicial)',
                 'vaat_min_2026': 10192.38, 'url_habilitacao': VAAT_URL},
        'vaaf': {'vaaf_min_2026': 6030.44, 'nota': 'O ES não está entre as 9 UFs que recebem complementação VAAF em 2026.'},
        'icms': {'fonte': 'Sefaz-ES – Distribuição de tributos estaduais (ICMS 25%) às prefeituras, PDFs mensais',
                 'meses': meses_icms, 'total_bruto_mensal': {str(m): rnd(v) for m, v in icms_tot.items()},
                 'peso_iqe': PESO_IQE_2026, 'soma_iqe': soma_iqe, 'coef_mediana': coef_med,
                 'iqe_mediano': coef_med * soma_iqe, 'bolo_educ_periodo': sum(bolo_educ.values()),
                 'icms_educ_mediano_periodo': coef_med * sum(bolo_educ.values()),
                 'fonte_ipm': 'Decreto nº 6.276-R/2025 (IPM definitivo 2026)',
                 'fonte_iqe': 'Reconstrução Sapion da metodologia do Guia Técnico do IQE (Sedu/ABC), ciclo IQE 2025 → repasse 2026',
                 'versao_metodo': 'ICMS-Educ v1.0 (29/09/2026)'},
    }
    save_json('financiamento.json', {'meta': meta, 'municipios': out})
    return out, meta


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    o, m = build()
    print(m['vaar'])
    print({k: v for k, v in m['icms'].items() if k != 'total_bruto_mensal'})
    print(m['icms']['total_bruto_mensal'])
    miss = [ib for ib, x in o.items() if any(v is None for v in x['icms']['mensal'].values())]
    print('ICMS sem match:', miss)
    s = lambda f: sum(f(x) or 0 for x in o.values())
    print('perda VAAR anual', s(lambda x: x['vaar']['perda_estimada_anual']), 'parcial', s(lambda x: x['vaar']['perda_estimada_parcial']))
    print('ICMS educ acumulado', s(lambda x: x['icms']['icms_educ_acumulado_estimado']))
