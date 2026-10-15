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

Limitações conhecidas:
- O limite de dispensa vale **por ramo de atividade e por unidade gestora**, não por fornecedor. O fracionamento é aproximado pelo fornecedor e precisa de leitura humana dos objetos.
- O PNCP depende do que a prefeitura cadastra. Erros de cadastro geram falsos positivos, e omissões geram falsos negativos.
- Reajustes e prorrogações às vezes aparecem como aditivo de valor.

Regras planejadas:
- **preço fora do mercado**: comparação do preço unitário com itens equivalentes de outros municípios no PNCP;
- **empresa aberta pouco antes do contrato**;
- **licitação com participante único**;
- **cruzamento entre pagamentos e contratos** (depende dos dados do portal municipal).

## Escada de encaminhamento

1. **Ofício à Secretaria ou ao setor de compras.** O tom é técnico: pede-se esclarecimento e correção. Se a licitação ainda não aconteceu, esse é o melhor momento.
2. **Controle Interno da prefeitura e Câmara de Vereadores**, se não houver resposta ou correção em prazo razoável (30 dias é o usual; a LAI dá 20 + 10 dias).
3. **TCE-SC (Ouvidoria ou representação) e Ministério Público de SC**, quando houver indício consistente de irregularidade ou dano ao erário.
4. **Imprensa**: só depois das etapas anteriores, com documentação completa e a resposta (ou o silêncio) do órgão registrados.

Pule etapas só em caso de urgência real, por exemplo um contrato prestes a ser assinado com indício grave. Nesse caso, vá direto ao TCE-SC ou ao MP.
