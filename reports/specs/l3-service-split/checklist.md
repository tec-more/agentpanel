# P1 验收清单（`packages/agentpanel_common` 抽取 / manifest 三拆 / 配置契约）

## 共享包与兼容层

- [x] `packages/agentpanel_common` 可导入，且包内无 `from base` / `import base`
- [x] `masking`、`upstream/*`、`gateway/{constants,contracts}`、`models/*`（6 个模型模块 + base）已迁入共享包
- [x] 6 组兼容 shim（13 个文件）全部落在原路径，`import *` 单来源转发
- [x] 引用 shim 目标的 167 处 import / 145 个文件无需修改即可运行
- [x] `base/common/setting.py::get_model_list()` 改指共享模型路径，模型单一来源
- [x] `HarnessRun` 等模型 `__module__` 为 `packages.agentpanel_common.models.*`，表名不变

## 配置契约

- [x] `ConfigError` 只列字段名、不含值
- [x] `coerce()` 覆盖 str/int/float/bool/list/int_list/json，类型不符即失败
- [x] L2 继续读 `config.conf`；L3 两入口只读环境变量
- [x] L3 密钥支持 `<ENV>_FILE`
- [x] 必填缺失/类型不符 → 启动即失败，退出码 2
- [x] L2 专有字段（JWT 密钥等）不出现在 L3 契约

## manifest 三拆

- [x] L2 `manifest.json` 含 `gateway_issuance`，不再含 `gateway` / `orchestration`
- [x] `services/l3-gateway/manifest.json` 只含数据面配置
- [x] `services/l3-orchestration/manifest.json` 只含编排配置
- [x] 网关/编排配置路径无 `plugin_manager` 引用

## 入口与健康

- [x] `run.py` → 9998 `/health/health` 200 `healthy`
- [x] 网关 → 9999 `/health` 200 `status=ok`、`deployment=standalone`、`fail_closed=true`
- [x] 编排 → 9100 `/health/health` 200、`/health/orchestration` 200 `healthy`
- [x] 三入口互不 import 对方入口模块

## 业务链路

- [x] L2 → L3 代理读 200
- [x] L2 → L3 代理写 200，且可读回
- [x] L3 停机时 L2 代理返回 503（fail-closed）
- [x] 网关租约校验：正确 200、错误 secret 401、非法 JSON 400、匿名 401
- [x] 网关用量记账：`usage_record.idem_key` 前缀 `gw:`，`source=gateway`
- [x] 编排预占/结算经 L2 内部额度 API，`quota_reservation.counter_mode=redis` 且已结算
- [x] L3 内部接口拒绝匿名与用户 JWT（401）

## 交付物

- [x] `reports/ops/l3-split-p1-report.md`（搬运清单 / shim 落点 / import 变更面 / 验证证据 / C1–C4 建议 / 回滚方式）
- [x] `tasks.md` T1.1–T1.8 勾选
