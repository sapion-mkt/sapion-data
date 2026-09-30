# Sapion Data — v1

Painel de dados educacionais dos 78 municípios do Espírito Santo para o time comercial da Sapion Nova Educação.

O resultado é um arquivo único, `dist/index.html`, com os dados embutidos, publicado como Artifact no claude.ai.

## Estrutura

```
sapion-data-app/
  pipeline/            scripts Python que leem as fontes da pasta "Sapion Data" e geram os dados
    common.py          chaves de município (IBGE), normalização de nomes, utilidades
    profissionais.py   Bloco 1 – folha TCE-ES + Censo Escolar (classificação de cargos)
    ideb.py            Bloco 2 – IDEB 2021/2023/2025 (Inep)
    alfabetizacao.py   Bloco 3 – Indicador Criança Alfabetizada (Inep/MEC)
    financiamento.py   Bloco 4 – Fundeb, VAAF, VAAT, VAAR, ICMS, IQE, saldo e perda
    execucao.py        execução da despesa em Educação (API Siconfi) – pronto, mas fora do painel na v1
    build.py           junta tudo e gera dist/index.html
    validar.py         confere os totais contra as fontes
  site/index.template.html   interface (HTML/CSS/JS, design system Sapion)
  data/                JSON intermediários + dicionario_cargos.csv (auditoria da classificação)
  dist/index.html      painel pronto para publicar
```

## Como atualizar

Requisitos: Python 3.12 com `pandas openpyxl python-calamine pdfplumber pyarrow httpx`.

1. Substitua ou acrescente o arquivo novo na pasta de fontes (ex.: novo `TCEES/vinculo-AAAA-T.csv`, novo mês em
   `Financiamento da Educação/Complementações do FUNDEB/2026/`, novo PDF da Sefaz). Se o nome do arquivo mudar,
   ajuste o caminho no módulo correspondente (constantes no topo de cada arquivo).
2. Rode, dentro de `pipeline/`:
   ```
   python build.py --full
   python validar.py
   ```
3. Republique `dist/index.html` no mesmo Artifact (mesmo link).
4. Para o GitHub: o `build.py` também recria a pasta `publicar-github/` (na raiz de "Sapion Data") com o
   `index.html` completo para o GitHub Pages (com `noindex`, fora dos buscadores) e o código em `sistema/`.
   No repositório, envie o novo `index.html` (Add file → Upload files) substituindo o anterior.
   Fontes brutas e o cache do pipeline (que contém nomes de servidores) nunca vão para essa pasta.

`build.py` sem `--full` reaproveita os JSON já calculados em `data/` (útil ao mexer só na interface).
O cache de downloads (Siconfi, lista VAAT) fica em `pipeline/.cache/`; apague um arquivo de lá para forçar nova coleta.

## Onde cada fonte entra

| Bloco | Arquivo/fonte | Frequência |
|---|---|---|
| Profissionais | `TCEES/vinculo-2026-2.csv` (dados.es.gov.br) + Sinopse do Censo Escolar 2025 | trimestral |
| IDEB | `IDEB/divulgacao_anos_*_municipios_2025` (Inep) | a cada 2 anos |
| Alfabetização | `Alfabetização/resultados_e_metas_municipios_2025_3.xlsx` (Inep/MEC) | anual (março) |
| Fundeb/VAAT/VAAR | CSVs mensais do Tesouro + `VAAR_ES_2026.xlsx` (lista FNDE e Portaria 11/2026) | mensal / portarias |
| Habilitação VAAT | lista final FNDE 2026 (baixada automaticamente) | anual |
| ICMS | PDFs mensais da Sefaz-ES, `IPM_2026_municipios_ES.xlsx`, `IQE_municipios_ES_reconstruido.xlsx` | mensal / anual |
| Execução (fora da v1) | API Siconfi, RREO Anexo 2 (completo ou simplificado) | bimestral (automático) |
| Logo | `Logo Sapion Data.png` (recortado e convertido para o tema escuro no build) | — |

## Estados

O painel já tem seletor de estado. Cada município leva a sigla da UF (`uf` no pacote de dados) e os estados do plano de
expansão ficam listados em `ESTADOS` no `build.py` (ativos = com dados). Para incluir um estado novo: criar as fontes
estaduais equivalentes (folha do tribunal de contas, repasses de ICMS, índice educacional do ICMS), gerar os blocos com
`uf` do estado e marcar o estado como ativo.

## Regras que merecem atenção

- **Estimativas** (selo "Estimativa Sapion" no painel): etapa dos professores sem etapa no cargo, IQE reconstruído,
  coeficiente do IQE, ICMS Educacional em R$, VAAR deixado na mesa, diferença do ICMS para a mediana.
  A metodologia completa está na aba "Metodologia e fontes" do painel.
- **Peso do IQE**: 12% no repasse de 2026 e 12,5% a partir de 2027 (`PESO_IQE_2026` em `financiamento.py`).
- **Classificação de cargos**: regras por nome em `profissionais.py` (`MUNI_RULES` para redes com nomenclatura
  própria). Revise `data/dicionario_cargos.csv` a cada atualização da folha.
