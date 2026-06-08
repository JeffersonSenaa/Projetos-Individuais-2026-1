"""Estratégia híbrida de chunking semântico."""

from dataclasses import dataclass

from src.extraction.parser import PageContent

KEYWORDS = {
    "vendas",
    "vso",
    "estoque",
    "unidades",
    "receita",
    "vgv",
    "margem",
    "obras",
    "operacional",
    "previa",
    "prévia",
    "resultado",
    "incorporação",
    "incorporacao",
}

FULL_SCAN_PAGE_THRESHOLD = 15


@dataclass
class DocumentChunk:
    """Trecho do documento enviado ao LLM para extração."""

    chunk_id: str
    page_number: int
    text: str
    is_image: bool = False


def _is_relevant(text: str) -> bool:
    """
    Verifica se o texto contém palavras-chave operacionais do setor habitacional.

    Args:
        text: Conteúdo textual da página.

    Returns:
        True se alguma keyword operacional for encontrada.
    """
    lower = text.lower()
    return any(kw in lower for kw in KEYWORDS)


def chunk_document(pages: list[PageContent]) -> list[DocumentChunk]:
    """
    Divide o documento em chunks para envio ao LLM (estratégia híbrida).

    - Documentos curtos (<=15 páginas): full-scan — todas as páginas vão ao LLM.
    - Documentos longos: apenas páginas com keywords operacionais.
    - Páginas sem texto: marcadas como imagem para extração via vision.
    - Fallback: se nenhum chunk for selecionado, usa a primeira página.

    Args:
        pages: Páginas parseadas do PDF.

    Returns:
        Lista de chunks prontos para extração semântica.
    """
    use_full_scan = len(pages) <= FULL_SCAN_PAGE_THRESHOLD
    chunks: list[DocumentChunk] = []

    for page in pages:
        if page.is_likely_image:
            chunks.append(
                DocumentChunk(
                    chunk_id=f"p{page.page_number}_img",
                    page_number=page.page_number,
                    text="",
                    is_image=True,
                )
            )
            continue

        if use_full_scan or _is_relevant(page.text):
            chunks.append(
                DocumentChunk(
                    chunk_id=f"p{page.page_number}",
                    page_number=page.page_number,
                    text=page.text,
                    is_image=False,
                )
            )

    if not chunks and pages:
        chunks.append(
            DocumentChunk(
                chunk_id="p1_fallback",
                page_number=1,
                text=pages[0].text,
                is_image=pages[0].is_likely_image,
            )
        )

    return chunks
