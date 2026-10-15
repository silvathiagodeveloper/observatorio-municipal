"""Coleta do PNCP para um município configurado.

Uso:  python -m observatorio.coleta config/tijucas.yaml
"""
from __future__ import annotations

import sys
from datetime import date

import yaml

from . import db
from .pncp import MODALIDADES, PNCP


def coletar(cfg_path: str):
    cfg = yaml.safe_load(open(cfg_path, encoding="utf-8"))
    cnpj = cfg["orgao"]["cnpj"]
    inicio = date.fromisoformat(str(cfg["coleta"]["desde"]))
    fim = date.today()
    con = db.conectar(cfg["coleta"]["banco"])
    api = PNCP()

    n = 0
    for mod in MODALIDADES:
        for c in api.contratacoes(cnpj, inicio, fim, mod):
            db.salvar_contratacao(con, c); n += 1
        con.commit()
    print(f"contratações: {n}")

    n = 0
    for c in api.contratos(cnpj, inicio, fim):
        db.salvar_contrato(con, c); n += 1
    con.commit()
    print(f"contratos: {n}")

    # Termos aditivos: um pedido por contrato (só os que ainda não temos)
    pend = con.execute("""SELECT id, ano, seq FROM contratos
                          WHERE id NOT IN (SELECT DISTINCT contrato_id FROM termos)""").fetchall()
    n = 0
    for i, r in enumerate(pend, 1):
        for t in api.termos(cnpj, r["ano"], r["seq"]):
            db.salvar_termo(con, r["id"], t); n += 1
        if i % 50 == 0:
            con.commit(); print(f"  termos: {i}/{len(pend)} contratos verificados")
    con.commit()
    print(f"termos aditivos: {n}")


if __name__ == "__main__":
    coletar(sys.argv[1] if len(sys.argv) > 1 else "config/tijucas.yaml")
