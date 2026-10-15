"""Equivalência aproximada entre itens de compras públicas.

A maioria dos itens municipais no PNCP não tem código de catálogo, então a
equivalência é estimada pela descrição: as mesmas palavras, as mesmas medidas
(ex.: 5,48X1,60) e a mesma unidade de fornecimento. Isso é indício de que os
itens são comparáveis, não prova. O relatório pede a leitura das especificações.
"""
from __future__ import annotations

import html
import re
import unicodedata
from collections import defaultdict

# Palavras que aparecem em quase toda descrição e não ajudam a distinguir itens.
VAZIAS = {
    "and", "com", "como", "conforme", "das", "dos", "demais", "deve", "devera", "edital", "anexo",
    "especificacao", "especificacoes", "descrito", "descricao", "item", "itens", "mais", "nao", "para", "pela", "pelo",
    "por", "que", "referencia", "sem", "sua", "termo", "uma", "unidade", "tipo", "modelo",
    "aquisicao", "fornecimento", "contratacao", "empresa", "servico", "servicos", "material",
    "materiais", "municipio", "secretaria", "atender", "necessidades", "minimo", "maximo",
}

UNIDADES = {"un": "unidade", "und": "unidade", "unid": "unidade", "unidade": "unidade",
            "pc": "peca", "pca": "peca", "peca": "peca", "cx": "caixa", "caixa": "caixa",
            "kg": "kg", "quilograma": "kg", "l": "litro", "lt": "litro", "litro": "litro",
            "m2": "m2", "metro quadrado": "m2", "m": "metro", "metro": "metro", "m3": "m3"}


def _ascii(s: str) -> str:
    # NFKD também transforma "m²" em "m2".
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


# "tipo IV", "modelo 3", "classe A": identificam a variante do item e precisam bater.
RE_VARIANTE = re.compile(r"\b(tipo|modelo|classe|categoria|nivel|grau)\s*[-:.]?\s*(?:n[o.]?\s*)?([ivx]+|\d+|[a-z])\b")
# Medidas mantêm a unidade ("1m" não é "40cm"); frações de polegada ficam inteiras
# ("1 1/2" não é "2"); códigos como "PA2" também.
RE_PALAVRA = re.compile(r"\d+(?:[ .-]\d+)?/\d+|[a-z]{2,}\d[a-z\d]*|\d+(?:[.,]\d+)*(?:mm|cm|m2|m3|kg|mg|ml|m|g|l)?|[a-z]{3,}")


def tokens(descricao: str | None, limite: int = 15) -> frozenset[str]:
    """Primeiras palavras, medidas e variantes da descrição. O começo da
    descrição é o nome do item; o resto costuma ser especificação longa."""
    t = _ascii(html.unescape(descricao or "")).lower()
    t = re.sub(r"^\s*(lote|grupo|item)\s*\d+\s*[-:.]\s*", "", t)  # "Lote 1 - ..." é agrupamento, não o item
    vistos: list[str] = []
    for m in RE_VARIANTE.finditer(t[:200]):
        v = f"#{m.group(1)}{m.group(2)}"
        if v not in vistos:
            vistos.append(v)
    for p in RE_PALAVRA.findall(t):
        p = re.sub(r"[ .]", "-", p) if "/" in p else p  # "1.1/2" e "1 1/2" -> "1-1/2"
        if len(vistos) >= limite:
            break
        if p not in VAZIAS and p not in vistos:
            vistos.append(p)
    return frozenset(vistos)


def unidade(u: str | None) -> str:
    u = re.sub(r"\(.*?\)", "", _ascii(u or "").lower()).strip(" .")
    return UNIDADES.get(u, u)


def _numeros(ts: frozenset[str]) -> frozenset[str]:
    """Medidas, códigos e variantes: o que distingue itens de mesmo nome."""
    return frozenset(t for t in ts if t[0] == "#" or any(c.isdigit() for c in t))


def similaridade(a: frozenset[str], b: frozenset[str]) -> float:
    """Proporção da descrição mais curta contida na mais longa. Se as duas têm
    medidas ou variantes, as da mais curta precisam estar todas na mais longa
    (e se só uma tem, não são comparáveis):
    "tipo 3 (5,48X1,60)" não casa com "tipo 4 (4,00X2,00)". Descrições genéricas
    ("camiseta manga longa, conforme termo de referência") não servem de
    referência: a mais curta precisa de 4 termos e as duas, de sobreposição mínima."""
    curta, longa = (a, b) if len(a) <= len(b) else (b, a)
    if len(curta) < 4:
        return 0.0
    nc, nl = _numeros(curta), _numeros(longa)
    if bool(nc) != bool(nl) or not nc <= nl:
        return 0.0  # medida de um lado só ("mangueira 2''" x "mangueira") ou medidas diferentes
    comum = len(curta & longa)
    if comum / len(curta | longa) < 0.3:
        return 0.0
    return comum / len(curta)


# Resultado que vale para o município: o do fornecedor que ele contratou naquela
# compra, se houver; senão o 1º colocado.
_RESULTADO = """(SELECT r.{col} FROM resultados r
      LEFT JOIN contratos c ON c.compra_id = r.compra_id AND c.fornecedor_ni = r.fornecedor_ni
      WHERE r.compra_id = i.compra_id AND r.numero_item = i.numero AND r.valor_unitario > 0
      ORDER BY c.id IS NULL, r.sequencial LIMIT 1)"""


def itens_do_municipio(con, valor_minimo: float) -> list[dict]:
    """Itens que valem a comparação, com o preço homologado ou, sem resultado, o estimado:
    - compras próprias: itens com valor total a partir de valor_minimo;
    - compras de outros órgãos que geraram contratos do município (consórcio):
      itens vencidos por um fornecedor que o município contratou naquela compra.
      O valor total do item é o do consórcio inteiro, por isso não serve de filtro."""
    rows = con.execute(f"""
      SELECT i.*, p.processo, p.objeto AS objeto_compra, p.orgao_cnpj, p.orgao_nome, p.externa,
        {_RESULTADO.format(col="valor_unitario")} AS homologado,
        {_RESULTADO.format(col="fornecedor_nome")} AS fornecedor
      FROM itens i JOIN contratacoes p ON p.id = i.compra_id
      WHERE (p.externa = 0 AND i.valor_total >= ?)
         OR (p.externa = 1 AND EXISTS (
              SELECT 1 FROM resultados r JOIN contratos c
                ON c.compra_id = r.compra_id AND c.fornecedor_ni = r.fornecedor_ni
              WHERE r.compra_id = i.compra_id AND r.numero_item = i.numero))""", (valor_minimo,)).fetchall()
    return [_preparar(dict(r)) for r in rows]


def itens_de_referencia(con) -> list[dict]:
    rows = con.execute("""
      SELECT i.*, c.orgao_cnpj, c.orgao_nome, c.municipio, c.uf, c.numero AS numero_compra,
             c.modalidade, c.data_publicacao,
        (SELECT r.valor_unitario FROM resultados r WHERE r.compra_id = i.compra_id
           AND r.numero_item = i.numero AND r.valor_unitario > 0 ORDER BY r.sequencial LIMIT 1) AS homologado,
        (SELECT r.fornecedor_nome FROM resultados r WHERE r.compra_id = i.compra_id
           AND r.numero_item = i.numero AND r.valor_unitario > 0 ORDER BY r.sequencial LIMIT 1) AS fornecedor
      FROM itens i JOIN compras_referencia c ON c.id = i.compra_id""").fetchall()
    return [_preparar(dict(r)) for r in rows]


def _preparar(it: dict) -> dict:
    it["tokens"] = tokens(it["descricao"])
    it["unidade_norm"] = unidade(it["unidade"])
    it["preco"] = it["homologado"] or it["valor_unitario_estimado"] or 0
    it["preco_tipo"] = "homologado" if it["homologado"] else "estimado"
    return it


class Indice:
    """Índice invertido das descrições de referência, para não comparar cada
    item com todos os outros."""

    def __init__(self, itens: list[dict]):
        self.itens = itens
        self.por_token: dict[str, list[int]] = defaultdict(list)
        for i, it in enumerate(itens):
            for t in it["tokens"]:
                if not t[0].isdigit():
                    self.por_token[t].append(i)

    def similares(self, toks: frozenset[str], und: str, minimo: float) -> list[tuple[dict, float]]:
        cont: dict[int, int] = defaultdict(int)
        for t in toks:
            for i in self.por_token.get(t, ()):
                cont[i] += 1
        out = []
        for i, n in cont.items():
            it = self.itens[i]
            if n < 2 or it["unidade_norm"] != und:
                continue
            s = similaridade(toks, it["tokens"])
            if s >= minimo:
                out.append((it, s))
        return out
