# Social Eval Pilot

<p align="right">
  <a href="#english">English</a> | <a href="#chinese">中文</a>
</p>

<a id="english"></a>
<details open>
<summary><strong>English</strong></summary>

## Overview
An AI-assisted academic paper evaluation pilot for humanities and social-science workflows, starting from legal scholarship review and designed for broader domain adaptation.

## Highlights
- Uses a configurable multi-dimension evaluation framework instead of a single overall score.
- Supports concurrent scoring across multiple LLM providers and compares score variance for reliability checks.
- Routes low-confidence cases into a human expert review workflow.
- Keeps discipline-specific evaluation standards in YAML so the framework can expand beyond law without rewriting the core system.
- Organizes the repo as an MVP-oriented application skeleton spanning API, frontend, queueing, storage, and reporting.

## Repository Layout
- `src/ingestion/`: document intake and preprocessing.
- `src/knowledge/`: discipline framework configuration loading.
- `src/evaluation/`: multi-model scoring engine.
- `src/reliability/`: confidence and disagreement checks.
- `src/review/`: human-in-the-loop review workflow.
- `src/reporting/`: report generation layer.
- `src/api/`: backend API.
- `src/web/`: frontend application.

## Getting Started
```bash
uv sync --extra dev
docker-compose up -d
alembic upgrade head
uv run uvicorn src.api.main:app --reload --port 8000
```

</details>

<a id="chinese"></a>
<details>
<summary><strong>中文</strong></summary>

## 项目简介
这是一个面向人文社科论文流程的 AI 辅助评价试点系统，从法学论文评审切入，并为更广泛的学科迁移预留了空间。

## 项目亮点
- 使用可配置的多维评价框架，而不是单一总分。
- 支持多个大模型并发打分，并通过分数方差进行可靠性检查。
- 对低置信度案例自动引入人工专家复核流程。
- 将学科评价标准保存在 YAML 中，扩展到其他学科时不需要重写核心系统。
- 仓库按 MVP 应用骨架组织，覆盖 API、前端、任务队列、存储和报告输出。

## 仓库结构
- `src/ingestion/`：文档接收与预处理。
- `src/knowledge/`：学科框架配置加载。
- `src/evaluation/`：多模型评分引擎。
- `src/reliability/`：置信度与分歧检查模块。
- `src/review/`：人类在环复核流程。
- `src/reporting/`：报告生成层。
- `src/api/`：后端 API。
- `src/web/`：前端应用。

## 快速开始
```bash
uv sync --extra dev
docker-compose up -d
alembic upgrade head
uv run uvicorn src.api.main:app --reload --port 8000
```

</details>