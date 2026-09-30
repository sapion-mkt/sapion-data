# Sapion Data

Painel de dados educacionais por município, feito pela Sapion Nova Educação para o seu time comercial.
A versão 1 cobre os 78 municípios do Espírito Santo: profissionais da educação, IDEB, alfabetização e
financiamento da educação (Fundeb, VAAR, VAAT e ICMS Educacional).

- `index.html` – o painel, em um único arquivo (publicado pelo GitHub Pages).
- `sistema/` – código que gera o painel a partir das fontes oficiais (pipeline em Python e interface).
  Veja `sistema/README.md` para atualizar os dados.

Os números marcados como **Estimativa Sapion** no painel são cálculos próprios da Sapion a partir de dados
oficiais, e não dados oficiais. A metodologia completa está na aba "Metodologia e fontes" do painel.

Fontes: TCE-ES (folha de pagamento declarada pelos municípios), Inep (IDEB, Censo Escolar, Indicador Criança
Alfabetizada), FNDE/Tesouro Nacional (Fundeb), Sefaz-ES (repasses de ICMS e IPM), Sedu-ES (metodologia do IQE).
