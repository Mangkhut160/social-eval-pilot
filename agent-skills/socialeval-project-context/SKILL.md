---
name: socialeval-project-context
description: 在 SocialEval 仓库内工作时使用；统一加载项目背景、领域约束、目录约定、评审维度与 AI 调用边界，避免在实现时偏离仓库规则。
---

# SocialEval Project Context

在这个仓库中工作时，先对齐项目约束，再开始实现。

## 什么时候使用

- 用户要在 `SocialEval` 仓库里新增功能、修复问题、补测试或讨论实现方案
- 任务涉及论文评价、知识体系配置、AI 模型接入、可靠性验证、报告导出
- 需要确认项目级约束，而不是仅靠通用工程经验

## 先读哪些内容

- [CLAUDE.md](../../CLAUDE.md)：项目背景、领域知识、架构方向、关键约束
- [docs/requirements/SocialEval-requirements-v0.4.md](../../docs/requirements/SocialEval-requirements-v0.4.md)：当前需求版本
- `configs/frameworks/`：学科知识体系配置，禁止在业务逻辑中硬编码评价维度

## 必须遵守的约束

- AI 模型调用必须通过统一抽象层，不能在业务模块里直接绑定某个 SDK
- 知识体系维度只能来自 `configs/frameworks/` 的 YAML/JSON 配置
- 所有 AI 调用都要保留可审计记录，至少包含输入、输出、模型名、时间戳
- API 端点默认要求鉴权；不要引入未鉴权的新接口
- 上传文件必须做类型校验，至少覆盖 PDF、DOCX、TXT

## 项目偏好

- Python 依赖与命令优先使用 `uv`
- 默认做最小必要改动，优先修根因，不做无关重构
- 核心逻辑变更应补测试或给出可重复验证步骤

## 任务落地提示

- 做评价或可靠性相关改动时，优先检查 `src/evaluation/`、`src/reliability/` 和对应 `tests/`
- 做知识体系相关改动时，先看 `src/knowledge/` 和 `configs/frameworks/`
- 需要新增项目专属工作流时，在 `agent-skills/` 下新增独立 skill 目录，不要把长流程继续堆进 `CLAUDE.md`
