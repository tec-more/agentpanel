# L2 业务面镜像（第三容器，端口 19998）
#
# 为什么容器化 L2：编排容器需要通过 http://l2:9998 访问 L2 内部额度/心跳接口。
# 若 L2 仍跑在宿主机，容器必须依赖 host.docker.internal 且无法与 compose 服务
# 使用同一 DNS；同时三容器链路无法自包含验证。L2 依赖面很大（插件/LLM/检索），
# 复用已构建的 aipanel-app:latest 运行时依赖，只覆盖当前仓库代码，避免重复
# 安装数 GB 依赖；迁移仍不随容器启动执行。
#
# 基础镜像按 digest 固定（本地构建产物，非 registry 拉取）：
#   tag    : aipanel-app:latest
#   digest : sha256:aaac04f3cf85eeeef3b52fa1a7ee0c496135a78eb47cf5790bafe4f044b11dc1
#   Created: 2026-11-05T08:58:16.157428854Z
#   docker image inspect aipanel-app:latest --format '{{.Id}} {{.Created}} {{json .RepoDigests}}'
# 该镜像包含 L2 完整运行时依赖（langchain/langgraph/llama-index/qdrant 等，约 10.9GB）。
# 选型理由：另写 Dockerfile 从 python:3.12-slim 按 lock 重装依赖，成本高且体积/构建时长
# 无收益；固定 digest 已消除“latest 漂移”，镜像内容可复现。
#
# 构建（仓库根目录）：
#   docker build --provenance=false -f deploy/l3/Dockerfile.l2 -t agentpanel-l2:local .
# 可复现验收：--provenance=false 时连续两次构建 image ID 完全一致
# （当前代码内容对应 sha256:b2a720aec44d59bf9b990ee6d0af25e53f90e92700257d10888411d0996c47e2）；
# 默认开启 provenance attestation 会把构建时间戳写入外层 manifest list，导致该外层
# digest 不同，但内层 manifest/config digest 一致，可解释为构建时间戳差异。
#
# 2026-11-09 全流程复检 F2 修复：基础镜像自带的 /app/web/dist 是 11-05 构建时的
# 前端快照，与本仓库当前 web/ 源码不一致（/panel 返回 200 但是旧页面）。本镜像
# 此前没有 COPY 前端产物，也没有编译阶段。现按 deploy/app/Dockerfile 的同一范式
# 加多阶段构建：从源码 + package-lock 编译 dist 并覆盖基础镜像快照。
# 不直接 `COPY web/dist/`：该目录未入库且被 .dockerignore 的 `**/dist/` 排除，
# 依赖本地残留产物会让镜像不可复现。

# ===== 阶段1：管理后台前端（web → /build/dist）=====
ARG NODE_IMAGE=docker.m.daocloud.io/library/node:20-alpine
FROM ${NODE_IMAGE} AS web-builder
ARG NPM_REGISTRY=https://registry.npmmirror.com
WORKDIR /build
# 先装依赖（package-lock 锁定版本，命中 Docker 层缓存）
COPY web/package.json web/package-lock.json ./
RUN npm config set registry ${NPM_REGISTRY} && npm ci
# 本地 node_modules/ 与 dist/ 已被 .dockerignore 排除，不会覆盖上面安装的依赖
COPY web/ ./
RUN npm run build

# ===== 阶段2：L2 运行时 =====
FROM aipanel-app@sha256:aaac04f3cf85eeeef3b52fa1a7ee0c496135a78eb47cf5790bafe4f044b11dc1

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEPLOY_ENV=docker \
    STRICT_STARTUP=true \
    UVICORN_HOST=0.0.0.0 \
    UVICORN_PORT=9998

# 覆盖旧代码目录与基础镜像里的旧前端快照；运行时依赖由基础镜像提供
RUN rm -rf /app/base /app/packages /app/run.py /app/web/dist \
    && groupadd -g 10001 app \
    && useradd -u 10001 -g 10001 -M -s /sbin/nologin app \
    && mkdir -p /app/logs /app/storage

COPY run.py /app/run.py
COPY base/ /app/base/
COPY packages/ /app/packages/
# L2 复用网关领域包（租约校验/预算/审计/常量），并读取 services/*/manifest.json。
# 网关与编排的进程代码（run.py / app/ / tests/）不进入 L2 镜像。
COPY services/__init__.py /app/services/__init__.py
COPY services/gateway/__init__.py /app/services/gateway/__init__.py
COPY services/gateway/manifest.json /app/services/gateway/manifest.json
COPY services/gateway/common/ /app/services/gateway/common/
COPY services/orchestration/manifest.json /app/services/orchestration/manifest.json
# F2：用当前源码编译出的前端产物覆盖基础镜像快照（/panel 与 /install 走这里）
COPY --from=web-builder /build/dist /app/web/dist

RUN chown -R 10001:10001 /app/base /app/packages /app/run.py /app/services /app/web/dist /app/logs /app/storage

USER 10001
EXPOSE 9998

HEALTHCHECK --interval=15s --timeout=5s --start-period=60s --retries=5 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:9998/health/health', timeout=3).status == 200 else 1)"

CMD ["python", "run.py"]
