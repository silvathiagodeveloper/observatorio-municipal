"""Coleta do PNCP para um município configurado.

Uso:
  python -m observatorio.coleta config/tijucas.yaml              # todas as etapas
  python -m observatorio.coleta config/tijucas.yaml termos       # só uma etapa
Etapas: contratacoes, contratos, compras_externas, termos, itens, referencias
"""
from __future__ import annotations

import re
import sys
from datetime import date

import yaml

from . import db, precos
from .pncp import MODALIDADES, PNCP

ETAPAS = ("contratacoes", "contratos", "compras_externas", "termos", "itens", "referencias")


def _partes(compra_id: str):
    # 82892274000105-1-000016/2024 -> ("82892274000105", 2024, 16)
    cnpj, _, resto = compra_id.split("-", 2)
    seq, ano = resto.split("/")
    return cnpj, int(ano), int(seq)


def _coletar_itens(con, api, compra_id: str, valor_minimo: float | None = None):
    """Baixa os itens de uma compra. Com valor_minimo, baixa também o resultado
    (preço homologado) dos itens a partir desse valor total."""
    cnpj, ano, seq = _partes(compra_id)
    for it in api.itens(cnpj, ano, seq):
        db.salvar_item(con, compra_id, it)
        if valor_minimo is not None and it.get("temResultado") and (it.get("valorTotal") or 0) >= valor_minimo:
            _coletar_resultados(con, api, compra_id, it["numeroItem"])
    con.execute("INSERT OR REPLACE INTO itens_verificados VALUES (?, datetime('now'))", (compra_id,))


def _coletar_resultados(con, api, compra_id: str, numero: int):
    cnpj, ano, seq = _partes(compra_id)
    for r in api.resultados(cnpj, ano, seq, numero):
        db.salvar_resultado(con, compra_id, r)
    con.execute("INSERT OR REPLACE INTO resultados_verificados VALUES (?, ?, datetime('now'))", (compra_id, numero))


RE_ENTE = re.compile(r"Munic[íi]pio de ([^,.;/()]+?)\s*(?:/\s*([A-Z]{2}))?(?=[,.;/()]|$)", re.I)
RE_CERTAME = re.compile(r"(Preg[ãa]o|Concorr[êe]ncia)\D{0,40}?(\d+)\s*/\s*(\d{4})", re.I)


def _origem_da_adesao(api, objeto: str, municipio: str, uf: str) -> list[dict]:
    """Localiza no PNCP o certame que gerou a ata aderida, a partir do texto do
    objeto ("Ata nº 040/2025, do Município de São José/SC, decorrente do Pregão
    Eletrônico nº 008/2024"). Só resolve atas de municípios; consórcios e órgãos
    federais ficam para a configuração manual."""
    entes = [(m.group(1).strip(), (m.group(2) or uf).upper()) for m in RE_ENTE.finditer(objeto or "")]
    entes = [e for e in entes if precos._ascii(e[0]).lower() != precos._ascii(municipio).lower()]
    cert = RE_CERTAME.search(objeto or "")
    if not entes or not cert:
        return []
    nome, uf_ente = entes[0]
    num, ano = int(cert.group(2)), int(cert.group(3))
    modalidades = (6, 7) if cert.group(1).lower().startswith("preg") else (4, 5)
    alvo = precos._ascii(nome).upper()
    nomes_ok = {f"MUNICIPIO DE {alvo}", f"PREFEITURA MUNICIPAL DE {alvo}", f"PREFEITURA DE {alvo}"}
    cnpjs = {o["cnpj"] for o in api.orgaos(f"MUNICIPIO DE {alvo}")
             if precos._ascii(o.get("razaoSocial") or "").upper().strip() in nomes_ok}
    achadas = []
    for cnpj in cnpjs:
        for mod in modalidades:
            for c in api.contratacoes(cnpj, date(ano, 1, 1), min(date(ano + 1, 3, 31), date.today()), mod):
                digitos = re.sub(r"\D", "", (c.get("numeroCompra") or "").split("/")[0])
                if (c.get("anoCompra") == ano and digitos and int(digitos) == num
                        and (c.get("unidadeOrgao") or {}).get("ufSigla") == uf_ente):
                    achadas.append(c)
    return achadas


def coletar(cfg_path: str, etapas=ETAPAS):
    cfg = yaml.safe_load(open(cfg_path, encoding="utf-8"))
    cnpj = cfg["orgao"]["cnpj"]
    inicio = date.fromisoformat(str(cfg["coleta"]["desde"]))
    fim = date.today()
    con = db.conectar(cfg["coleta"]["banco"])
    api = PNCP()

    if "contratacoes" in etapas:
        n = 0
        for mod, nome in MODALIDADES.items():
            k = 0
            for c in api.contratacoes(cnpj, inicio, fim, mod):
                db.salvar_contratacao(con, c); k += 1
            con.commit(); n += k
            if k:
                print(f"  {nome}: {k}", flush=True)
        print(f"contratações: {n}", flush=True)

    if "contratos" in etapas:
        n = 0
        for c in api.contratos(cnpj, inicio, fim):
            db.salvar_contrato(con, c); n += 1
            if n % 50 == 0:
                con.commit(); print(f"  contratos: {n}", flush=True)
        con.commit()
        print(f"contratos: {n}", flush=True)

    if "compras_externas" in etapas:
        # Contratos do município cuja compra foi feita por outro órgão (consórcios
        # como o CINCATARINA, atas de outros entes). Buscamos a compra de origem.
        pend = con.execute("""SELECT DISTINCT compra_id FROM contratos
                              WHERE compra_id IS NOT NULL
                                AND compra_id NOT IN (SELECT id FROM contratacoes)""").fetchall()
        n = 0
        for (cid,) in pend:
            cnpj_o, _, resto = cid.split("-", 2)
            seq, ano = resto.split("/")
            c = api.compra(cnpj_o, int(ano), int(seq))
            if c:
                db.salvar_contratacao(con, c, externa=cnpj_o != cnpj); n += 1
        con.commit()
        print(f"compras de outros órgãos: {n}/{len(pend)}", flush=True)

    if "termos" in etapas:
        # Um pedido por contrato. Reverifica só contratos atualizados no PNCP
        # depois da última verificação.
        pend = con.execute("""
          SELECT c.id, c.ano, c.seq FROM contratos c
          LEFT JOIN termos_verificados v ON v.contrato_id = c.id
          WHERE v.contrato_id IS NULL
             OR json_extract(c.bruto, '$.dataAtualizacaoGlobal') > v.verificado_em""").fetchall()
        n = 0
        for i, r in enumerate(pend, 1):
            for t in api.termos(cnpj, r["ano"], r["seq"]):
                db.salvar_termo(con, r["id"], t); n += 1
            con.execute("INSERT OR REPLACE INTO termos_verificados VALUES (?, datetime('now'))", (r["id"],))
            if i % 50 == 0:
                con.commit(); print(f"  termos: {i}/{len(pend)} contratos verificados, {n} aditivos", flush=True)
        con.commit()
        print(f"termos aditivos: {n}", flush=True)

    cp = cfg.get("precos") or {}
    minimo = cp.get("item_valor_minimo", 20000)

    if "itens" in etapas:
        # Itens das compras do município e das compras de outros órgãos que
        # geraram contratos dele (consórcio). Nas próprias, já baixa o preço
        # homologado dos itens relevantes; nas externas, os resultados são
        # escolhidos depois, pelos fornecedores contratados.
        pend = con.execute("""
          SELECT p.id, p.externa FROM contratacoes p LEFT JOIN itens_verificados v ON v.compra_id = p.id
          WHERE v.compra_id IS NULL
             OR json_extract(p.bruto, '$.dataAtualizacaoGlobal') > v.verificado_em""").fetchall()
        for i, (cid, externa) in enumerate(pend, 1):
            _coletar_itens(con, api, cid, None if externa else minimo)
            if i % 50 == 0:
                con.commit(); print(f"  itens: {i}/{len(pend)} compras", flush=True)
        con.commit()
        print(f"itens: {len(pend)} compras verificadas", flush=True)

        # Compras externas (consórcio): o resultado de cada item diz quem venceu,
        # e só interessam os itens vencidos por fornecedores contratados pelo município.
        pend = con.execute("""
          SELECT i.compra_id, i.numero FROM itens i JOIN contratacoes p ON p.id = i.compra_id
          LEFT JOIN resultados_verificados v ON v.compra_id = i.compra_id AND v.numero_item = i.numero
          WHERE p.externa = 1 AND i.tem_resultado = 1 AND v.compra_id IS NULL""").fetchall()
        for i, (cid, n) in enumerate(pend, 1):
            _coletar_resultados(con, api, cid, n)
            if i % 100 == 0:
                con.commit(); print(f"  resultados de compras externas: {i}/{len(pend)}", flush=True)
        con.commit()
        print(f"resultados de compras externas: {len(pend)}", flush=True)

    if "referencias" in etapas:
        _referencias(con, api, cfg, cp, minimo)


def _referencias(con, api, cfg, cp, minimo):
    """Compras de outros órgãos para comparar preços: municípios vizinhos e o
    certame de origem das adesões a atas."""
    cnpj = cfg["orgao"]["cnpj"]
    inicio = date.fromisoformat(str(cp.get("referencias_desde", cfg["coleta"]["desde"])))
    falhas = 0

    for nome, ibge in (cp.get("vizinhos") or {}).items():
        k, nomes = 0, set()
        for mod in cp.get("modalidades_referencia", (4, 6, 7)):
            try:
                for c in api.contratacoes_municipio(ibge, inicio, date.today(), mod):
                    nomes.add((c.get("unidadeOrgao") or {}).get("municipioNome"))
                    if (c.get("orgaoEntidade") or {}).get("cnpj") != cnpj:
                        db.salvar_referencia(con, c, "vizinho"); k += 1
            except RuntimeError as e:
                falhas += 1; print(f"  falha em {nome}: {e}", flush=True)
        con.commit()
        if nomes and precos._ascii(nome).lower() not in {precos._ascii(n or "").lower() for n in nomes}:
            print(f"  ATENÇÃO: o código {ibge} devolveu {sorted(nomes)}, não {nome}. Confira a configuração.", flush=True)
        print(f"  {nome}: {k} compras", flush=True)

    # Certame de origem das adesões: configuração manual primeiro, depois o texto do objeto.
    manuais = {str(k): v for k, v in (cp.get("origem_adesoes") or {}).items()}
    adesoes = con.execute("""SELECT id, processo, objeto FROM contratacoes
                             WHERE objeto LIKE 'Ades%' AND externa = 0""").fetchall()
    for a in adesoes:
        if a["processo"] in manuais:
            origens = manuais[a["processo"]]
            for oid in ([origens] if isinstance(origens, str) else origens):
                c = api.compra(*_partes(oid))
                if c:
                    db.salvar_referencia(con, c, "origem_adesao")
                    con.execute("INSERT OR REPLACE INTO adesao_origem VALUES (?, ?, datetime('now'))", (a["id"], oid))
            continue
        if con.execute("SELECT 1 FROM adesao_origem WHERE adesao_id = ?", (a["id"],)).fetchone():
            continue
        try:
            achadas = _origem_da_adesao(api, a["objeto"], cfg["municipio"], cfg["uf"])
        except RuntimeError as e:
            falhas += 1; print(f"  falha na origem da adesão {a['processo']}: {e}", flush=True)
            continue
        for c in achadas:
            db.salvar_referencia(con, c, "origem_adesao")
            con.execute("INSERT OR REPLACE INTO adesao_origem VALUES (?, ?, datetime('now'))", (a["id"], c["numeroControlePNCP"]))
        if not achadas:
            con.execute("INSERT OR REPLACE INTO adesao_origem VALUES (?, '', datetime('now'))", (a["id"],))
        print(f"  adesão {a['processo']}: " + (", ".join(c["numeroControlePNCP"] for c in achadas) or "origem não encontrada"), flush=True)
    con.commit()

    # Itens das compras de referência (um pedido por compra, só uma vez).
    pend = con.execute("""SELECT c.id FROM compras_referencia c
                          LEFT JOIN itens_verificados v ON v.compra_id = c.id
                          WHERE v.compra_id IS NULL""").fetchall()
    for i, (cid,) in enumerate(pend, 1):
        try:
            _coletar_itens(con, api, cid)
        except RuntimeError as e:
            falhas += 1; print(f"  falha nos itens de {cid}: {e}", flush=True)
        if i % 50 == 0:
            con.commit(); print(f"  itens de referência: {i}/{len(pend)} compras", flush=True)
    con.commit()

    # Resultado (preço homologado) só dos itens de referência parecidos com
    # algum item relevante do município: evita um pedido por item de cada compra.
    indice = precos.Indice([r for r in precos.itens_de_referencia(con) if r["tem_resultado"]])
    feitos = {(r[0], r[1]) for r in con.execute("SELECT compra_id, numero_item FROM resultados_verificados")}
    alvo = set()
    for it in precos.itens_do_municipio(con, minimo):
        for ref, _ in indice.similares(it["tokens"], it["unidade_norm"], cp.get("similaridade_minima", 0.7)):
            if (ref["compra_id"], ref["numero"]) not in feitos:
                alvo.add((ref["compra_id"], ref["numero"]))
    for i, (cid, n) in enumerate(sorted(alvo), 1):
        try:
            _coletar_resultados(con, api, cid, n)
        except RuntimeError as e:
            falhas += 1; print(f"  falha no resultado {cid} item {n}: {e}", flush=True)
        if i % 50 == 0:
            con.commit(); print(f"  resultados de referência: {i}/{len(alvo)}", flush=True)
    con.commit()
    n_ref = con.execute("SELECT COUNT(*) FROM compras_referencia").fetchone()[0]
    print(f"referências: {n_ref} compras, {len(alvo)} resultados novos, {falhas} falha(s)", flush=True)


if __name__ == "__main__":
    cfg = sys.argv[1] if len(sys.argv) > 1 else "config/tijucas.yaml"
    coletar(cfg, tuple(sys.argv[2:]) or ETAPAS)
