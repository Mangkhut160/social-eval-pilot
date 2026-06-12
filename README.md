# Social Eval Pilot

An AI-assisted academic paper evaluation pilot for humanities and social-science workflows, starting from legal scholarship review and designed for broader domain adaptation.

## Highlights
- Uses a configurable multi-dimension evaluation framework instead of a single overall score
- Supports concurrent scoring across multiple LLM providers and compares score variance for reliability checks
- Routes low-confidence cases into a human expert review workflow
- Keeps discipline-specific evaluation standards in YAML so the framework can expand beyond law without rewriting the core system
- Organizes the repo as an MVP-oriented application skeleton spanning API, frontend, queueing, storage, and reporting

## Evaluation Flow
1. Upload and preprocess a paper
2. Run multi-model scoring across the configured dimensions
3. Measure agreement and standard deviation across model outputs
4. Auto-approve high-confidence cases or send low-confidence cases to expert review
5. Export structured reports for editors and authors

## Repository Layout
- `src/ingestion/`: document intake and preprocessing
- `src/knowledge/`: discipline framework configuration loading
- `src/evaluation/`: multi-model scoring engine
- `src/reliability/`: confidence and disagreement checks
- `src/review/`: human-in-the-loop review workflow
- `src/reporting/`: report generation layer
- `src/api/`: backend API
- `src/web/`: frontend application

## Status
This repository is best understood as a pilot / MVP foundation. It is already organized around deployment, operations, and architecture documentation, but its strongest value on a resume is the system design and product-thinking story: configurable evaluation standards, reliability control, and explicit human oversight.

## Getting Started
```bash
uv sync --extra dev
docker-compose up -d
alembic upgrade head
uv run uvicorn src.api.main:app --reload --port 8000
```