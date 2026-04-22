# SocialEval MVP Milestones Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 1 周内交付 SocialEval 最小 MVP 闭环，并在此基础上按业务依赖顺序迭代到需求 `v0.4` 的 v1 范围。

**Architecture:** 以现有 Python/FastAPI 后端骨架为基础，优先打通“上传论文 → 预处理 → 多模型评分 → 可靠性判断 → 内部报告查看”主链路。后续里程碑再逐步补齐专家复核、公开报告、审计、批量任务和管理员恢复能力，避免在第一周同时铺开 Web 全角色、PDF 导出和运营后台。

**Tech Stack:** Python 3.10+, FastAPI, SQLAlchemy, Alembic, PostgreSQL, Redis, Celery, Pydantic, PyMuPDF, python-docx, PyYAML, pytest, httpx

---

## Milestone Summary

| Milestone | 时间目标 | 交付重点 | 成功标准 |
|----------|----------|----------|----------|
| M0 | 0.5 天 | 冻结一周 MVP 边界与接口口径 | 团队对范围、接口、延后项无歧义 |
| M1 | 1 周内 | 单篇论文自动评审闭环 | 能上传、评审、查状态、看内部报告 |
| M2 | 第 2 周 | 专家复核工作流 | 低置信度任务可进入复核并完成多人并行复核 |
| M3 | 第 3 周 | 报告版本化与访问审计 | 公开/内部报告隔离、可追溯、可导出 |
| M4 | 第 4 周 | 批量任务与恢复运维 | 技术失败可恢复，批量任务可追踪 |

## Scope Decisions

- 一周 MVP 仅覆盖内部可演示链路，不把投稿人公开门户和专家完整门户列为第 1 周硬门槛。
- OCR、扫描版 PDF 复杂解析、期刊系统预置对接、回调通知，不进入 v1 第一阶段。
- 默认仅启用 `configs/frameworks/law_v1.yaml` 作为第一阶段知识体系。
- 第一阶段报告以 JSON 和最小可视化为主，PDF 导出延后到 M3。
- 所有 AI 调用必须继续通过 `src/evaluation/providers/` 抽象层，不允许业务逻辑直接调用 SDK。

## Pre-Execution Cleanup

- 删除未完成的草稿文件，避免后续实现时误把中断状态当成正式基线：
  - `src/api/dependencies.py`
  - `tests/test_api/test_mvp_flow.py`
- 开始 M1 前先确认仓库中不存在引用 `src.main`、`create_app`、`/api/papers` 的半成品代码路径。
- 若执行人准备重新开启 M1，必须从“先写失败测试”重新开始，不得复用中断时的未验证代码片段。

## File Map

**现有可复用模块**

- `src/ingestion/`: 已有预处理、参考文献抽取、结构识别基础能力
- `src/knowledge/`: 已有 YAML 加载、schema 校验、权重校验
- `src/evaluation/`: 已有 prompt 构造、provider 抽象、并发评分基础
- `src/reliability/`: 已有均值/标准差/置信度计算
- `src/models/`: 已有论文、任务、评分、可靠性、报告、复核等基础模型

**M1 预计新增或补齐**

- Create: `src/main.py`
- Create: `src/api/dependencies.py`
- Create: `src/api/routers/papers.py`
- Create: `src/services/evaluation_pipeline.py`
- Create: `src/reporting/internal_report_builder.py`
- Modify: `src/core/config.py`
- Modify: `src/core/database.py`
- Modify: `src/models/paper.py`
- Modify: `src/models/evaluation.py`
- Modify: `src/models/report.py`
- Modify: `src/api/routers/__init__.py`
- Test: `tests/test_api/test_mvp_flow.py`
- Test: `tests/test_reliability/test_internal_report_builder.py`
- Test: `tests/test_reporting/test_internal_report_builder.py`

**M2 预计新增或补齐**

- Create: `src/review/service.py`
- Create: `src/api/routers/reviews.py`
- Create: `src/tasks/notifications.py`
- Modify: `src/models/review.py`
- Modify: `src/models/paper.py`
- Test: `tests/test_review/test_review_workflow.py`
- Test: `tests/test_api/test_review_api.py`

**M3 预计新增或补齐**

- Create: `src/reporting/public_report_builder.py`
- Create: `src/reporting/exporters/pdf_exporter.py`
- Create: `src/reporting/exporters/json_exporter.py`
- Create: `src/models/audit.py`
- Modify: `src/models/report.py`
- Modify: `src/api/routers/papers.py`
- Test: `tests/test_reporting/test_public_report.py`
- Test: `tests/test_api/test_report_permissions.py`

**M4 预计新增或补齐**

- Create: `src/tasks/recovery.py`
- Create: `src/api/routers/admin.py`
- Modify: `src/models/paper.py`
- Modify: `src/knowledge/version_manager.py`
- Test: `tests/test_api/test_batch_tasks.py`
- Test: `tests/test_api/test_admin_recovery.py`

## M0: 范围冻结与接口基线

### 目标

- 锁定一周 MVP 的业务边界、接口口径、状态模型和延后项。

### 交付内容

- 统一以 `docs/requirements/SocialEval-requirements-v0.4.md` 为开发基线。
- 在 `docs/architecture/` 新增一页 ADR，明确：
  - M1 仅交付内部评审闭环
  - M1 不包含专家复核、公开报告、PDF 导出、批量任务
  - 任务状态第一阶段最少支持 `pending / processing / completed / closed`
  - 失败原因采用独立字段，不把失败类型塞进主状态

### 验收标准

- 团队可以用同一套措辞描述 M1 做什么、不做什么。
- 后续任务拆分不再讨论“第一周要不要做专家复核或公开门户”。

## M1: 一周最小 MVP 闭环

### 目标

- 打通单篇论文自动评审最小链路，支持内部角色上传、评审、查状态和查看内部完整报告。

### 用户路径

1. 编辑或管理员携带 Token 上传论文
2. 系统校验文件类型并保存原始文件
3. 系统执行预处理，抽取正文、参考文献、结构状态
4. 系统按默认法学框架逐维评分
5. 系统计算每维均值、标准差和高低置信度
6. 系统生成内部完整报告并持久化
7. 编辑或管理员查询任务状态与内部报告

### 一周排期建议

- Day 1: 冻结接口与状态口径，补应用入口与最小鉴权骨架
- Day 2: 完成上传入口、文件保存、文件类型校验、扫描版 PDF 拒绝逻辑
- Day 3: 串起评审编排服务，打通预处理、框架加载、并发评分和可靠性计算
- Day 4: 生成内部完整报告并暴露状态/报告查询接口
- Day 5: 补测试、补失败口径、整理 Alembic/模型差异并完成端到端验证
- Day 6-7: 缓冲，只用于修复主链路缺陷和补最小文档，不新增 M2 范围功能

### 接口口径

- `POST /api/papers`
  - 入参：单个文件上传，可选 `framework_name`，默认 `law_v1`
  - 返回：`paper_id`、`task_id`、`status`
- `GET /api/papers/{id}/status`
  - 返回：`paper_id`、`task_id`、`status`、`failure_reason`
- `GET /api/papers/{id}/internal-report`
  - 仅 `editor` / `admin` / 后续 `expert` 可访问
  - 返回内部完整报告 JSON

### 非目标

- 不在 M1 内实现专家分配、邮件通知、公开报告、PDF 导出、批量任务、管理员恢复。
- 不在 M1 内引入完整 Web 角色门户；Swagger 或最小内部页面足以支撑演示。
- 不在 M1 内做“可配置任意多模型”后台界面，默认并发数按配置固定。

### 内部报告字段最低要求

- `paper_id`
- `task_id`
- `weighted_total`
- `summary.overall_high_confidence`
- `summary.low_confidence_dimensions`
- `dimensions[]`
- `dimensions[].dimension_key`
- `dimensions[].dimension_name`
- `dimensions[].weight`
- `dimensions[].mean`
- `dimensions[].std`
- `dimensions[].is_high_confidence`
- `dimensions[].model_scores`
- `dimensions[].evidence_quotes`
- `dimensions[].analysis`
- `dimensions[].results`

### M1 Task 1: 应用入口与依赖注入

**Files:**
- Create: `src/main.py`
- Create: `src/api/dependencies.py`
- Modify: `src/api/routers/__init__.py`
- Test: `tests/test_api/test_mvp_flow.py`

- [ ] **Step 1: 写失败测试，约束应用可创建并暴露 `papers` 路由**

```python
def test_upload_then_fetch_status_and_internal_report():
    client = TestClient(create_app(...))
    response = client.post("/api/papers", ...)
    assert response.status_code == 201
```

- [ ] **Step 2: 运行测试确认当前失败**

Run: `uv run pytest tests/test_api/test_mvp_flow.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.main'`

- [ ] **Step 3: 实现最小应用工厂**

```python
def create_app(session_factory=None, evaluation_service=None) -> FastAPI:
    app = FastAPI(title="SocialEval")
    app.state.session_factory = session_factory or SessionLocal
    app.state.evaluation_service = evaluation_service or EvaluationPipelineService(...)
    app.include_router(papers_router, prefix="/api")
    return app
```

- [ ] **Step 4: 增加 Token 解码和角色校验依赖**

```python
def require_role(*allowed_roles: str):
    payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    if payload["role"] not in allowed_roles:
        raise HTTPException(status_code=403, detail="权限不足")
```

- [ ] **Step 5: 运行测试确认进入下一层失败或局部通过**

Run: `uv run pytest tests/test_api/test_mvp_flow.py -q`
Expected: 由“应用入口缺失”推进到“路由/服务尚未实现”的失败

- [ ] **Step 6: 提交当前最小骨架**

```bash
git add src/main.py src/api/dependencies.py src/api/routers/__init__.py tests/test_api/test_mvp_flow.py
git commit -m "feat: add mvp app bootstrap and auth skeleton"
```

### M1 Task 2: 上传入口与文件校验

**Files:**
- Create: `src/api/routers/papers.py`
- Modify: `src/core/config.py`
- Modify: `src/models/paper.py`
- Test: `tests/test_api/test_mvp_flow.py`

- [ ] **Step 1: 写失败测试，约束非法文件与扫描版 PDF 会被拦截**

```python
def test_scan_pdf_is_rejected_before_evaluation():
    response = client.post("/api/papers", files={"file": (...)})
    assert response.status_code == 422
    assert "扫描版 PDF" in response.json()["detail"]
```

- [ ] **Step 2: 运行该测试确认失败**

Run: `uv run pytest tests/test_api/test_mvp_flow.py::test_scan_pdf_is_rejected_before_evaluation -q`
Expected: FAIL because endpoint is missing or validation is absent

- [ ] **Step 3: 实现最小上传入口**

```python
@router.post("/papers", status_code=201)
def upload_paper(file: UploadFile, payload=Depends(require_role("editor", "admin"))):
    validate_extension(file.filename)
    saved_path = save_upload(file)
    reject_scanned_pdf_if_needed(saved_path)
    result = evaluation_service.evaluate_file(...)
    return result
```

- [ ] **Step 4: 为 `Paper` 增加最小状态字段**

```python
status: str = "pending"
failure_reason: str | None = None
processing_stage: str | None = None
```

- [ ] **Step 5: 运行上传相关测试**

Run: `uv run pytest tests/test_api/test_mvp_flow.py -q`
Expected: 上传成功用例与扫描版拒绝用例通过，内部报告权限用例可能仍待补齐

- [ ] **Step 6: 提交上传与校验能力**

```bash
git add src/api/routers/papers.py src/core/config.py src/models/paper.py tests/test_api/test_mvp_flow.py
git commit -m "feat: add mvp paper upload validation"
```

### M1 Task 3: 评审编排服务

**Files:**
- Create: `src/services/evaluation_pipeline.py`
- Modify: `src/evaluation/concurrent_evaluator.py`
- Modify: `src/evaluation/call_logger.py`
- Modify: `src/models/evaluation.py`
- Modify: `src/models/reliability.py`
- Test: `tests/test_api/test_mvp_flow.py`

- [ ] **Step 1: 写失败测试，约束上传后会返回 `paper_id/task_id/status`**

```python
assert data["paper_id"]
assert data["task_id"]
assert data["status"] == "completed"
```

- [ ] **Step 2: 运行测试确认失败点在服务返回结构缺失**

Run: `uv run pytest tests/test_api/test_mvp_flow.py::test_upload_then_fetch_status_and_internal_report -q`
Expected: FAIL because upload endpoint has no real result payload

- [ ] **Step 3: 实现最小编排服务**

```python
class EvaluationPipelineService:
    def evaluate_file(...):
        paper = create_paper(...)
        task = create_task(...)
        processed = process_file(file_path)
        framework = load_framework("configs/frameworks/law_v1.yaml")
        for dimension in framework.dimensions:
            results = asyncio.run(evaluate_dimension_concurrent(...))
            save_dimension_scores(...)
            reliability = calculate_reliability(...)
            save_reliability(...)
        report = build_internal_report(...)
        save_report(...)
        return {"paper_id": paper.id, "task_id": task.id, "status": "completed"}
```

- [ ] **Step 4: 保证 AI 调用完整日志持久化**

```python
log_call(
    db=db,
    task_id=task_id,
    model_name=provider.model_name,
    dimension_key=dimension.key,
    prompt=prompt,
    response=response_text,
    start_time=start_time,
)
```

- [ ] **Step 5: 运行 API 主链路测试**

Run: `uv run pytest tests/test_api/test_mvp_flow.py::test_upload_then_fetch_status_and_internal_report -q`
Expected: PASS

- [ ] **Step 6: 提交评审编排主链路**

```bash
git add src/services/evaluation_pipeline.py src/evaluation/concurrent_evaluator.py src/evaluation/call_logger.py src/models/evaluation.py src/models/reliability.py tests/test_api/test_mvp_flow.py
git commit -m "feat: add mvp evaluation pipeline"
```

### M1 Task 4: 内部报告构造与查询接口

**Files:**
- Create: `src/reporting/internal_report_builder.py`
- Modify: `src/models/report.py`
- Modify: `src/api/routers/papers.py`
- Test: `tests/test_reporting/test_internal_report_builder.py`
- Test: `tests/test_api/test_mvp_flow.py`

- [ ] **Step 1: 写失败测试，约束内部报告字段齐全**

```python
assert report["weighted_total"] == 84.5
assert report["summary"]["overall_high_confidence"] is True
assert report["dimensions"][0]["model_scores"]["gpt-4o"] == 83
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/test_api/test_mvp_flow.py::test_upload_then_fetch_status_and_internal_report -q`
Expected: FAIL because internal report payload is incomplete

- [ ] **Step 3: 实现内部报告 builder**

```python
def build_internal_report(...):
    return {
        "paper_id": paper.id,
        "task_id": task.id,
        "weighted_total": weighted_total,
        "summary": summarize_reliability(reports),
        "dimensions": [...],
    }
```

- [ ] **Step 4: 实现 `GET /api/papers/{id}/internal-report`**

```python
@router.get("/papers/{paper_id}/internal-report")
def get_internal_report(...):
    report = evaluation_service.get_internal_report(paper_id)
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")
    return report
```

- [ ] **Step 5: 运行报告与权限测试**

Run: `uv run pytest tests/test_api/test_mvp_flow.py -q`
Expected: PASS

- [ ] **Step 6: 提交内部报告能力**

```bash
git add src/reporting/internal_report_builder.py src/models/report.py src/api/routers/papers.py tests/test_reporting/test_internal_report_builder.py tests/test_api/test_mvp_flow.py
git commit -m "feat: add mvp internal report endpoint"
```

### M1 Task 5: 状态查询与失败口径

**Files:**
- Modify: `src/services/evaluation_pipeline.py`
- Modify: `src/models/paper.py`
- Modify: `src/api/routers/papers.py`
- Test: `tests/test_api/test_mvp_flow.py`

- [ ] **Step 1: 写失败测试，约束状态接口返回失败原因字段**

```python
status = client.get("/api/papers/paper-1/status", ...)
assert status.json()["status"] == "completed"
assert "failure_reason" in status.json()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/test_api/test_mvp_flow.py::test_upload_then_fetch_status_and_internal_report -q`
Expected: FAIL because status payload or route is incomplete

- [ ] **Step 3: 实现状态查询**

```python
@router.get("/papers/{paper_id}/status")
def get_status(...):
    return evaluation_service.get_status(paper_id)
```

- [ ] **Step 4: 统一失败口径**

```python
paper.status = "closed" if input_failure else "processing"
paper.failure_reason = str(exc)
```

- [ ] **Step 5: 运行完整 M1 测试**

Run: `uv run pytest tests/test_api/test_mvp_flow.py -q`
Expected: PASS

- [ ] **Step 6: 提交状态接口与失败口径**

```bash
git add src/services/evaluation_pipeline.py src/models/paper.py src/api/routers/papers.py tests/test_api/test_mvp_flow.py
git commit -m "feat: add mvp paper status tracking"
```

### M1 验收命令

- [ ] `uv run pytest tests/test_api/test_mvp_flow.py -q`
- [ ] `uv run pytest tests/test_ingestion tests/test_knowledge tests/test_evaluation -q`
- [ ] `uv run pytest -q`

### M1 交付门槛

- 单篇 TXT / DOCX / PDF 能触发评审
- 扫描版 PDF 会被明确拒绝
- 内部报告可由编辑/管理员读取
- AI 原始调用日志已入库
- 至少有一组端到端 API 测试覆盖主链路

### M1 明确退出条件

- 若 Day 4 结束时仍未打通 `POST /api/papers` 到 `GET /internal-report` 主链路，立即停止扩展功能，只修主链路。
- 若真实模型接入阻塞，允许临时以 provider stub 完成系统验证，但接口、日志、持久化结构不得变化。
- 若数据库迁移与模型不一致，优先修数据模型与迁移，不允许绕过持久化直接以内存结果交付 M1。

## M2: 专家复核工作流

### 目标

- 把低置信度任务从自动评审延伸到人工复核闭环。

### 关键能力

- 低置信度任务自动进入 `reviewing`
- 编辑可手动追加复核
- 专家可查看任务并提交修改理由
- 多专家并行提交，全部完成后任务才完成

### 验收标准

- 单专家与多专家用例均可闭环
- AI 评分与专家评分并列保存，不覆盖
- 编辑可看部分提交结果，投稿人不可见

## M3: 报告版本化、公开报告与审计

### 目标

- 从“内部可用”提升到“对外可交付且可追溯”。

### 关键能力

- 区分公开结果报告与内部完整报告
- 每次生成都形成新快照版本
- 内部完整报告访问写入审计日志
- 支持 JSON / PDF 导出

### 验收标准

- 公开报告字段严格少于内部报告
- 历史报告版本可回溯
- 内部访问审计最小字段集完整

## M4: 批量任务与管理员恢复

### 目标

- 补齐 v1 运维和恢复能力，支撑试运行。

### 关键能力

- 批量任务提交与状态聚合
- 技术失败可重试，输入失败不可重试
- `recovering` 与 `closed` 状态落地
- 全局阈值设置与框架版本回滚

### 验收标准

- 批量任务有完成数/失败数统计
- 管理员可查看失败原因、重试当前阶段、标记关闭
- 学科框架切换与回滚无需改代码

## Risks And Defaults

- 默认风险最高的是第一周同时展开“API + Web + 复核 + 导出”，本计划已经明确避免。
- 若 AI key 尚未准备好，M1 先以 provider stub 或测试替身完成链路验证，再接入真实模型。
- 若数据库迁移尚未同步，优先保证 SQLAlchemy 模型和测试数据库闭环，再补 Alembic 迁移。
- 若时间继续压缩，优先级固定为：上传/评审/状态/内部报告 > 权限 > 复核 > 审计 > PDF > 批量。

## Execution Notes

- 所有实现任务遵守 @superpowers:test-driven-development，先写失败测试再写实现。
- 完成每个 milestone 前，必须执行 @superpowers:verification-before-completion。
- 若后续要正式开始编码，优先按 M1 Task 1 到 Task 5 顺序执行，不要跨阶段并行铺开。
