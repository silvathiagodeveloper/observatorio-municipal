# Metodologia

Inspirada na metodologia da rede **Observatório Social do Brasil (OSB)**: atuação técnica, apartidária e **preventiva**. O objetivo é corrigir o problema, não fazer denúncia.

## Princípios

1. **Indício não é irregularidade.** Toda regra tem explicações legítimas, e o relatório sempre lista quais são.
2. **Evidência rastreável.** Todo alerta aponta para o documento oficial no PNCP.
3. **Revisão humana obrigatória** antes de qualquer contato externo.
4. **Dados obtidos de forma lícita.** Usamos fontes abertas e a Lei de Acesso à Informação. Não contornamos captcha nem bloqueios.
5. **Ninguém é exposto publicamente com base em alerta não verificado.**

## Regras

| Regra | O que verifica | Base legal | Gravidade |
|---|---|---|---|
| `dispensa_acima_do_limite` | Dispensa por valor (art. 75, I ou II) acima do teto do ano | Lei 14.133, art. 75; decretos anuais de atualização | alta |
| `aditivo_acima_do_limite` | Soma de acréscimos acima de 25% do valor inicial (50% em reforma) | Lei 14.133, art. 125 | alta se passar do dobro do limite; média nos demais casos |
| `possivel_fracionamento` | Mesmo fornecedor, várias dispensas por valor no ano, cada uma abaixo do teto e a soma acima | Lei 14.133, art. 75, §1º | média |
| `fornecedor_recorrente_sem_licitacao` | Três ou mais dispensas ou inexigibilidades para o mesmo fornecedor no ano | Lei 14.133, arts. 72 a 75 | baixa ou média |
| `concentracao_de_fornecedor` | Um fornecedor com mais de 10% do valor total contratado | — | baixa (monitoramento) |
| `preco_acima_da_referencia` | Preço unitário acima de 1,2x o menor preço do certame de origem (adesões) ou de 1,5x a mediana de itens parecidos em municípios vizinhos (mínimo de 3 referências) | Lei 14.133, art. 23 (pesquisa de preços) e art. 86 (adesão com vantagem) | alta se passar do dobro; média nos demais casos |

Limitações conhecidas:
- O limite de dispensa vale **por ramo de atividade e por unidade gestora**, não por fornecedor. O fracionamento é aproximado pelo fornecedor e precisa de leitura humana dos objetos.
- O PNCP depende do que a prefeitura cadastra. Erros de cadastro geram falsos positivos, e omissões geram falsos negativos.
- Reajustes e prorrogações às vezes aparecem como aditivo de valor.
- Na comparação de preços, a equivalência entre itens é estimada pela descrição: as mesmas palavras, as mesmas medidas e a mesma unidade. Itens parecidos podem ter especificações diferentes, e referências de anos anteriores não são corrigidas pela inflação. Só entram itens com valor total a partir de R$ 20 mil.
- Em compras de consórcio (ex.: CINCATARINA), entram os itens vencidos por fornecedores que o município contratou naquela compra. O PNCP não informa quais itens nem quanto o município contratou de cada um: se o fornecedor venceu vários itens, todos entram na comparação, e o alerta não estima a diferença em reais. Confira no contrato quais itens foram de fato contratados.
- Diferenças acima de 5x a referência são ignoradas: quase sempre são de unidade ou embalagem (pacote com 100 contra unidade avulsa). Um sobrepreço real dessa ordem passa sem alerta.
- O certame de origem de uma adesão é localizado pelo texto do objeto ("Município de X ... Pregão nº N/AAAA"). Atas de consórcios e de órgãos federais, ou objetos sem essas informações, precisam ser informados à mão em `precos.origem_adesoes`.

Regras planejadas:
- **empresa aberta pouco antes do contrato**;
- **licitação com participante único**;
- **cruzamento entre pagamentos e contratos** (depende dos dados do portal municipal).

## Escada de encaminhamento

1. **Ofício à Secretaria ou ao setor de compras.** O tom é técnico: pede-se esclarecimento e correção. Se a licitação ainda não aconteceu, esse é o melhor momento.
2. **Controle Interno da prefeitura e Câmara de Vereadores**, se não houver resposta ou correção em prazo razoável (30 dias é o usual; a LAI dá 20 + 10 dias).
3. **TCE-SC (Ouvidoria ou representação) e Ministério Público de SC**, quando houver indício consistente de irregularidade ou dano ao erário.
4. **Imprensa**: só depois das etapas anteriores, com documentação completa e a resposta (ou o silêncio) do órgão registrados.

Pule etapas só em caso de urgência real, por exemplo um contrato prestes a ser assinado com indício grave. Nesse caso, vá direto ao TCE-SC ou ao MP.
