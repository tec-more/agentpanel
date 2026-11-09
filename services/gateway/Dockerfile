# L3 网关服务镜像（services/gateway）
# 构建（仓库根目录）：
#   docker build -f services/gateway/Dockerfile -t agentpanel-l3-gateway:local .
# 说明：多阶段构建只安装 L3 数据面所需最小依赖；不在容器启动时执行任何迁移。

ARG BASE_IMAGE=docker.m.daocloud.io/library/python:3.12-slim
FROM ${BASE_IMAGE} AS builder

ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
WORKDIR /build
COPY deploy/l3/requirements-l3.txt ./
RUN pip install --no-cache-dir --prefix=/install -i ${PIP_INDEX_URL} -r requirements-l3.txt

FROM ${BASE_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TMPDIR=/tmp

RUN groupadd -g 10001 app \
    && useradd -u 10001 -g 10001 -M -s /sbin/nologin app

COPY --from=builder /install /usr/local

WORKDIR /app
COPY packages/ ./packages/
COPY services/gateway/ ./services/gateway/

RUN chown -R 10001:10001 /app

USER 10001
EXPOSE 9999

HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:9999/health', timeout=3).status == 200 else 1)"

CMD ["python", "services/gateway/run.py"]
