"""Scraper de Centrais de Resultados das construtoras."""

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin

import httpx
import yaml
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

PREVIA_KEYWORDS = re.compile(
    r"pr[eé]via\s+operacional|operational\s+preview|preview\s+operacional",
    re.IGNORECASE,
)


@dataclass
class SourceConfig:
    """Configuração de uma fonte RI definida em sources.yaml."""

    empresa: str
    ri_url: str
    resultados_path: str = ""


@dataclass
class DiscoveredPDF:
    """PDF de Prévia Operacional descoberto pelo scraper."""

    empresa: str
    url: str
    link_text: str


def load_sources(config_path: Path | None = None) -> list[SourceConfig]:
    """
    Carrega lista de construtoras e URLs do arquivo sources.yaml.

    Args:
        config_path: Caminho opcional; usa config/sources.yaml por padrão.

    Returns:
        Lista de SourceConfig para cada construtora configurada.
    """
    if config_path is None:
        config_path = Path(__file__).resolve().parents[2] / "config" / "sources.yaml"
    with open(config_path) as f:
        data = yaml.safe_load(f)
    return [SourceConfig(**s) for s in data.get("sources", [])]


class RIScraper:
    """Descobre links de Prévia Operacional nas Centrais de Resultados."""

    def __init__(self) -> None:
        """Inicializa scraper com User-Agent identificável para acesso respeitoso."""
        self.headers = {"User-Agent": "UDA-Habitacional-Bot/1.0 (projeto-academico-unb)"}

    def _fetch(self, url: str) -> str:
        """
        Faz requisição HTTP GET e retorna o HTML da página.

        Args:
            url: URL da página de Central de Resultados.

        Returns:
            Conteúdo HTML da resposta.

        Raises:
            httpx.HTTPError: Se a requisição falhar.
        """
        with httpx.Client(follow_redirects=True, timeout=30.0, headers=self.headers) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.text

    def discover_pdfs(self, source: SourceConfig) -> list[DiscoveredPDF]:
        """
        Varre a página de resultados de uma construtora buscando PDFs de Prévia Operacional.

        Filtra links .pdf cujo texto ou URL contenha keywords de prévia operacional.

        Args:
            source: Configuração da construtora (empresa, URL, path).

        Returns:
            Lista de PDFs descobertos; lista vazia se a página for inacessível.
        """
        base_url = source.ri_url.rstrip("/")
        target_url = urljoin(base_url + "/", source.resultados_path.lstrip("/")) if source.resultados_path else base_url

        try:
            html = self._fetch(target_url)
        except Exception as e:
            logger.warning("Falha ao acessar %s: %s", target_url, e)
            return []

        soup = BeautifulSoup(html, "html.parser")
        discovered: list[DiscoveredPDF] = []

        for link in soup.find_all("a", href=True):
            href = link["href"]
            text = link.get_text(strip=True)
            full_url = urljoin(target_url, href)

            if not full_url.lower().endswith(".pdf"):
                continue

            combined = f"{text} {full_url}"
            if PREVIA_KEYWORDS.search(combined) or "previa" in combined.lower():
                discovered.append(
                    DiscoveredPDF(empresa=source.empresa, url=full_url, link_text=text)
                )

        logger.info("Encontrados %d PDFs para %s", len(discovered), source.empresa)
        return discovered

    def scan_all_sources(self, config_path: Path | None = None) -> list[DiscoveredPDF]:
        """
        Varre todas as construtoras configuradas em sources.yaml.

        Args:
            config_path: Caminho opcional do arquivo de fontes.

        Returns:
            Lista agregada de todos os PDFs descobertos.
        """
        sources = load_sources(config_path)
        all_pdfs: list[DiscoveredPDF] = []
        for source in sources:
            all_pdfs.extend(self.discover_pdfs(source))
        return all_pdfs
