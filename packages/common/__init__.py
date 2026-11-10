"""app 与 独立服务共享能力（模型 / 日志 / 配置契约 / DB 连接 / upstream / 网关契约）。

2026-11-09 由 `packages/agentpanel_common/` 改名为 `packages/common/`，
导入名 `packages.agentpanel_common.*` → `packages.common.*`。

共享包内禁止 import `base.*` / `services.*`；app 通过 `base/*` 同路径 shim 反向兼容。

命名区分：本包是**三进程共享基础包**，与 `services/gateway/common/`（网关服务领域包）
和 `base/common/`（app 兼容 shim）互不等价，分别以 `packages.common.*`、
`services.gateway.common.*`、`base.common.*` 绝对导入区分。
"""

__version__ = "0.1.0"
