from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class RawDocument:
    text: str
    metadata: dict = field(default_factory=dict)


class BaseParser(ABC):
    @abstractmethod
    def parse(self, file_path: str) -> RawDocument:
        """解析文件，返回原始文本和元数据"""
