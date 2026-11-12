# AgentPanel 产品需求文档（PRD）v1.0（重建版）

> ## ⚠️ 状态提示（2026-11-12 第二轮复审）
>
> **本文档已被复审判定「不通过，须重构」，不得继续作为内部对齐基线引用。**
>
> 原因：§1.1 将产品定位写为「智能体租用 + 计量计费平台」，与产品负责人确认的定位「后台管理 + 业务支撑平台，以独立插件方式工作，后续集成 CRM/HR/财务等信息化模块」不符；全文需求按 Harness 插件视角展开，平台层需求为零。
>
> 处置：本文档应改名降级为《Harness 商业化插件 PRD》，另建《平台 PRD》。首轮评审的「有条件通过」决议已撤销。
>
> 详见同目录 `AgentPanel-PRD-复审报告-2026-11-12.md`。
>
> **更新（2026-11-12 第三轮）：平台层正式需求基线已由 `AgentPanel-平台PRD-v2.0-2026-11-12.md` 承接**——该文件按标准需求规格说明书格式重建，含 33 条需求的评级与价值评定。本文档保留历史原貌，待按 v2.0 附录 C 改名降级为《Harness 商业化插件 PRD》。
>
> **更新（2026-11-12 第四轮）：本文档全部需求条目已作废。** 产品负责人要求「不保留修改前的需求，重新确定一版新需求」。现行平台级基线为 `AgentPanel-平台级需求规格-v3.0-2026-11-12.md`（全新基线、25 条需求、零继承），`FR-01~15` / `NFR-01~08` / `PC-1~6` 不再作为任何需求的输入、来源或追溯依据。本文档仅作归档。

| 项目 | 内容 |
|---|---|
| 文档版本 | v1.0（重建版 / 待评审） |
| 整理日期 | 2026-11-12 |
| 产品版本 | AgentPanel `v0.1.0`（`config.conf [app]`） |
| 状态 | **草稿，待产品负责人确认** |
| 适用范围 | 服务端控制面 + 网关数据面 + 编排服务 + Windows 桌面客户端 + Web 运营后台 |
| 关联文档 | `reports/architecture/*`、`reports/specs/*`、`reports/ops/*`、`.workbuddy/memory/2026-11-0{9,10}.md` |

---

## 0. 本次整理说明（务必先读）

### 0.1 为什么要「重建」而不是「修订」

全仓检索确认：**仓库内不存在任何 PRD 文件，`docs/` 目录整体缺失**。但代码中存在对一份已丢失 PRD 的硬引用：

- `base/plugins/customer/services/identity_service.py:5` 溯源 `docs/用户侧智能体设计流PRD.md §3.2（D1~D8）` 与 `§3.3（L1~L10，本服务的直接依据）`；
- 同文件 `:8` 引用 `docs/arch/04-核心流程与接口契约.md`、`docs/arch/06-架构自检与开发基线.md R-04/R-14`；
- `reports/ops/l3-split-p7-observation-log.md:745` 将「customer 插件 PRD 编号 L1~L10」列入改名白名单（改了会错义）；
- `.workbuddy/memory/2026-11-10.md:57` 明确三套 L 编号体系不可混改，其中「customer 插件 PRD 编号 L1~L10 与脱敏等级」属排除项。

即：**需求基线文档已丢失，现存的是技术规格（spec）、架构快照、验收报告与代码实现**。用户侧智能体设计流、身份关联 L1~L10、脱敏等级 D1~D8 的逐条原文均无从查证；历史会话检索亦无留存。因此本版是按「现存事实 + 代码可确认行为」重建的可执行基线，而非原 PRD 的复原。

### 0.2 证据等级标注约定

全文每条需求标注来源等级，评审与验收时按等级区别对待：

| 等级 | 含义 | 可否直接作为验收依据 |
|---|---|---|
| **A** | 有 spec / 架构文档 / 验收报告明确记载 | 可以 |
| **B** | 代码实现与配置可确认，但无产品文档定义 | 有条件，需产品补签 |
| **C** | 仅从代码注释、变量命名反推的「原 PRD 意图」 | **不可以**，须产品负责人逐条确认 |

### 0.3 本版新增/变更

1. 首次把散落在 12 份 spec、3 份架构文档、20+ 份运维报告中的需求统一编号（FR-01 ~ FR-15、NFR-01 ~ NFR-08）。
2. 首次显式区分「已交付 / 观察期 / 未交付 / 形同虚设」四种交付状态。
3. 首次列出「明确非目标」清单（§3.2）与「待产品决策」清单（§11.2）。
4. 补齐原 PRD 缺失的商业闭环、成功指标与验收口径章节（其中大部分内容为**待定义**，见评审报告）。

### 0.4 阅读约定

- §5 功能需求中的「状态」指**当前实现状态**，不是计划状态。
- 涉及密钥、口令、支付商户号的配置一律不记录取值，只记录键名与位置。
- 端口、TTL、阈值等数值均引自 spec 原文，改动须同步更新 `reports/specs/*` 与本文档。

---

## 1. 产品概述

### 1.1 一句话定位

> 把开源 AI Agent 客户端 DeepSeek Harness（`dshw`）改造成可商业化运营的 **「智能体租用 + 计量计费平台」**：终端用户在定制 Windows 桌面端注册登录 → 换取网关短期租约 → 在本机执行 Agent、模型流量经平台网关代理 → 平台按真实用量计量扣配额 → 通过会员与订单充值；运营方在 Web 后台管理客户、组织配额、模型凭据、订单与审计。

来源：`dshw/README.md`（上游开源定位）、`dshw/apps/desktop/src/agentpanel-account-backend.ts:1-22`、`base/plugins/harness/manifest.json`、`reports/architecture/target-architecture-local-agent.md §2`。证据等级 **A/B**。

### 1.2 背景与要解决的问题

| 问题 | 本产品的应对 |
|---|---|
| 开源 Harness 需用户自备 provider API Key，无法商业化 | 平台代管 provider 凭据，客户端只持短期虚拟 key（`dgw.*`），真实 key 不落地客户端 |
| Agent 在本机执行，服务端无法感知用量，无法计费 | 模型流量强制经网关数据面，网关 `source=gateway` 记账为**唯一权威口径** |
| 客户端不可信，可能绕过计量或欠费跑模型 | 租约 TTL + 额度预占 + 流式看门狗 + 越额截断 + 自动吊销 |
| 运营方需要管客户、定价、配额、审计 | Web 后台 + 客户/会员/订单/配额/审计模块 |
| 双主体（客户 customer / 后台用户 user）身份割裂 | 身份关联：认人不并资产，需「提示→确认→验证」 |

来源：`reports/specs/harness-llm-credentials/spec.md`、`reports/specs/harness-quota-interrupt/spec.md`、`reports/architecture/target-architecture-local-agent.md §4.2`、`base/plugins/customer/services/identity_service.py:2-13`。证据等级 **A**。

### 1.3 产品目标（建议稿，待确认）

| ID | 目标 | 度量 | 状态 |
|---|---|---|---|
| G1 | 用户无需持有 provider key 即可使用 Agent | 客户端零 provider key 落地率 100% | 已实现，缺量化验收 |
| G2 | 平台可按真实用量准确计费 | 网关账 vs 客户端证据差异率 ≤ 阈值 | 部分，三套账未收敛 |
| G3 | 不出现无配额的无限使用 | 越额拦截率 100% | **未达成**（见 §11.1 R-04） |
| G4 | 客户可自助注册、登录、充值 | 端到端链路可用 | 注册登录已通，**充值未通** |
| G5 | 运营方可管、可查、可审 | 看板/审计/报表覆盖 | 部分 |
| G6 | 服务可独立发布、可回滚 | 三进程独立镜像 + 灰度开关 | 已实现（二元切换） |

> **缺口**：原 PRD 与现存文档中**没有任何商业成功指标**（注册数、付费转化率、ARPU、留存、毛利、成本上限）。G1~G6 为本次整理按功能反推的建议稿，**证据等级 C**，须产品负责人重新定义。

### 1.4 关键产品契约（不可协商的红线）

以下 6 条是各 spec 反复声明、且已构成系统行为基础的契约，任何需求变更不得违反：

| ID | 契约 | 出处 |
|---|---|---|
| PC-1 | **网关是唯一计费权威**：模型流量必须且只能经网关；`UsageRecord(source=gateway)` 为权威账，客户端上报只是「证据」，三套账严禁混算 | `target-architecture-local-agent.md §4.2/§7`、`harness-reconciliation/spec.md §1` |
| PC-2 | **租约是短期通行证**：虚拟 key 仅签发时返回一次，可续期/吊销；在途请求不因续期切断，吊销即时生效（存在 8s 缓存窗口） | `gateway-lease-ttl-renewal/spec.md §1/§3` |
| PC-3 | **不让用户欠费跑模型**：入口预检 → 估算 → 原子预占 → 流式看门狗 → 越额主动截断 → `partial` 记账 → 自动吊销；已发给 provider 的 token 收不回，**不承诺零超支** | `harness-quota-interrupt/spec.md §1/§2` |
| PC-4 | **真实凭据不落地客户端**：provider key 只存后台、注入子进程、全链路脱敏、未配置 fail-closed；`dgw.*` / JWT / `client_id.secret` 三类凭据双向拒绝 | `harness-llm-credentials/spec.md`、`gateway/api-boundary.md §2` |
| PC-5 | **对账只发现、不改账**：网关账 vs 客户端证据按 `idem_key` 前缀分区产出差异，供人工处理，不自动清零、不自动修正计费 | `harness-reconciliation/spec.md §1/§13` |
| PC-6 | **服务端不承诺客户端隔离**：不执行 agent、不提供沙箱、不承诺本机权限隔离；策略快照只「说清楚」不「阻断」，**不保证客户端完全不出网** | `target-architecture-local-agent.md §11`、`harness-egress-policy/spec.md §1` |

---

## 2. 用户与角色

| 角色 | 主体 / 凭据 | 入口 | 核心诉求 | 证据 |
|---|---|---|---|---|
| **终端客户 customer** | `typ=cus` JWT，`customer` 表，email 唯一 + bcrypt | Windows 桌面客户端（定制 dshw） | 注册登录、使用 Agent、查余额/用量、充值 | `base/plugins/customer/api/v1/auth.py`；`.workbuddy/memory/2026-11-10.md:174-176` |
| **运营管理员 User** | 账号密码 + RBAC | `web` 管理后台 `/panel/login` | 管客户、组织配额、模型价格、凭据、订单、审批、审计 | `base/core/users/api/v1/*`、`web/src/router/index.js` |
| **组织 Owner** | `customer_organization` + 成员，多租户配额 | 后台组织管理 | 分配组织额度、查成员用量 | `customer/api/v1/organization_admin.py`、`base/common/quota/api/organization.py` |
| **编排服务 / 网关服务** | `X-Service-Id` + HMAC（编排无注册登录端点） | 内部 API | 会话编排、额度回呼、鉴权 | `.workbuddy/memory/2026-11-10.md:291` |
| **双身份关联对象** | 一个自然人 = 1 customer + 1 user | 身份关联流程 | 认人不并资产 | `customer/models/identity_link.py`、`identity_service.py` |

### 2.1 核心用户场景

- **S1 新用户首次使用**：下载安装桌面端 → 欢迎页邮箱验证码注册 → 自动签发网关租约 → 进入工作区使用 Agent（不出现「填写 API Key」入口）。
- **S2 老用户登录**：密码或邮箱验证码登录 → 自动签发/续期租约 → 使用。
- **S3 用量耗尽**：网关预检/流式看门狗判定越额 → 截断输出 → `partial` 记账 → 自动吊销租约 → 客户端提示购买。
- **S4 充值**：选择套餐/会员 → 下单 → 支付 → 回调增加时长/额度 → 恢复使用。
- **S5 运营配置**：后台配置 provider 凭据、模型价格、配额套餐、会员等级、动作策略 → 查看用量与审计报表。
- **S6 双主体关联**：系统发现同邮箱另一主体 → 打码提示 → 用户主动确认 → 验证对方归属 → 建立映射（不并资产）→ 可解绑（30 天冷却）。

> **缺口**：S1~S6 均为按实现反推，无用户故事、无交互原型、无异常分支文案定义。证据等级 **C**。

---

## 3. 范围界定

### 3.1 本期范围内（In Scope）

1. 桌面客户端的注册/登录/租约/账号展示与品牌定制（「DeepSeek 账号」→ 项目名）。
2. 服务端控制面：客户、组织、配额、会员、订单、模型凭据与价格、策略、审批、审计、看板。
3. 网关数据面：`dgw.*` 鉴权、上游 SSE 透传、用量记账、预算/并发/额度预检与截断。
4. 编排服务：会话/run/step 生命周期、策略三档评估、审批、审计事件。
5. 三进程物理拆分、监控告警、灰度与回滚能力。
6. 身份关联（认人不并资产）。

### 3.2 明确非目标（Out of Scope，来自各 spec 的硬声明）

| # | 非目标 | 出处 |
|---|---|---|
| 1 | 服务端不执行 agent、不提供沙箱、不承诺隔离本机权限 | `target-architecture-local-agent.md §11` |
| 2 | 不保证客户端完全不出网；哈希链只「发现」不「阻止」 | 同上；`harness-egress-policy/spec.md §1` |
| 3 | 不拆数据库、不改表结构、不迁历史数据 | `l3-service-split/spec.md §0.2` |
| 4 | 不做 K8s / 服务网格；不引入消息队列或 outbox（离线结算列为 P2 技术债） | 同上；`harness-orchestration-split/spec.md §1.3` |
| 5 | 不做同一时刻双写；app 迁移期只代理不本地落库 | `harness-orchestration-split/spec.md §2.5/§8.1` |
| 6 | 不调用真实 provider 做自动化验收（统一用本地假 provider） | 各 spec 验证章节 |
| 7 | 对账不合并账单、不自动修正计费、不引入 APScheduler | `harness-reconciliation/spec.md §13` |
| 8 | 不引入密钥加密 / KMS；不改审批 fail-closed 语义 | `harness-llm-credentials/spec.md §6` |
| 9 | 不提供真实出网阻断；不修改额度算法/对账算法/策略三档语义/网关鉴权协议 | `harness-egress-policy/spec.md §1`；`l3-service-split/spec.md §0.2` |
| 10 | 不做按租户 / 按百分比灰度（当前仅部署级二元切换） | `l3-split-p7-grayscale.md §2` |

### 3.3 当前交付状态总览（截至 2026-11-12）

| 状态 | 内容 |
|---|---|
| **已交付并验收** | 网关 standalone 数据面、编排 9100 逻辑与物理拆分（P0–P6 全通过）、共享包 `packages/common` 单一来源、租约 TTL/续期、额度中断、网关对账、共享上游客户端、出网策略快照、凭据脱敏、T7.4 监控告警（2 组 14 条规则）、customer 邮箱验证码注册登录与租约 E2E（16/16）、桌面端 20/20 自动化、业务逻辑回归 215 断言全绿 |
| **灰度观察期（未收口）** | 起算 `2026-11-09 13:33:40 +0800`，14 天，最早 `2026-11-23 13:33 +0800` 收口；T7.5（删灰度开关与 app 旧编排代码、更新架构图）只做预案不执行；五项准入未齐、三方签字未做 |
| **未交付（目标态）** | 服务端创建 run + 客户端 `claim`；服务端执行迁移到本机 dsh；配置包版本化与 Agent 强制升级；设备指纹/mTLS/IP 白名单；客户端心跳与在线状态；事件哈希链；三套账收敛（停写 `LLMUsageRecord`、历史回填、P6 三方对账门禁）；离线结算 outbox；额度执行下沉共享存储；独立只读 DB 账号；对账触发迁移到编排；按租户灰度；TLS 终止 / 远程直连；Alertmanager 外部值班渠道 |
| **形同虚设 / 待激活** | 三个支付插件（`qixiang_pay` / `wechat_pay` / `alipay`）`is_installed=false` 且 `is_enabled=false`，路由不挂载；`[aif2f]` 配置节无代码读取；用户门户 `LandingPage.vue` 为模板文案且下载按钮为 `console.log` TODO；后台「财务管理/库存管理/智能体管理/第三方平台」等菜单对应插件未启用 |

来源：`reports/architecture/as-built-architecture-2026-11-09.md §10`、`reports/ops/l3-split-acceptance.md`、`reports/ops/l3-split-t75-closeout-plan.md`、各插件 `manifest.json`。证据等级 **A/B**。

---

## 4. 产品架构视图（面向需求理解，非技术设计）

```
[L1 表示层] Windows 桌面端（定制 dshw，本机执行 Agent，不可信，不持真实 key）
      │ ① 邮箱验证码注册/登录 → JWT(cus)
      │ ② 用 JWT 换 dgw.<lease_id>.<secret> 虚拟 key（短期租约）
      ▼
[L2 控制面] app :9998（127.0.0.1）
   客户/组织/配额/会员/订单/凭据/价格/策略/审批/审计/看板/租约签发
      │ ③ 编排请求经 9998 代理；额度由编排 HMAC 回呼 app 内部 API
      ▼
[L3-a 编排] :9100   会话/run/step、策略三档、审批、审计事件（只读 DB）
[L3-b 网关数据面] :9999   dgw.* 鉴权 → 上游 provider SSE 透传 → usage_record 记账
      │
      ▼   PG 15432 / Redis 6379（硬依赖）/ Prometheus :9090 / RabbitMQ
```

- **L1/L2/L3 术语有两套含义，禁止混用**：① 部署分层 L1=桌面端 / L2=app 控制面 / L3=独立服务（编排+网关）；② 安全分层 authz L1 接入层 / L2 路由层 / L3 服务层（`docs/arch/05 §2.1`）。③ customer 插件 PRD 的 L1~L10 是需求编号，与前两者无关。
- **两个不同 origin**：`:9998` 控制面只认 JWT、拒 `dgw.*`；`:9999` 数据面只认 `dgw.*`、拒 JWT（双向隔离）。
- 三端口仅绑定 `127.0.0.1`，无 TLS；远程直连属未交付范围。

来源：`reports/architecture/agentpanel-architecture.mmd`、`as-built-architecture-2026-11-09.md §2/§3`、`reports/specs/gateway/api-boundary.md §2`。证据等级 **A**。

---

## 5. 功能需求

> 优先级：P0 = 商业闭环必需；P1 = 运营与体验必需；P2 = 增强 / 技术债。状态见 §3.3 口径。

### FR-01 客户注册与登录（P0 / 已交付）

| 项 | 内容 |
|---|---|
| 描述 | 终端客户以邮箱为主体注册与登录，主体为 `customer`（JWT `typ=cus`），不复用后台 User 账号体系 |
| 规则 | 支持邮箱验证码注册、密码登录、邮箱验证码登录、重置密码、登出；email 唯一、bcrypt 存储、`is_active`/`is_verified` 状态位；验证码 Redis 优先（TTL 5min）+ 进程内降级 |
| 限频 | 邮箱 60s ≤ 3 次、IP 60s ≤ 10 次；`send-code` 已限流；`SECRET_KEY` 已外置 |
| 客户端 | 欢迎页只保留「登录」+「连接账号注册」，移除可见「添加 API Key」入口（后端 save/skip、hasApiKey、IPC 保留） |
| 验收 | `customer-auth-e2e-2026-11-11.md`：16/16 PASS，SMTP 可用，注册→登录→租约→网关鉴权→续期/吊销全通 |
| 来源 | `base/plugins/customer/api/v1/auth.py`、`dshw/apps/desktop/src/agentpanel-account-backend.ts`、`.workbuddy/memory/2026-11-10.md:159-177,229-231` |
| 等级 | **A/B** |

### FR-02 双主体身份关联「认人不并资产」（P1 / 已交付，原文缺失）

> ⚠️ 本节为**按代码注释反推的原 PRD §3.3，证据等级 C**。L1~L10、D1~D8 逐条原文已随 `docs/用户侧智能体设计流PRD.md` 丢失，以下编号**不得直接作为验收依据**，须产品负责人逐条补签。

| 编号 | 反推内容 | 代码依据 |
|---|---|---|
| L1 | 身份关联仅「发现与提示」：按同邮箱查找另一主体，只读、不建立映射；须用户主动确认 | `identity_service.py:151,227,413` |
| L2 | **原文缺失，无法反推** | — |
| L3 | 提示信息邮箱打码（保留首字符与域名 `a***@example.com`），不展示任何资产数据 | `:56,249` |
| L4 | **原文缺失，无法反推** | — |
| L5 | 建立关联前必须验证对方主体归属 | `:268,413` |
| L6 | 验证失败 5 次上限，锁定 10 分钟（600s） | `:39`、`VERIFY_MAX_ATTEMPTS` |
| L7 | 同一对主体 30 天最多提示 1 次；「不再提示」30 天 | `:34,36,380,524,714` |
| L8 | 仅建立映射，不复制/迁移/合并任何资产 | `:414`（D5 同义） |
| L9 | 解绑需再次验证归属，只解映射不删资产；解绑后 30 天冷却，冷却期不可手动恢复 | `:35,560,716,732` |
| L10 | 全量审计落库，用户可查操作历史（审计失败仅记日志不阻断） | `:167,196,755` |

状态机：`none` / `prompted` / `linked` / `dismissed` / `cooldown`。
红线：**R-14** 仅「提示→主动确认→验证」建立映射，无任何静默绑定入口；**D1** 双向唯一；**D5** 不并资产；**D2** 限频走封装方法（硬超时+熔断），失败退化进程内。
相关脱敏等级 **D1~D8 逐条缺失**，仅 D1/D2/D5/D7 可从注释反推。

### FR-03 网关租约（P0 / 已交付）

| 项 | 内容 |
|---|---|
| 描述 | 客户用 JWT 向控制面换取短期虚拟 key `dgw.<lease_id>.<secret>`，作为网关数据面唯一通行凭据 |
| 规则 | 虚拟 key 仅签发时返回一次；支持续期 / 吊销 / 查询；`owner_type/owner_id` 固定 `cus:<id>`，`client_id` 固定 `cus:<id>`；在途请求不因续期切断；吊销即时生效（缓存窗口见 NFR-01） |
| 客户端 | `account.json` 权限 0o600；TTL 80% 时自动续期；30s 周期检查 |
| 隔离 | `:9999` 拒 JWT、`:9998` 拒 `dgw.*`；编排服务无注册登录端点 |
| 验收 | E2E 16/16：签发→鉴权→续期→吊销后 401 |
| 来源 | `customer/api/v1/lease_router.py`、`services/gateway/common/lease_auth.py`、`dshw/apps/desktop/src/agentpanel-account-backend.ts:210-260`、`gateway-lease-ttl-renewal/spec.md` |
| 等级 | **A** |

### FR-04 Agent 使用链路（P0 / 部分交付）

| 项 | 内容 |
|---|---|
| 描述 | 用户在本机桌面端发起 Agent 会话；服务端不执行 Agent，模型流量经网关代理上游 provider |
| 规则 | 会话/run/step 生命周期、步骤上报含 usage、心跳、结算、取消；上游 SSE 字节级透传；`dsh_session_log` 剥离；失败也记账；上游超时 504、连接失败 502 |
| 品牌 | 账号提供方显示名取自后端 `[app] name`（当前 `AgentPanel`），隐藏原厂 `llm-deepseek` provider 行 |
| 凭据 | 真实 provider key 由网关注入子进程，客户端只见虚拟 key |
| 未交付 | 服务端创建 run + 客户端 `claim`（当前仍客户端自建 session/run）；服务端执行迁移到本机 dsh；配置包版本化与强制升级 |
| 来源 | `base/plugins/harness/api/v1/*`、`services/orchestration/app/api/*`、`shared-upstream-client/spec.md §2`、`target-architecture-local-agent.md §9` |
| 等级 | **A** |

### FR-05 计量与计费口径（P0 / 部分交付）

| 项 | 内容 |
|---|---|
| 描述 | 按真实模型用量记账并作为扣费依据，历史账单不受调价影响 |
| 权威账 | `usage_record(source=gateway)`；`HarnessStep` 为客户端证据；`LLMUsageRecord` 为历史遗留账。**三套账严禁混算** |
| 流水 | `price_snapshot` + `currency` 写入用量流水（`migrations/core_alter_table_usage_record_1793940000.sql`）；结算按 `model_price` 生效记录取价 |
| 幂等 | `usage_record.idem_key = harness:{run_id}:{node_id}:{seq}`；预占 `hold_id = harness:{run_id}`；预估宁高不低，`reserve_output` 须大于模型最大输出 |
| 配额归属 | 按 owner 累计，会话只做展示汇总 |
| 时长扣减 | 后台定时任务按 usage 汇总扣 `remaining_hours`（`base/start.py:410-445`） |
| 未交付 | 三套账收敛、停写 `LLMUsageRecord`、历史回填、P6 三方对账门禁 |
| 来源 | `harness-reconciliation/spec.md §1`、`target-architecture-local-agent.md §4.2`、`reports/ops/agentpanel-harness-plan.md:284-325` |
| 等级 | **A** |

### FR-06 配额与额度中断（P0 / 已交付但有语义缺口）

| 项 | 内容 |
|---|---|
| 描述 | 不让用户欠费跑模型：入口预检 → 估算 → 原子预占 → 流式看门狗 → 越额截断 → `partial` 记账 → 自动吊销租约 |
| 限额 | 单请求输出上限 4096 token、单租户并发 8、`estimate_chars_per_token=2.0`、`min_output_allowance=1`、`auto_revoke_on_exhausted=true` |
| 状态码 | 编排预占超限 → `429 quota_exceeded`；网关预算耗尽 → `402 lease_budget_exhausted` |
| 套餐回落 | 会员过期 / 无记录 / 等级 null / 客户不存在一律回落 `regular` |
| **语义缺口** | 无 `QuotaPlan` 的 customer → `resolve_plan=None` → `limit=0.0`；仅当 `owner_limit>0` 才施加账户级限制，故 **0 = 不计量不拦截**。新注册客户可无限使用（见 §11.1 R-04） |
| 来源 | `harness-quota-interrupt/spec.md §1/§2/§4`、`l3-service-split/spec.md §893-902`、`business-logic-test-2026-11-11.md:54,73`、`.workbuddy/memory/2026-11-10.md:251-252` |
| 等级 | **A/B** |

### FR-07 会员与等级（P1 / 已交付，口径缺文档）

| 项 | 内容 |
|---|---|
| 描述 | 三级折扣（regular/vip/svip）+ Fibonacci 动态等级（按累计充值时长） |
| 等级规则 | 等级 n 需 `sum(F(1)…F(n))` 小时；称号：Lv0 免费用户、1-2 体验、3-4 正式、5-7 高级、8-12 青铜、13-20 白银、21-33 黄金、34-54 铂金、55-88 钻石、89-143 至尊、≥144 传奇 |
| 配置 | `customer/manifest.json` 中 `default_free_hours: 0`、`max_fibonacci_level: 20`；`config.conf [aif2f.membership]` 同名字段**无任何代码读取** |
| 权益 | 总时长 / 剩余时长 / 折扣定价 / 升级进度 |
| **缺口** | 折扣率、免费赠送时长、时长与 token 的换算口径、等级上限 20 与称号表 ≥144 的矛盾，均无产品定义 |
| 来源 | `customer/services/membership_service.py:85-175`、`customer/models/{membership,customer_membership}.py` |
| 等级 | **B/C** |

### FR-08 订单与支付充值（P0 / **未打通**）

| 项 | 内容 |
|---|---|
| 描述 | 客户购买充值包 / 会员 → 生成订单 → 聚合支付 → 回调增加时长/额度 |
| 已实现 | `orders`/`order_items` 模型、`sales` 订单、`payment_transaction` 流水、`purchase_service`（会员折扣定价）、`payment_service`（回调开通）、`qixiang_service`（七相聚合支付）、订单过期定时任务 |
| **阻断** | 三个支付插件 `manifest.json` 均 `is_installed=false` / `is_enabled=false`，`base/common/router.py:25` 按 `is_installed && is_enabled` 门控 → **路由不挂载，notify 回调链路不可达** |
| **配置假启用** | `config.conf [qixiang_pay] enabled=true` 但 `setting.py` 无该属性、服务代码不读；`[aif2f] enabled=true` 全库零读取点；`order_expire_minutes=15` 无代码读取，定时任务硬编码 `sleep(600)` |
| **TODO** | `payment_service.py:24` 明确 `# TODO: 从配置文件或数据库加载支付配置` |
| 来源 | 各支付插件 `manifest.json`、`customer/services/payment_service.py`、`base/start.py:398,433,557`、`config.conf` |
| 等级 | **B（阻断事实）** |

### FR-09 组织与多租户配额（P1 / 已交付）

客户可归属 `customer_organization`（含 owner 成员），支持组织级配额管理与成员用量查询；配额按 owner 累计。来源：`customer/api/v1/organization_admin.py`、`base/common/quota/api/organization.py`。**缺口**：组织与 customer 个体配额的优先级、超额归属、成员退出后的额度归属未定义。等级 **B/C**。

### FR-10 动作安全与审批（P1 / 已交付，有限制）

三档策略判定（allow / 需审批 / deny）、人工审批请求与授权、Harness 审计事件。**已知限制**：DSH 原生审批无终端应答者，`outcome=unavailable`，依赖超时拒绝 fail-closed；服务端无法阻止客户端直连出网工具。来源：`harness/api/v1/{policy,approval,audit}_router.py`、`l3-split-acceptance.md:104-106`。等级 **A**。

### FR-11 审计与可观测（P1 / 部分交付）

全链路审计（输入/决策/执行/输出/系统层）、登录日志、数据变更日志、风险报表、`audit_log` 与五层审计表、`[audit] retention_days=90`；Prometheus `/metrics` 三进程 + 2 组 14 条告警规则。**未闭环**：`event_source` 未拆分、pushgateway/node_exporter 未启动、Alertmanager 外部值班渠道未配置、trace 保留 30 天仅规划。来源：`base/start.py:41-69`、`plugins/audit/*`、`l3-split-p7-metrics.md §8/§9`。等级 **A/B**。

### FR-12 运营后台（P1 / 部分交付）

RBAC / 菜单 / 部门 / 系统设置 / 插件管理 / 安装向导 / 仪表盘 / 客户 CRUD 与详情 / 会员等级配置。**问题**：存在对应插件未启用的空菜单（财务管理、库存管理、智能体管理、第三方平台）；落地页 `LandingPage.vue` 为模板文案（「轻松分享快乐时光」）、Windows/Android 下载按钮仅 `console.log` TODO、联系方式为遗留旧品牌 `sales@aif2f.cloud`。来源：`web/src/router/index.js`、`web/src/views/LandingPage.vue:146,179-186`。等级 **B**。

### FR-13 模型凭据与价格管理（P0 / 已交付）

provider / model / API key、`service_credential`、模型价格版本、子进程凭据注入与脱敏、未配置 fail-closed；不做 KMS。来源：`harness/api/v1/{admin,price}_router.py`、`migrations/harness_create_table_service_credential_1794200000.sql`、`harness-llm-credentials/spec.md`。等级 **A**。

### FR-14 对账（P1 / 已交付，只发现不改账）

网关账 vs 客户端证据按 `idem_key` 前缀分区，产出差异明细供人工处理；interval 600s、window 24h、max 168h；高阈值 `diff_amount=1000` token、`diff_rate=0.10`、`diff_cost=1.0`、`missing=1000`、`duplicate_ratio=2.0`。**未交付**：对账触发仍在 app（`reconcile_in_orchestration=false`）、P6 三方对账门禁。来源：`harness-reconciliation/spec.md §6/§13`、`as-built-architecture-2026-11-09.md §9.6`。等级 **A**。

### FR-15 灰度与发布（P1 / 已交付，能力受限）

`orchestration.mode = app | proxy`（当前 `proxy`）：app 只代理不双写、下游不可达统一 503；三独立 Docker 镜像、每阶段可回滚、14 天观察期。**限制**：仅部署级整机二元切换，无按租户/百分比切流；T7.5 收口后**无运行时回切能力**，只能 `git revert` + 重建三镜像 + 恢复 `mode=proxy` + 重新起算观察期。回切阈值见 NFR-07。来源：`l3-split-p7-grayscale.md §2/§4/§5`、`l3-split-t75-closeout-plan.md:137-147`。等级 **A**。

---

## 6. 核心业务流程（正常路径）

```
① 注册/登录  桌面端 → POST /v1/customer/auth/send-code → /register 或 /login-code → JWT(cus)
② 换租约    POST /v1/customer/leases（JWT）→ dgw.<lease_id>.<secret>（仅返回一次）
③ 发起会话  客户端 → 9998 /api/v1/harness/* 代理 → 编排 9100 建 session/run
④ 额度预占  编排 HMAC 回呼 app /internal/v1/harness/quota/* → hold_id=harness:{run_id}
⑤ 模型调用  客户端 → 9999 /chat/completions（dgw.*）→ 网关注入真实 provider key → 上游 SSE
⑥ 记账      网关写 usage_record(source=gateway, price_snapshot, currency, idem_key)
             ↑ 唯一权威账；HarnessStep 仅为证据；失败也记账
⑦ 结算释放  step 结算 / 释放 hold → 后台定时按 usage 汇总扣 remaining_hours
⑧ 越额     看门狗截断 → partial 记账 → auto_revoke → 租约吊销（≤8s 缓存窗口）
⑨ 充值     选择套餐 → orders → 支付回调 → 增加时长/额度 → 重新签发租约
```

异常分支：租约过期/续期失败降级、Redis 不可用回落 DB、上游 429/5xx 按策略重试、上游超时 504 / 连接失败 502、额度预占超限 429 / 预算耗尽 402、审批超时 fail-closed。

> **流程断点**：第 ⑨ 步当前不可达（FR-08）。即当前产品**从注册到付费的商业闭环是断的**。

---

## 7. 非功能需求

| ID | 类别 | 指标 | 出处 |
|---|---|---|---|
| NFR-01 | 租约 | 默认 TTL 300s→**900s**，renew **900s**，上限 **3600s**；80% TTL 主动续期；剩余 <30% TTL 返回 `renew_after`；缓存 `gw:lease:state` TTL **8s**（限 5–10s），吊销写穿、Redis 不可用回落 DB，**吊销后最多 8s 内仍可能被接受** | `gateway-lease-ttl-renewal/spec.md §2/§3` |
| NFR-02 | 额度 | 输出上限 **4096** token、单租户并发 **8**、预算 key TTL **86400s**、并发槽 TTL **60s**、hold/hash TTL **3600s** | `harness-quota-interrupt/spec.md §4`、`harness-orchestration-split/spec.md §16` |
| NFR-03 | 上游 | connect **10s** / read **300s** / total **0（关闭）**；llm 非流式 read **60s**、流式 **120s**；网关重试 **3** 次、llm **1** 次；backoff **0.5** 上限 **4.0**；重试状态 `429,500,502,503,504`；连接池 **100**、keepalive **20/30s** | `shared-upstream-client/spec.md §3.1/§4.1/§7` |
| NFR-04 | 内部调用 | `ORCH_INTERNAL_TIMEOUT=5s`、HTTP **30s**、HMAC 时间窗 **±60s**（30–300）、健康检查 `SELECT 1` **2.5s**、网关 health **3s**、DB connect/command **30s** | `l3-service-split/spec.md §5`、`harness-orchestration-split/spec.md §3.1` |
| NFR-05 | 对账 | interval **600s**、window **24h**、max **168h**；阈值 `diff_amount 1000` / `diff_rate 0.10` / `diff_cost 1.0` / `missing 1000` / `duplicate_ratio 2.0` | `harness-reconciliation/spec.md §6` |
| NFR-06 | 出网快照 | version **1**、`min_supported_version=1`、`snapshot_ttl 300s`（30–86400）；版本未知/过低 **426** + fail-closed | `harness-egress-policy/spec.md §3/§4` |
| NFR-07 | 灰度回切 | 观察期 **14 天**（最短 7 天）；5 分钟窗口 5xx/503 **>1%**、P95 **翻倍持续 10 分钟**、401 比例 **5%/for 5m**、绝对速率 **>0.05/s**（≈5 分钟 15 次）、**10 分钟**未恢复 → 回切；P6 回滚门禁 代理错误率 **>1%** 或 P95 翻倍 | `l3-split-p7-grayscale.md §2/§4/§5`、`l3-service-split/spec.md §9.2` |
| NFR-08 | 心跳/保留 | 客户端心跳 **30s**、run 心跳 **10s**、trace 保留 **30 天**；审计保留 **90 天** | `target-architecture-local-agent.md §8.2`、`agentpanel-harness-plan.md B3`、`config.conf [audit]` |

> **缺口**：无 SLA 可用性目标（如 99.9%）、无并发用户规模与容量模型、无客户端启动/首屏性能指标、无数据留存与个人信息合规要求（邮箱、用量、审计）、无灾备 RPO/RTO。均须补齐。

---

## 8. 数据与口径定义

### 8.1 核心实体

`customer`、`customer_membership`、`customer_membership_level`、`customer_payment_transaction`、`identity_link`、`customer_organization(_member)`、`orders`/`order_items`；`harness_client`、`harness_identity`、`harness_session`、`harness_run`、`harness_step`、`harness_audit_event`、`harness_action_policy/rule`、`harness_approval_request/grant`、`harness_gateway_lease`（含 `invalidated_at`/`budget`/`concurrency`/`reconcile_*`）、`service_credential`、`model_price`；`usage_record`、`quota_plan/binding/account/reservation`；`llm_provider/llm_model/llm_api_key/llm_usage_record`；`user/role/permission/menu`、`audit_log` 及五层审计表。模型唯一来源 `packages/common`，`migrations/*.sql` 均为增量 ALTER/seed。

### 8.2 术语与口径

| 术语 | 定义 |
|---|---|
| 权威账 | `usage_record(source=gateway)`，唯一可计费口径 |
| 证据账 | `HarnessStep` 客户端上报，仅供对账比对 |
| 遗留账 | `LLMUsageRecord`，待停止写入与历史回填 |
| `idem_key` | `harness:{run_id}:{node_id}:{seq}`，用量幂等键；对账按前缀分区 |
| `hold_id` | `harness:{run_id}`，额度预占键 |
| `price_snapshot` | 结算时的价格快照，防调价影响历史账单 |
| owner | 配额归属主体；customer 固定 `cus:<id>` |
| 租约 | `dgw.<lease_id>.<secret>`，短期通行证，非身份凭据 |
| 三档策略 | allow / 需审批 / deny |
| 两个 origin | `:9998` 控制面（JWT）、`:9999` 数据面（`dgw.*`） |
| `mode` | `app`（app 本地写）/ `proxy`（app 只代理，当前值） |

### 8.3 状态码约定

`200` 正常 / `401` 租约无效或吊销 / `402 lease_budget_exhausted` 网关预算耗尽 / `426` 出网快照版本过低 / `429 quota_exceeded` 编排预占超限 / `502` 上游连接失败 / `503` 下游编排不可达 / `504` 上游超时。

---

## 9. 验收标准与测试基线

| 报告 | 结论 |
|---|---|
| `reports/ops/business-logic-test-2026-11-11.md` | 全部套件 PASS，215 断言 / 0 失败，未发现产品业务逻辑缺陷；唯一为测试脚本窗口标题模糊匹配缺陷（已按进程 PID 精确匹配修复） |
| `reports/ops/customer-auth-e2e-2026-11-11.md` | 16/16 PASS、0 FAIL、0 BLOCKED；注册→登录→租约→网关鉴权→续期/吊销全通，`deepseek-chat` 真实 200 |
| `reports/ops/desktop-autotest-2026-11-10.md` | 20/20 PASS |
| `reports/ops/l3-split-acceptance.md` | P6 硬项全通过；三容器形态可接管 9998/9999/9100 |
| `reports/ops/l3-split-p3-report.md` 等 | 黄金用例 P1–P14 20/20；39/39、28/28 回归 |

**未覆盖 / 已知限制**：
- 网关套件跑在临时 9990 + 本地假 provider，9999 真实上游仅覆盖 `deepseek-chat` 单模型；
- 验证码链路依赖 Redis；测试账号 `dsh.e2e.*@example.com` 仍在库，需按 SQL 清理；
- Prometheus 9090 不可达记 WARN；`used` 基线新增计量键为历次 E2E 真实调用产生；
- 无效 model 返回 502 属预期；E09 为预期行为；
- 真实出网阻断与 dsh 侧应用效果未验证；本机无 dsh 可执行文件，`launch()` 真实启动未验证；
- **支付回调链路无任何端到端验收**（因路由未挂载）。

> **验收口径缺口**：现存 215 断言均为技术与接口断言，**无业务验收用例**（如「新客户注册后默认额度=？」「购买 10 小时后余额增加 10」「会员折扣后实付金额」）。须补业务验收矩阵。

---

## 10. 里程碑与当前阶段

| 阶段 | 时间 | 状态 |
|---|---|---|
| 网关 standalone 数据面上线 | 2026-11-07 前 | 完成 |
| L3 物理拆分 P0–P6 | 2026-11-09 | 完成并通过验收 |
| T7.4 监控告警补齐 | 2026-11-09 | 完成 |
| 14 天灰度观察期 | `2026-11-09 13:33:40` ~ 最早 `2026-11-23 13:33` | **进行中** |
| 桌面端 customer 登录/租约改造 + E2E | 2026-11-10 ~ 11-11 | 完成（16/16、20/20） |
| 业务逻辑回归 | 2026-11-11 | 完成（215 断言） |
| **PRD 重建与评审** | **2026-11-12** | **本次** |
| T7.5 收口（删灰度开关/旧代码/更新架构图） | 观察期后 | 仅预案，五项准入 + 三方签字未齐 |
| P2 技术债（outbox / 额度下沉 / 幂等建 run / Redis 分支实测） | 未排期 | 未开始 |
| 商业闭环打通（支付插件启用） | 未排期 | **未开始** |

**T7.5 五项准入**（`l3-split-t75-closeout-plan.md:19-23`）须全部满足方可收口；任一不满足即顺延，**不以「时间到了」强行收口**。观察期明令禁止：删旧编排代码/`mode` 开关、改架构图资产与 spec §11/tasks 状态、提前勾选准入或代签、重置起算时刻、读取并输出 `config.conf` 敏感值。

---

## 11. 风险与待决事项

### 11.1 已登记风险

| ID | 风险 | 影响 | 等级 |
|---|---|---|---|
| R-01 | 原 PRD 与 `docs/` 全缺，L1~L10 / D1~D8 仅代码反推 | 需求基线不可追溯，验收与合规无依据 | 高 |
| R-02 | 支付插件全未安装启用，配置 `enabled=true` 为假启用 | 商业闭环断裂，产品目标不可验收 | 高 |
| R-03 | 三套账并存未收敛，P6 三方对账门禁未做 | 计费权威性不足，可能多扣/少扣 | 高 |
| R-04 | 无 `QuotaPlan` 时 `limit=0` = 不计量不拦截 | 新客户可无限免费使用 | 高 |
| R-05 | `web_fetch`/`web_search` 可绕网关直连（Linux 实测 example.com 200） | 计量逃逸、PC-6 承诺边界 | 高 |
| R-06 | `config.conf` 明文存放支付商户密钥、SMTP 口令、`secret_key`、Redis/Qdrant 口令 | 凭据泄露 | 高 |
| R-07 | `_settle_redis_counters` 用 0 播种，窗口内无预占直接 settle 导致 Redis `used` 低估、配额偏松（F5） | 少扣费 | 中 |
| R-08 | 桌面端 `signOut` 只清 Host 内存态，不吊销 customer 租约，重启后仍登录 | 共享设备账号安全 | 中 |
| R-09 | 依赖上游开源 DeepSeek Harness「developer preview」，声明会有破坏性兼容变更；Windows 链锁定 0.1.5rc1 | 版本升级风险 | 中 |
| R-10 | 三端口仅 127.0.0.1 无 TLS，远程直连未交付 | 仅能本机/内网使用 | 中 |
| R-11 | spec 自身状态未闭环：quota-interrupt/reconciliation 标「待评审」且验收复选框全未勾；orchestration-split 头部称「尚未编码」与正文矛盾 | 文档可信度 | 中 |
| R-12 | 观察期未闭环项 F3（监控栈与外部通知）、F5（0 播种）、F6（§5 准入） | 收口延期 | 中 |
| R-13 | 每日 G1 人工抽查（重复结算/`used` 多加/预占悬挂）刻意不自动化，Prometheus 判不了 | 运营负担与漏检 | 中 |
| R-14 | T7.5 收口后无运行时回切能力 | 变更风险 | 中 |

### 11.2 待产品负责人决策清单（本 PRD 无法自行填补）

| Q# | 待决问题 |
|---|---|
| Q1 | 能否找回 `docs/用户侧智能体设计流PRD.md` 原文？若不能，L1~L10 / D1~D8 是否按本版反推内容追认？L2/L4 如何补？ |
| Q2 | 商业化是否为本期目标？若是，支付插件何时启用、用哪家通道、`config.conf` 中的 `enabled` 与插件 `is_installed/is_enabled` 谁为准？ |
| Q3 | 计费单位究竟是「时长（小时）」还是「token/金额」？`remaining_hours` 与 `usage_record` 的换算公式是什么？ |
| Q4 | 新注册客户默认额度 = 0（可无限使用）还是 0（完全不可用）？免费赠送时长是多少？ |
| Q5 | 会员折扣率、套餐与价格表、`max_fibonacci_level=20` 与称号表 ≥144 的冲突如何解释？ |
| Q6 | 订单过期 15 分钟（`order_expire_minutes`）是否生效？定时任务硬编码 600s 是否要改为可配置？ |
| Q7 | 成功指标与上线判定标准（注册数/付费转化/ARPU/准确率/SLA）如何定义？ |
| Q8 | PC-6「不保证客户端不出网」是可接受的产品边界，还是必须在正式发布前解决（网络策略 / 工具禁用 / 客户端改造）？ |
| Q9 | 组织配额与个体配额的优先级、超额归属、成员退出规则？ |
| Q10 | 落地页与空菜单：是补齐、下线，还是明确列为「已知占位」？旧品牌 `aif2f.cloud` 是否清理？ |
| Q11 | 个人信息合规：邮箱、用量流水、审计日志的留存期限、用户导出/删除权如何满足？ |
| Q12 | T7.5 收口与「支付闭环打通」的先后顺序与排期？ |

---

## 12. 附录：需求来源索引

| 类别 | 路径 |
|---|---|
| 架构 | `reports/architecture/as-built-architecture-2026-11-09.md`、`target-architecture-local-agent.md`、`agentpanel-architecture.mmd` |
| 规格 | `reports/specs/{l3-service-split,harness-orchestration-split,harness-quota-interrupt,harness-reconciliation,harness-llm-credentials,harness-egress-policy,gateway-standalone-data-plane,gateway-lease-ttl-renewal,shared-upstream-client}/spec.md`、`gateway/api-boundary.md` |
| 运维/验收 | `reports/ops/l3-split-acceptance.md`、`l3-split-p7-grayscale.md`、`l3-split-t75-closeout-plan.md`、`business-logic-test-2026-11-11.md`、`customer-auth-e2e-2026-11-11.md`、`desktop-autotest-2026-11-10.md`、`agentpanel-harness-plan.md` |
| 工作日志 | `.workbuddy/memory/2026-11-09.md`、`2026-11-10.md` |
| 代码 | `base/plugins/customer/*`、`base/plugins/harness/*`、`services/{gateway,orchestration}/*`、`packages/common/*`、`dshw/apps/desktop/src/*`、`web/src/*`、`migrations/*.sql` |
| **缺失** | `docs/用户侧智能体设计流PRD.md`、`docs/arch/02/04/05/06-*.md`（全仓均无） |

---

*本文档由现存文档与代码重建，标注 C 级的条款未经产品负责人确认前不得作为验收或对外承诺依据。评审意见见同目录 `AgentPanel-PRD-评审报告-2026-11-12.md`。*
