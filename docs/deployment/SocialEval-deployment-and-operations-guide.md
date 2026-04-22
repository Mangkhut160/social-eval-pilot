# 文科论文评价系统部署与运维说明

**版本**：2026-04-16  
**适用范围**：单机 MVP 生产部署、容器化部署、宿主机 `systemd` 部署

---

## 1. 当前推荐部署形态

当前仓库已经具备单机 MVP 生产部署骨架，推荐拓扑为：

- `Nginx`
- `FastAPI`
- `Celery Worker`
- `PostgreSQL`
- `Redis`
- `SMTP`
- `对象存储（local 或 S3 兼容）`

配套上线能力已经覆盖：

- 生产环境变量校验与 Session/CORS 安全配置
- API / Worker Docker 镜像与 `docker-compose.prod.yml`
- `systemd` 服务单元
- SMTP 邮件发送
- 本地磁盘 / S3 对象存储抽象
- `/api/health` 数据库、Redis、对象存储与任务队列可见性检查
- JSON 结构化日志
- GitHub Actions CI
- 端到端 launch smoke test

云资源规格建议见：`docs/architecture/SocialEval-mvp-cloud-sizing.md`

若当前处于“先本地演示、后解决平台公网入口”的阶段，另见：

- `docs/deployment/local-demo-guide.md`

---

## 2. 仓库内现成部署文件

- API 镜像：`Dockerfile.api`
- 前端镜像：`src/web/Dockerfile`
- 生产编排：`docker-compose.prod.yml`
- Nginx 模板：`deploy/nginx/socialeval.conf`
- API 服务单元：`deploy/systemd/socialeval-api.service`
- Worker 服务单元：`deploy/systemd/socialeval-worker.service`
- 生产环境变量示例：`docs/deployment/production-env.example.md`
- 上线清单与回滚计划：`docs/deployment/launch-checklist.md`

---

## 3. 上线前准备

### 3.1 基础设施

- 准备 `Ubuntu 22.04 LTS` 或同等级 Linux 主机
- 准备域名，例如 `app.socialeval.example`
- 配置 DNS A/AAAA 记录指向应用入口
- 申请 TLS 证书并规划 `80/443`
- 为 PostgreSQL、Redis、SMTP、对象存储准备网络访问策略

### 3.2 必须准备的密钥 / 凭据

- `SECRET_KEY`
- `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `DEEPSEEK_API_KEY`
- `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD`
- `OBJECT_STORAGE_*`
- 数据库与 Redis 连接串

### 3.3 环境变量文件

以 `docs/deployment/production-env.example.md` 为基线填写正式配置，至少保证：

- `APP_ENV=production`
- `ALLOWED_ORIGINS` 为真实前端来源
- `SESSION_COOKIE_SECURE=true`
- `SESSION_COOKIE_DOMAIN` 与正式域名一致
- `PUBLIC_BASE_URL` 指向用户访问地址
- `API_BASE_URL` 指向 API 对外地址

说明：

- 前端未显式设置 `VITE_API_BASE` 时，会优先走同源 `/api`
- `OBJECT_STORAGE_BACKEND` 当前支持 `local` 和 `s3`
- `s3` 模式下，`OBJECT_STORAGE_ENDPOINT` 可用于校内对象存储或其他 S3 兼容服务

---

## 4. 容器化单机部署

### 4.1 准备 `.env`

```bash
cp .env.example .env
```

再按生产值修改 `.env`。

### 4.2 校验编排文件

```bash
docker compose -f docker-compose.prod.yml config
```

若宿主机没有 `docker compose` 插件，可改用：

```bash
docker-compose -f docker-compose.prod.yml config
```

### 4.3 构建镜像

```bash
docker compose -f docker-compose.prod.yml build api worker frontend
```

当前 `Dockerfile.api` 直接基于 `python:3.10` 运行时镜像，已经包含 PDF 导出所需的 Cairo / Pango 相关运行时库，因此不再依赖上线时额外 `apt-get install`。

### 4.4 启动依赖服务与迁移

```bash
docker compose -f docker-compose.prod.yml up -d postgres redis
docker compose -f docker-compose.prod.yml run --rm api uv run alembic upgrade head
```

### 4.5 启动应用

```bash
docker compose -f docker-compose.prod.yml up -d api worker frontend nginx
```

### 4.6 默认流量路径

- `/api/` -> `api:8000`
- `/` -> `frontend:80`

对外入口统一由 `nginx` 暴露。

说明：

- `OBJECT_STORAGE_BACKEND=local` 时，`api` 与 `worker` 会通过共享的 `appdata` 卷读写上传文件和导出产物。

---

## 5. 宿主机 + systemd 部署

适用于：

- PostgreSQL / Redis 由云服务提供
- 或希望应用直接运行在宿主机 Python 环境中

### 5.1 建议目录

- 代码：`/opt/social-eval`
- 环境变量：`/etc/socialeval/socialeval.env`
- systemd 运行用户：`socialeval`

### 5.2 宿主机准备

```bash
sudo useradd --system --home /opt/social-eval --shell /usr/sbin/nologin socialeval
sudo mkdir -p /etc/socialeval
sudo chown -R socialeval:socialeval /opt/social-eval /etc/socialeval
```

将仓库代码部署到 `/opt/social-eval`，并写入 `/etc/socialeval/socialeval.env`。

### 5.3 服务文件

复制：

- `deploy/systemd/socialeval-api.service`
- `deploy/systemd/socialeval-worker.service`

到 `/etc/systemd/system/`。

### 5.4 启动命令

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now socialeval-api
sudo systemctl enable --now socialeval-worker
```

如需查看运行状态：

```bash
sudo systemctl status socialeval-api
sudo journalctl -u socialeval-api -f
sudo journalctl -u socialeval-worker -f
```

---

## 6. Nginx 与 TLS

仓库已提供模板：

- `deploy/nginx/socialeval.conf`

该模板默认：

- 监听 `80`
- 将 `/api/` 代理到 API
- 将 `/` 代理到前端容器
- 设置常见反代头

正式生产应补齐：

- `443` 与证书续期
- HSTS
- 访问日志与错误日志落盘
- `client_max_body_size`
- 仅对公网暴露 `80/443`

---

## 7. 首个管理员初始化

当前仓库已支持“管理员邀请用户 -> 用户激活账号”的正式流程，但**首个管理员账号**仍需通过一次性种子方式创建。

推荐做法：

1. 先完成数据库迁移
2. 在生产环境中执行一次性脚本创建 `admin`
3. 首个管理员登录后，通过 `/api/users/invitations` 邀请其他角色账号

示例脚本：

```bash
uv run python - <<'PY'
from src.api.auth.password import hash_password
from src.core.database import SessionLocal
from src.models.user import User

db = SessionLocal()
try:
    email = "admin@example.com"
    existing = db.query(User).filter(User.email == email).first()
    if existing is not None:
        raise SystemExit(f"{email} already exists")

    db.add(
        User(
            email=email,
            display_name="Initial Admin",
            hashed_password=hash_password("change-this-immediately"),
            role="admin",
            is_active=True,
        )
    )
    db.commit()
finally:
    db.close()
PY
```

执行后必须：

- 立即登录验证
- 立刻修改为正式强密码
- 将初始密码从任何工单、聊天记录、跳板机历史中清除

---

## 8. 健康检查、日志与冒烟验证

### 8.1 健康检查

```bash
curl -fsS https://app.socialeval.example/api/health
```

成功时返回：

- `status=ok`
- `checks.database.status=ok`
- `checks.redis.status=ok`
- `checks.storage.status=ok`
- `checks.task_queue.status=ok`（并包含 `pending/processing/reviewing/recovering` 计数）

### 8.2 运维总览接口（管理员）

```bash
curl -fsS -H "X-API-Key: <admin-api-key>" \
  https://app.socialeval.example/api/admin/operations/overview
```

返回核心字段：

- `task_counts`：任务状态计数（含 `total`）
- `recent_failures`：最近失败任务摘要
- `pending_reviews`：待专家复核数
- `dependencies`：`database/redis/storage/task_queue` 依赖状态（`task_queue` 包含 worker 存活与队列计数摘要）

### 8.3 日志

API 与 Worker 启动后会输出 JSON 结构化日志，适合接入 Loki / ELK / 云日志服务。

### 8.4 最小冒烟路径

建议按以下顺序验证：

1. 管理员登录成功
2. 管理员创建 `submitter` / `editor` / `expert` 邀请
3. 受邀用户通过 `/?invitation_token=<token>` 完成激活并返回登录页
4. 投稿人上传一篇样例论文，并手动点击“开始评测”
5. Worker 完成任务，论文状态变为 `completed`，投稿人可读取公开报告
6. 若稿件被预检拒稿，投稿人界面会显示“需重新上传”及重传提示，而不是伪造 `0` 分报告
7. 编辑可读取内部报告与复核队列，并完成专家分配
8. 专家登录后可在网页端打开分配到的任务，逐维度填写专家评分与修改理由并提交复核
9. 若启用对象存储，确认 bucket 中出现 `uploads/` 与 `exports/` 对象
10. 若启用 SMTP，确认邀请/分配邮件成功发出

回归基线可参考自动化测试：`tests/integration/test_launch_smoke.py`

---

## 9. 备份、监控与回滚

上线前至少准备：

- PostgreSQL 迁移前快照 / 逻辑备份
- Redis 持久化策略确认
- 对象存储 bucket 生命周期与版本控制策略
- 应用日志保留周期

单机试点环境可直接使用仓库脚本生成时间戳备份包（默认输出到部署目录下 `./backups`）：

```bash
uv run python scripts/manage_backups.py create --dry-run
uv run python scripts/manage_backups.py create
```

说明：备份脚本使用 `docker compose`（Compose v2）并默认按 `socialevalpilot` project 名解析卷名；如环境 project 名不同，可加 `--compose-project <name>`。
正式执行 `create` 前必须先停止 `api`、`worker`、`redis` 等写入相关服务，并保持 `postgres` 运行；脚本会在执行前做这层校验。
正式执行 `create` / `restore` 前，脚本还会校验当前 `docker-compose.prod.yml` 仍声明并挂载预期的 `appdata` / `redisdata`，且对应命名卷真实存在，避免误备份/误恢复到新建空卷。
恢复时必须使用与备份时一致的 `--compose-project`；该值会写入 `manifest.json` 并在 restore 时校验，不一致会直接阻止破坏性恢复。
恢复时 `--postgres-user` 与 `--postgres-db` 也必须与创建备份时一致；这两个目标同样会写入 `manifest.json` 并在 restore 时校验。
若部署使用 `OBJECT_STORAGE_BACKEND=s3`，该脚本只覆盖 PostgreSQL/Redis/本地卷，不覆盖对象存储 bucket；必须另外配置 bucket 版本控制或独立备份流程。

恢复前先执行 dry-run 校验计划：

```bash
uv run python scripts/manage_backups.py restore \
  --bundle-dir ./backups/<backup-id> \
  --allow-destructive-restore \
  --confirm-backup-id <backup-id> \
  --dry-run
```

说明：
- dry-run 会打印接近真实执行的命令计划，包含 `pg_restore` 的输入重定向路径。
- 正式恢复前必须先停止 `api`、`worker`、`redis`、`frontend`、`nginx` 等相关服务，并保留 `postgres` 运行用于恢复预检与导入。
- 正式恢复前脚本还会校验 `postgres.dump` 与两个卷归档的有效性，并要求这些文件不是 symlink；未通过时不会进入破坏性恢复步骤。

恢复实操、前置条件、校验与回滚注意事项见：

- `docs/deployment/backup-and-recovery-runbook.md`

建议重点监控：

- `/api/health` 持续状态
- `/api/admin/operations/overview` 中 `recovering`、`recent_failures`、`pending_reviews` 变化
- API 5xx 比例
- Celery 队列堆积
- PostgreSQL 连接数 / 磁盘空间
- Redis 内存占用
- SMTP 发送失败率

可使用仓库脚本做单机告警判断（超阈值返回非 0）：

```bash
uv run python scripts/ops_monitor.py \
  --endpoint https://app.socialeval.example/api/admin/operations/overview \
  --api-key "<admin-api-key>" \
  --max-recovering 0 \
  --max-recent-failures 0 \
  --max-pending-reviews 10
```

回滚触发条件与步骤见：`docs/deployment/launch-checklist.md`

---

## 10. 相关文档

- `docs/deployment/production-env.example.md`
- `docs/deployment/launch-checklist.md`
- `docs/deployment/backup-and-recovery-runbook.md`
- `docs/architecture/SocialEval-mvp-cloud-sizing.md`
