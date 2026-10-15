"""Cliente mínimo e educado para a API pública do PNCP.

Documentação: https://pncp.gov.br/api/consulta/swagger-ui/index.html
Não exige autenticação. Respeitamos um intervalo entre chamadas e fazemos
poucas tentativas em caso de erro — sem insistência.
"""
from __future__ import annotations

import time
from datetime import date, timedelta
from typing import Iterator

import requests

CONSULTA = "https://pncp.gov.br/api/consulta/v1"
PNCP_API = "https://pncp.gov.br/api/pncp/v1"

# Modalidades de contratação (tabela de domínio do PNCP)
MODALIDADES = {
    1: "Leilão - Eletrônico", 2: "Diálogo Competitivo", 3: "Concurso",
    4: "Concorrência - Eletrônica", 5: "Concorrência - Presencial",
    6: "Pregão - Eletrônico", 7: "Pregão - Presencial", 8: "Dispensa",
    9: "Inexigibilidade", 10: "Manifestação de Interesse",
    11: "Pré-qualificação", 12: "Credenciamento", 13: "Leilão - Presencial",
}


class PNCP:
    def __init__(self, intervalo: float = 0.4, tentativas: int = 3, timeout: int = 60):
        self.s = requests.Session()
        self.s.headers["User-Agent"] = "observatorio-municipal/0.1 (controle social; codigo aberto)"
        self.intervalo, self.tentativas, self.timeout = intervalo, tentativas, timeout

    def _get(self, url: str, params: dict | None = None):
        for i in range(self.tentativas):
            time.sleep(self.intervalo)
            try:
                r = self.s.get(url, params=params, timeout=self.timeout)
            except requests.RequestException:
                time.sleep(2 * (i + 1))
                continue
            if r.status_code == 204:
                return None
            if r.status_code == 200:
                return r.json()
            if r.status_code == 429:
                # Limite de requisições do PNCP: esperamos o que o servidor pedir.
                espera = r.headers.get("Retry-After", "")
                time.sleep(int(espera) if espera.isdigit() else 30 * (i + 1))
                continue
            if r.status_code in (500, 502, 503, 504):
                time.sleep(2 * (i + 1))
                continue
            r.raise_for_status()
        raise RuntimeError(f"PNCP não respondeu após {self.tentativas} tentativas: {url} {params}")

    def _paginado(self, url: str, params: dict, tamanho: int = 50) -> Iterator[dict]:
        pagina = 1
        while True:
            d = self._get(url, {**params, "pagina": pagina, "tamanhoPagina": tamanho})
            if not d or not d.get("data"):
                return
            yield from d["data"]
            if not d.get("paginasRestantes"):
                return
            pagina += 1

    @staticmethod
    def _janelas(inicio: date, fim: date, dias: int = 365):
        a = inicio
        while a <= fim:
            b = min(a + timedelta(days=dias - 1), fim)
            yield a.strftime("%Y%m%d"), b.strftime("%Y%m%d")
            a = b + timedelta(days=1)

    def contratos(self, cnpj: str, inicio: date, fim: date) -> Iterator[dict]:
        for di, df in self._janelas(inicio, fim):
            yield from self._paginado(f"{CONSULTA}/contratos",
                                      {"dataInicial": di, "dataFinal": df, "cnpjOrgao": cnpj})

    def contratacoes(self, cnpj: str, inicio: date, fim: date, modalidade: int) -> Iterator[dict]:
        for di, df in self._janelas(inicio, fim):
            yield from self._paginado(f"{CONSULTA}/contratacoes/publicacao",
                                      {"dataInicial": di, "dataFinal": df, "cnpj": cnpj,
                                       "codigoModalidadeContratacao": modalidade})

    def contratacoes_municipio(self, ibge: int, inicio: date, fim: date, modalidade: int) -> Iterator[dict]:
        """Compras de todos os órgãos com unidade no município (prefeitura, câmara, fundos)."""
        for di, df in self._janelas(inicio, fim):
            yield from self._paginado(f"{CONSULTA}/contratacoes/publicacao",
                                      {"dataInicial": di, "dataFinal": df, "codigoMunicipioIbge": ibge,
                                       "codigoModalidadeContratacao": modalidade})

    def orgaos(self, razao_social: str, paginas: int = 5) -> Iterator[dict]:
        """Busca órgãos por parte da razão social (a API devolve correspondências parciais)."""
        for pagina in range(1, paginas + 1):
            d = self._get(f"{PNCP_API}/orgaos/", {"razaoSocial": razao_social, "pagina": pagina})
            if not d:
                return
            yield from d

    def compra(self, cnpj: str, ano: int, seq: int) -> dict | None:
        """Uma contratação específica, de qualquer órgão (ex.: consórcio que licitou pelo município)."""
        return self._get(f"{CONSULTA}/orgaos/{cnpj}/compras/{ano}/{seq}")

    def termos(self, cnpj: str, ano: int, seq: int) -> list[dict]:
        return self._get(f"{PNCP_API}/orgaos/{cnpj}/contratos/{ano}/{seq}/termos") or []

    def itens(self, cnpj: str, ano: int, seq: int) -> list[dict]:
        return self._get(f"{PNCP_API}/orgaos/{cnpj}/compras/{ano}/{seq}/itens") or []

    def resultados(self, cnpj: str, ano: int, seq: int, item: int) -> list[dict]:
        return self._get(f"{PNCP_API}/orgaos/{cnpj}/compras/{ano}/{seq}/itens/{item}/resultados") or []
