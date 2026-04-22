from src.ingestion.parsers.base import BaseParser, RawDocument
from src.core.exceptions import IngestionError


class TxtParser(BaseParser):
    def parse(self, file_path: str) -> RawDocument:
        try:
            with open(file_path, encoding="utf-8", errors="replace") as f:
                text = f.read()
            return RawDocument(text=text, metadata={"format": "txt"})
        except Exception as e:
            raise IngestionError(f"TXT 解析失败：{e}") from e
