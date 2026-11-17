# ContentOps · 多租户 Customer 权限验证设计 PRD

| 项 | 内容 |
|---|---|
| 文档编号 | AP-CONOPS-AUTHZ-1.0 |
| 版本 / 日期 | v1.0 / 2026-11-17（首版：确立 customer(CUS) 为租户主体，复用 authz 全栈，整改权限码双轨判定） |
| 状态 | **设计有效，含 1 项 P0 代码缺陷待整改**（见 §7 缺陷 C1）；整改完成前 CUS 租户无法调用 contentops 业务接口 |
| 文档类型 | 权限验证专项 PRD（配套专项，不取代业务 PRD 的功能范围） |
| 适用层级 | contentops 插件 + `base/common/authz` 公共层（归属模型、鉴权依赖、审计） |
| 租户主体 | `customer`（CUS 域），JWT `typ=cus` / `sub=customer.id`；USR 域（员工/dept）不属于本文租户范畴 |
| 权限机制 | 复用既有 authz 全栈：L1 上下文 → L2 归属过滤 → L3 服务复核 → resource_grant 资源授权 → F8 越权审计；**CUS 主体不走 RBAC** |
| 上游文档 | `ContentOps-内容合规与自适应处理台-开发PRD-2026-11-17.md`（US-6 租户隔离、§6.7 权限、§10 数据模型、§14 T-01）、`ContentOps-多平台自媒体内容合规与自适应PRD-2026-11-17.md`（D7） |
| 落地代码 | `base/common/authz/{context,constants,filter,guard,service,audit}.py`、`base/common/authz/middleware/owner_context.py`、`base/common/authz/models/resource_grant.py`、`base/common/permissions.py`、`base/common/security.py`、`base/plugins/customer/api/v1/auth.py`、`base/plugins/contentops/**` |
| 安全约定 | 只列配置键名、权限码、代码路径与数据字段，**不记录 `config.conf` / `.env` / secrets 的任何取值** |

> **本文只解决一个问题**：把既有三份 ContentOps 文档中"全表 `tenant_id` + 全局租户过滤中间件 + RBAC 四元组"的**虚构权限设计**，替换为项目真实存在的、以 `customer` 为租户的 **authz 归属体系**，并给出可落地的数据模型、鉴权契约、路由改造与验收口径。功能范围（合规引擎/自适应/6 平台适配/审核/导出）不在本文重复，以开发 PRD 为准。

---

## 0. 决策锁定与本文定位

### 0.1 三项决策（v1.0，2026-11-17 确认）

| # | 决策项 | 确认结论 | 本文对应章节 |
|---|---|---|---|
| A1 | 交付形态 | **新增权限专项 PRD**，保留既有三份 ContentOps 文档不改 | 本文即该专项；§12 给出与既有文档的关系 |
| A2 | 租户主体域 | **`customer`（CUS 域）**：外部客户即租户，JWT `typ=cus`，归属 `owner_type='cus' + owner_id=customer.id`，恒 `self` 隔离 | §2 / §3 / §4 |
| A3 | 权限机制 | **复用 authz 全栈**：上下文 + 归属过滤 + 资源授权 + 越权审计；**CUS 不走 RBAC** | §3–§6；功能码双轨判定见 §7 |

### 0.2 术语对齐口径（本文最重要的一句话）

> 既有 PRD 中的 `tenant_id` / `tenant` 表 / "全局租户过滤中间件" / "RBAC 四元组" **在代码中不存在**，不得作为实现依据。本文全部替换为下表真实术语。凡既有文档与本文冲突，**权限与租户部分以本文为准**。

| 旧 PRD 术语（废弃） | 本文 / 代码真实术语 | 说明 |
|---|---|---|
| `tenant_id` | `owner_type` + `owner_id` | 双列归属，非单列；CUS 租户为 `('cus', customer.id)` |
| `tenant` 表 | `customer` 表（`base/plugins/customer/models/customer.py`） | 客户即租户，无独立租户表 |
| 全局租户过滤中间件 | `AuthzContextMiddleware` + `owned_queryset` / `get_owned_or_404` | 上下文注入 + 声明式归属过滤，非 ORM 全局中间件 |
| RBAC 角色-权限-数据范围-租户四元组 | CUS：归属过滤 + `resource_grant`；USR：归属过滤 + RBAC `data_scope` + 权限码 | CUS 与 USR 是两套并存的鉴权路径（§2.3） |
| 跨租户 404/403 | 统一 **404**（不暴露存在性）+ F8 审计限流 | 见 §6 |
| 租户管理员 / 平台管理员 | 本文不新造角色；CUS 租户内分权见 §7.3 与 §13 已知边界 | 避免与 USR 的 RBAC 角色混淆 |

---

## 1. 背景与要解决的问题

### 1.1 问题陈述

既有 ContentOps PRD 在"多租户隔离"上给出的是一套**脱离代码的设计**：假设有独立 `tenant` 表、全表 `tenant_id`、ORM 全局租户中间件、以及"角色-权限-数据范围-租户"RBAC 四元组。而 contentops 插件代码实际采用的是平台统一的 **authz 归属体系**（`base/common/authz/`）。二者是"两套语言"，直接导致：

- **实现口径不一致**：开发按 PRD 找 `tenant_id` 字段找不到，按 `owner_type/owner_id` 实现又与 PRD 验收标准对不上。
- **CUS 租户实际上无法使用 contentops**（P0 缺陷 C1，见 §7）：路由同时挂了 `require_owner`（支持 CUS）与 `require_permission`（USR/RBAC），后者以 `customer.id` 当 `user_id` 查 RBAC 权限，必然查不到 → 403，极端撞号情况下还会错误放行。
- **规则可见性语义无出处**：平台级规则 `owner=NULL` 全局可见、租户级规则归属隔离的现行设计（`ComplianceEngine.load_rules`），在 PRD 里没有定义。

### 1.2 本文目标

1. 确立"customer = CUS 租户"的单一术语与主体域边界（§2）。
2. 把 authz 全栈的每一层 mapped 到 contentops 的具体落点（§3–§6、§8）。
3. 定位并给出 P0 缺陷 C1 的整改方案（§7），使 CUS 租户能真正调用内容合规接口。
4. 给出全量数据模型对齐表（§9）、API 鉴权矩阵（§10）、回归验收口径（§11）。

### 1.3 本文不改什么

- 不改 contentops 的合规判定逻辑、平台适配规格、状态机、导出格式（以开发 PRD 为准）。
- 不改 JWT 签发算法与 `base/common/security.py` 的 `decode_access_token` 语义。
- 不引入 CUS 域的 RBAC（A3 硬约束）；不为 USR 域新增 data_scope 档位。
- 不新增独立 `tenant` 表或 `tenant_id` 字段。

---

## 2. 单一真源：主体域与术语

### 2.1 两棵树不可混用（项目铁律）

| 域 | 主体 | 主体表 | JWT | 组织树 | 本文角色 |
|---|---|---|---|---|---|
| **CUS** | 外部客户 | `customer` | `typ=cus`, `sub=customer.id` | `customer_organization` / `customer_organization_member` | **租户（本文唯一租户主体）** |
| **USR** | 企业内部员工 | `user`（`base/core/users/models/users.py`） | `typ=usr`, `sub=user.id` | `department` | 平台侧运营/管理（非租户） |

- `department`（USR）与 `customer_organization`（CUS）是**两棵独立组织树，禁止混用**。
- CUS ↔ USR 的唯一桥梁是 `identity_link`（一个自然人最多关联 1 个 customer + 1 个 user，双列各自 UNIQUE，**仅允许"提示→主动确认→验证"建立，禁止自动绑定**）。本文的权限判定**不依赖** `identity_link`。

### 2.2 归属字段（所有 contentops 业务表通用）

| 字段 | 类型 | 约定 |
|---|---|---|
| `owner_type` | `char(3)` | `cus` / `usr` / `org`；`NULL` 表示平台级（仅规则/配置类表允许） |
| `owner_id` | `bigint` | `customer.id`（CUS）/ `user.id`（USR）/ `org.id`（ORG）；平台级为 `NULL` |

- CUS 租户归属 = `owner_type='cus' AND owner_id=customer.id`；**不接受客户端传入 owner 字段**，一律由 JWT 上下文注入，杜绝水平越权（对齐 `customer/api/v1/usage_router.py` 现行写法）。

### 2.3 两套鉴权路径并存（务必区分）

| 路径 | 主体 | 认证依赖 | 数据权限 | 功能权限 |
|---|---|---|---|---|
| 新版 authz | CUS / USR | `require_owner`（校验 typ/sub 同源） | `owned_queryset` 归属过滤；USR 叠加 RBAC `data_scope` | CUS：`resource_grant`（§7）；USR：`require_permission` 权限码 |
| 旧版 | USR（管理端） | `get_current_user_id`（**不校验 typ**） | RBAC `data_scope` | `require_permission` 权限码 |

> **红线**：CUS token（`typ=cus`）一旦流经 `get_current_user_id` / `require_permission` 这枚旧版齿轮，就会被当成 USR 处理（R-04 禁止的"跨表借用 ID"）。§7 的整改本质就是**切断 CUS 到这枚齿轮的通路**。

---

## 3. L1 身份与上下文层

### 3.1 JWT 签发（customer 登录，已落地）

`base/plugins/customer/api/v1/auth.py`（register / login / email-login 三处一致）：

```python
access_token = create_access_token(
    data={"sub": str(customer.id), "typ": "cus", "email": customer.email},
)
```
- 登录前置校验 `customer.is_active`；禁用账号不签发。
- `typ=cus` 与 `sub=customer.id` **同源**（R-04）；禁止兼容旧 token 语义、禁止跨表借用 ID。

### 3.2 上下文注入中间件（已落地）

`base/common/authz/middleware/owner_context.py::AuthzContextMiddleware`（`PRIORITY=5`，在审计 `TraceMiddleware(10)` 之后执行以继承 `trace_id`）：

- 读取 `Authorization: Bearer` → `parse_owner_token` → `resolve_full_owner`；
- `set_owner_context(owner)` 写入 `ContextVar.current_owner`，`request.state.owner` 同步注入；`finally` 清理；
- F8 越权限流闸门：封禁期主体直接 429（见 §6）；
- 排除路径：`/health`、`/docs`、`/openapi.json`、`/redoc`、`/static`、`/favicon.ico`、`/metrics`、`/v1/gateway`（数据面不参与业务 owner 上下文）。

### 3.3 `OwnerContext` 关键字段（`base/common/authz/context.py`）

| 字段 | CUS 取值 | 说明 |
|---|---|---|
| `owner_type` | `"cus"` | 来自 JWT `typ` |
| `owner_id` | `customer.id` | 来自 JWT `sub` |
| `data_scope` | `"self"`（恒定） | `resolve_full_owner` 对非 USR 主体直接原样返回，不叠加 RBAC |
| `org_ids` | `[]`（P0 不注入） | CUS 组织维度由 resource_grant 侧 `_customer_org_ids` 单独解析（§5.2） |
| `visible_user_ids` | `None` | 仅 USR 有意义 |
| `identity` | `"cus:{customer.id}"` | 限流/审计键 |

### 3.4 `require_owner` 依赖（已落地）

- 无 token / 非法 token → 401；合法 token → 完整 `OwnerContext`（USR 已叠加 data_scope）。
- 用法：`owner: OwnerContext = Depends(require_owner)`。
- **本文要求**：contentops 全部业务路由必须保留该依赖（现状已具备）。

---

## 4. L2 归属过滤层

### 4.1 核心 API（`base/common/authz/filter.py`，已落地）

| API | 用途 | 行为 |
|---|---|---|
| `build_owner_filter(owner, *, include_public, for_write, model)` | 构建归属 `Q` 条件 | CUS：`Q(owner_type='cus', owner_id=本人)`；USR：按 data_scope 收缩 |
| `owned_queryset(model, owner, ...)` | 列表/详情查询 | 返回强制带归属过滤的 QuerySet，可继续链式 filter；模型无 owner 字段抛 `TypeError` |
| `get_owned_or_404(model, pk, owner, ...)` | 单条强校验 | 先按主键查（不带归属）；不存在 → 404；存在但越权 → **记审计 + 404** |
| `is_accessible(obj, owner, ...)` | 对象级判定 | 本人恒可访问；公开只读（`visibility∈{public,template}`）读可跨归属、写不可 |

**CUS 恒 self 的硬语义**：`build_owner_filter` 对 CUS 不做任何 data_scope 扩展，严格本人归属；即使 `include_public=True` 也只对具备 `visibility` 字段的模型并入公开只读（contentops 10 张表均无 `visibility`，故实际不并入）。

### 4.2 contentops 表归属字段盘点（已落地，逐表核对）

| 模型 | Python 符号 | `owner_type` | `owner_id` | 平台级 `NULL` 允许 | CUS 租户可见性 |
|---|---|---|---|---|---|
| 源内容 | `ContentItem` | default `usr` | nullable | 否 | 仅本人 CUS 内容 |
| 成品版本 | `ContentVersion` | default `usr` | nullable | 否 | 仅本人 |
| 合规规则 | `ComplianceRule` | nullable | nullable | **是**（L1–L3 平台级） | 平台级全局 + 本人 L4 |
| 合规命中 | `ComplianceHit` | default `usr` | nullable | 否 | 仅本人 |
| 审核任务 | `ReviewTask` | default `usr` | nullable | 否 | 仅本人 |
| 导出快照 | `ExportPackage` | default `usr` | nullable | 否 | 仅本人 |
| 发布台账 / 效果数据 | `PublishLedger` / `EffectData` | default `usr` | nullable | 否 | 仅本人 |
| 平台规则配置 | `PlatformRuleConfig` | nullable | nullable | **是**（全局默认） | 全局默认 + 本人覆盖 |
| LLM 供应商配置 | `LlmProviderConfig` | nullable | nullable | **是**（全局） | 全局；租户级覆盖按 owner 叠加 |
| 素材 | `MediaAsset` | default `usr` | nullable | 否 | 仅本人 |

> **落地要求**：CUS 租户创建任何业务记录时，`owner_type` 必须写 `'cus'`、`owner_id` 写 `owner.owner_id`。经逐服务核对，现有**全部创建路径已在 service 层显式注入**（见 §7.4），模型 default `'usr'` 仅作 `owner=None` 时的兜底；**新增创建端点必须挂载 `require_owner`**，否则会静默落入 `('usr', None)`。

---

## 5. L3 服务复核层 + 资源授权

### 5.1 服务层复核（已落地）

`base/common/authz/guard.py`：
- `assert_owner_access(obj, owner, for_write=True)`：写操作/敏感读前二次校验，不匹配 → 404 + 审计；
- `recheck_owner(obj, owner, ...)`：非抛出式，供引擎/内部服务消费判定结果（R-02）。

**contentops 落点**：审核放行（`/reviews/{id}/decide`）、人工确认（`/versions/{id}/confirm`）、导出打包（`/exports`）等**状态跃迁与导出**操作，除 L2 过滤外须在 service 层调用 `assert_owner_access(obj, for_write=True)`（详见 §10 矩阵）。

### 5.2 资源授权（`base/common/authz/service.py` + `models/resource_grant.py`，已落地）

`ResourceGrant` 表：四元组 `(owner_type, owner_id, resource_type, resource_id)` 唯一；`effect=allow`、`expires_at` 可空（永久）、`granted_by` 标注来源。

`ResourceGrantService` 契约：

| API | 用途 |
|---|---|
| `check_resource_access(owner, resource_type, resource_id)` | 单资源授权判定；主体有效性校验 + 自身授权 + **CUS 组织继承** |
| `check_many(...)` | 批量判定（资源选择器） |
| `grant(...)` / `revoke(...)` | 授权/撤销（幂等；`get_or_create`，openGauss 不用 `ON CONFLICT`） |
| `list_by_subject(...)` / `list_by_resource(...)` | 授权清单 / 反查 |

**CUS 组织继承（本文复用的关键能力）**：
- `_customer_org_ids(customer_id)` 查 active 成员关系 + 组织本身 active，Redis 缓存 300s（`authz:org_ids:{customer_id}`），成员变动由 `organization_service` 主动失效；
- `check_resource_access` 对 `owner_type='cus'` 追加 `'org'` 维度授权，成员加入/退出组织自动生效/失效；
- `is_subject_active` 对 CUS 查 `Customer.is_active`，对 ORG 查 `status=='active'`，禁用主体不放行、恢复后自动恢复。

**现行 `ResourceType` 枚举**（`base/common/authz/constants.py`）：`model` / `kb` / `tool` / `agent` / `node_type`。**不含功能权限码**——§7.3 给出扩展建议。

---

## 6. F8 越权审计与限流（已落地）

`base/common/authz/audit.py` + `constants.py`：

| 项 | 值 / 行为 |
|---|---|
| 越权响应 | 统一 **404**（`OwnedResourceNotFound`），**不暴露资源存在性** |
| 审计写入 | `record_violation` → `AuditLog`（`module='authz'`, `operation='authz.violation'`, `level='warning'`, `status_code=404`），含 `trace_id` / `owner` / `path` / `method` / `resource_hint` |
| 限流阈值 | 同主体（`{owner_type}:{owner_id}`）1 分钟（`RL_WINDOW_SECONDS=60`）内越权 > 10 次（`RL_THRESHOLD=10`）→ 封禁 60s（`RL_BLOCK_SECONDS=60`） |
| 限流响应 | 封禁期请求直接 429 + `code=42901`；`record_rate_limited_hit` 留 info 级痕 |
| 超限审计 | `authz.rate_limit_alert`，`level='critical'`，`status_code=429` |
| 降级 | Redis 不可用退化为进程内计数（`_memory_counters`）；审计写失败仅打日志，**绝不阻断业务** |

**contentops 落点**：凡经 `get_owned_or_404` / `assert_owner_access` 的越权访问自动纳入上述体系，无需 contentops 自行实现。既有 PRD 要求的"跨租户写入审计日志"由此满足。

---

## 7. 核心缺陷与整改（本文重点）

> 核对结论：**唯一真实代码缺陷是 C1**（P0，CUS 被 RBAC 权限码误判）。其余均为既有能力确认或设计约束——不虚构缺陷。

### 7.1 缺陷 C1（P0）：CUS 租户被 RBAC 权限码误判

**现状**：contentops 7 个路由文件、全部业务端点均同时声明（逐文件核对，见 §10）：

```python
owner: OwnerContext = Depends(require_owner),                       # authz，支持 CUS
user_id: int = require_permission("contentops:xxx:yyy"),           # base/common/permissions.py，USR/RBAC
```

`require_permission` 的内部链路（`base/common/permissions.py`）：

```python
async def dependency(request, user_id=Depends(get_current_user_id)):
    user_perms = await get_user_permissions_cached(user_id)   # → PermissionService...RBAC 表
    if "*" in user_perms: return user_id
    missing = set(permissions) - set(user_perms)
    if missing: raise HTTPException(403, ...)                  # CUS 必然命中
```

而 `get_current_user_id`（`base/common/security.py`）**只从 JWT 取 `sub`、不校验 `typ`** → 对 `typ=cus` token 返回 `customer.id`。于是：

- **正常情况**：以 `customer.id` 查 RBAC 权限 → 无此 user → 空权限 → **403**，CUS 租户无法调用任何 contentops 接口；
- **撞号情况**：若 `customer.id` 恰好等于某 `user.id`，会错误继承该 user 的 contentops 权限 → **功能级越权**（R-04 明令禁止的跨表借用 ID）。

**结论**：这是既有 PRD"RBAC 四元组"虚构设计直接导致的工程后果，必须在进入内容合规开发前整改。

### 7.2 整改方案对比

| 方案 | 做法 | 满足 A3（CUS 不走 RBAC） | 保留功能码分权 | 评价 |
|---|---|---|---|---|
| **A（推荐）** | 新增**双轨鉴权依赖** `require_action(code)`：USR 分支走 `require_permission`（RBAC）；CUS 分支走 `resource_grant` 判定（把 12 个 contentops 权限码建模为资源授权） | ✅ | ✅ | 复用 `ResourceGrantService` + org 继承，改动可控，语义统一 |
| B | CUS 仅做归属过滤，完全不判功能码 | ✅ | ❌ | 最简单，但租户内无法区分"运营/审核员"，不满足开发 PRD §4 角色分工 |
| C | 为 CUS 建 RBAC 影子 user（`identity_link` 绑定） | ❌ | ✅ | 违背 R-14（禁止自动绑定）与 A3，引入双主体混乱，**否决** |

### 7.3 方案 A 落地契约（建议实现，非现状）

1. **扩展资源类型**：在 `base/common/authz/constants.py::ResourceType` 增加 `CONTENTOPS_ACTION = "contentops_action"`（用于内容合规功能码授权）。
2. **新增双轨依赖**（建议置于 `base/common/authz/permissions.py`，与旧 `permissions.py` 区分命名）：

```python
def require_action(code: str):
    async def dep(owner: OwnerContext = Depends(require_owner)) -> OwnerContext:
        if owner.is_admin_user:
            # USR：沿用既有 RBAC 权限码（行为不变）
            await _check_rbac_permission(owner.owner_id, code)   # 复用 get_user_permissions_cached
            return owner
        if owner.is_customer:
            # CUS：查 resource_grant（含组织继承），绝不进入 get_current_user_id
            ok = await check_resource_access(
                ("cus", owner.owner_id), "contentops_action", code
            )
            if not ok:
                raise HTTPException(404, "资源不存在")            # 不暴露功能存在性
            return owner
        raise HTTPException(401, "无效的认证凭据")
    return Depends(dep)
```

3. **授权数据初始化**：由平台管理员通过 `ResourceGrantService.grant(("cus", customer_id), "contentops_action", code)` 给租户授权；组织授权 `("org", org_id)` 可被成员继承。默认策略遵循 §5.2——**不隐式放行**，未授权即拒绝。
4. **租户内分权粒度**：以 customer 账号为单位授权（不同 customer 可有不同功能码组合）。**同一 customer 账号下的多个自然人无法再分权**——这是 CUS 恒 self 模型的固有限制，见 §13 已知边界 K2。

### 7.4 既有能力确认（非缺陷）：创建路径 owner 字段已正确注入

逐服务核对结果：contentops 全部 7 个 service 的创建路径**已显式注入** `owner_type=owner.owner_type if owner else "usr"` 与 `owner_id=owner.owner_id if owner else None`（`content_service` / `rule_service` / `review_service` / `ledger_service` / `export_service` / `media_service` / `adapt_service`；`ComplianceRule` 平台级规则在 `owner=None` 时为 NULL）。禁止信任请求体传入 owner 的约束已满足，与 `customer/api/v1/usage_router.py` 写法一致。

**保留要求**：新增任何创建端点必须沿用该注入范式；V7 回归断言长期保留以防回退。本文不将其列为缺陷。

---

## 8. 合规规则的可见性（平台级 + 租户级叠加）

`base/plugins/contentops/services/compliance_service.py::ComplianceEngine.load_rules` 已落地双来源加载：

```python
# 1. 平台级规则：owner 为 NULL，全局可见
q = Q(enabled=True) & (Q(owner_type__isnull=True) | Q(owner_id__isnull=True))
rules = list(await ComplianceRule.filter(q))
# 2. 租户级规则：叠加当前归属私有规则（owned_queryset）
owned = await owned_queryset(ComplianceRule, owner).filter(enabled=True)
rules.extend(r for r in owned if r.id not in seen)
# 3. 平台维度过滤：platform=NULL 为通用，否则仅匹配目标平台
```

**规则分层与归属映射（对齐开发 PRD §6.2 的 L1–L4）**：

| 层 | 内容 | `owner_type/owner_id` | 可见性 | 平台维度 |
|---|---|---|---|---|
| L1 法律法规 | 广告法绝对化用语等 | `NULL` | 全局 | `platform=NULL` 通用 |
| L2 行业规则 | 医疗/金融/教育等 | `NULL` | 全局 | 通用或按行业 |
| L3 平台规则 | 6 平台社区规范（公众号/微博/小红书/抖音/头条/B站） | `NULL` | 全局 | `platform` 指向具体平台 |
| L4 品牌规则 | 租户自定义词库/竞品词 | `('cus', customer.id)` | 仅本租户 | 可叠加平台限定 |

**跨租户保证**：L4 规则带 CUS 归属，经 `owned_queryset` 严格隔离；租户 A 无法读取/命中租户 B 的 L4 规则。`compliance_hit.rule_id` 关联规则，命中记录同样带归属（§4.2）。

---

## 9. 数据模型对齐表（旧 PRD `tenant_id` → 真实 `owner`）

> 生成规则：所有 contentops 业务表**不新增 `tenant_id` 列**；以 `owner_type`/`owner_id` 双列表达归属，CUS 租户取 `('cus', customer.id)`。既有迁移 `migrations/contentops_*.sql` 已含 owner 字段，无需为权限新增列（除非采纳 §7.3 的 resource_grant 授权数据）。

| 旧 PRD 表（概念） | 真实模型 / 归属字段 | CUS 租户落法 |
|---|---|---|
| `tenant` | `customer`（外部表，非 contentops 所有） | 一个 customer = 一个租户 |
| `content_item(tenant_id,…)` | `ContentItem(owner_type,owner_id,creator_id,…)` | `('cus', customer.id)`；`creator_id` 记录自然人 |
| `content_version` | `ContentVersion(owner_type,owner_id,…)` | 同上 |
| `compliance_rule` | `ComplianceRule(owner_type nullable,owner_id nullable,layer,platform,…)` | L4 写 `('cus', id)`；L1–L3 保持 NULL |
| `compliance_hit` | `ComplianceHit(owner_type,owner_id,rule_id,…)` | 同内容归属 |
| `review_task` | `ReviewTask(owner_type,owner_id,…)` | 同内容归属 |
| `export_package` | `ExportPackage(owner_type,owner_id,…)` | 同内容归属 |
| `publish_ledger` / `effect_data` | `PublishLedger` / `EffectData`(owner_type,owner_id,…) | 同内容归属 |
| `platform_rule_config` | `PlatformRuleConfig(owner_type nullable,owner_id nullable,platform,key,…)` | 全局默认 NULL；租户覆盖写 `('cus', id)` |
| `llm_provider_config` | `LlmProviderConfig(owner_type nullable,owner_id nullable,…)` | 全局 NULL；租户级按 owner 叠加 |
| `media_asset` | `MediaAsset(owner_type,owner_id,…)` | 同内容归属 |
| `audit_log` | `base.plugins.audit` 的 `AuditLog`（公共，非 contentops 表） | 由 `record_violation` 写入，含 `trace_id` / `user_id` |
| （旧无） | `resource_grant`（公共表） | CUS 功能码授权 + 组织继承（§7.3） |

---

## 10. API 鉴权矩阵（整改目标态）

> 图例：**R** = `require_owner`；**P** = `require_permission`（USR/RBAC）；**A** = `require_action`（§7.3 双轨，待实现）；**L2** = `owned_queryset`/`get_owned_or_404`；**L3** = `assert_owner_access`。现状全部为 `R + P`；目标态把 `P` 替换为 `A`（CUS 走 resource_grant，USR 保持 RBAC）。

| 路由文件 | 端点示例 | 现状 | 目标态 | 备注 |
|---|---|---|---|---|
| `content.py` | 创建/编辑/删除源内容 | R+P | R+A+L3(写) | 创建已注入 owner（§7.4 既有能力） |
| `content.py` | 列表/详情 | R+P | R+A+L2 | L2 声明式过滤 |
| `content.py` | `versions/{id}/confirm` | R+P(`review:decide`) | R+A+L3 | 状态跃迁，人工确认唯一出口 |
| `content.py` | `adapt/generate` | R+P | R+A+L2 | 生成成品后二次合规 |
| `compliance.py` | `compliance/check` | R+P | R+A+L2 | CUS 当前必 403（C1 直接受害者） |
| `review.py` | 队列 / `decide` | R+P | R+A+L2+L3(写) | 审核放行需复核 |
| `export.py` | 导出 / 下载 | R+P | R+A+L2+L3 | 导出快照绑定归属 |
| `ledger.py` | 台账 CRUD / 效果回填 | R+P | R+A+L2 | CUS 租户仅本人台账 |
| `rules.py` | 规则 CRUD / 平台配置 | R+P | R+A+L2(租户级) | 平台级规则只读全局可见；**CUS 不应有 `rule:manage` 默认授权** |
| `media.py` | 上传/列表/删除/OCR/封面 | R+P | R+A+L2 | 素材归属隔离 |

**统一约束**：
- 所有端点保留 `require_owner`；禁止接收客户端传入的 `owner_type`/`owner_id`。
- 所有单条写/状态跃迁端点追加 L3 `assert_owner_access(..., for_write=True)`。
- 平台管理员（USR）管理租户授权走 `ResourceGrantService.grant/revoke`，不经 contentops 业务路由。

---

## 11. 验收与回归口径

> 采用项目现行回归脚本风格（`tests/regression_*.py`，pass/fail 计数）。以下为权限专项必须覆盖的断言清单。

| # | 用例 | 预期 |
|---|---|---|
| V1 | CUS token 调 `/compliance/check`（已授权 `contentops:compliance:check`） | 200；命中结果仅含平台级规则 + 本租户 L4 规则 |
| V2 | CUS token 调任一 contentops 端点（整改前） | 403（C1 复现，整改前为已知失败态） |
| V3 | CUS token 访问另一 customer 的 `content_item` 详情 | 404 + `AuditLog` 写入 `authz.violation`（warning） |
| V4 | CUS 列表接口 `owned_queryset(ContentItem)` | 仅返回 `owner_type='cus' AND owner_id=本人` 的记录 |
| V5 | L4 规则隔离：租户 A 规则不出现在租户 B 的 `load_rules` 结果 | 通过 |
| V6 | L1–L3 平台级规则（`owner=NULL`）对任意 CUS 可见 | 通过 |
| V7 | 创建路径归属注入：CUS 新建内容落库 `owner_type='cus'` | 通过（既有能力回归守护，§7.4） |
| V8 | 未授权功能码的 CUS 调对应端点 | 404（不暴露功能存在性），无功能码跨界 |
| V9 | org 继承：customer 加入组织后获得该 org 的 `contentops_action` 授权；退出后失效 | 通过（缓存失效生效，≤300s TTL 兜底） |
| V10 | 禁用主体（Customer.is_active=false）调用 | 不放行；恢复后自动恢复 |
| V11 | F8 限流：同 CUS 1 分钟内 >10 次越权 | 第 11 次起 429（`code=42901`）+ critical 审计 |
| V12 | USR 主体既有 RBAC 行为不回归 | 全部原有用例通过（方案 A 不改 USR 分支） |
| V13 | JWT typ/sub 非法（typ=其他 / sub 非数值） | 401，不进入业务层（R-04） |

---

## 12. 与既有文档的关系

| 文档 | 定位 | 本文处理 |
|---|---|---|
| `ContentOps-多平台自媒体内容合规与自适应PRD-2026-11-17.md`（v1.2） | 产品决策（D1–D9），D7=多租户 | 本文落实 D7 的真实技术口径；**§9 数据模型表的 `tenant_id` 以本文 §9 替换** |
| `ContentOps-内容合规与自适应处理台-开发PRD-2026-11-17.md`（v1.0） | 功能开发范围（US-1~6、§6 功能、§10 模型、§14 任务） | 本文取代其中 §1 边界第 4 条、§4 角色权限、§6.7 权限、§10 数据模型、§11 API 鉴权相关表述；**功能范围不变** |
| `ContentOps-卡点解决报告-平台API与LLM合规-2026-11-17.md`（v1.1） | 平台 API / LLM 出域调研 | 与本文无冲突；T2 LLM 出域约束继续适用 |

> 既有文档中的 `tenant_id` / 全局租户中间件 / RBAC 四元组表述**不删除、不重写**（保持历史留档），但在涉及权限实现时**一律引用本文**。

---

## 13. 已知边界（不隐瞒）

| # | 边界 | 影响 | 建议 |
|---|---|---|---|
| K1 | **C1 整改未完成前，CUS 租户无法调用 contentops**（P0） | 内容合规的 C 端客户场景不可用 | 按 §7.3 实现 `require_action` + 路由替换 + 授权初始化，先于 M1 联调 |
| K2 | CUS 恒 self，**同一 customer 账号下多个自然人无法再分权** | 租户内"运营/审核员"双人分权无法用 RBAC 表达 | 短期以不同 customer 账号 + 不同功能码授权区分；中期评估 `customer_organization` 成员角色模型 |
| K3 | `resource_grant` 现无 `contentops_action` 类型 | §7.3 需扩展枚举 + 授权数据 | 属小改动；须同步管理端授权 UI |
| K4 | 既有 `require_permission` 仍被 USR 管理端大量接口使用 | 方案 A 只替换 contentops 路由，不动全局 | 避免全局替换，防止 USR 回归 |
| K5 | 本文未做真库端到端压测 | 断言 V1–V13 中涉及 DB/MQ 的为设计态 | 按项目回归脚本在 dev 环境实跑后回填结果 |
| K6 | 越权审计依赖 audit 插件表存在 | 缺表时 `record_violation` 仅打日志（降级不阻断） | 保持既有降级语义，不改为 fail-closed |
| K7 | `customer_organization` 在 `base/plugins/customer/models/customer_organization.py` 为兼容 shim | resolve_plugin_symbol 解析路径为 shim 路径，功能正常 | 真源在 `packages/common/models/customer_organization.py`，勿改 shim 语义 |

---

## 附录：代号索引表

| 前缀 | 英文 | 含义 | 位置 |
|---|---|---|---|
| A1–A3 | Decision | 本文三项决策（交付形态 / 租户主体 / 权限机制） | §0.1 |
| C1 | Conflict/Defect | 唯一真实代码缺陷：CUS 被 RBAC 权限码误判（P0） | §7.1 |
| D1–D9 | Decision | 产品决策（既有文档，本文沿用） | 既有 v1.2 §0 |
| K1–K7 | Known boundary | 已知边界 | §13 |
| L1–L3 | Layer | authz 分层（上下文 / 归属过滤 / 服务复核） | §3–§5 |
| R / P / A / L2 / L3 | — | 鉴权矩阵图例（require_owner / require_permission / require_action / 归属过滤 / 服务复核） | §10 |
| V1–V13 | Verification | 回归验收断言 | §11 |

> 注：`P0` 在缺陷 C1 中表示**缺陷严重度**；在合规规则（L1–L4 / hit 等级）中表示**风险等级**，二者无关，按上下文区分。
