# Padrão de atualização e inserção de dados do Sapion Data

**Princípio:** todo dado entra pelo mesmo caminho, é conferido antes de aparecer no painel e fica registrado com a fonte e a data.

## 1. Onde ficam os dados

Todas as fontes ficam na pasta **`Fontes/`**, na raiz da pasta "Sapion Data":

```
Fontes/
  catalogo_fontes.xlsx          ← lista de todas as fontes (abrir no Excel)
  01-profissionais/tcees-vinculo/2026-T2/vinculo-2026-2.csv
  02-ideb/inep-ideb-municipios/2025/...
  03-alfabetizacao/inep-ica/2025/...
  03-alfabetizacao/tcees-fluencia/2026-11-13/fluencia.json   ← coletado pelo sistema
  04-financiamento/...
  05-escolas/...                                             ← coletado pelo sistema
  _entrada/                     ← arquivos recebidos que ainda não foram classificados
  _modelos/                     ← ficha de novo indicador e planilha-modelo por município
```

Regras:

1. **Nunca edite um arquivo de fonte.** Coloque o original exatamente como foi baixado.
2. **Uma subpasta por referência:** ano (`2026`), trimestre (`2026-T3`), mês (`2026-10`) ou data de coleta (`2026-11-13`). As antigas ficam guardadas e formam a série histórica.
3. O sistema usa sempre a **subpasta mais recente**, a não ser que o catálogo indique outra na coluna "referencia".

## 2. O catálogo de fontes

`Fontes/catalogo_fontes.xlsx` tem uma linha por fonte, com o órgão, o link, a periodicidade, a próxima publicação esperada, o padrão de nome do arquivo e o passo a passo para obter o dado. O sistema lê o catálogo para saber qual arquivo usar. A aba "Metodologia e fontes" do painel mostra essa lista com a referência em uso.

Há dois tipos de fonte:

- **Manual:** alguém baixa o arquivo e coloca na subpasta certa. Exemplos: folha do TCE-ES, IDEB, ICA, CSVs do Fundeb, PDFs de ICMS.
- **Automática:** o sistema busca sozinho a cada atualização e guarda uma cópia datada. Exemplos: Fluência em Leitura e escolas/IDEB por escola, do painel do TCE-ES.

## 3. Como atualizar (o caminho combinado)

1. **Coloque o arquivo novo** na subpasta da referência. Por exemplo, o Fundeb de outubro vai em `Fontes/04-financiamento/tesouro-fundeb-mensal/2026/outubro.csv`. Se não souber onde vai, deixe em `Fontes/_entrada/`.
2. **Peça ao Claude:** "atualize o Sapion Data". Ele roda a atualização, lê o relatório de conferência, explica o que mudou e publica depois da sua aprovação.

Quem quiser rodar sozinho: dois cliques em **`Atualizar Sapion Data.bat`** (raiz da pasta "Sapion Data"). Para registrar uma versão nova, use o terminal:

```
python atualizar.py --versao 1.2 "Descrição da novidade 1" "Descrição da novidade 2"
```

### O que a atualização faz

| Etapa | O que acontece | Se der errado |
|---|---|---|
| 1. Conferência das fontes manuais | Confere se cada arquivo existe e tem o conteúdo esperado (colunas e textos do catálogo) | Para e diz qual arquivo está faltando ou errado |
| 2. Coleta automática | Busca Fluência e escolas no painel do TCE-ES | Para e mostra o erro (ex.: painel fora do ar) |
| 3. Cálculo dos blocos | Recalcula todos os indicadores | Para e mostra o erro |
| 4. Checagens | Confere totais com as fontes oficiais: ICMS do mês, VAAR e VAAT, IPM, escolas e matrículas contra o Censo, cobertura dos 78 municípios | Para; o painel não é gerado |
| 5. Relatório de conferência | Compara cada município com a atualização anterior e lista as mudanças grandes | — |
| 6. Painel | Registra a data dos dados, gera o painel e a pasta do GitHub | — |

### O relatório de conferência

Fica em `sapion-data-app/relatorios/`. Lista as mudanças acima dos limites de atenção. Exemplos: um município que passou a receber VAAR, uma queda de mais de 10% no número de professores, uma variação de 0,3 ponto no IDEB. Mudança grande não é erro, mas precisa de explicação antes de publicar: dado novo de verdade ou problema no arquivo?

## 4. Calendário das fontes

| Quando | O que atualizar |
|---|---|
| Todo mês | CSV do Fundeb do mês (Tesouro) e PDF do ICMS (Sefaz-ES, cerca de 4 semanas depois) |
| A cada trimestre | Arquivo Vínculo do TCE-ES (profissionais) |
| Fevereiro | Censo Escolar do ano anterior (Sinopse; escolas entram pela coleta automática) |
| Março | ICA do ano anterior (Inep/MEC) |
| Abril e agosto | Portarias do Fundeb: atualizar a planilha do VAAR (previstos) |
| 2º semestre | Fluência em Leitura (coleta automática, quando o TCE-ES publicar) e lista do VAAR do ciclo seguinte |
| Agosto e dezembro | IPM provisório e definitivo (Sefaz-ES) |
| Outubro | Lista de habilitação ao VAAT do ciclo seguinte (FNDE) |
| Anos pares | IDEB (o IDEB 2027 sai em 2028) |

A coluna "proxima_atualizacao" do catálogo deve ser revista a cada atualização.

## 5. Como incluir um tipo de dado novo

1. Preencha a **Ficha de novo indicador** (`Fontes/_modelos/Ficha de novo indicador.xlsx`): o que é, para que serve ao comercial, fonte, chave (código IBGE ou INEP), periodicidade, se é oficial ou estimativa, como aparece e o texto do botão "?".
2. Coloque um arquivo de exemplo da fonte em `Fontes/_entrada/`.
3. Se o dado não vier num arquivo oficial pronto (ex.: números enviados por uma secretaria), use a **planilha-modelo por município** (`Fontes/_modelos/Modelo de dados por municipio.xlsx`), que já tem os 78 códigos IBGE.
4. Com a ficha e o exemplo, o desenvolvimento segue o modelo dos módulos existentes: entrada no catálogo, módulo de cálculo em `pipeline/`, checagem em `validar.py`, quadro na interface, entrada na Metodologia e item no histórico de versões.

## 6. Publicação

- **claude.ai:** o Claude republica o painel no mesmo link do Artifact.
- **GitHub:** enviar o novo `index.html` da pasta `publicar-github/` para o repositório (Add file → Upload files), substituindo o anterior. Quando houver código novo, enviar também a pasta `sistema/`.

## 7. Cuidados

- **Dados pessoais:** o arquivo Vínculo do TCE-ES tem nomes e CPF parcial de servidores. Ele fica só em `Fontes/` e nunca vai para o GitHub nem para o painel. O painel só mostra totais.
- **Estimativas:** todo número calculado pela Sapion leva o selo "Estimativa Sapion" e tem a conta explicada na Metodologia.
- **Fontes automáticas:** dependem do painel do TCE-ES continuar publicado do mesmo jeito. Se o TCE-ES mudar o painel, a coleta para com uma mensagem, e a última coleta continua valendo até o ajuste.
