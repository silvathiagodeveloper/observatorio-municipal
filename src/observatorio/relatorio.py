"""Gera o relatório em Markdown a partir de dados/alertas.json.

Se existir dados/revisao.json (saída do agente revisor), os alertas são
agrupados por classificação; caso contrário, saem como 'não revisados'.

Uso:  python -m observatorio.relatorio config/tijucas.yaml
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import yaml

from . import db
from .regras import brl

ROTULO = {"alta": "🔴 Alta", "media": "🟠 Média", "baixa": "⚪ Baixa"}


def gerar(cfg_path: str) -> Path:
    cfg = yaml.safe_load(open(cfg_path, encoding="utf-8"))
    base = Path(cfg["coleta"]["banco"]).parent
    con = db.conectar(cfg["coleta"]["banco"])
    alertas = json.loads((base / "alertas.json").read_text(encoding="utf-8"))
    rev_path = base / "revisao.json"
    revisao = json.loads(rev_path.read_text(encoding="utf-8")) if rev_path.exists() else {}

    n_compras, v_compras = con.execute("SELECT COUNT(*), SUM(COALESCE(valor_homologado, valor_estimado)) FROM contratacoes").fetchone()
    n_contr, v_contr = con.execute("SELECT COUNT(*), SUM(COALESCE(valor_global, valor_inicial)) FROM contratos").fetchone()
    n_termos = con.execute("SELECT COUNT(*) FROM termos").fetchone()[0]

    L = [f"# Relatório — {cfg['municipio']}/{cfg['uf']}", "",
         f"Gerado em {date.today():%d/%m/%Y}. Fonte: PNCP, desde {cfg['coleta']['desde']}.", "",
         "> Este relatório lista **indícios** gerados por regras automáticas. Nenhum item é conclusão de irregularidade. "
         "Leia a seção *como verificar* de cada caso antes de qualquer encaminhamento.", "",
         "## Volume analisado", "",
         f"- {n_compras} contratações publicadas ({brl(v_compras)})",
         f"- {n_contr} contratos ({brl(v_contr)})",
         f"- {n_termos} termos aditivos", ""]

    for grav in ("alta", "media", "baixa"):
        itens = [a for a in alertas if a["gravidade"] == grav]
        if not itens:
            continue
        L += [f"## Gravidade {ROTULO[grav]} ({len(itens)})", ""]
        for i, a in enumerate(itens, 1):
            r = revisao.get(a["titulo"], {})
            L += [f"### {i}. {a['titulo']}", ""]
            if r:
                L += [f"**Revisão:** {r.get('classificacao', '—')}. {r.get('justificativa', '')}", ""]
            L += [a["descricao"], "", "**Evidências:** " + ", ".join(f"[{j+1}]({u})" for j, u in enumerate(a["evidencias"][:8])), "",
                  "**Pode ter explicação legítima se:**"] + [f"- {x}" for x in a["explicacoes_legitimas"]] + [
                  "", "**Como verificar:**"] + [f"- {x}" for x in a["como_verificar"]] + [
                  "", f"**Encaminhamento sugerido:** {a['encaminhamento']}", ""]
    out = base / "relatorio.md"
    out.write_text("\n".join(L), encoding="utf-8")
    print(out)
    return out


if __name__ == "__main__":
    gerar(sys.argv[1] if len(sys.argv) > 1 else "config/tijucas.yaml")
