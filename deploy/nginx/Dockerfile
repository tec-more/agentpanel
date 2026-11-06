# agentpanel 网关镜像（多阶段构建）：node 编译用户端 web-user → nginx 托管
# 构建上下文为项目根目录：docker build -f deploy/nginx/Dockerfile -t agentpanel-nginx .
#
# 阶段1：编译 web-user（依赖 web-shared/schema-validator，@validator 源码直引）
# 阶段2：nginx 运行时，dist 静态文件进镜像（nginx.conf/conf.d 由 compose 卷挂载下发）
#
# 国内网络友好：基础镜像与 npm 源默认走国内镜像，海外环境用 build-arg 覆盖：
#   docker build --build-arg NODE_IMAGE=node:20-alpine --build-arg NGINX_IMAGE=nginx:alpine \
#     --build-arg NPM_REGISTRY=https://registry.npmjs.org ...

# ===== 全局 ARG（供 FROM 使用；必须在第一个 FROM 之前声明）=====
ARG NODE_IMAGE=docker.m.daocloud.io/library/node:20-alpine
ARG NGINX_IMAGE=docker.m.daocloud.io/library/nginx:alpine

# ===== 阶段1：用户端前端构建（web-user → /build/dist）=====
FROM ${NODE_IMAGE} AS user-builder
ARG NPM_REGISTRY=https://registry.npmmirror.com
WORKDIR /build
# 先装依赖（package-lock 锁定，命中层缓存）
COPY web-user/package.json web-user/package-lock.json ./
RUN npm config set registry ${NPM_REGISTRY} && npm ci
# 再拷源码；web-user 通过 alias @validator 源码直引 ../web-shared/schema-validator（需与 /build 同级）
COPY web-user/ ./
COPY web-shared/ /web-shared/
RUN npm run build

# ===== 阶段2：nginx 运行时 =====
FROM ${NGINX_IMAGE}
# 用户端静态产物进镜像（/api 反代与 SPA 回退规则见 conf.d/aipanel-user.conf）
COPY --from=user-builder /build/dist /usr/share/nginx/html/user
