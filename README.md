# 文科论文评价系统

**面向自主知识体系的 AI 辅助文科学术评价系统**

> 以法学论文评审为切入点，通过多模型并发评价 + 可靠性验证 + 专家复核，构建标准统一、可解释的学术论文自动化初审流程，并可扩展至人文社科各学科。

---

## 核心机制

```
论文上传 → 预处理 → 多模型并发评价 → 一致性验证 → [专家复核] → 报告输出
```

- **六维评价框架**：问题创新性、现状洞察度、理论建构力、逻辑严密性、学术共识度、前瞻延展性
- **多模型并发**：同一维度同时调用多个 AI 模型（GPT-4o、Claude、DeepSeek 等），结果取均值并计算标准差
- **可靠性验证**：标准差 ≤ 阈值 → 高置信度；超出阈值 → 低置信度，自动进入专家复核队列
- **知识体系可配置**：评价维度、权重、提示词模板均通过 YAML 文件定义，新增学科无需改代码

---

## 技术栈

| 层次 | 技术选型 |
|------|----------|
| 后端 | Python 3.10+，FastAPI，uv |
| 前端 | React + TypeScript |
| 数据库 | PostgreSQL（论文/评分/日志），Redis（任务队列） |
| 任务队列 | Celery + Redis |
| AI 接入 | 统一抽象层，支持 OpenAI / Anthropic / DeepSeek |

---

## 目录结构（规划）

```
social-eval/
├── src/
│   ├── ingestion/       # F1: 文档摄取与预处理
│   ├── knowledge/       # F2: 知识体系配置（YAML 动态加载）
│   ├── evaluation/      # F3: AI 评价引擎（多模型并发）
│   ├── reliability/     # F4: 可靠性验证层
│   ├── review/          # F5: 专家复核工作流
│   ├── reporting/       # F6: 报告生成（PDF / JSON）
│   ├── api/             # F8: RESTful API
│   └── web/             # F7: Web 前端
├── configs/
│   └── frameworks/      # 各学科知识体系 YAML 配置
├── docs/
│   ├── requirements/    # 需求文档
│   ├── architecture/    # ADR（架构决策记录）
│   └── archive/         # 历史版本归档
├── tests/               # 镜像 src/ 结构
├── .env.example
├── .gitignore
└── README.md
```

---

## 用户角色

| 角色 | 权限范围 |
|------|----------|
| 投稿人 | 上传论文、查看进度、下载最终报告 |
| 编辑委员 | 批量初审、指定专家、查看完整 AI 评分 |
| 领域专家 | 复核任务列表、修改评分并填写理由 |
| 系统管理员 | 用户管理、知识体系配置、全局参数设置 |

---

## 文档

- 需求文档：`docs/requirements/SocialEval-requirements-v0.4.md`
- 当前法学框架：`configs/frameworks/law-v2.0-20260413.yaml`
- 架构决策：`docs/architecture/20260414_ADR-001_evaluation-framework-v2.md`
- 云资源建议：`docs/architecture/SocialEval-mvp-cloud-sizing.md`
- 部署与运维：`docs/deployment/SocialEval-deployment-and-operations-guide.md`
- 生产环境变量：`docs/deployment/production-env.example.md`
- 上线清单与回滚计划：`docs/deployment/launch-checklist.md`
- 开发路线图：`development-roadmap.md`
- 参考资料：`ref/` 目录（法学论文评价方法论、AI 评价系统方案）

---

## 本地运行

### 后端

```bash
uv sync --extra dev
docker-compose up -d
alembic upgrade head
uv run uvicorn src.api.main:app --reload --port 8000
```

### 前端

```bash
cd src/web
npm install
npm run dev
```

前端默认开发地址：`http://localhost:5173`  
后端默认开发地址：`http://localhost:8000`

## 生产部署

当前仓库已经补齐生产上线骨架，包含：

- API / 前端 Dockerfile
- `docker-compose.prod.yml`
- `systemd` 服务单元
- 生产环境变量校验
- 健康检查、结构化日志、CI、launch smoke test

正式部署请优先阅读：

1. `docs/deployment/SocialEval-deployment-and-operations-guide.md`
2. `docs/deployment/production-env.example.md`
3. `docs/deployment/launch-checklist.md`

---

## 当前已落地能力

- Session 登录 + API Key 认证
- 邀请制账号激活
- 论文单篇/批量上传
- v2.0 准入检查 + 六维评分 + 可靠性计算
- 内部/公开报告生成与 JSON/PDF 导出
- 专家复核队列、分配、提交
- 审计日志、管理员重试/关闭、批量任务状态聚合
- React + TypeScript 最小角色化前端（投稿人 / 编辑 / 专家 / 管理员）

---

## 开发规范

- Python 依赖管理：`uv`
- 代码风格：Ruff（Python），ESLint + Prettier（前端）
- 提交规范：Conventional Commits（`feat:` / `fix:` / `refactor:` / `docs:`）
- AI 模型调用必须通过统一抽象层，禁止业务层直接 import SDK
- 所有 AI 调用记录须持久化（输入/输出/时间戳/模型名）
- `.env` 已加入 `.gitignore`，禁止提交任何 API Key

---

## License

Private — All rights reserved.
