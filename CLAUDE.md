# Contexto para o Claude

Observatório social municipal semiautônomo. Primeira instância: Tijucas/SC (CNPJ 82.577.636/0001-65). O mantenedor é programador e acompanha tudo pelo VS Code.

## Princípios (não negociáveis)
- **As regras encontram, a IA explica e o humano decide.** Nenhum alerta é acusação. Use linguagem factual e nunca "fraude", "corrupção" ou "desvio".
- **Só fontes lícitas.** PNCP (API aberta) e Diário Oficial (DOM/SC). O portal municipal (IPM/Atende.net) tem captcha: **não contornar, não automatizar**. Os dados de lá entram só por exportação manual ou por pedido via LAI.
- **`dados/` nunca vai para o git**: banco, alertas, revisão e relatórios ficam fora.
- **Fluxo de trabalho:** branch → PR → o mantenedor revisa e faz o merge. Nada direto no `main`.
- **Não entrar em loop.** Se algo falhar 2 ou 3 vezes, pare e pergunte antes de tentar outra abordagem (preferência do mantenedor).
- **PNCP tem limite de requisições** (HTTP 429, "Limite de requisições excedido"). Testes manuais em sequência estouram o limite. O cliente (`pncp.py`) espera o `Retry-After`. Use só as APIs documentadas (`api/consulta/v1` e `api/pncp/v1`). A busca textual do site (`api/search`) derrubou a conexão em out/2026 e não é usada.
- Escada de encaminhamento (METODOLOGIA.md): secretaria e Controle Interno → LAI → Câmara → TCE-SC/MP → imprensa.

## Estado atual (out/2026)
- Coleta PNCP desde 2025-01-01: 471 contratações próprias, 78 compras de outros órgãos, 861 contratos e 78 aditivos.
- 84% dos contratos **em número** (712 de 861), mas só cerca de 13% **em valor** (R$ 13,7 mi de R$ 108 mi), vêm de compras do consórcio **CINCATARINA** (CNPJ 12.075.748/0001-32). A etapa `compras_externas` busca essas compras.
- 9 regras em `src/observatorio/regras.py`, incluindo `preco_acima_da_referencia` (vizinhos em `precos.vizinhos` e certame de origem das adesões). A revisão manual fica em `dados/revisao.json`.

## Caso em aberto
**Abrigos de ônibus** (processos 243/2025 e 200/2026): duas adesões à Ata 040/2025 de São José (Floripaineis). Pontos levantados:
- abrigo Tipo 3: 25 unidades contra limite de 20 (50% de 40);
- preços de 58% a 97% acima dos que a Tecno ao Cubo obteve no mesmo pregão 008/2024;
- segunda adesão depois do primeiro ano da ata.

Próximo passo: ofício à Secretaria de Obras e ao Controle Interno, pedindo o processo e a pesquisa de preços.

Inconclusivos:
- Emmel & Emmel (3 inexigibilidades, R$ 203 mil);
- jaquetas escolares (adesão à ata de Governador Celso Ramos, R$ 80 por unidade).

## Próximos passos técnicos
1. Agente revisor via API (`agentes/revisor.md`) para gerar `dados/revisao.json`.
2. Importador de planilhas exportadas do portal Atende.net.
3. Pedido via LAI à prefeitura pela base de empenhos e pagamentos em formato aberto.

## Comandos
```bash
pip install -e .
python -m observatorio.coleta config/tijucas.yaml [contratacoes|contratos|compras_externas|termos|itens|referencias]
python -m observatorio.regras config/tijucas.yaml
python -m observatorio.relatorio config/tijucas.yaml
```
