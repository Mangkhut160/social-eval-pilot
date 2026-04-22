from pathlib import Path
from src.core.text import sanitize_nul_chars
from src.ingestion.parsers.base import BaseParser
from src.ingestion.parsers.pdf_parser import PDFParser
from src.ingestion.parsers.docx_parser import DocxParser
from src.ingestion.parsers.txt_parser import TxtParser
from src.ingestion.reference_extractor import extract_references
from src.ingestion.structure_detector import detect_structure
from src.ingestion.schemas import ProcessedPaper
from src.core.exceptions import IngestionError

PARSERS: dict[str, type[BaseParser]] = {
    "pdf": PDFParser,
    "docx": DocxParser,
    "txt": TxtParser,
}


def process_file(file_path: str) -> ProcessedPaper:
    """主入口：根据文件扩展名选择 Parser，返回 ProcessedPaper"""
    ext = Path(file_path).suffix.lower().lstrip(".")
    parser_cls = PARSERS.get(ext)
    if not parser_cls:
        raise IngestionError(f"不支持的文件类型：{ext}")

    raw = parser_cls().parse(file_path)
    sanitized_text = sanitize_nul_chars(raw.text)
    body_text, refs = extract_references(sanitized_text)
    paper = detect_structure(body_text)
    paper.abstract = sanitize_nul_chars(paper.abstract)
    paper.introduction = sanitize_nul_chars(paper.introduction)
    paper.body = sanitize_nul_chars(paper.body)
    paper.conclusion = sanitize_nul_chars(paper.conclusion)
    paper.references = sanitize_nul_chars(refs)
    paper.warnings = sanitize_nul_chars(paper.warnings)
    paper.full_text = sanitized_text
    return paper
