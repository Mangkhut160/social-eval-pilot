# SocialEval 单机备份与恢复 Runbook

**版本**：2026-04-18  
**适用范围**：`docker-compose.prod.yml` 单机部署（试点环境）

---

## 1. 目标与范围

本 runbook 面向当前单机试点形态，提供可执行的最小备份/恢复流程：

- PostgreSQL 逻辑备份（`pg_dump -Fc`）
- `appdata` 卷归档（本地对象存储/导出文件）
- `redisdata` 卷归档
- 备份清单（manifest）记录元数据与产物路径

不覆盖多机编排、跨可用区容灾、自动调度编排。
若部署使用 `OBJECT_STORAGE_BACKEND=s3`，本脚本**不**负责 bucket 级备份；必须额外启用对象存储版本控制、生命周期或独立备份流程。

---

## 2. 前置条件

- 在部署目录执行命令（目录内有 `docker-compose.prod.yml`）
- Docker 可用；脚本会优先使用 `docker compose`（Compose v2），若机器仅安装 `docker-compose` v1，会自动回退
- `postgres` 服务可执行 `pg_dump` / `pg_restore`
- 操作账号具备读写备份目录权限
- 恢复窗口内允许短时中断（恢复是破坏性操作）

推荐先确认：

```bash
docker compose -f docker-compose.prod.yml ps
```

若机器没有 `docker compose` 子命令，可改用：

```bash
docker-compose -f docker-compose.prod.yml ps
```

---

## 3. 备份包结构

默认输出目录：`<deploy-dir>/backups`（可用 `--output-dir` 覆盖）

每次备份生成一个时间戳目录：

```text
backups/
  backup-YYYYMMDDTHHMMSSZ/
    manifest.json
    postgres.dump
    appdata.tar.gz
    redisdata.tar.gz
```

`manifest.json` 记录：

- `backup_id`
- `created_at_utc`
- `postgres_user`
- `postgres_db`
- `compose_project`
- 部署形态、服务/卷清单
- 备份产物文件名

---

## 4. 创建备份

正式执行 `create` 前，必须先进入维护窗口：

1. 停止 `api`、`worker`、`redis` 等写入相关服务
2. 保持 `postgres` 运行，以便执行 `pg_dump`
3. 确认不会再有新的文件写入 `appdata`
4. 确认当前部署目录中的 `docker-compose.prod.yml` 仍声明并挂载 `appdata` / `redisdata`，且对应命名卷实际存在

先查看执行计划：

```bash
uv run python scripts/manage_backups.py create --dry-run
```

执行备份：

```bash
uv run python scripts/manage_backups.py create
```

可选参数：

- `--deploy-dir <path>`：部署根目录
- `--output-dir <path>`：备份输出目录（默认 `<deploy-dir>/backups`）
- `--compose-project <name>`：Compose project 名称（默认 `socialevalpilot`，影响卷名解析）
- `--postgres-user <user>`：默认 `socialeval`
- `--postgres-db <db>`：默认 `socialeval`

说明：`--deploy-dir`、`--output-dir`、`--compose-project` 既可以放在子命令前，也可以放在子命令后。

执行成功后会输出本次备份目录绝对路径。
若未先停止上述写入相关服务，脚本会直接阻止创建备份。

---

## 5. 恢复流程（破坏性）

### 5.1 恢复前检查

1. 确认目标备份目录存在且包含 `manifest.json`
2. 确认恢复窗口已获批，通知业务方
3. 必须先停止写入相关服务，包括 `api`、`worker`、`redis`、`frontend`、`nginx`，并确保对外入口不再产生新请求
4. 强烈建议在恢复前再做一次“当前状态”备份，便于回退
5. 确认本次恢复使用的 `--compose-project` 与创建备份时写入 `manifest.json` 的值一致
6. 保持 `postgres` 服务运行，以便执行 `pg_restore` 预检与正式恢复
7. 确认当前部署目录中的 `docker-compose.prod.yml` 仍声明并挂载 `appdata` / `redisdata`，且对应命名卷实际存在

### 5.2 Dry-run 校验

```bash
uv run python scripts/manage_backups.py restore \
  --bundle-dir ./backups/<backup-id> \
  --allow-destructive-restore \
  --confirm-backup-id <backup-id> \
  --dry-run
```

dry-run 会打印接近真实执行的命令计划；在 restore 场景下会显示 `pg_restore < postgres.dump` 的输入重定向路径，适合用于人工复核。

### 5.3 执行恢复

```bash
uv run python scripts/manage_backups.py restore \
  --bundle-dir ./backups/<backup-id> \
  --allow-destructive-restore \
  --confirm-backup-id <backup-id>
```

恢复时会执行：

- 清空并重建 PostgreSQL `public` schema
- 导入 `postgres.dump`
- 覆盖恢复 `appdata`、`redisdata` 卷内容

---

## 6. 安全护栏与注意事项

- 必须显式传入 `--allow-destructive-restore`
- 必须传入 `--confirm-backup-id`，且与 manifest 中 `backup_id` 完全一致
- `--postgres-user` 与 `--postgres-db` 必须与创建备份时写入 manifest 的值完全一致，否则会阻止恢复
- manifest 中的 `schema_version`、`deployment_shape`、`compose_file`、`compose_project`、`services`、`volumes`、`artifacts` 必须与当前脚本预期一致，否则会阻止恢复
- `manifest.json`、`postgres.dump`、`appdata.tar.gz`、`redisdata.tar.gz` 必须都是有效的常规文件，不能是 symlink；归档损坏或类型不对会在破坏性步骤前被阻止
- 正式恢复前会先校验 `postgres.dump` 可被 `pg_restore --list` 读取；校验失败不会进入 `DROP SCHEMA`
- 正式恢复前会检查写入相关服务是否已停止；若 `api`、`worker`、`redis` 等仍在运行，会直接阻止恢复
- create / restore 执行前都会校验当前 `docker-compose.prod.yml` 仍声明并挂载预期卷，且对应命名卷真实存在
- 任一条件不满足会阻止恢复
- 恢复会覆盖现有数据，无法“自动合并”
- 卷恢复会先清空目标卷中的全部内容（包括隐藏文件）再解压备份
- 跨版本恢复前需先确认数据库迁移兼容性

---

## 7. 恢复后验证

最小验证建议：

```bash
curl -fsS http://127.0.0.1/api/health
```

再执行业务冒烟：

1. 管理员登录
2. 投稿列表可读
3. 随机抽查 1-2 条历史论文报告
4. 队列任务状态无明显异常堆积

---

## 8. 失败回滚建议

若恢复后验证失败：

1. 立即停止新的写操作
2. 记录失败时间、错误日志、执行命令
3. 使用“恢复前额外备份”反向恢复到操作前状态
4. 在 `docs/deployment/launch-checklist.md` 对应回滚流程中登记事件
