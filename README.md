# Observatório Municipal

Projeto semiautônomo, com agentes de IA, que facilita a implantação de **observatórios sociais em municípios**. Ele monitora as compras públicas no PNCP e traz um guia simples de como proceder diante de inconsistências.

Começou em **Tijucas/SC** e foi feito para ser replicado em qualquer cidade. Basta um arquivo de configuração com o CNPJ da prefeitura.

> **As regras encontram, a IA explica e o humano decide.** Nenhum alerta é acusação: é um ponto a verificar.

---

## O que ele faz

1. **Coleta** no [PNCP](https://pncp.gov.br) (Portal Nacional de Contratações Públicas), que é público, sem login e obrigatório pela Lei 14.133/2021:
   - licitações, dispensas, inexigibilidades e adesões a atas publicadas pelo município;
   - contratos e termos aditivos;
   - compras feitas **por outros órgãos** que geraram contratos do município, como consórcios intermunicipais e atas de terceiros. Em Tijucas, 84% dos contratos vêm do consórcio CINCATARINA.
2. **Aplica regras determinísticas** que apontam indícios (veja abaixo).
3. **Revisão:** cada alerta é conferido contra os documentos oficiais, e falsos positivos são descartados. O revisor pode ser um agente de IA (`agentes/revisor.md`) ou uma pessoa.
4. **Gera um relatório** com o fato, as evidências (links do PNCP), o que pode explicar o caso de forma legítima, como verificar e a quem encaminhar.

## Regras atuais

| Regra | O que aponta |
|---|---|
| `dispensa_acima_do_limite` | Dispensa por valor acima do teto legal do ano (art. 75) |
| `aditivo_acima_do_limite` | Acréscimos acima de 25% do valor inicial, ou 50% em reforma (art. 125). Reajustes e apostilamentos não entram na conta |
| `aditivo_com_prorrogacao` | Aditivos que combinam acréscimo e prorrogação. É um indício fraco, só para monitorar |
| `possivel_fracionamento` | Várias dispensas para o mesmo fornecedor no ano, cada uma abaixo do teto e a soma acima |
| `adesao_a_ata_de_outro_ente` | "Carona" em ata de registro de preços de outro município (art. 86, §2º) |
| `adesoes_repetidas_mesma_ata` | Mais de uma adesão à mesma ata, com risco de passar o limite de 50% por item (art. 86, §4º) |
| `fornecedor_recorrente_sem_licitacao` | Três ou mais contratações diretas para o mesmo fornecedor no ano |
| `concentracao_de_fornecedor` | Um fornecedor com mais de 10% do valor contratado |
| `preco_acima_da_referencia` | Preço unitário acima da referência: numa adesão, mais de 1,2x o menor preço do certame que gerou a ata; nos demais casos, mais de 1,5x a mediana de itens parecidos comprados por municípios vizinhos |

**Próximas regras:**
- empresa aberta pouco antes do contrato;
- licitação com participante único;
- cruzamento de pagamentos com contratos.

Detalhes e limitações de cada regra estão em [METODOLOGIA.md](METODOLOGIA.md).

## O que fazer quando aparece uma inconsistência

Resumo da escada de encaminhamento, inspirada na metodologia da rede [Observatório Social do Brasil](https://osbrasil.org.br). O texto completo está em [METODOLOGIA.md](METODOLOGIA.md).

1. **Verifique primeiro.** Abra os links do alerta e leia os documentos. Siga o roteiro "como verificar" do relatório. Muitos alertas têm explicação legítima.
2. **Ofício à secretaria responsável**, com cópia ao Controle Interno da prefeitura. O tom é técnico: pedimos o processo e esclarecimentos. Se a licitação ainda não aconteceu, esse é o melhor momento para corrigir.
3. **Pedido via LAI** (Lei 12.527/2011) para os documentos que não estão públicos. O prazo de resposta é de 20 dias, prorrogáveis por mais 10.
4. **Câmara de Vereadores**, se não houver resposta ou correção.
5. **TCE-SC (Ouvidoria ou representação) e Ministério Público**, quando o indício for consistente ou houver risco de dano ao erário.
6. **Imprensa:** só depois das etapas anteriores, com a documentação completa e a resposta (ou o silêncio) do órgão registrados.

Em todo o caminho:
- descreva fatos ("acréscimo de 40% sobre o valor inicial"), não intenções;
- não use "fraude", "corrupção" ou "desvio" sem decisão de órgão competente;
- não exponha empresas ou pessoas com base em alerta não verificado.

## Como rodar

Requisitos: Python 3.10 ou superior.

```bash
git clone <este repositório>
cd observatorio-municipal
pip install -e .

python -m observatorio.coleta config/tijucas.yaml      # baixa do PNCP para dados/tijucas.sqlite
python -m observatorio.regras config/tijucas.yaml      # gera dados/alertas.json
python -m observatorio.relatorio config/tijucas.yaml   # gera dados/relatorio.md
```

Sobre a coleta:
- A primeira leva de 15 a 30 minutos: o coletor espera entre as chamadas para não sobrecarregar o PNCP. As seguintes só buscam o que mudou.
- Para rodar uma etapa isolada, use `python -m observatorio.coleta config/tijucas.yaml termos`. As etapas são `contratacoes`, `contratos`, `compras_externas`, `termos`, `itens` e `referencias`.
- `referencias` baixa as compras dos municípios vizinhos listados em `precos.vizinhos` e o certame de origem de cada adesão a ata. A primeira vez é a mais demorada.
- Para rodar em segundo plano, com log em `dados/coleta.log`, use `scripts/coletar.sh config/tijucas.yaml`.

### Revisão dos alertas

Crie `dados/revisao.json` com a classificação de cada alerta (`PROCEDENTE`, `INCONCLUSIVO`, `DESCARTADO` ou `MONITORAR`), usando o título do alerta como chave. O relatório passa a abrir com o resumo da revisão. O formato esperado está em `agentes/revisor.md`.

### Automação semanal

O workflow `.github/workflows/semanal.yml` roda a coleta, as regras e o relatório toda segunda-feira, no GitHub Actions. **O relatório não é publicado:** ele fica como artefato privado da execução, para revisão humana.

## Abrindo o observatório da sua cidade

1. Faça um fork deste repositório.
2. Copie `config/tijucas.yaml` para `config/<sua-cidade>.yaml`.
3. Troque o nome, o código IBGE e o **CNPJ da prefeitura**. O CNPJ está no rodapé do site oficial ou em qualquer edital.
4. Confira os limites legais do ano em `limites:`. Os valores de dispensa mudam todo ano por decreto federal.
   Troque também a lista de vizinhos em `precos.vizinhos` (nome e código IBGE). A coleta avisa se um código não corresponder ao nome.
5. Rode os três comandos acima e leia o relatório com calma.
6. Acrescente sua cidade na `matrix` do workflow semanal.

Vai além do código:
- reúna outras pessoas, porque um observatório tem mais força como associação apartidária;
- considere filiar-se à rede [Observatório Social do Brasil](https://osbrasil.org.br), que oferece metodologia e capacitação;
- busque parceria com universidades locais.

## Fontes de dados

| Fonte | Como é usada |
|---|---|
| PNCP: API de consulta e API pública | Coleta automática |
| Diário Oficial dos Municípios de SC | Conferência manual. Coleta automática planejada |
| Portal de transparência municipal | **Não é coletado automaticamente** (veja abaixo) |

**Sobre portais municipais:** muitos portais de transparência (IPM/Atende.net, Betha e outros) bloqueiam acesso automatizado com captcha. **Este projeto não contorna essas proteções.** Os caminhos legítimos são dois:
- **Exportação manual** de planilhas pelo voluntário. Um importador está em construção.
- **Pedido via LAI** da base completa em formato aberto. O art. 8º, §3º, II e III da Lei 12.527 exige que os portais permitam acesso automatizado em formato legível por máquina. Um portal que bloqueia isso já é, por si, um ponto de transparência a cobrar.

## Estrutura do repositório

```
config/              um arquivo por município (CNPJ, limites legais, parâmetros das regras)
src/observatorio/
  pncp.py            cliente da API do PNCP
  db.py              banco SQLite (guarda o JSON bruto de cada registro, para auditoria)
  coleta.py          coleta por etapas
  regras.py          regras de indício
  relatorio.py       relatório em Markdown
agentes/             prompts dos agentes de IA (revisor e redator)
scripts/             utilitários
METODOLOGIA.md       princípios, regras, limitações e escada de encaminhamento
dados/               (fora do git) banco, alertas, revisão e relatórios de cada instância
```

## Privacidade dos dados

A pasta `dados/` está no `.gitignore`. **Alertas e relatórios nunca vão para o repositório público.** Eles contêm nomes de empresas e indícios ainda não verificados. Publique só casos revisados, e só depois de seguir a escada de encaminhamento.

## Como contribuir

- **Nova regra:** escreva uma função `r_<nome>(con, cfg)` em `regras.py` que devolva alertas com evidências, explicações legítimas, como verificar e encaminhamento. Documente a regra em `METODOLOGIA.md`.
- **Nova cidade:** abra um PR com o `config/<cidade>.yaml`.
- **Adaptador de portal municipal:** importador de planilhas exportadas de um sistema específico (IPM, Betha e outros).
- **Erros e falsos positivos:** abra uma issue com o link do PNCP.

## Licença

MIT — veja [LICENSE](LICENSE).
