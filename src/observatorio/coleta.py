"""Coleta do PNCP para um município configurado.

Uso:
  python -m observatorio.coleta config/tijucas.yaml              # todas as etapas
  python -m observatorio.coleta config/tijucas.yaml termos       # só uma etapa
Etapas: contratacoes, contratos, compras_externas, termos
"""
from __future__ import annotations

import sys
from datetime import date

import yaml

from . import db
from .pncp import MODALIDADES, PNCP

ETAPAS = ("contratacoes", "contratos", "compras_externas", "termos")


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


if __name__ == "__main__":
    cfg = sys.argv[1] if len(sys.argv) > 1 else "config/tijucas.yaml"
    coletar(cfg, tuple(sys.argv[2:]) or ETAPAS)
