# Sapion Data — sistema

Painel de dados educacionais por município para o time comercial da Sapion Nova Educação (versão 1: Espírito Santo).
O resultado é um arquivo único, `dist/index.html`, com os dados embutidos, publicado como Artifact no claude.ai e
no GitHub Pages (pasta `publicar-github/`).

**Para atualizar dados ou incluir um indicador novo, siga o [Padrão de atualização](PADRAO-DE-ATUALIZACAO.md).**

## Estrutura

```
Sapion Data/
  Fontes/                       fontes de dados (originais) + catalogo_fontes.xlsx + _modelos
  Atualizar Sapion Data.bat     atalho para a atualização completa
  publicar-github/              gerado: index.html para o GitHub Pages + cópia do sistema
  sapion-data-app/
    versao.json                 versão em uso, data dos dados e histórico de novidades
    PADRAO-DE-ATUALIZACAO.md
    pipeline/
      atualizar.py              atualização completa (conferência → coleta → cálculo → checagens → relatório → painel)
      fontes.py                 acesso às fontes pelo catálogo (nenhum caminho fixo no código)
      tcees_powerbi.py          consulta ao painel de Educação do TCE-ES (Power BI público)
      profissionais.py          bloco 1 – folha TCE-ES + Censo (classificação de cargos)
      ideb.py                   bloco 2 – IDEB por município
      alfabetizacao.py          bloco 3 – Indicador Criança Alfabetizada
      fluencia.py               bloco 3 – Avaliação da Fluência em Leitura (ES)
      financiamento.py          bloco 4 – Fundeb, VAAF, VAAT, VAAR, ICMS, IQE, saldo e perda
      escolas.py                bloco 5 – escolas municipais e estaduais, IDEB e fluência por escola
      validar.py                checagens contra as fontes oficiais
      conferencia.py            fotografia dos indicadores e relatório do que mudou
      build.py                  junta os blocos e gera o painel e a pasta do GitHub
      criar_catalogo.py         recria o catálogo do zero (só para restaurar o modelo)
      criar_modelos.py          recria os modelos de Fontes/_modelos
      execucao.py               execução da despesa (Siconfi) – pronto, fora do painel por enquanto
    site/index.template.html    interface (HTML/CSS/JS, design system Sapion)
    data/                       resultados intermediários por bloco + dicionario_cargos.csv
    historico/                  fotografias de cada atualização (base do relatório de conferência)
    relatorios/                 relatórios de conferência
    dist/index.html             painel pronto para publicar
```

## Comandos

Requisitos: Python 3.12 com `pandas openpyxl python-calamine pdfplumber pyarrow httpx pillow numpy`.

Dentro de `pipeline/`:

```
python atualizar.py                 # atualização completa de dados
python atualizar.py --sem-coleta    # idem, sem consultar o TCE-ES (usa a última coleta)
python atualizar.py --versao 1.2 "Novidade 1" "Novidade 2"
python build.py                     # só regera o painel (ao mexer na interface)
python validar.py                   # só as checagens
```

O cache de leitura de arquivos grandes fica em `pipeline/.cache/` e pode ser apagado a qualquer momento.

## Regras que merecem atenção

- **Estimativas** (selo "Estimativa Sapion"): etapa dos professores sem etapa no cargo, IQE reconstruído, coeficiente
  do IQE, ICMS Educacional em R$, VAAR deixado na mesa e diferença do ICMS para a mediana. A metodologia completa está
  na aba "Metodologia e fontes" do painel.
- **Peso do IQE:** 12% no repasse de 2026 e 12,5% a partir de 2027 (`PESO_IQE_2026` em `financiamento.py`).
- **Classificação de cargos:** regras por nome em `profissionais.py` (`MUNI_RULES` para redes com nomenclatura própria).
  Revise `data/dicionario_cargos.csv` a cada folha nova.
- **Painel do TCE-ES:** `tcees_powerbi.py` usa a interface pública do relatório Power BI de Educação. Se o TCE-ES
  republicar o painel com outra chave, atualize `RESOURCE_KEY` (está no endereço `app.powerbi.com/view?r=...`
  embutido na página de Educação do painel).
- **Estados:** cada município leva a sigla da UF; os estados do plano de expansão estão em `ESTADOS` no `build.py`.
