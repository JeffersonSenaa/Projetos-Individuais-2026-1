"""Parsing de PDFs com PyMuPDF."""

from dataclasses import dataclass
from pathlib import Path

import fitz


@dataclass
class PageContent:
    """Conteúdo extraído de uma página do PDF."""

    page_number: int
    text: str
    is_likely_image: bool


def parse_pdf(pdf_path: Path) -> list[PageContent]:
    """
    Extrai texto de cada página do PDF.

    Páginas com menos de 50 caracteres são marcadas como provável slide/imagem
    rasterizada (sem texto embutido).

    Args:
        pdf_path: Caminho para o arquivo PDF.

    Returns:
        Lista de PageContent, uma entrada por página.
    """
    pages: list[PageContent] = []
    with fitz.open(pdf_path) as doc:
        for i, page in enumerate(doc):
            text = page.get_text("text").strip()
            is_likely_image = len(text) < 50
            pages.append(
                PageContent(
                    page_number=i + 1,
                    text=text,
                    is_likely_image=is_likely_image,
                )
            )
    return pages


def render_page_as_png(pdf_path: Path, page_number: int, dpi: int = 150) -> bytes:
    """
    Renderiza uma página do PDF como imagem PNG.

    Usado como fallback de vision para slides sem texto extraível.

    Args:
        pdf_path: Caminho do PDF.
        page_number: Número da página (1-indexed).
        dpi: Resolução da renderização.

    Returns:
        Bytes da imagem PNG.
    """
    with fitz.open(pdf_path) as doc:
        page = doc[page_number - 1]
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat)
        return pix.tobytes("png")
