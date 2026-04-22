# 文科论文评价系统本地演示模式说明

**版本**：2026-04-16  
**适用目录**：`/home/xiwen/social-eval-pilot`

---

## 1. 目标

本地演示模式用于：

- 固定本机演示入口
- 保留当前 `Zenmux` 外部模型调用能力
- 提供统一的启动、停止、状态查看、日志查看命令
- 在平台公网 IP 直连未打通前，保留临时外网隧道能力

说明：

- 本模式**不会修改**当前 `.env` 中的 `ZENMUX_BASE_URL` 和 `ZENMUX_API_KEY`
- 本模式**不会解决** `111.186.57.186` 的平台侧公网映射问题
- 当前固定本地入口为：`http://127.0.0.1`

---

## 2. 固定演示入口

在部署目录 `/home/xiwen/social-eval-pilot` 中执行：

```bash
uv run python scripts/manage_demo.py urls
```

默认会输出：

- 本机入口：`http://127.0.0.1`
- 局域网入口：`http://<当前内网 IP>`
- 临时外网入口：若已有 `Pinggy` 隧道，会显示 `https://...run.pinggy-free.link`

---

## 3. 常用命令

以下命令均在 `/home/xiwen/social-eval-pilot` 中执行。

### 3.1 启动演示栈

```bash
uv run python scripts/manage_demo.py up
```

### 3.2 查看当前状态

```bash
uv run python scripts/manage_demo.py status
```

### 3.3 查看固定入口

```bash
uv run python scripts/manage_demo.py urls
```

### 3.4 查看日志

查看全部关键服务最近 100 行日志：

```bash
uv run python scripts/manage_demo.py logs
```

只看 `api` 和 `worker`：

```bash
uv run python scripts/manage_demo.py logs --tail 200 api worker
```

### 3.5 停止演示栈

```bash
uv run python scripts/manage_demo.py down
```

---

## 4. 临时外网演示入口

当前已接入 `Pinggy` 临时隧道。

### 4.1 启动临时外网隧道

```bash
uv run python scripts/manage_demo.py tunnel-up
```

脚本会：

- 若发现已有隧道在运行，直接打印现有 `https://` 地址
- 若没有，则后台拉起新的隧道并打印新的地址

### 4.2 停止临时外网隧道

```bash
uv run python scripts/manage_demo.py tunnel-down
```

说明：

- 隧道 PID 保存在部署目录下的 `pinggy.pid`
- 隧道输出日志保存在部署目录下的 `pinggy.log`
- 匿名 `Pinggy` 隧道通常是临时的，不可视为正式生产入口

---

## 5. 演示前建议检查

### 5.1 栈状态

```bash
uv run python scripts/manage_demo.py status
```

应确认以下容器为 `Up`：

- `api`
- `worker`
- `frontend`
- `nginx`
- `postgres`
- `redis`

### 5.2 健康检查

```bash
curl http://127.0.0.1/api/health
```

应返回 `status=ok`。

### 5.3 外部模型能力

本地演示模式保留当前 `.env` 中的：

- `DEFAULT_PROVIDER_NAMES`
- `ZENMUX_BASE_URL`
- `ZENMUX_API_KEY`

因此上传论文后，评测任务仍会走 `Zenmux`。

---

## 6. 当前已验证的演示链路

当前试点环境已验证：

- 本地首页访问成功
- `/api/health` 返回 `200`
- 管理员登录成功
- 管理员可创建邀请，受邀用户可通过激活链接完成首次设密
- 上传 `txt` 样例成功
- `worker` 实际调用 `Zenmux`
- 公开报告可读取
- 专家可在网页端打开待复核任务并逐维度提交复核意见
- `Pinggy` 临时外网隧道可访问首页和 `/api/health`

当前前端演示重点界面：

- 登录页 / 邀请激活页共用同一入口，激活链接格式为：

```text
http://127.0.0.1/?invitation_token=<token>
```

- 投稿人首页提供拖拽上传区，也可点击选择文件
- 投稿人需先上传稿件，再点击“开始评测”，随后可查看状态摘要、报告快照历史、多轮结果切换
- 若稿件被预检拒稿，界面会提示“需重新上传”并给出修改后再次上传的动作提示
- 左侧展示最近论文列表
- 右侧展示当前论文的状态摘要、报告快照历史、多轮结果切换
- 每个快照均可直接下载 `JSON` / `PDF`
- 专家首页提供待复核任务列表，点击任务后可填写各维度专家评分与修改理由，再提交复核

---

## 7. 注意事项

- 代码同步到 `social-eval-pilot` 时，不要覆盖 `.env`
- 若只做本地演示，优先使用 `http://127.0.0.1`
- 若需要临时外网演示，再启动或复用 `tunnel-up`
- 若要正式公网直连，仍需单独处理云平台的公网映射 / NAT / 安全组
