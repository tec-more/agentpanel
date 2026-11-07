# 共享上游 HTTP 客户端 — Tasks

- [x] T1 新增 `base/common/upstream/{__init__,config,egress,client}.py`，实现配置、强制出网校验、连接池缓存、非流式/流式调用、重试与异常映射、SSE 迭代。
- [x] T2 网关配置：`gateway/config.py` 增加 retry/timeout/TLS/代理/连接池默认键与 `gateway_upstream_config()`，并在 `validate_gateway_config()` 增加轻量校验。
- [x] T3 网关路由：`gateway/router.py` 改用共享客户端；非流式 `replay=True`；流式仅在响应头前重试；删除自建 client 与 `_timeout()`；保持透传/记账/504/502/白名单语义。
- [x] T4 llm 服务改造：openai、deepseek、zhipu、localai、anthropic 的 chat/chat_stream；alibaba/baidu 逐行 JSON；baidu token；tencent；doubao 两处 fallback；local provider 映射到 LocalAIService 以保留本地出网策略。
- [x] T5 编写临时假 provider 与验证脚本，跑共享客户端/网关场景 + 额度中断回归 + llm chat/stream。
- [x] T6 清理临时脚本与假 provider，汇总行为一致性结论并汇报。
