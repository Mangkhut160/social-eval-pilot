from pydantic import BaseModel


class ProcessedPaper(BaseModel):
    abstract: str = ""
    introduction: str = ""
    body: str = ""
    conclusion: str = ""
    references: list[str] = []
    full_text: str
    structure_status: str  # "detected" | "degraded"
    warnings: list[str] = []
