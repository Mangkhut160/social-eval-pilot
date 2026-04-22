# 文科论文评价系统生产环境变量示例

以下变量用于正式部署时的最小配置基线。

## 应用环境

```env
APP_ENV=production
PUBLIC_BASE_URL=https://app.socialeval.example
API_BASE_URL=https://api.socialeval.example
ALLOWED_ORIGINS=https://app.socialeval.example
SESSION_COOKIE_SECURE=true
SESSION_COOKIE_DOMAIN=socialeval.example
SECRET_KEY=<strong-random-secret>
DEFAULT_PROVIDER_NAMES=z-ai/glm-5.1,qwen/qwen3.6-plus,openai/gpt-5.4
```

## 数据与队列

```env
DATABASE_URL=postgresql://socialeval:<password>@postgres:5432/socialeval
REDIS_URL=redis://redis:6379/0
```

## AI Provider

```env
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
DEEPSEEK_API_KEY=
ZENMUX_BASE_URL=https://zenmux.ai/api/v1
ZENMUX_API_KEY=
```

## 邮件

```env
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=noreply@socialeval.example
```

## 对象存储

```env
OBJECT_STORAGE_BACKEND=local
OBJECT_STORAGE_ENDPOINT=
OBJECT_STORAGE_REGION=
OBJECT_STORAGE_BUCKET=
OBJECT_STORAGE_ACCESS_KEY=
OBJECT_STORAGE_SECRET_KEY=
OBJECT_STORAGE_PREFIX=socialeval
```

## 说明

- `APP_ENV=production` 时，`SECRET_KEY` 不能使用默认占位值。
- `APP_ENV=production` 时，`ALLOWED_ORIGINS` 不能为空。
- 前端若未显式提供 `VITE_API_BASE`，会回退到当前页面同源地址。
- `DEFAULT_PROVIDER_NAMES` 可用来切换默认模型集合；当前试点推荐 `z-ai/glm-5.1,qwen/qwen3.6-plus,openai/gpt-5.4`。
- `OBJECT_STORAGE_BACKEND` 当前支持 `local` 与 `s3`。
- 使用 `s3` 时，`OBJECT_STORAGE_BUCKET` 必填；`OBJECT_STORAGE_ENDPOINT` 可用于 S3 兼容对象存储。
- `SESSION_COOKIE_DOMAIN` 为空时表示不显式指定 cookie domain；生产环境通常应设置为正式主域名。
