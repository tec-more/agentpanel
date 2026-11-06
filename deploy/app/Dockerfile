# agentpanel 应用镜像（docker-compose 部署形态，多阶段构建）
# 构建上下文为项目根目录：docker build -f deploy/app/Dockerfile -t agentpanel-app .
#
# 阶段1：node 编译管理后台前端 web → dist（部署期编译，产物与源码版本一致，不依赖本地残留）
# 阶段2：python 后端运行时（COPY 后端源码 + 用阶段1的 dist 覆盖 web/dist，供 app_wrapper serve）
#
# 注意：requirements.txt 若含 torch 等重型依赖，构建较慢且镜像较大；
# 生产可按需裁剪为 requirements-prod.txt（本文件不代裁，避免改变依赖契约）
#
# 国内网络友好：基础镜像与 pip/npm 源默认走国内镜像，海外环境用 build-arg 覆盖：
#   docker build --build-arg BASE_IMAGE=python:3.12-slim --build-arg NODE_IMAGE=node:20-alpine \
#     --build-arg PIP_INDEX_URL=https://pypi.org/simple --build-arg NPM_REGISTRY=https://registry.npmjs.org ...

# ===== 全局 ARG（供 FROM 使用；必须在第一个 FROM 之前声明）=====
ARG NODE_IMAGE=docker.m.daocloud.io/library/node:20-alpine
ARG BASE_IMAGE=docker.m.daocloud.io/library/python:3.12-slim

# ===== 阶段1：管理后台前端构建（web → /build/dist）=====
FROM ${NODE_IMAGE} AS web-builder
ARG NPM_REGISTRY=https://registry.npmmirror.com
WORKDIR /build
# 先装依赖（package-lock 锁定版本，命中 Docker 层缓存）
COPY web/package.json web/package-lock.json ./
RUN npm config set registry ${NPM_REGISTRY} && npm ci
# 再拷源码构建（本地 node_modules/dist 已被 .dockerignore 排除，不覆盖上面装的依赖）
COPY web/ ./
RUN npm run build

# ===== 阶段2：后端运行时 =====
FROM ${BASE_IMAGE}

ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# 先装依赖（利用镜像层缓存）
COPY requirements.txt .
RUN pip install --no-cache-dir -i ${PIP_INDEX_URL} -r requirements.txt

# 再拷源码（本地 web/dist 已被 .dockerignore 排除）
COPY . .

# 用阶段1新编译的管理后台产物覆盖 web/dist（供 app_wrapper 托管 /panel）
COPY --from=web-builder /build/dist /app/web/dist

# 数据目录（容器内日志/存储，生产以卷挂载覆盖）
RUN mkdir -p /app/logs /app/storage

EXPOSE 9998

# 上线硬约束默认值（H-1 单 worker；生产模式 + 严格自检）
# 可被 docker-compose environment 覆盖，但不建议覆盖 UVICORN_WORKERS
ENV UVICORN_WORKERS=1 \
    UVICORN_PORT=9998 \
    DEPLOY_ENV=docker \
    STRICT_STARTUP=true

CMD ["python", "run.py"]
