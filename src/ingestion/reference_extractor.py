import re

REFERENCE_SECTION_PATTERNS = [
    r"(?:参考文献|References|Bibliography)\s*\n([\s\S]+?)(?:\n\s*\n\s*\n|\Z)",
    r"(?:参考文献|References|Bibliography)\s*\n([\s\S]+)",
]


def extract_references(text: str) -> tuple[str, list[str]]:
    """返回 (去除参考文献后的正文, 参考文献列表)"""
    for pattern in REFERENCE_SECTION_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            refs_text = match.group(1)
            # 按编号分割：[1] 或 1. 开头
            refs = [
                r.strip()
                for r in re.split(r"\n(?=\[\d+\]|\d+[\.、])", refs_text)
                if r.strip()
            ]
            body = text[: match.start()].strip()
            return body, refs
    return text, []
