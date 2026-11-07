"""网关稳定契约：错误类型、幂等键/缓存键前缀、跨服务业务错误码。

这些字面量此前散落在 `gateway/app.py`、`gateway/service.py`、`gateway/lease_auth.py`
及各内部路由中；集中到共享包后，L2/L3 两侧引用同一份定义，避免漂移。
"""

# ---------------- OpenAI 兼容错误类型 ----------------
ERROR_AUTH = "gateway_auth_error"           # 401 / 403
ERROR_RATE_LIMIT = "gateway_rate_limit_error"  # 429
ERROR_INVALID_REQUEST = "invalid_request_error"  # 400
ERROR_GATEWAY = "gateway_error"             # 其余（上游/网关内部）

# ---------------- 幂等键前缀 ----------------
# 网关 usage 记账的确定性幂等键前缀
GATEWAY_IDEM_PREFIX = "gw:"
# Harness 编排侧确定性幂等键前缀
HARNESS_IDEM_PREFIX = "harness:"

# ---------------- Redis 缓存键前缀 ----------------
LEASE_CACHE_PREFIX = "gw:lease:state:"

# ---------------- 稳定业务错误码（与现有响应逐字一致） ----------------
ORCH_DEPENDENCY_UNAVAILABLE = "orchestration_dependency_unavailable"
ORCH_NOT_PRIMARY = "orchestration_not_primary"
QUOTA_EXCEEDED = "quota_exceeded"
QUOTA_HOLD_CLOSED = "quota_hold_closed"
QUOTA_RESERVATION_IN_PROGRESS = "quota_reservation_in_progress"
