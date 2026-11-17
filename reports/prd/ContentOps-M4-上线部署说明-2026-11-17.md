# ContentOps · M4 上线部署说明

| 项 | 内容 |
|---|---|
| 版本 | v1.1 / 2026-11-17（M7 修订：移除本地模型依赖，OCR/ASR/语义改走线上 llm 模块） |
| 范围 | M4 收尾：规则后台增强 + 对外开放 API + 压测与上线 |
| 前置 | M1/M2/M3 已上线（内容中心/合规/自适应/审核/导出/台账/素材识别） |
| 配套 | `ContentOps-多租户Customer权限验证设计PRD-2026-11-17.md`（CUS 鉴权基线） |

---

> **M7 修订（2026-11-17 晚）· 覆盖本文 §依赖固化相关描述**
> 已**删除** `requirements-contentops.txt` 及 Dockerfile 中的安装引用，镜像不再包含
> rapidocr-onnxruntime / onnxruntime / opencv / imageio-ffmpeg / faster-whisper / pyclipper / shapely。
> 素材文字提取改走 `VisionAdapter`（llm 模块线上视觉模型），语义合规判定改走 `LLMAdapter.compliance_check`
> （线上大模型），本地不再加载任何模型。本文下方 §2/§3 关于"固化本地依赖、cp 模型进容器"的描述
> **已作废**，以《Customer-客户内容工作台前端-M5部署说明》§9「线上模型配置」为准。
> 未配置线上模型时：文本合规（关键词/正则/归一化/消歧）照常工作，素材识别与语义层明确降级为
> `unavailable/skipped`，不阻塞上传与检测。

---

## 1. 本轮交付清单

| 模块 | 内容 | 落点 |
|---|---|---|
| 规则灰度 | `ComplianceRule` 增 `status`(draft/gray/active/archived) + `rollout_percent`(0-100)；gray 按确定性哈希 `(owner_id,rule_id)` 分桶，同一租户命中稳定 | `models/compliance_rule.py`、`services/compliance_service.py::_in_rollout` |
| 规则启停 | `PUT /rules/{id}/toggle` 独立端点，不改版本号 | `api/v1/rules.py`、`services/rule_service.py::toggle_rule` |
| 词库批量导入 | `POST /rules/import`，按归属去重 bulk_create | `services/rule_service.py::bulk_import` |
| LLM 供应商配置 | `CRUD /llm-providers`，强制 region=domestic（复用 LLMAdapter 海外黑名单） | `api/v1/llm_providers.py`、`services/llm_provider_service.py` |
| 对外 API Key | `contentops_api_key` 表（secret 只存 SHA-256 + 前缀展示）；签发/校验/吊销/限流 | `models/api_key.py`、`services/api_key_service.py`、`services/openapi_auth.py` |
| Key 管理端点 | `CRUD /api-keys`（登录态，owner 从 JWT 注入）；明文 secret 仅签发回显一次 | `api/v1/api_keys.py` |
| 对外只读端点 | `POST /openapi/compliance/check`、`GET /openapi/rules`，scope 鉴权 + 429 限流 + 审计 | `api/openapi/__init__.py` |
| 依赖固化 | OCR/ASR/ffmpeg/opencv-headless 依赖写入 requirements-contentops.txt，纳入镜像构建 | `requirements-contentops.txt`、`deploy/app/Dockerfile` |
| 压测 | 文本合规引擎压测脚本（dry-run，P95/吞吐指标） | `tests/bench_contentops.py` |

## 2. 数据库迁移（启动自动执行）

新增两个迁移，随 app 启动 `_run_sql_migrations()` 全量重跑（幂等）：

- `migrations/contentops_rule_gray_1794890000.sql`：给 `contentops_compliance_rule` 加 `status`/`rollout_percent` 列 + 索引。
- `migrations/contentops_api_key_1794890100.sql`：新建 `contentops_api_key` 表 + 索引。

均为 openGauss 兼容写法（`information_schema` 判列 / `ADD COLUMN IF NOT EXISTS` / 无 `to_regclass` / 无 `ON CONFLICT`）。
**验证启动日志出现 `Application startup complete` 且无迁移报错**，再确认新表/新列存在。

## 3. 镜像重建（必须）

M2/M3 的多媒体依赖此前是 `docker cp` + 离线 `pip install` 进当前容器的，**重建镜像会丢**。本轮已固化：

```bash
docker build -f deploy/app/Dockerfile -t agentpanel-app:latest .
```

构建会：① node 阶段编译前端；② `pip install -r requirements.txt` + `-r requirements-contentops.txt`（含 opencv-headless，避免 Debian 缺 libxcb 崩溃）。

> faster-whisper base 模型（≈145MB）不打入镜像：运行时优先 `/app/models/faster-whisper-base`，缺失则走 hf-mirror 下载兜底。容器网络不通外网时需提前把模型目录 `docker cp` 到 `/app/models/faster-whisper-base`，否则 ASR 部分降级跳过（不阻断 OCR 与文本检测）。

## 4. 对外开放 API 开通流程

默认不放行。租户需先由管理员（持 `contentops:rule:manage`）为「自己租户」签发 Key：

```bash
# 1) 签发（secret 仅此一次回显，务必保存）
POST /v1/contentops/api-keys
{
  "name": "第三方系统A",
  "scopes": ["compliance:check", "rules:read"],
  "rate_limit_rpm": 60,
  "allowed_ips": ["1.2.3.4"],   // 可选
  "expires_at": "2027-01-01T00:00:00+08:00"  // 可选
}
# → data.key_id + data.secret

# 2) 外部调用（两种凭据头二选一）
POST /v1/contentops/openapi/compliance/check
X-ContentOps-Key-Id: <key_id>
X-ContentOps-Secret: <secret>
{ "text": "待检测文案", "platform": "wechat" }
# 或 Authorization: Bearer <key_id>.<secret>

# 3) 规则查询（需 rules:read scope）
GET /v1/contentops/openapi/rules?layer=L4

# 4) 吊销
DELETE /v1/contentops/api-keys/<key_id>
```

**安全要点**：
- 对外端点与登录态路由物理隔离，走独立 `require_openapi_scope`，不读 JWT、不进 RBAC。
- scope 白名单只有 `compliance:check` / `rules:read`，签发时非法 scope 直接拒绝。
- 归属继承 Key 绑定的 CUS 租户：只可见平台级规则 + 本租户 L4 规则，跨租户隔离（authz L2）。
- fail-closed：无效凭据 401 / IP 不符 403 / scope 不足 403 / 超限 429；审计写 AuditLog（module=`contentops_openapi`，不记正文）。
- 限流按 key 维度 60s 窗口，Redis 优先、进程内降级（单实例可接受）。
- 对外端点只读：不落命中记录、不做改写/导出，写能力不对外开放。
- `AuthzContextMiddleware` 对 `ckey_*.secret` 形态 token 安全返回 None（不误判为非法 JWT），对外鉴权由依赖层完成。

## 5. 回归验证

```bash
.venv/Scripts/python tests/regression_contentops_m4.py       # M4 专项 26/26
.venv/Scripts/python tests/regression_contentops_authz.py    # CUS 鉴权 20/20
.venv/Scripts/python tests/regression_contentops.py          # 装配/建表 24/24
.venv/Scripts/python tests/smoke_contentops_flow.py          # M1 闭环 8/8
.venv/Scripts/python tests/bench_contentops.py               # 压测 P95 PASS
```

所有脚本测试数据 finally 清理；回归脚本需禁用本地不可达 Redis 走 DB/进程内降级（脚本内已处理）。

## 6. 已知边界

- 灰度分桶是确定性哈希，非按比例随机流量；好处是租户命中稳定，代价是分布近似而非精确百分比。
- API Key 以 customer 账号为单位，同一 customer 下多自然人无法再分权（对齐权限专项 PRD K2）。
- 对外限流进程内降级仅单实例准确；多副本部署须确保 Redis 可用。
- publisher confirms 未真正开启、真库真 MQ 端到端未跑等底座遗留仍适用（见长期记忆）。
