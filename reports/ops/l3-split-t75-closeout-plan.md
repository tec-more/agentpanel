# T7.5 收口执行预案（观察期内只做预案，不执行）

- 状态：**预案 / 未执行**
- 建立时间：2026-11-09 16:32 +0800
- 适用时点：14 天观察期满足全部准入之后（起算 2026-11-09 13:33:40 +0800，**最早 2026-11-23 13:33:40 +0800**）
- 准入台账：`reports/ops/l3-split-p7-observation-log.md` §5（五项 checkbox）+ §5.1 三方签字栏
- 关联任务：`reports/specs/l3-service-split/tasks.md` P4 / T7.5、`checklist.md` T7.5、`spec.md` §11 与 P7 状态表

> 本文只描述**到期当天怎么执行**。观察期内禁止执行本文任何删除动作，也禁止提前把
> `tasks.md` / `checklist.md` / `spec.md` / 架构图中的 T7.5 打勾。
> 本文基于 2026-11-09 16:32 的代码现状编写；到期执行前**必须重新扫描引用点**，以实际代码为准。

---

## 1. 准入（不满足则顺延，不以「时间到了」为由强行收口）

执行前逐项核对台账 §5，**五项全部满足且 §5.1 三方签字齐全**方可进入 §3：

1. 连续 14 天无 P1 故障；
2. 灰度方案 §4 的 R1–R7 阈值全部未触发、无回切/重置记录；
3. §3 每日巡检连续 14 行无缺口，WARN 均有业务写入说明；
4. 第 1 / 第 2 周 G1 抽查通过，`used`/`held` 与对账无异常；
5. L3 拆分负责人 + 值班运维 + 数据/配额负责人三方签字。

任一不满足：按 `l3-split-p7-grayscale.md` §2 顺延保留期，保留 `mode` 开关与旧代码。

---

## 2. 删除与更新范围（到期逐项复核）

### 2.1 灰度开关 `orchestration.mode`

当前 `mode` 取值仍为 `l2 | proxy_l3`，运行态固定 `proxy_l3`。收口即删除 `l2` 分支与开关本身，
让 L2 只做代理/控制面、编排只做写主，不再有整机二元切换。已知读取点（**到期重新 grep 确认**）：

| 文件 | 位置 / 内容 |
|---|---|
| `base/plugins/harness/services/orchestration_config.py` | `DEFAULTS["mode"]`、`validate_orchestration_config()` 的 `l2/proxy_l3` 枚举校验 |
| `services/orchestration/app/config.py` | 同上（编排侧独立配置副本） |
| `services/orchestration/manifest.json` | `config.orchestration` 段的 mode 项 |
| `base/plugins/harness/services/orchestration_proxy.py` | `proxy_mode_enabled()`、`require_client_or_proxy()` 的 `l2` 回落分支 |
| `base/plugins/harness/services/service_auth.py` | 约 260–272 行「只有 mode=proxy_l3 才是写主」闸门 |
| `services/orchestration/app/auth.py` | 约 256–266 行同语义的写接口总开关 |
| `base/plugins/harness/api/l2_internal/quota_router.py` | `_ensure_primary()`（409 `orchestration_not_primary`）、`/status` 的 `primary` 字段 |
| `services/orchestration/app/api/internal.py` | 健康/状态响应里的 `orchestration_mode` 字段 |
| `deploy/l3/scripts/observe_check.py` | 巡检中的 `mode=proxy_l3` 断言——收口后必须同步改为最终态口径或归档 |
| `config.conf`（L2 secret 挂载） | 是否含 `mode` 覆盖项：**线下受控人工核对**，不读取、不输出敏感值（§7 遗留项） |

保留但需确认语义的：单写者闸门（防止 L2/L3 双写）不能随 `mode` 一起删掉，
应改为**结构性保证**（L2 侧不再有写编排的入口），否则会引入双写风险。

### 2.2 L2 旧编排代码（P4 删除边界，以 `tasks.md` §P4 为准）

`33b9883` 已下线旧编排入口（删除 `server.py`、`api/l3/*`、`api/internal/router.py` 等约 525 行）。
剩余过渡层按 P4 清单逐项确认无外部引用后再删：

| 任务 | 范围 | 删除前判据 |
|---|---|---|
| T4.1 | `base/plugins/harness/server.py`、`api/l3/*`、`api/internal/*` | L2 不再暴露 9100 入口（多数已由 `33b9883` 完成，复核残留） |
| T4.2 | `start.py` / `app_wrapper.py` 的 embedded `/v1/gateway` 挂载 | L2 启动无网关路由；`base/common/gateway` 不再被 L2 import |
| T4.3 | `orchestration_runtime` 角色分支、`quota_backend` 的 L3 分支 | L2 直调 `QuotaService`；`is_l3()` 无引用 |
| T4.7 | `orchestration.mode` | §2.1 所有读取点清零 |
| T4.8 | L3 专用依赖（aerich 保留给 L2） | 依赖清单无冗余、三镜像 build 通过 |
| T4.10 | P2 阶段 3 遗留决策（用户已确认延后到 P4 处理） | 与 T4.2 / T4.12 合并处理 |
| T4.11 | `base/common/quota/services/{quota_service,plan_service,plan_resolver}.py` 与 `metrics.py` shim | `grep "base.common.quota.services" --include=*.py` 仅剩计划内引用 |
| T4.12 | `base/common/gateway/*` shim | L2 无 `base.common.gateway` 运行引用；`gateway_lease_service` 只依赖 `issuance_config` 与共享 `lease_auth` |

> 目录改名后的现状：`services/gateway/common/` 是网关领域包（**运行代码，不在删除范围**）；
> `packages/agentpanel_common/` 是跨进程共享内核（**不在删除范围**）。
> 不要按旧文档里的 `services/l3-gateway` / `services/l3-orchestration` 路径去找文件。

### 2.3 配置与部署

- `deploy/l3/docker-compose.yml`、三份 `Dockerfile`（`deploy/l3/Dockerfile.l2`、`services/gateway/Dockerfile`、`services/orchestration/Dockerfile`）：复核 COPY 边界与环境注入，删除仅服务于 `l2` 模式的分支；
- `services/orchestration/manifest.json` 与 `base/plugins/harness/services/orchestration_config.py` 的默认值同步；
- `deploy/l3/.env` / secrets：仅线下受控核对，密钥不入库、不进任何报告。

### 2.4 架构图与状态文档（收口时统一更新）

| 资产 | 动作 |
|---|---|
| `reports/architecture/agentpanel-architecture.mmd` | 更新为最终态（以 `as-built-architecture-2026-11-09.md` §2/§5/§10 为输入） |
| `reports/architecture/agentpanel-architecture.html` | 由 mmd 重新渲染 |
| `reports/specs/l3-service-split/spec.md` | §11 数据流目标态 + P7 状态表改为完成 |
| `reports/specs/l3-service-split/tasks.md` | P4 剩余任务与 T7.5 标记完成 |
| `reports/specs/l3-service-split/checklist.md` | T7.5 打勾 |
| `reports/ops/l3-split-p7-report.md` | T7.5 行由「未开始」改为完成 |
| `reports/ops/l3-split-p7-grayscale.md` | 保留期/二元切换章节标注「已收口、历史留档」 |
| `reports/architecture/as-built-architecture-2026-11-09.md` | 保留为 as-built 基线归档，不覆盖 |

---

## 3. 建议执行顺序（分提交，便于逐段回退）

1. **提交 A：开关收口** —— §2.1 删除 `l2` 分支，保留结构性单写者闸门；同步 `observe_check.py` 口径。
2. **提交 B：旧代码清理** —— §2.2 / §2.3，逐项 grep 判据通过后删除。
3. **提交 C：文档与架构图** —— §2.4 统一更新并打勾。

每步之间都跑 §4 验证；任一失败立即 `git revert` 回到上一步，不继续往下删。

---

## 4. 验证命令（每步执行后）

```bash
# 1) 引用点清零
grep -rn "proxy_l3\|orchestration.mode\|is_l3()\|orchestration_runtime" --include=*.py --include=*.json . --exclude-dir=.venv

# 2) 语法与镜像
.venv/Scripts/python.exe -m compileall -q base packages services
docker compose -f deploy/l3/docker-compose.yml --env-file deploy/l3/.env build
docker compose -f deploy/l3/docker-compose.yml --env-file deploy/l3/.env up -d --wait --wait-timeout 180

# 3) 运行态（巡检口径需按最终态更新后执行）
.venv/Scripts/python.exe deploy/l3/scripts/observe_check.py --append

# 4) 网关数据面完整链路（写入/破坏性，需单独授权；独立 9990 实例 + fixture 自动清理）
#    services/gateway/tests/verify_gateway.py  → 期望 66/66 PASS

# 5) 额度链路（编排容器经 L2 内部 API；凭据只在容器内流转）
#    reserve / settle / release 幂等与并发，验证后精确恢复计量基线
```

必过判据：三容器 healthy、四健康端点 200、L2 代理 401（非 503）、网关 `/metrics` 与编排
`/metrics` 200、Prometheus 三个 L3 job up、`used`/`held` 与收口前一致、测试行 0 残留。

---

## 5. 留痕与签字

- 在 `l3-split-p7-observation-log.md` 新增「T7.5 收口执行」章节：执行时刻、提交号、§4 各项输出、回退预案状态；
- 在 §5.1 三方签字栏填写实际签字（**代理不可代签**）；
- 记录 Prometheus `rate()`/`increase()` 是否因重建容器跨 counter reset 窗口。

---

## 6. 回退路径（收口后无运行时回切能力）

删除 `mode` 开关后不再有部署级二元回切，只能做**代码级回滚**：

1. `git revert` 提交 C → B → A（或 `git checkout <收口前 tag>`）；
2. 重建三镜像并 `up -d --force-recreate --wait`；
3. 恢复 `config.conf` / manifest 中的 `mode=proxy_l3`（线下受控操作，密钥不入库）；
4. 按 `l3-split-p7-report.md` §2/§3 的 P7 回滚演练实测路径（容器旧端口 18.0s / 宿主三进程约 33s）核验；
5. 重新起算观察期，不得沿用已收口的 14 天记录。

执行前必须先确认「收口前提交号 + 三镜像 tag + 配置备份」齐备，否则不得开始删除。

---

## 7. 观察期内明令禁止

- 删除任何旧编排代码或 `mode` 开关；
- 修改架构图资产、`spec.md` §11、`tasks.md` / `checklist.md` 的 T7.5 状态；
- 提前勾选 §5 任一项或代签 §5.1；
- 重置/改写起算时刻 13:33:40 +0800；
- 读取或输出 `config.conf` 中的敏感值（§7.1 遗留项由人工线下受控核对）。

---

## 8. 到期前需人工复核的开放项

1. `config.conf` 是否含真实凭据及 `mode` 覆盖项（线下受控，本预案不读取、不推断）；
2. `tasks.md` §P4 中 T4.4 / T4.5 / T4.6 / T4.9 是否仍有残留代码，本文未列全，以原文为准；
3. Alertmanager 仍未配置（台账 §6），告警只求值不外发；收口前建议补齐或书面接受；
4. 单写者闸门改为结构性保证后的具体实现方式（§2.1 备注），需由 L3 拆分负责人确认。
