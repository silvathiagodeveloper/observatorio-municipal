"""Banco local (SQLite). Guardamos o JSON bruto de cada registro para auditoria
e colunas extraídas para as regras. Nada é apagado: a coleta só acrescenta
ou atualiza, preservando a trilha de evidências."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS contratacoes (
  id TEXT PRIMARY KEY,               -- numeroControlePNCP da compra
  ano INTEGER, seq INTEGER, processo TEXT, numero TEXT,
  modalidade_id INTEGER, modalidade TEXT, amparo_legal TEXT,
  objeto TEXT, valor_estimado REAL, valor_homologado REAL,
  data_publicacao TEXT, situacao TEXT, unidade TEXT, link TEXT,
  externa INTEGER DEFAULT 0,        -- 1 = compra feita por outro órgão (consórcio, ata de terceiro)
  orgao_cnpj TEXT, orgao_nome TEXT,
  bruto TEXT, coletado_em TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS contratos (
  id TEXT PRIMARY KEY,               -- numeroControlePNCP do contrato
  compra_id TEXT, ano INTEGER, seq INTEGER, numero TEXT, processo TEXT,
  tipo TEXT, categoria TEXT, objeto TEXT,
  fornecedor_ni TEXT, fornecedor_nome TEXT,
  valor_inicial REAL, valor_global REAL, valor_acumulado REAL,
  data_assinatura TEXT, vigencia_inicio TEXT, vigencia_fim TEXT, unidade TEXT,
  bruto TEXT, coletado_em TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS termos (
  contrato_id TEXT, sequencial INTEGER, tipo TEXT, objeto TEXT,
  valor_acrescido REAL, prazo_aditado_dias INTEGER, data_assinatura TEXT,
  bruto TEXT, PRIMARY KEY (contrato_id, sequencial)
);
CREATE TABLE IF NOT EXISTS termos_verificados (
  contrato_id TEXT PRIMARY KEY, verificado_em TEXT
);
-- Compras de outros órgãos usadas só como referência de preço (municípios
-- vizinhos, certame de origem de uma adesão). Ficam fora de contratacoes para
-- não entrar nas outras regras nem no volume do relatório.
CREATE TABLE IF NOT EXISTS compras_referencia (
  id TEXT PRIMARY KEY,               -- numeroControlePNCP da compra
  ano INTEGER, seq INTEGER, numero TEXT, modalidade TEXT, objeto TEXT, data_publicacao TEXT,
  orgao_cnpj TEXT, orgao_nome TEXT, municipio TEXT, uf TEXT,
  motivo TEXT,                       -- 'vizinho' ou 'origem_adesao'
  bruto TEXT, coletado_em TEXT DEFAULT CURRENT_TIMESTAMP
);
-- Itens e resultados valem para as duas tabelas de compras (compra_id).
CREATE TABLE IF NOT EXISTS itens (
  compra_id TEXT, numero INTEGER, descricao TEXT, unidade TEXT, quantidade REAL,
  valor_unitario_estimado REAL, valor_total REAL, tem_resultado INTEGER, situacao TEXT,
  bruto TEXT, PRIMARY KEY (compra_id, numero)
);
CREATE TABLE IF NOT EXISTS resultados (
  compra_id TEXT, numero_item INTEGER, sequencial INTEGER,
  fornecedor_ni TEXT, fornecedor_nome TEXT, quantidade REAL, valor_unitario REAL, data_resultado TEXT,
  bruto TEXT, PRIMARY KEY (compra_id, numero_item, sequencial)
);
CREATE TABLE IF NOT EXISTS itens_verificados (
  compra_id TEXT PRIMARY KEY, verificado_em TEXT
);
CREATE TABLE IF NOT EXISTS resultados_verificados (
  compra_id TEXT, numero_item INTEGER, verificado_em TEXT, PRIMARY KEY (compra_id, numero_item)
);
-- Certame de origem de cada adesão a ata de outro ente. origem_id vazio =
-- procurado e não encontrado (informe à mão em precos.origem_adesoes).
CREATE TABLE IF NOT EXISTS adesao_origem (
  adesao_id TEXT, origem_id TEXT, verificado_em TEXT, PRIMARY KEY (adesao_id, origem_id)
);
"""


def conectar(caminho: str | Path) -> sqlite3.Connection:
    Path(caminho).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(caminho)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    _migrar(con)
    return con


def _migrar(con):
    cols = {r[1] for r in con.execute("PRAGMA table_info(contratacoes)")}
    for col, tipo in (("externa", "INTEGER DEFAULT 0"), ("orgao_cnpj", "TEXT"), ("orgao_nome", "TEXT")):
        if col not in cols:
            con.execute(f"ALTER TABLE contratacoes ADD COLUMN {col} {tipo}")


def _j(x):
    return json.dumps(x, ensure_ascii=False)


def salvar_contratacao(con, c: dict, externa: bool = False):
    amparo = (c.get("amparoLegal") or {}).get("nome")
    con.execute("""INSERT OR REPLACE INTO contratacoes
      (id, ano, seq, processo, numero, modalidade_id, modalidade, amparo_legal, objeto,
       valor_estimado, valor_homologado, data_publicacao, situacao, unidade, link,
       externa, orgao_cnpj, orgao_nome, bruto)
      VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
        c["numeroControlePNCP"], c.get("anoCompra"), c.get("sequencialCompra"), c.get("processo"),
        c.get("numeroCompra"), c.get("modalidadeId"), c.get("modalidadeNome"), amparo,
        c.get("objetoCompra"), c.get("valorTotalEstimado"), c.get("valorTotalHomologado"),
        c.get("dataPublicacaoPncp"), c.get("situacaoCompraNome"),
        (c.get("unidadeOrgao") or {}).get("nomeUnidade"), c.get("linkSistemaOrigem"),
        int(externa), (c.get("orgaoEntidade") or {}).get("cnpj"),
        (c.get("orgaoEntidade") or {}).get("razaoSocial"), _j(c)))


def salvar_contrato(con, c: dict):
    con.execute("""INSERT OR REPLACE INTO contratos
      (id, compra_id, ano, seq, numero, processo, tipo, categoria, objeto, fornecedor_ni,
       fornecedor_nome, valor_inicial, valor_global, valor_acumulado, data_assinatura,
       vigencia_inicio, vigencia_fim, unidade, bruto)
      VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
        c["numeroControlePNCP"], c.get("numeroControlePncpCompra"), c.get("anoContrato"),
        c.get("sequencialContrato"), c.get("numeroContratoEmpenho"), c.get("processo"),
        (c.get("tipoContrato") or {}).get("nome"), (c.get("categoriaProcesso") or {}).get("nome"),
        c.get("objetoContrato"), c.get("niFornecedor"), c.get("nomeRazaoSocialFornecedor"),
        c.get("valorInicial"), c.get("valorGlobal"), c.get("valorAcumulado"),
        c.get("dataAssinatura"), c.get("dataVigenciaInicio"), c.get("dataVigenciaFim"),
        (c.get("unidadeOrgao") or {}).get("nomeUnidade"), _j(c)))


def salvar_referencia(con, c: dict, motivo: str):
    u = c.get("unidadeOrgao") or {}
    con.execute("""INSERT OR REPLACE INTO compras_referencia
      (id, ano, seq, numero, modalidade, objeto, data_publicacao, orgao_cnpj, orgao_nome,
       municipio, uf, motivo, bruto)
      VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
        c["numeroControlePNCP"], c.get("anoCompra"), c.get("sequencialCompra"), c.get("numeroCompra"),
        c.get("modalidadeNome"), c.get("objetoCompra"), c.get("dataPublicacaoPncp"),
        (c.get("orgaoEntidade") or {}).get("cnpj"), (c.get("orgaoEntidade") or {}).get("razaoSocial"),
        u.get("municipioNome"), u.get("ufSigla"), motivo, _j(c)))


def salvar_item(con, compra_id: str, i: dict):
    con.execute("""INSERT OR REPLACE INTO itens
      (compra_id, numero, descricao, unidade, quantidade, valor_unitario_estimado, valor_total,
       tem_resultado, situacao, bruto)
      VALUES (?,?,?,?,?,?,?,?,?,?)""", (
        compra_id, i.get("numeroItem"), i.get("descricao"), i.get("unidadeMedida"), i.get("quantidade"),
        i.get("valorUnitarioEstimado"), i.get("valorTotal"), int(bool(i.get("temResultado"))),
        i.get("situacaoCompraItemNome"), _j(i)))


def salvar_resultado(con, compra_id: str, r: dict):
    con.execute("""INSERT OR REPLACE INTO resultados
      (compra_id, numero_item, sequencial, fornecedor_ni, fornecedor_nome, quantidade,
       valor_unitario, data_resultado, bruto)
      VALUES (?,?,?,?,?,?,?,?,?)""", (
        compra_id, r.get("numeroItem"), r.get("sequencialResultado"), r.get("niFornecedor"),
        r.get("nomeRazaoSocialFornecedor"), r.get("quantidadeHomologada"), r.get("valorUnitarioHomologado"),
        r.get("dataResultado"), _j(r)))


def salvar_termo(con, contrato_id: str, t: dict):
    con.execute("""INSERT OR REPLACE INTO termos
      (contrato_id, sequencial, tipo, objeto, valor_acrescido, prazo_aditado_dias, data_assinatura, bruto)
      VALUES (?,?,?,?,?,?,?,?)""", (
        contrato_id, t.get("sequencialTermoContrato"), t.get("tipoTermoContratoNome"),
        t.get("objetoTermoContrato"), t.get("valorAcrescido"), t.get("prazoAditadoDias"),
        t.get("dataAssinatura"), _j(t)))
