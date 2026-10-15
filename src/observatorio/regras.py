"""Motor de regras determinístico.

As regras ENCONTRAM indícios. Elas não acusam ninguém: cada alerta traz as
evidências (links do PNCP), o que pode explicar o caso de forma legítima e
como verificar. A revisão humana vem antes de qualquer encaminhamento.

Uso:  python -m observatorio.regras config/tijucas.yaml
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import yaml

from . import db


def link_contrato(id_: str) -> str:
    # id: 82577636000165-2-000001/2026
    cnpj, _, resto = id_.split("-", 2)
    seq, ano = resto.split("/")
    return f"https://pncp.gov.br/app/contratos/{cnpj}/{ano}/{int(seq)}"


def link_compra(id_: str) -> str:
    cnpj, _, resto = id_.split("-", 2)
    seq, ano = resto.split("/")
    return f"https://pncp.gov.br/app/editais/{cnpj}/{ano}/{int(seq)}"


def brl(v) -> str:
    return "R$ " + f"{(v or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _limite(cfg, chave, ano):
    tab = cfg["limites"][chave]
    return tab.get(ano) or tab[max(tab)]


def alerta(regra, gravidade, titulo, descricao, evidencias, legitimo, verificar, encaminhar, valor=0):
    return dict(regra=regra, gravidade=gravidade, titulo=titulo, descricao=descricao,
                valor=valor, evidencias=evidencias, explicacoes_legitimas=legitimo,
                como_verificar=verificar, encaminhamento=encaminhar)


def r_aditivos(con, cfg):
    lim, lim_ref = cfg["limites"]["aditivo_percentual"], cfg["limites"]["aditivo_percentual_reforma"]
    out = []
    # Conta só termos aditivos marcados como acréscimo/supressão e que NÃO são
    # reajuste (apostilamentos e reajustes ficam fora do limite do art. 125).
    # Termos que também prorrogam a vigência são contados à parte, porque o
    # valor pode ser do novo período e não acréscimo de objeto.
    rows = con.execute("""
      SELECT c.*,
        COALESCE(SUM(CASE WHEN t.tipo = 'Termo Aditivo'
               AND json_extract(t.bruto,'$.qualificacaoAcrescimoSupressao') = 1
               AND json_extract(t.bruto,'$.qualificacaoReajuste') = 0
               AND json_extract(t.bruto,'$.qualificacaoVigencia') = 0
               THEN t.valor_acrescido END), 0) AS acrescido,
        COALESCE(SUM(CASE WHEN t.tipo = 'Termo Aditivo'
               AND json_extract(t.bruto,'$.qualificacaoAcrescimoSupressao') = 1
               AND json_extract(t.bruto,'$.qualificacaoReajuste') = 0
               AND json_extract(t.bruto,'$.qualificacaoVigencia') = 1
               THEN t.valor_acrescido END), 0) AS acrescido_com_prorrogacao,
        COUNT(t.sequencial) AS n_termos
      FROM contratos c LEFT JOIN termos t ON t.contrato_id = c.id
      GROUP BY c.id""").fetchall()
    for c in rows:
        base = c["valor_inicial"] or 0
        if base <= 0:
            continue
        acrescido = c["acrescido"] or 0
        ambiguo = c["acrescido_com_prorrogacao"] or 0
        pct = acrescido / base
        teto_c = lim_ref if re.search(r"reforma", c["objeto"] or "", re.I) else lim
        if pct <= teto_c and ambiguo / base > teto_c:
            # Só passa do limite somando termos que também prorrogaram a vigência: indício fraco.
            out.append(alerta(
                "aditivo_com_prorrogacao", "baixa",
                f"Aditivos com prorrogação somam {ambiguo/base:.0%} do valor inicial — {c['fornecedor_nome']}",
                f"Contrato {c['numero']} (processo {c['processo']}), valor inicial {brl(base)}. Os termos combinam acréscimo "
                f"e prorrogação ({brl(ambiguo)}); pode ser só o valor do novo período. Objeto: {(c['objeto'] or '')[:200]}",
                [link_contrato(c["id"])],
                ["Prorrogação de serviço contínuo: o valor acrescido corresponde ao novo período, o que é legal."],
                ["Ler os termos: o valor acrescido é proporcional ao prazo prorrogado? Se for maior, há acréscimo de objeto embutido."],
                "Monitoramento; vira caso só se o acréscimo de quantidade ficar claro.", valor=ambiguo))
            continue
        reforma = bool(re.search(r"reforma", c["objeto"] or "", re.I))
        teto = lim_ref if reforma else lim
        if pct > teto:
            out.append(alerta(
                "aditivo_acima_do_limite", "alta" if pct > 2 * teto else "media",
                f"Acréscimo de {pct:.0%} sobre o valor original — {c['fornecedor_nome']}",
                f"Contrato {c['numero']} (processo {c['processo']}), valor inicial {brl(base)}, "
                f"acréscimos de {brl(acrescido)} em {c['n_termos']} termo(s). O art. 125 da Lei 14.133 "
                f"limita acréscimos a {teto:.0%}{' (reforma)' if reforma else ''}. Objeto: {c['objeto'][:200]}",
                [link_contrato(c["id"])],
                ["Reajuste ou repactuação contratual não conta no limite de 25% e às vezes é lançado como aditivo de valor.",
                 "Prorrogação de serviço contínuo soma um novo período de valor, sem ser acréscimo de objeto.",
                 "Erro de cadastro no PNCP (valor inicial lançado errado)."],
                ["Abrir cada termo aditivo no PNCP e ler a justificativa: é acréscimo de quantidade/objeto, reajuste ou prorrogação?",
                 "Somar só os acréscimos quantitativos e comparar com 25% do valor inicial atualizado.",
                 "Pedir à prefeitura (LAI) o processo completo do contrato, com pareceres jurídicos dos aditivos."],
                "Se o acréscimo quantitativo passar de 25%: ofício à Secretaria responsável pedindo esclarecimento; "
                "sem resposta, Câmara de Vereadores e Controle Interno; persistindo, TCE-SC.",
                valor=acrescido))
    return out


def _dispensas(con):
    return con.execute("""
      SELECT c.*, p.modalidade_id, p.modalidade, p.amparo_legal, p.valor_homologado,
             p.objeto AS objeto_compra, CAST(substr(c.data_assinatura,1,4) AS INT) AS ano_ass
      FROM contratos c JOIN contratacoes p ON p.id = c.compra_id
      WHERE p.modalidade_id IN (8, 9)""").fetchall()


def r_dispensa_acima_limite(con, cfg):
    out = []
    for p in con.execute("""SELECT * FROM contratacoes WHERE modalidade_id = 8
                             AND (amparo_legal LIKE '%75, I' OR amparo_legal LIKE '%75, II')
                             AND objeto NOT LIKE 'Ades%'""").fetchall():
        chave = "dispensa_obras_eng" if p["amparo_legal"].endswith("75, I") else "dispensa_outros"
        lim = _limite(cfg, chave, p["ano"])
        v = p["valor_homologado"] or p["valor_estimado"] or 0
        if v > lim * 1.001:
            out.append(alerta(
                "dispensa_acima_do_limite", "alta",
                f"Dispensa por valor acima do teto legal — {brl(v)}",
                f"Compra {p['numero']} (processo {p['processo']}) com amparo em {p['amparo_legal']}, "
                f"valor {brl(v)} contra limite de {brl(lim)} em {p['ano']}. Objeto: {(p['objeto'] or '')[:200]}",
                [link_compra(p["id"])],
                ["Amparo legal cadastrado errado no PNCP (a dispensa pode ser por outro inciso, ex.: emergência).",
                 "Valor estimado plurianual lançado no lugar do valor anual."],
                ["Abrir o processo no PNCP e conferir o fundamento legal no ato de ratificação.",
                 "Conferir no Diário Oficial (DOM/SC) o extrato da dispensa."],
                "Se confirmado: ofício à Prefeitura e Controle Interno; em seguida TCE-SC (Ouvidoria).",
                valor=v))
    return out


def r_fracionamento(con, cfg):
    """Mesmo fornecedor, várias dispensas por valor no mesmo ano, cada uma abaixo
    do teto mas a soma acima. Heurística: a lei olha o 'ramo de atividade' por
    unidade gestora, não o fornecedor — por isso é indício, não conclusão."""
    out = []
    grupos = defaultdict(list)
    for d in _dispensas(con):
        if d["modalidade_id"] == 8 and (d["amparo_legal"] or "").rstrip().endswith(("75, I", "75, II")):
            grupos[(d["fornecedor_ni"], d["ano_ass"], d["amparo_legal"].endswith("75, I"))].append(d)
    for (ni, ano, obras), ds in grupos.items():
        if len(ds) < 2 or not ano:
            continue
        lim = _limite(cfg, "dispensa_obras_eng" if obras else "dispensa_outros", ano)
        soma = sum(d["valor_global"] or d["valor_inicial"] or 0 for d in ds)
        if soma > lim:
            out.append(alerta(
                "possivel_fracionamento", "media",
                f"{len(ds)} dispensas por valor para {ds[0]['fornecedor_nome']} em {ano} somam {brl(soma)}",
                f"Cada contratação ficou abaixo do teto ({brl(lim)}), mas a soma no ano o ultrapassa. "
                f"Objetos: " + " | ".join((d["objeto"] or "")[:90] for d in ds[:5]),
                [link_contrato(d["id"]) for d in ds],
                ["Objetos de naturezas diferentes (o limite vale por ramo de atividade, não por fornecedor).",
                 "Contratações de unidades gestoras distintas (fundos, autarquias) têm limites próprios.",
                 "Demanda imprevisível que surgiu ao longo do ano."],
                ["Comparar os objetos: são do mesmo ramo? Poderiam ter sido planejados juntos (Plano de Contratações Anual)?",
                 "Ver se houve, no mesmo ano, licitação para o mesmo tipo de objeto.",
                 "Checar as datas: compras muito próximas sugerem divisão artificial."],
                "Se os objetos forem do mesmo ramo: ofício à Secretaria pedindo o planejamento das compras; "
                "depois Controle Interno e Câmara. Fracionamento é tema típico de representação ao TCE-SC.",
                valor=soma))
    return out


def r_recorrencia(con, cfg):
    out = []
    minimo = cfg["regras"]["recorrencia_dispensa_min"]
    grupos = defaultdict(list)
    for d in _dispensas(con):
        grupos[(d["fornecedor_ni"], d["ano_ass"])].append(d)
    for (ni, ano), ds in grupos.items():
        if len(ds) >= minimo:
            soma = sum(d["valor_global"] or d["valor_inicial"] or 0 for d in ds)
            out.append(alerta(
                "fornecedor_recorrente_sem_licitacao", "baixa" if soma < 100000 else "media",
                f"{ds[0]['fornecedor_nome']}: {len(ds)} contratações sem licitação em {ano} ({brl(soma)})",
                "Modalidades: " + ", ".join(sorted({d['modalidade'] for d in ds})) + ". Objetos: "
                + " | ".join((d["objeto"] or "")[:80] for d in ds[:5]),
                [link_contrato(d["id"]) for d in ds],
                ["Fornecedor exclusivo (inexigibilidade legítima: ex. software proprietário, artista).",
                 "Credenciamento ou serviços de baixo valor e natureza diversa."],
                ["Ler as justificativas de inexigibilidade/dispensa no PNCP.",
                 "Pesquisar se há outros fornecedores do mesmo item na região (PNCP de municípios vizinhos)."],
                "Normalmente só monitoramento. Se as justificativas forem frágeis: ofício pedindo os estudos que embasaram a contratação direta.",
                valor=soma))
    return out


def r_concentracao(con, cfg):
    out = []
    lim = cfg["regras"]["concentracao_top_fornecedor"]
    total = con.execute("SELECT SUM(COALESCE(valor_global, valor_inicial)) FROM contratos").fetchone()[0] or 0
    for r in con.execute("""SELECT fornecedor_ni, fornecedor_nome, COUNT(*) n,
                              SUM(COALESCE(valor_global, valor_inicial)) v
                            FROM contratos GROUP BY fornecedor_ni ORDER BY v DESC LIMIT 10""").fetchall():
        if total and r["v"] / total > lim:
            ids = [x[0] for x in con.execute("SELECT id FROM contratos WHERE fornecedor_ni=? ORDER BY valor_global DESC LIMIT 5",
                                             (r["fornecedor_ni"],))]
            out.append(alerta(
                "concentracao_de_fornecedor", "baixa",
                f"{r['fornecedor_nome']} concentra {r['v']/total:.0%} do valor contratado ({brl(r['v'])})",
                f"{r['n']} contrato(s) no período coletado.",
                [link_contrato(i) for i in ids],
                ["Contratos naturalmente grandes (coleta de lixo, transporte escolar, obra relevante)."],
                ["Ver quantos concorrentes participaram das licitações vencidas por esse fornecedor.",
                 "Comparar o preço com contratos semelhantes de outros municípios no PNCP."],
                "Monitoramento. Vira caso só se combinado com outro indício (preço, aditivos, pouca concorrência).",
                valor=r["v"]))
    return out


def r_adesao(con, cfg):
    """Adesão ('carona') a ata de registro de preços de outro ente. É legal
    (art. 86, §2º), mas exige justificativa de vantagem e preços de mercado."""
    out = []
    lim = _limite(cfg, "dispensa_outros", 2026)
    for p in con.execute("""SELECT * FROM contratacoes WHERE objeto LIKE 'Ades%' AND externa = 0
                            ORDER BY COALESCE(valor_homologado, valor_estimado) DESC""").fetchall():
        v = p["valor_homologado"] or p["valor_estimado"] or 0
        if v < lim:
            continue
        cadastro = (f" Atenção: está cadastrada no PNCP como {p['modalidade']} com amparo em {p['amparo_legal']}, "
                    "o que não corresponde a uma adesão (erro de cadastro a ser corrigido).") if p["modalidade_id"] == 8 else ""
        out.append(alerta(
            "adesao_a_ata_de_outro_ente", "media" if v > 5 * lim else "baixa",
            f"Adesão a ata de outro ente — {brl(v)} (processo {p['processo']})",
            f"{(p['objeto'] or '')[:260]}.{cadastro}",
            [link_compra(p["id"])],
            ["Adesão é permitida pelo art. 86, §2º da Lei 14.133 quando há vantagem comprovada.",
             "Pode ter sido mais rápida e barata que licitar do zero."],
            ["Pedir o estudo que justificou a adesão: comparação de preços com o mercado e com atas de outros entes.",
             "Conferir se a quantidade aderida respeita o limite de 50% dos quantitativos da ata (art. 86, §4º).",
             "Verificar se o órgão gerenciador e o fornecedor autorizaram a adesão (documentos no processo)."],
            "Se faltar justificativa de vantagem: ofício à Secretaria pedindo o processo; depois Controle Interno. "
            "Se o cadastro no PNCP estiver errado, pedir a correção (transparência).",
            valor=v))
    return out


def r_adesoes_repetidas(con, cfg):
    """Várias adesões do município à MESMA ata. O art. 86, §4º limita cada órgão
    aderente a 50% dos quantitativos da ata; adesões fatiadas podem somar mais."""
    out, grupos = [], defaultdict(list)
    for p in con.execute("SELECT * FROM contratacoes WHERE objeto LIKE 'Ades%' AND externa = 0").fetchall():
        o = p["objeto"] or ""
        ata = re.search(r"Ata de Registro de Pre[çc]os n[ºo°.]*\s*([\d./-]+)", o, re.I)
        ente = re.search(r"(Munic[íi]pio de [^,.;/]+|FNDE|Fundo Nacional[^,.;]+|Cons[óo]rcio[^,.;]+)", o, re.I)
        if ata:
            grupos[(ata.group(1).strip(" ./-"), (ente.group(1).strip() if ente else "?").lower())].append(p)
    for (ata, ente), ps in grupos.items():
        if len(ps) < 2:
            continue
        soma = sum(x["valor_homologado"] or x["valor_estimado"] or 0 for x in ps)
        out.append(alerta(
            "adesoes_repetidas_mesma_ata", "media",
            f"{len(ps)} adesões à mesma ata ({ata}, {ente.title()}) somam {brl(soma)}",
            "Processos: " + "; ".join(f"{x['processo']} ({brl(x['valor_homologado'] or x['valor_estimado'])}, publicado {x['data_publicacao'][:10]})" for x in ps)
            + ". Objeto: " + (ps[0]["objeto"] or "")[:220],
            [link_compra(x["id"]) for x in ps],
            ["A ata pode ter quantitativos grandes o bastante para as duas adesões dentro do limite de 50%.",
             "As adesões podem ser de itens diferentes da mesma ata."],
            ["Obter a ata original no PNCP do órgão gerenciador e os quantitativos registrados por item.",
             "Somar o que Tijucas aderiu, por item, nas duas adesões, e comparar com 50% do registrado (art. 86, §4º).",
             "Ver se a ata ainda estava vigente na data da segunda adesão (validade máxima de 1 ano, prorrogável por mais 1)."],
            "Se a soma passar de 50% de algum item ou a ata estiver vencida: ofício à Secretaria e ao Controle Interno; "
            "sem correção, representação ao TCE-SC.",
            valor=soma))
    return out


REGRAS = [r_dispensa_acima_limite, r_adesoes_repetidas, r_adesao, r_aditivos, r_fracionamento, r_recorrencia, r_concentracao]


def rodar(cfg_path: str):
    cfg = yaml.safe_load(open(cfg_path, encoding="utf-8"))
    con = db.conectar(cfg["coleta"]["banco"])
    alertas = [a for r in REGRAS for a in r(con, cfg)]
    ordem = {"alta": 0, "media": 1, "baixa": 2}
    alertas.sort(key=lambda a: (ordem[a["gravidade"]], -a["valor"]))
    saida = Path(cfg["coleta"]["banco"]).with_name("alertas.json")
    saida.write_text(json.dumps(alertas, ensure_ascii=False, indent=2), encoding="utf-8")
    resumo = defaultdict(int)
    for a in alertas:
        resumo[(a["regra"], a["gravidade"])] += 1
    for k, v in sorted(resumo.items()):
        print(k, v)
    print(f"{len(alertas)} alertas -> {saida}")
    return alertas


if __name__ == "__main__":
    rodar(sys.argv[1] if len(sys.argv) > 1 else "config/tijucas.yaml")
