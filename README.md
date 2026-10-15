# Observatório Municipal

Ferramenta aberta para **controle social de compras públicas municipais**, baseada em dados abertos e agentes de IA. Começou em **Tijucas/SC** e foi feita para ser replicada em qualquer cidade.

O que ela faz:

1. **Coleta** licitações, dispensas, inexigibilidades, contratos e termos aditivos no **PNCP** (Portal Nacional de Contratações Públicas). É uma fonte obrigatória pela Lei 14.133, pública e sem login.
2. **Aplica regras** determinísticas que apontam *indícios*:
   - aditivos acima do limite legal;
   - dispensa acima do teto;
   - possível fracionamento;
   - fornecedor recorrente sem licitação;
   - concentração de fornecedores.
3. **Agentes de IA** revisam cada alerta, descartam falsos positivos óbvios e redigem o relatório com *como verificar* e *a quem encaminhar*.
4. **Um humano revisa** antes de qualquer contato com a prefeitura, a Câmara ou a imprensa.

> As regras encontram, a IA explica, e o humano decide. Nenhum alerta é acusação.

## Rodando

```bash
pip install -e .
python -m observatorio.coleta config/tijucas.yaml   # baixa do PNCP para dados/tijucas.sqlite
python -m observatorio.regras config/tijucas.yaml   # gera dados/alertas.json
python -m observatorio.relatorio config/tijucas.yaml # gera dados/relatorio.md
```

A primeira coleta leva de 10 a 20 minutos, porque o coletor espera entre as chamadas para não sobrecarregar o PNCP.

## Abrindo o observatório da sua cidade

1. Copie `config/tijucas.yaml` para `config/<sua-cidade>.yaml`.
2. Troque o nome, o código IBGE e o **CNPJ da prefeitura**. O CNPJ está no rodapé do site oficial ou em qualquer edital.
3. Rode os três comandos acima.
4. Leia `METODOLOGIA.md` antes de encaminhar qualquer coisa.

Para rodar automaticamente toda semana, use o workflow em `.github/workflows/semanal.yml`. Por padrão ele **não publica** os alertas: só gera o relatório como artefato privado da execução.

## Estrutura

```
config/            uma configuração por município (limites legais, CNPJ, fontes)
src/observatorio/  coletor PNCP, banco SQLite, regras, relatório
agentes/           prompts dos agentes de IA (revisor e redator), versionados
METODOLOGIA.md     o que cada regra significa, limites, escada de encaminhamento
dados/             (ignorado pelo git) banco e relatórios de cada instância
```

## Fontes que não são coletadas automaticamente

Portais municipais de transparência (IPM/Atende.net, Betha e outros) muitas vezes bloqueiam acesso automatizado com captcha. **Este projeto não contorna essas proteções.** Os caminhos são estes:
- **exportação manual** de CSV pelo voluntário, com importação na pasta `dados/importar/` (em construção);
- **pedido via LAI** da base em formato aberto. O art. 8º, §3º, II e III da Lei 12.527 exige que os portais permitam acesso automatizado em formato legível por máquina.

## Licença

MIT.
