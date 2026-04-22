import fitz  # PyMuPDF
from src.ingestion.parsers.base import BaseParser, RawDocument
from src.core.exceptions import IngestionError


class PDFParser(BaseParser):
    def parse(self, file_path: str) -> RawDocument:
        try:
            doc = fitz.open(file_path)
            pages = [page.get_text() for page in doc]
            return RawDocument(
                text="\n".join(pages),
                metadata={"page_count": len(pages), "format": "pdf"},
            )
        except Exception as e:
            raise IngestionError(f"PDF 解析失败：{e}") from e
