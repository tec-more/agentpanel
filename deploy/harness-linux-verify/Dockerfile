# agentpanel Linux 容器验证镜像（临时验证用，不进入生产镜像）
# 目标：在 Linux x64 上验证 dsh 的进程内拦截、workspace 越界、出网与原生审批通道。
# 构建：
#   docker build -t agentpanel-dsh-verify:0.1.5rc1 -f Dockerfile .
# 运行：
#   docker run --rm --name agentpanel-dsh-verify --network none \
#     --security-opt seccomp=unconfined agentpanel-dsh-verify:0.1.5rc1
#
# 约束：不调用真实 provider；镜像内以占位 key 指向本机假 provider。

# 默认走本地已有的国内镜像；可用 --build-arg BASE_IMAGE=python:3.12-slim 覆盖。
# 直接连 docker.io 在当前网络下不可达（IPv6 连接超时），故不默认使用官方 tag。
ARG BASE_IMAGE=docker.m.daocloud.io/library/python:3.12-slim
FROM ${BASE_IMAGE}

ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ARG APT_MIRROR=mirrors.tuna.tsinghua.edu.cn

# bubblewrap / libcap 供 dsh-sandbox-local 的 Linux 沙箱后端使用；
# ca-certificates 供白名单域名可达性测试。
RUN sed -i "s|deb.debian.org|${APT_MIRROR}|g" /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        bubblewrap \
        ca-certificates \
        curl \
        iproute2 \
        procps \
    && rm -rf /var/lib/apt/lists/*

# 锁定 dsh SDK 版本，与业务侧 manifest lock_runtime_version 一致
RUN pip install --no-cache-dir -i ${PIP_INDEX_URL} "deepseek-harness-sdk==0.1.5rc1"

WORKDIR /opt/verify
COPY . /opt/verify

# 非 root 运行，便于 user namespace + bubblewrap/landlock 生效
# /work 本身对运行用户可写，确保“越界写失败”是 dsh 沙箱导致，而不是 OS 权限导致。
RUN useradd -m -u 10001 verifier \
    && mkdir -p /data/dsh /work/ws /out \
    && chown -R verifier:verifier /data /work /out /opt/verify

USER verifier
ENV PYTHONUNBUFFERED=1 \
    DSH_HOME=/data/dsh \
    FAKE_PROVIDER_PORT=18080 \
    VERIFY_WORKDIR=/work/ws \
    VERIFY_OUTDIR=/out

# 不 EXPOSE 业务端口；假 provider 仅监听容器内 127.0.0.1:18080（高位非默认端口）
CMD ["python", "scripts/run_all.py"]
