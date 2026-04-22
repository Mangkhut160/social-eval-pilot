# SocialEval — 项目上下文

## 快速开始

### 环境搭建

```bash
# 1. 安装 uv（如果尚未安装）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. 创建虚拟环境并安装依赖
uv venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
uv pip install -e ".[dev]"

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填入必需的 API Keys（见下方"环境配置"）

# 4. 启动依赖服务（PostgreSQL + Redis）
docker-compose up -d

# 5. 初始化数据库
alembic upgrade head

# 6. 启动开发服务器
uvicorn src.api.main:app --reload --port 8000
# API 文档：http://localhost:8000/docs
```

### 开发命令

```bash
# 代码检查与格式化
ruff check src/ tests/        # 检查代码规范
ruff format src/ tests/       # 自动格式化

# 运行测试
pytest                        # 运行所有测试
pytest tests/test_evaluation/ # 运行特定模块测试
pytest -v -s                  # 详细输出模式
pytest --cov=src              # 生成覆盖率报告

# 数据库迁移
alembic revision --autogenerate -m "描述"  # 创建迁移脚本
alembic upgrade head                       # 应用所有迁移
alembic downgrade -1                       # 回滚一步
alembic history                            # 查看迁移历史

# 依赖管理
uv pip install <package>      # 安装新依赖
uv pip list                   # 查看已安装依赖
uv pip freeze > requirements.txt  # 导出依赖（如需要）
```

---

## 项目简介

**SocialEval** 是一套面向自主知识体系的 AI 辅助学术评价系统，以法学论文评审为切入点，支持拓展至人文社科各学科。

核心机制：多模型并发评价 → 一致性验证 → 专家复核 → 标准化报告输出

需求文档：`docs/requirements/SocialEval-requirements-v0.4.md`

---

## 架构

### 技术栈
- **后端**：Python 3.10+ (FastAPI)，依赖管理用 `uv`
- **前端**：React + TypeScript（开发中）
- **数据库**：PostgreSQL（论文/评分/审计日志）
- **缓存/队列**：Redis（任务队列）
- **任务队列**：Celery + Redis（异步评审任务）
- **AI 接入**：统一抽象层，支持 OpenAI / Anthropic / DeepSeek

### 目录结构

```
src/
  api/             # F8: RESTful API（FastAPI）
  core/            # 核心配置与工具
  evaluation/      # F3: AI 评价引擎（多模型并发）
  ingestion/       # F1: 文档摄取与预处理
  knowledge/       # F2: 知识体系配置（YAML/JSON 动态加载）
  models/          # 数据库模型（SQLAlchemy）
  reliability/     # F4: 可靠性验证层（均值/标准差/置信度）
  reporting/       # F6: 报告生成（PDF / JSON 导出）
  review/          # F5: 专家复核工作流（开发中）
  web/             # F7: Web 前端（开发中）
configs/
  frameworks/      # 各学科知识体系 YAML 配置文件
    law-v2.3-20260421.yaml  # 法学评价框架 v2.3（运行时默认）
    law-v2.0-20260413.yaml  # 法学评价框架 v2.0（生产稳定版）
    archive/                 # 历史版本归档
docs/
  requirements/    # 需求文档
  architecture/    # ADR（架构决策记录）
  evaluation/      # 评价方法论文档
  discussion/      # 设计讨论记录
tests/             # 测试（镜像 src/ 结构）
alembic/           # 数据库迁移脚本
scripts/           # 工具脚本
```

---

## 环境配置

### 必需的环境变量（`.env` 文件）

```bash
# 数据库
DATABASE_URL=postgresql://socialeval:socialeval@localhost:5432/socialeval

# Redis
REDIS_URL=redis://localhost:6379/0

# 安全
SECRET_KEY=change-me-in-production  # ⚠️ 生产环境必须修改

# AI 模型 API Keys（多模型评价必需）
OPENAI_API_KEY=sk-...        # OpenAI API 密钥
ANTHROPIC_API_KEY=sk-ant-... # Anthropic API 密钥
DEEPSEEK_API_KEY=...         # DeepSeek API 密钥（可选）

# SMTP 配置（邮件通知）
SMTP_HOST=smtp.mailtrap.io
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=noreply@socialeval.local
```

### 配置说明

- **DATABASE_URL**: PostgreSQL 连接字符串，格式 `postgresql://user:password@host:port/dbname`
- **SECRET_KEY**: JWT 签名密钥，生产环境必须使用强随机字符串
- **AI API Keys**: 至少配置 2 个模型的 API Key（用于多模型并发验证）
- **SMTP**: 用于发送专家复核通知邮件，开发环境可使用 Mailtrap

---

## 常见问题（Gotchas）

### AI 模型调用
- ✅ **必须通过统一抽象层**：所有 AI 调用必须通过 `src/evaluation/providers/` 的抽象层
- ❌ **禁止直接 import SDK**：不要在业务代码中直接 `import openai` 或 `import anthropic`
- 📝 **自动持久化**：所有 AI 调用记录（输入/输出/时间戳/模型名）会自动保存到数据库

### 配置文件加载
- 📂 **动态加载**：评价框架配置从 `configs/frameworks/*.yaml` 动态加载
- 🔄 **无需重启**：修改配置后无需重启服务，下次评价时自动生效
- ✅ **Schema 验证**：配置文件必须符合 `configs/frameworks/schema_v3.json` 定义的 schema（v2.2+使用schema_v3）
- 🚫 **禁止硬编码**：不要在代码中硬编码评价维度，必须从配置文件读取

### 数据库迁移
- 📝 **自动生成**：修改 `src/models/` 下的模型后，运行 `alembic revision --autogenerate -m "描述"`
- ⚠️ **检查脚本**：生成后检查 `alembic/versions/` 下的迁移脚本，确认无误后再 `alembic upgrade head`
- 🔙 **可回滚**：使用 `alembic downgrade -1` 回滚上一次迁移

### 安全注意事项
- 🔒 **`.env` 不提交**：`.env` 文件已在 `.gitignore` 中，不要提交任何 API Key
- 🔐 **Token 认证**：所有 API 接口必须 Token 认证，不得暴露未鉴权端点
- 📄 **文件校验**：用户上传文件必须做类型校验（仅允许 PDF/DOCX/TXT）

### 测试相关
- 🧪 **测试结构**：测试目录镜像 `src/` 结构，如 `tests/test_evaluation/` 对应 `src/evaluation/`
- ⚡ **异步测试**：使用 `pytest-asyncio`，测试函数标记 `@pytest.mark.asyncio`
- 📊 **覆盖率**：核心业务逻辑（evaluation, knowledge, reliability）需要测试覆盖

---

## 核心领域知识

### 法学评价框架（多版本并存）

| 版本 | 配置文件 | 状态 | 适用场景 |
|------|----------|------|----------|
| v2.3 | `law-v2.3-20260421.yaml` | **运行时默认** | AI测试推荐，大模型可操作性最佳 |
| v2.0 | `law-v2.0-20260413.yaml` | 生产稳定版 | 已验证，生产环境使用 |

**运行时默认**：v2.3  
**评分规程**：`docs/evaluation/law-scoring-rules-v0.1-20260413.md`  
**架构决策**：`docs/architecture/20260414_ADR-001_evaluation-framework-v2.md`

#### 准入条件（前置筛选）

在进入六维评分前，论文必须通过学术规范性检查：
- **写作规范性**：语言表达清晰、结构完整
- **引用规范性**：格式符合学术规范、引用准确无捏造
- **学术伦理**：无抄袭、无数据造假

前置筛选支持四种状态：
- **pass**：通过准入检查，进入六维评分
- **conditional_pass**：存在轻微问题但可继续评分
- **manual_review**：需要专家人工复核
- **reject**：不合格论文直接退稿

#### v2.3 核心特性（运行时默认）

1. **ceiling_rules（上限规则）**：显式定义触发条件和分数上限
2. **review_flags（复核标记）**：统一枚举，便于触发专家复核
3. **limit_rule_triggered**：结构化输出，明确规则触发证据
4. **跨维度一致性检查**：识别不合理的评分组合
5. **governance_appendix**：分离治理逻辑，包含风险检测机制

#### 六维度评分（总分 0-100）

| 维度 | 英文名 | 权重 | 描述 |
|------|--------|------|------|
| 问题创新性 | Problem Originality | 30% | 研究问题是否为"真问题"且具有枢纽意义 |
| 现状洞察度 | Literature Insight | 15% | 对既有研究的穷尽程度与未竟点的精准识别 |
| 分析框架建构力 | Analytical Framework Construction | 15% | 是否建立可操作的分析框架（类型化/比较框架/实证设计） |
| 逻辑严密性 | Logical Coherence | 25% | 推理链条是否不可颠倒，后一步是否是对前一步的必然回应 |
| 结论共识度 | Conclusion Consensus | 10% | 对策/结论在制度框架内的可行性（"在司法现实中说得通"） |
| 前瞻延展性 | Forward Extension | 5% | 为后续研究"画地图"（权重最低，对判例分析类论文影响小） |

**判断链条**：起点（问题创新性）→ 定位（现状洞察度）→ 工具（分析框架建构力）→ 骨架（逻辑严密性）→ 落脚（结论共识度）→ 开放（前瞻延展性）

#### 评分结构

- **总分范围**：0–100 分（符合学术惯例）
- **可靠性阈值**：多模型评分标准差 ≤ 5 分为高置信度

#### v2.0 核心改进（相比 v1.0）

1. **新增准入条件**：学术规范性前置筛选，不合格直接退稿
2. **保持六维结构，调整权重**：
   - 问题创新性 30%（提升 5%）
   - 逻辑严密性 25%（提升 5%）
   - 结论共识度 10%（降低 5%）
   - 前瞻延展性 5%（权重最低，对判例分析类论文影响小）
3. **维度重命名**：
   - 理论建构力 → 分析框架建构力（涵盖法教义学、判例分析、实证研究等多元类型）
   - 学术共识度 → 结论共识度（强调可行性而非"符合主流"）
4. **总分 100**：符合学术惯例，便于与其他评价系统对比

---

## 开发规范

### 语言与工具
- Python 3.10+，依赖管理用 `uv`
- TypeScript（前端），禁用 `any` 和 `@ts-ignore`
- Ruff（Python lint/format），ESLint + Prettier（前端）

### 代码风格
- Python: 遵循 PEP 8，行长度 88（Ruff 默认）
- 类型注解: 所有公共函数必须有类型注解
- 文档字符串: 公共 API 必须有 docstring

### 关键约束
- **AI 模型调用**必须通过统一抽象层，禁止在业务层直接 import SDK
- **知识体系配置**只能通过 `configs/frameworks/` 的 YAML/JSON 文件定义，禁止硬编码维度
- **所有 AI 调用记录**须持久化（输入/输出/时间戳/模型名），不可只存最终结果
- **API 接口**必须 Token 认证，不得暴露未鉴权端点

### 安全红线
- `.env` 必须在 `.gitignore` 中，不得提交任何 API Key
- 所有用户上传文件须做类型校验（PDF/DOCX/TXT）
- 生产环境 `SECRET_KEY` 必须使用强随机字符串

### 提交规范
- Conventional Commits：`feat:` / `fix:` / `refactor:` / `docs:`
- 每个 PR 不超过 400 行，每次 commit = 一个逻辑变更
- Commit message 必须清晰描述变更内容

---

## 已确认的决策（来自需求 v0.4）

以下事项在需求文档中已有结论，开发时须遵守：

- **OCR 支持**：v1 默认不支持扫描版 PDF OCR；疑似扫描版需提示用户重新上传可解析版本（F1.5）
- **多模型并发数**：默认值 3，上限 5（F3.4）
- **专家通知触发条件**：进入复核队列且已完成专家指定后，自动发送邮件通知（F5.5）；编辑也可对高置信度论文手动追加复核
- **用户注册方式**：全角色邀请制，不支持开放自注册（U1.1）
- **认证方式**：Web 端使用 Session，API 调用使用 API Key（U1.3, U1.4）

---

## 待澄清事项（来自需求 v0.4）

以下事项需在后续版本迭代时确认：

- [ ] 外部期刊系统接入方式、签名机制、幂等策略
- [ ] MinerU 纳入后续版本时的启用方式（自动通道 or 管理员手动启用）

---

## 参考资料

| 文件 | 说明 |
|------|------|
| `ref/法学论文的人工评价逻辑.pptx` | 法学论文人工评价方法论 |
| `ref/AI_Legal_Paper_Evaluation_System.pptx` | AI 评价系统方案演示 |
| `ref/lecture_citation_quality.pdf` | 引用质量相关学术参考 |
| `ref/【会议纪要V2】...研讨会.docx` | 专家研讨会纪要 |

---

## 项目级 Skills

项目专属 skill 统一放在 `agent-skills/`，这里是内容真源；不要分别维护 Claude/Codex 两套副本。

### 当前可用

- `socialeval-project-context`
  - 文件：`agent-skills/socialeval-project-context/SKILL.md`
  - 触发场景：在本仓库里做功能开发、修复、测试、方案设计时
  - 作用：统一加载项目背景、领域约束、目录约定与实现边界

### 使用约定

- 需要项目上下文时，优先读取对应的 `agent-skills/<name>/SKILL.md`
- 新增项目专属工作流时，在 `agent-skills/` 下新增独立目录，避免继续扩写本文件
- 若本地代理支持用户级 skill 目录，可用 `scripts/install_project_skills.py` 把仓库内 skill 软链接到本机技能目录，例如 `~/.agents/skills/`
