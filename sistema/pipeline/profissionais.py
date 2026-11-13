"""Bloco 1 — Profissionais da educação por município (folha TCE-ES + Censo Escolar).

Regras:
1. Competência = último mês do arquivo trimestral (folha declarada ao TCE-ES via CidadES).
2. Exclui Governo do Estado, consórcios, unidades gestoras que não são da educação
   (previdência, saúde, câmara...) e vínculos que não são quadro (estágio, pensão...).
3. Classifica cada cargo em: professor (com etapa), gestão pedagógica/escolar,
   outros profissionais (apoio) ou fora do escopo.
4. Professores cuja etapa o cargo não informa são repartidos entre as etapas possíveis
   na proporção dos docentes do Censo Escolar 2025 (rede municipal) — ESTIMATIVA.
"""
import os
import re
import sys

import pandas as pd
from python_calamine import CalamineWorkbook

from common import CACHE, norm, key, load_municipios, save_json, rnd
import fontes

UG_EXC = re.compile(r"PREVID|REGIME PROPRIO|FUNDO FINANCEIRO|FUNDO PREVIDENCI|FUNDO DE REPARTICAO|"
                    r"FUNDO EM CAPITALIZACAO|FACELI|FACULDADE|CAMARA|PROCURADORIA|CONTROLADORIA|FAZENDA|"
                    r"SAUDE|ASSISTENCIA SOCIAL|CENTRAL|SERVICO AUTONOMO|SAAE|AGUA E ESGOTO|HOSPITAL|"
                    r"CONSORCIO|INSTITUTO DE PREV|IPASC|TRANSITO|DEFESA SOCIAL|AGENCIA MUNICIPAL")
UG_EDU = re.compile(r"EDUCA|ENSINO|MAGISTERIO|FUNDEB")

VINC_EXC = {'Estágio', 'Função não remunerada', 'Regime jurídico complementação de aposentadoria',
            'Regime jurídico pensão especial', 'Residente', 'Voluntário militar', 'Membro de conselho',
            'Membro de Conselho Tutelar', 'Juiz Leigo', 'Examinador DETRAN', 'PRONATEC',
            'Adolescente aprendiz', 'Voluntário'}
EFETIVO = {'Efetivo estatutário', 'Emprego público', 'Cargo vitalício'}
DT = {'Contratação temporária', 'Contratação por Processo Seletivo Público (Lei 11.350/2006, EC 51/2006)'}

# ---------- regras de cargo (sobre o nome normalizado: maiúsculas, sem acento) ----------
R = lambda p: re.compile(p)

FORA = R(r"MOTORISTA|SERVICOS? GERAIS|LIMPEZA|MERENDEIR|COZINH|VIGIA|VIGILANTE|PORTEIRO|ZELADOR|OBRAS|"
         r"TRANSPORTE|CUIDADOR SOCIAL|EDUCADOR SOCIAL|ORIENTADOR SOCIAL|ASSISTENTE SOCIAL|NUTRICION|PSICOLOG|"
         r"FONOAUDIOL|ENFERM|MEDICO|DENTISTA|CONTADOR|ADVOGAD|ENGENHEIR|MECANIC|PEDREIRO|JARDINEIR|"
         r"OPERADOR SERV|OPERADOR DE SERV|AUXILIAR ADMINISTRATIVO|ASSISTENTE ADMINISTRATIVO|AGENTE ADMINISTRATIVO|"
         r"TECNICO DE NIVEL SUPERIOR|TECNICO NIVEL SUPERIOR|RECEPCION|TELEFONIST|DIGITADOR|ALMOXARIF")

GESTOR_KW = R(r"PEDAGOG(?!IA)|SUPERVIS|ORIENTADOR EDUC|ORIENTACAO EDUC|TECNICO PEDAG|TECNICA PEDAG|"
              r"FUNCAO PEDAG|FUNCAO TECNICO PEDAG|ASSESSORAMENTO PEDAG|ASSESSOR PEDAG|SUPORTE PEDAG|"
              r"COORDENADOR PEDAG|COORDENACAO PEDAG|ESPECIALISTA EM EDUC|ESPEC PEDAG|EDUCADOR ESPECIALISTA|"
              r"DIRETOR( A)? (ESCOLAR|DE ESCOLA|DE UNIDADE (DE )?ENSINO|DE UNIDADE ESCOLAR|DE CMEI|DE EMEF|DE CRECHE|"
              r"ESCOLA|EDUCACIONAL|EDU |UNIDADE EDUCACIONAL)|DIRETORA? ESCOLAR|VICE.?DIRETOR|DIRETOR ADJUNTO ESCOLAR|"
              r"GESTOR ESCOLAR|COORDENADOR( A)? (ESCOLAR|DE TURNO|TURNO|DE ESCOLA|DE CMEI|DE EMEF|DE ENSINO|DE AREA|"
              r"DE UNIDADE|EDUCACIONAL|DE PROJETOS EDUCACIONAIS)|COORD (ESCOLAR|DE TURNO)|COORDENADOR DE EDUCACAO|"
              r"SECRETARI[OA] MUNICIPAL DE EDUCACAO|SUBSECRETARI[OA] DE EDUCACAO|PROFISSIONAL DE EDUCACAO P$|"
              r"GERENTE EDUCACIONAL|ASSESSOR EDUCACIONAL$|TECNICO EDUCACIONAL")
GESTOR_CODE = R(r"\bMAPP\b|\bMAMPP\b|\bMMPP\b|\bMA ?PP\b|\bMAP P\b|\bPP\b|PROFESSOR P\b|PROFESSOR P ?2\b|"
                r"PROFESSOR P ?-|PEB ?-? ?IV\b|PROFISSIONAL DE EDUCACAO P$|P V TECNICO|DT MAPP")
GESTOR_EDU_UG = R(r"^COORDENADOR(A)?( -? ?DT| I+| [A-C]\d)?$|^DIRETOR(A)?$|^COORDENADOR DE SECAO$|^COORDENADOR TECNICO$")

EE = R(r"ESPECIAL(?!IZ|ISTA)|DEFICIEN|\bDEF\b|\bAEE\b|ATENDIMENTO EDUCACIONAL ESP|LIBRAS|BRAIL+E|SURD|CEGO|"
       r"INTELECTUAL|\bTEA\b|ALTAS HABILIDADES|BILINGUE|\bMAPEE\b|^MAPEE|SALA DE RECURSO|\bDV\b|\bDI\b|INCLUSIV")

APOIO_SEC = R(r"SECRETARI[OA]( A)? ESCOLAR|SECRETARIA ESCOLAR|AUX\.? ?SECRETARIA ESCOLAR|AUXILIAR DE SECRETARIA|"
              r"BIBLIOTEC|AUXILIAR DE BIBLIOTECA|ATENDENTE DE ESCOLA|INSPETOR DE ALUNO|INSPETOR ESCOLAR|"
              r"^SEC ESCOLAR|AUXSECESCOLAR")
APOIO = R(r"^AUX\.? ?PROF|AUXILIAR (DE )?(SALA|CRECHE|CLASSE|TURMA|EDUCA|ED |PROF|ATIVIDADES EDUC|SERVICOS EDUC|"
          r"APOIO DOCENTE|APOIO ESCOLAR|DESENVOLVIMENTO INFANTIL|BERCARIO|ENSINO|DOCENTE|CMEI|INCLUS)|"
          r"AUXILIAR DE SERVICOS? EDUCACIONA|AUXILIAR SERV\.? CENTRO EDUC|"
          r"ASSISTENTE (DE )?(EDUCA|APOIO ESCOLAR|APOIO EDUC|CMEI|CRECHE|SALA|TURNO|ALUNO|SERVICOS DE EDUCA|SERVICOS EDUCA|"
          r"PEDAG|ESCOLAR|ENSINO|DESENVOLVIMENTO INFANTIL)|ASSISTENTE EDUCACIONAL|ASSISTENTE AUXILIAR DE SALA|"
          r"CUIDADOR|MONITOR|PROFISSIONAL DE APOIO|AGENTE DE APOIO (EDUC|ESCOLAR|PEDAG)|AGENTE DE INCLUSAO|"
          r"AGENTE ESCOLAR|AGENTE EDUCACIONAL|BERCARISTA|ATENDENTE DE (CRECHE|CMEI|EDUCACAO)|INTERPRETE|TRADUTOR|"
          r"MEDIADOR|APOIO ESCOLAR|APOIO PEDAG|APOIO A INCLUS|ESTIMULADOR|RECREADOR|AGENTE DE SERVICO DA EDUCACAO|"
          r"ACOMPANHANTE (TERAPEUTICO|ESCOLAR|DE ALUNO)|PROFESSOR AUXILIAR|PORTADOR DE DEFICIENCIA|"
          r"AUXILIAR DE ATENDIMENTO EDUC|^ASS DE TURNO|INSTRUTOR DE (ATIVIDADES EDUC|MUSICA)")

PROF = R(r"^PROF(?!ISSIONAL)|PROFESSOR|PROFESSROR|DOCENTE|EDUCADOR D[AE] EDUCACAO BASICA|"
         r"PROFISSIONAL DE EDUCACAO [AB]$|PROFISSIONAL DO MAGISTERIO|SUPERIOR EM PEDAGOGIA|^DT MAP|"
         r"REGENTE|DINAMIZADOR|^MAPA|^MAPB|^MA PA|^MA PB|MAGISTERIO|^MAPEE")
PROF_NAO = R(r"AUXILIAR|ASSISTENTE|APOIO DOCENTE|AUX PROF|MONITOR|CUIDADOR|TECNICO NIVEL SUPERIOR")

# etapa do professor
EI_KW = R(r"INFANTIL|CRECHE|CMEI|PRE ESCOLA|PRE-ESCOLA|BERCARIO|MATERNAL|\bEI\b|ED INF|EDUC INF|EDUC\.INF")
AI_KW = R(r"ANOS INICIAIS|SERIES INICIAIS|SERIE INICIAIS|\bAI\b|1 ?O? AO 5|1 ?A A 5|1 A 5 ANO|EFI\b|ALFABETIZ|"
          r"MULTISSERI|ESCOLAS? DO CAMPO|PROFESSOR DO CAMPO|ANOS INI\b|ENS FUND ANOS INI|1O AO 5O")
AF_KW = R(r"ANOS FINAIS|SERIES FINAIS|\bAF\b|6 ?O? AO 9|6O AO 9O|INICIAIS E FINAIS|AO 0?9 ?O? ANO")
EF_KW = R(r"ENSINO FUNDAMENTAL|ENS ?\.? ?FUND|\bEF\b|FUNDAMENTAL")
DISC_AF = R(r"MATEMATIC|PORTUGUES|LINGUA|INGLES|ESPANHOL|HISTORIA|GEOGRAFIA|CIENCIAS|FILOSOFIA|BIOLOG|QUIMIC|"
            r"LINGUAGENS|CIENCIAS HUMANAS|AGROPECUAR")
DISC_MULTI = R(r"EDUCACAO FISICA|ED\.? FISICA|EDUC\.? FISICA|EDUCADOR FISICO|ARTE|ARTISTIC|MUSICA|RELIGIOSO|TECNOLOGIA|"
               r"INFORMATICA|DINAMIZADOR|EIXOS TEMATICOS|LITERATURA|LEITURA E ESCRITA|PROJETO|INTEGRAD|CONTRATURNO|"
               r"TEMPO INTEGRAL")
CODE_A = R(r"\bMAPA\d?\b|\bMA ?PA\b|\bMAP A\b|\bMAMPA\b|\bMAM ?PA\b|\bMMPA\b|\bMMAA\b|\bA1 PA\b|"
           r"PROFESSOR (\(A\) )?A\b|PROFESSOR A\d|PROFESSOR A V\b|PROFESSOR PA\b|\bPA\b|PROFISSIONAL DE EDUCACAO A$|"
           r"PROFESSOR NMM ?PA|PROFESSOR MA PA")
CODE_B = R(r"\bMAPB\d?\b|\bMA ?PB\b|\bMAP B\b|\bMAMPB\b|\bMAM ?PB\b|\bMMPB\b|PROFESSOR (\(A\) )?B\b|"
           r"PROFESSOR PB\b|\bPB\b|PROFISSIONAL DE EDUCACAO B$|PROFESSOR B ?PB")

# Regras específicas de município (nomenclatura própria de cada rede)
MUNI_RULES = {
    'VITORIA': [(R(r"PEB ?-? ?IV\b"), 'gestor'), (R(r"PEB ?-? ?III\b.*DINAMIZADOR"), 'EI_AI_AF'),
                (R(r"PEB ?-? ?III\b"), 'AF'), (R(r"PEB ?-? ?II\b"), 'AI'), (R(r"PEB ?-? ?I\b"), 'EI')],
    'VIANA': [(R(r"PEB I\)|\(PEB I\b"), 'EI')],
    'CACHOEIRO DE ITAPEMIRIM': [(R(r"PEB C\b"), 'AF')],
    # Ibatiba não tem cargo de Educação Infantil: o PEB (AI) atende EI e anos iniciais
    'IBATIBA': [(R(r"PEB ?\(?AI\b"), 'EI_AI')],
    'COLATINA': [(R(r"\bMARC|\bMRAC"), 'EI_AI_AF'), (R(r"DOCENTE II\b|\bD ?T ?II\b"), 'AF')],
}


def classify(cargo, ug, muni_key):
    """Retorna (classe, etapa). classe ∈ professor|gestor|apoio|secretaria|fora."""
    c = norm(cargo)
    edu_ug = bool(UG_EDU.search(norm(ug)))
    if not c:
        return 'fora', None
    for rx, et in MUNI_RULES.get(muni_key, []):
        if rx.search(c):
            if et == 'gestor':
                return 'gestor', None
            if EE.search(c):
                return 'professor', 'EE'
            return 'professor', et
    if GESTOR_KW.search(c) and not PROF_NAO.search(c):
        return 'gestor', None
    if edu_ug and GESTOR_EDU_UG.search(c):
        return 'gestor', None
    if FORA.search(c):
        return 'fora', None
    if APOIO_SEC.search(c) and (edu_ug or 'ESCOLA' in c):
        return 'secretaria', None
    is_prof = bool(PROF.search(c)) and not PROF_NAO.search(c)
    if c == 'EDUCADOR FISICO' and not edu_ug:
        return 'fora', None
    if APOIO.search(c) and (not is_prof or c.startswith('PROFESSOR AUXILIAR')):
        return 'apoio', None
    if not is_prof and edu_ug and re.search(r"EDUCADOR FISICO", c):
        is_prof = True
    if not is_prof:
        return 'fora', None
    if EE.search(c):
        return 'professor', 'EE'
    if GESTOR_CODE.search(c) and 'DOCENTE' not in c:
        return 'gestor', None
    return 'professor', etapa_prof(c)


def etapa_prof(c):
    ei, ai, af = bool(EI_KW.search(c)), bool(AI_KW.search(c)), bool(AF_KW.search(c))
    if ei and (af or (EF_KW.search(c) and not ai)):
        return 'EI_AI_AF'
    if ei and ai:
        return 'EI_AI'
    if ai and af:
        return 'AI_AF'
    if ei:
        return 'EI'
    if ai:
        return 'AI'
    if af:
        return 'AF'
    if DISC_MULTI.search(c):
        return 'EI_AI_AF'
    if DISC_AF.search(c):
        return 'AF'
    if EF_KW.search(c):
        return 'AI_AF'
    if CODE_B.search(c):
        return 'AF'
    if CODE_A.search(c):
        return 'EI_AI'
    return 'EI_AI_AF'


# ---------------------------------------------------------------------------------------
def load_vinculos():
    vinc_file = fontes.arquivo('tcees-vinculo')
    cache = os.path.join(CACHE, os.path.basename(vinc_file).replace('.csv', '.parquet'))
    if os.path.exists(cache) and os.path.getmtime(cache) > os.path.getmtime(vinc_file):
        return pd.read_parquet(cache)
    df = pd.read_csv(vinc_file, sep=';', encoding='latin-1', dtype=str)
    df.to_parquet(cache)
    return df


def load_censo():
    """Docentes em regência na rede municipal (Censo 2025): total, EI, AI, AF."""
    sinopse = fontes.arquivo('inep-sinopse-censo')
    cache = os.path.join(CACHE, f"censo_docentes_{fontes.referencia('inep-sinopse-censo')}.parquet")
    if os.path.exists(cache):
        return pd.read_parquet(cache)
    wb = CalamineWorkbook.from_path(sinopse)
    tabs = {'total': '2.2', 'EI': 'Educação Infantil 2.7', 'AI': 'Anos Iniciais 2.26', 'AF': 'Anos Finais 2.31'}
    out = {}
    for k, sheet in tabs.items():
        for r in wb.get_sheet_by_name(sheet).to_python():
            if len(r) > 8 and str(r[1]).strip() == 'Espírito Santo' and isinstance(r[3], float):
                out.setdefault(str(int(r[3])), {})[k] = int(r[8] or 0)
    # situação funcional (2.6): efetivos e temporários na rede municipal
    for r in wb.get_sheet_by_name('2.6').to_python():
        if len(r) > 8 and str(r[1]).strip() == 'Espírito Santo' and isinstance(r[3], float):
            out[str(int(r[3]))]['efetivo'] = int(r[8] or 0)
            out[str(int(r[3]))]['temporario'] = int(r[12] or 0)
    df = pd.DataFrame.from_dict(out, orient='index').reset_index().rename(columns={'index': 'ibge'})
    df.to_parquet(cache)
    return df


SPLIT = {'EI_AI': ['EI', 'AI'], 'AI_AF': ['AI', 'AF'], 'EI_AI_AF': ['EI', 'AI', 'AF']}


def build(diagnose=False):
    mun = load_municipios()
    df = load_vinculos()
    comp_mes = df['MesReferencia'].astype(int).max()
    comp_ano = int(df['AnoReferencia'].iloc[0])
    df = df[df['MesReferencia'].astype(int) == comp_mes].copy()
    df['mkey'] = df['Município'].map(key)
    df = df[df['mkey'].isin(set(mun['key']))]
    df['ugn'] = df['NomeUnidadeGestora'].map(norm)
    df = df[~df['ugn'].str.contains(UG_EXC)]
    df = df[~df['TipoVinculo'].isin(VINC_EXC)]
    df['pessoa'] = df['NomeServidor'].map(norm) + '|' + df['CPFServidor'].fillna('')
    df['vinc'] = df['TipoVinculo'].map(lambda t: 'efetivo' if t in EFETIVO else ('dt' if t in DT else 'outro'))

    combos = df[['NomeCargo', 'NomeUnidadeGestora', 'mkey']].drop_duplicates()
    res = combos.apply(lambda r: classify(r['NomeCargo'], r['NomeUnidadeGestora'], r['mkey']), axis=1)
    combos['classe'] = [x[0] for x in res]
    combos['etapa'] = [x[1] for x in res]
    df = df.merge(combos, on=['NomeCargo', 'NomeUnidadeGestora', 'mkey'], how='left')
    edu = df[df['classe'] != 'fora'].copy()

    if diagnose:
        return df, edu, combos

    censo = load_censo().set_index('ibge')
    out = {}
    for _, m in mun.iterrows():
        e = edu[edu['mkey'] == m['key']]
        c = censo.loc[m['ibge']] if m['ibge'] in censo.index else None
        rec = summarize(e, c)
        rec['censo'] = None if c is None else {k: int(c[k]) for k in ['total', 'EI', 'AI', 'AF', 'efetivo', 'temporario']}
        out[m['ibge']] = rec

    # tiers de porte (critério Felipe: vínculos de magistério = professores + gestão pedagógica)
    for ib, r in out.items():
        v = r['magisterio']['vinculos']
        r['tier'] = 'Mais de 500' if v > 500 else ('200 a 500' if v >= 200 else 'Menos de 200')

    meta = {'competencia': f'{comp_mes:02d}/{comp_ano}', 'fonte': 'TCE-ES / CidadES – arquivo Vínculo 2026, 2º trimestre',
            'censo': 'Censo Escolar 2025 (Inep), Sinopse Estatística – docentes em regência, rede municipal'}
    save_json('profissionais.json', {'meta': meta, 'municipios': out})
    cargos = (edu.groupby(['mkey', 'NomeCargo', 'classe', 'etapa'], dropna=False)
              .agg(vinculos=('pessoa', 'size'), pessoas=('pessoa', 'nunique')).reset_index())
    cargos.to_csv(os.path.join(os.path.dirname(__file__), '..', 'data', 'dicionario_cargos.csv'),
                  index=False, encoding='utf-8-sig')
    return out


def _counts(g):
    """pessoas e vínculos, total e por tipo de vínculo."""
    r = {'pessoas': int(g['pessoa'].nunique()), 'vinculos': int(len(g))}
    for v in ['efetivo', 'dt', 'outro']:
        r[v] = int(g.loc[g['vinc'] == v, 'pessoa'].nunique())
    return r


def summarize(e, c):
    prof = e[e['classe'] == 'professor']
    ges = e[e['classe'] == 'gestor']
    apo = e[e['classe'].isin(['apoio', 'secretaria'])]
    mag = e[e['classe'].isin(['professor', 'gestor'])]

    # etapas identificadas pelo cargo
    ident = {k: _counts(prof[prof['etapa'] == k]) for k in ['EI', 'AI', 'AF', 'EE']}
    # grupos a repartir pelo Censo
    shares = {}
    if c is not None:
        tot = {k: max(int(c[k]), 0) for k in ['EI', 'AI', 'AF']}
    else:
        tot = {'EI': 1, 'AI': 1, 'AF': 1}
    etapas = {k: {f: float(ident[k][f]) for f in ['pessoas', 'efetivo', 'dt', 'outro']} for k in ['EI', 'AI', 'AF']}
    for k in etapas:
        etapas[k]['identificado'] = ident[k]['pessoas']
        etapas[k]['estimado'] = 0.0
    nao_ident = {}
    for grp, alvo in SPLIT.items():
        g = prof[prof['etapa'] == grp]
        if g.empty:
            continue
        cg = _counts(g)
        nao_ident[grp] = cg['pessoas']
        base = sum(tot[a] for a in alvo) or len(alvo)
        for a in alvo:
            w = (tot[a] / base) if sum(tot[x] for x in alvo) else 1 / len(alvo)
            for f in ['pessoas', 'efetivo', 'dt', 'outro']:
                etapas[a][f] += cg[f] * w
            etapas[a]['estimado'] += cg['pessoas'] * w
    for k in etapas:
        for f in list(etapas[k]):
            etapas[k][f] = rnd(etapas[k][f], 1)

    # sinalizadores de qualidade do dado declarado
    flags = []
    n_prof = max(len(prof), 1)
    sem = sum(nao_ident.values())
    if prof['pessoa'].nunique() and sem / prof['pessoa'].nunique() > 0.4:
        flags.append(f"{sem / prof['pessoa'].nunique():.0%} dos professores têm cargo sem etapa na folha; "
                     "a divisão por etapa desses é estimada pelo Censo.")
    ep = (mag['TipoVinculo'] == 'Emprego público').sum()
    if len(mag) and ep / len(mag) > 0.2:
        flags.append('O município declara parte do magistério como "emprego público" (tratado como efetivo).')
    com = (prof['vinc'] == 'outro').sum()
    if com / n_prof > 0.1:
        flags.append(f'{com} vínculos de professor declarados como comissionado/eletivo/outros (fora de efetivo e DT).')
    if len(e) and not e['ugn'].str.contains(UG_EDU).any():
        flags.append('A folha é lançada toda na Prefeitura (sem unidade da Educação): coordenadores e cargos '
                     'genéricos não podem ser atribuídos à Educação.')
    if len(prof) == 0:
        flags.append('Nenhum cargo de professor identificado na folha deste mês.')

    return {
        'flags': flags,
        'total': _counts(e),
        'magisterio': _counts(mag),
        'professores': _counts(prof),
        'etapas': etapas,
        'educacao_especial': ident['EE'],
        'gestores': _counts(ges),
        'outros': _counts(apo),
        'outros_detalhe': {'apoio': _counts(e[e['classe'] == 'apoio']),
                           'secretaria': _counts(e[e['classe'] == 'secretaria'])},
        'sem_etapa_pessoas': int(sum(nao_ident.values())),
        'sem_etapa_grupos': nao_ident,
    }


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    build()
    print('ok')
