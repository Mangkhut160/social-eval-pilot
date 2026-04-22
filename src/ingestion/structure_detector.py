import re
from src.ingestion.schemas import ProcessedPaper

# 常见章节标题正则：支持中文编号、阿拉伯数字、罗马字、关键字
SECTION_PATTERNS = [
    r"^(?:一|二|三|四|五|六|七|八|九|十)[、．]\s*.+",
    r"^\d+\.\s*[^\d].+",
    r"^(?:Abstract|摘\s*要|引\s*言|结\s*论|参考文献)",
]
COMBINED_PATTERN = re.compile("|".join(SECTION_PATTERNS), re.MULTILINE)


def detect_structure(text: str) -> ProcessedPaper:
    """
    尝试识别论文章节结构。
    - 识别成功（≥3 个标题命中）→ structure_status="detected"
    - 识别失败 → 降级为全文分段，structure_status="degraded"
    """
    matches = list(COMBINED_PATTERN.finditer(text))

    if len(matches) < 3:
        return ProcessedPaper(
            full_text=text,
            body=text,
            structure_status="degraded",
            warnings=[
                f"章节结构识别失败（命中标题 {len(matches)} 个，< 3），"
                "已降级为全文分段模式，评分可能受影响"
            ],
        )

    sections: dict[str, str] = {}
    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        title = match.group().strip().lower()
        content = text[start:end].strip()

        if any(k in title for k in ["摘要", "abstract"]):
            sections["abstract"] = content
        elif any(k in title for k in ["引言", "introduction"]):
            sections["introduction"] = content
        elif any(k in title for k in ["结论", "conclusion"]):
            sections["conclusion"] = content
        else:
            sections["body"] = sections.get("body", "") + "\n" + content

    return ProcessedPaper(
        full_text=text,
        abstract=sections.get("abstract", ""),
        introduction=sections.get("introduction", ""),
        body=sections.get("body", "").strip(),
        conclusion=sections.get("conclusion", ""),
        structure_status="detected",
    )
