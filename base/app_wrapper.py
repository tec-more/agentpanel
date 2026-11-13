#!/usr/bin/env python3
"""
应用包装器 - 添加 /api 前缀
使用 ProxyFix 模式的 ASGI 中间件
"""
from base.start import init_app

# 创建实际应用
real_app = init_app()

# 路径契约（与 base/common/plugin_contract.py 配套，唯一来源）：
# - 浏览器侧 /api 由本包装器剥离，插件内不得重复声明
# - 应用内 API 路径以 /v1/ 开头；/internal/ 为服务间接口
# - 静态资源与已知 SPA 页面走白名单，其余路径返回 404 JSON，
#   不再把所有未知路径伪装成 200 index.html
API_PATH_PREFIXES = ("/v1/", "/internal/")
PASSTHROUGH_PREFIXES = (
    "/docs", "/openapi", "/redoc", "/static", "/metrics", "/health",
    "/uploads/", "/files/",
)
SPA_EXACT_PATHS = {"/", "/index.html", "/favicon.ico"}
SPA_PREFIXES = ("/panel", "/install", "/login", "/assets/")


def apply_api_prefix(scope: dict, original_path: str, prefix: str) -> dict:
    """统一的 /api 剥离规则，HTTP 与 WebSocket 共用。"""
    if original_path.startswith(prefix):
        new_scope = dict(scope)
        new_scope["path"] = original_path[len(prefix):] or "/"
        new_scope["root_path"] = prefix
        return new_scope
    return scope


def is_spa_path(path: str) -> bool:
    """是否属于前端 SPA 页面或构建产物路径。"""
    return path in SPA_EXACT_PATHS or any(path.startswith(p) for p in SPA_PREFIXES)


class ASGIAppWithPrefix:
    """ASGI 应用包装器，自动添加路径前缀"""

    def __init__(self, app, prefix="/api"):
        self.app = app
        self.prefix = prefix

    def _check_install_status(self) -> bool:
        """检查系统是否已安装"""
        try:
            from base.core.install.services.install_service import InstallService
            return InstallService.is_installed()
        except Exception:
            # 如果检查失败，假设未安装
            return False

    async def __call__(self, scope, receive, send):
        # 处理 WebSocket 连接
        if scope["type"] == "websocket":
            client = scope.get("client", ["", ""])[0] if scope.get("client") else ""
            original_path = scope.get("path", "")

            # 与 HTTP 请求共用同一条 /api 剥离规则
            scope = apply_api_prefix(scope, original_path, self.prefix)
            await self.app(scope, receive, send)
            return

        # 处理 HTTP 请求
        if scope["type"] == "http":
            original_path = scope.get("path", "")
            method = scope.get("method", "")
            client = scope.get("client", ["", ""])[0] if scope.get("client") else ""

            # OPTIONS 请求（CORS 预检）直接透传
            if method == "OPTIONS":
                await self.app(scope, receive, send)
                return

            # 网关数据面是独立子应用：不叠加 /api 业务前缀、不改 root_path，
            # 保证 /v1/gateway/* 与业务 API 的路由/文档边界结构隔离。
            if (original_path.startswith("/v1/gateway")
                    or original_path.startswith("/api/v1/gateway")):
                if original_path.startswith(self.prefix):
                    scope = dict(scope)
                    scope["path"] = original_path[len(self.prefix):] or "/"
                await self.app(scope, receive, send)
                return

            # 静态资源/监控/上传文件路径直接透传（/uploads 由 start.py 挂载）
            if original_path.startswith(PASSTHROUGH_PREFIXES):
                await self.app(scope, receive, send)
                return

            # 服务间内部接口（如 Harness app touch）不走前端 SPA，直接进入应用路由
            if original_path.startswith("/internal/"):
                await self.app(scope, receive, send)
                return

            # 安装相关 API 路径始终可访问
            if original_path.startswith("/api/v1/install") or original_path.startswith("/v1/install"):
                # 如果路径以 /api 开头，移除前缀
                scope = apply_api_prefix(scope, original_path, self.prefix)
                await self.app(scope, receive, send)
                return

            # 公共配置 API 路径始终可访问（用于前端检查安装状态）
            if original_path.startswith("/api/v1/common") or original_path.startswith("/v1/common"):
                scope = apply_api_prefix(scope, original_path, self.prefix)
                await self.app(scope, receive, send)
                return

            # 检查系统安装状态（对非安装/公共路径进行拦截）
            is_installed = self._check_install_status()

            if not is_installed:
                # 未安装时，其他 API 请求返回 503（避免触发数据库操作导致崩溃）
                if original_path.startswith(self.prefix) or original_path.startswith("/v1/"):
                    from starlette.responses import JSONResponse
                    response = JSONResponse(
                        status_code=503,
                        content={"detail": "系统未安装，请先完成安装", "code": 503, "redirect": "/install"}
                    )
                    await response(scope, receive, send)
                    return

            # API 路径：统一剥离 /api 后交给 FastAPI
            if original_path.startswith(self.prefix):
                scope = apply_api_prefix(scope, original_path, self.prefix)
                await self.app(scope, receive, send)
                return

            # 应用内直连路径（/v1/...）：路径不变，仅标注 root_path
            if original_path.startswith(API_PATH_PREFIXES):
                scope = dict(scope)
                scope["path"] = original_path
                scope["root_path"] = self.prefix
                await self.app(scope, receive, send)
                return

            # 未知路径不再一律返回 index.html：接口写错前缀时必须给出 404 JSON，
            # 否则前端拿到 200 HTML 却解析失败，表现为「接口 404 / 页面白屏」。
            if not is_spa_path(original_path):
                from starlette.responses import JSONResponse
                await JSONResponse(
                    status_code=404,
                    content={
                        "detail": "Not Found",
                        "code": 404,
                        "hint": "API 路径需以 /api/v1/ 或 /v1/ 开头；页面路径需属于 SPA 白名单",
                    },
                )(scope, receive, send)
                return

            # 非 API 路径 - 返回前端页面
            from starlette.responses import FileResponse, HTMLResponse, PlainTextResponse, RedirectResponse
            import os

            static_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web", "dist")

            # 前端静态资源（/assets/*）必须优先于「未安装→跳转」处理：
            # 否则未安装时，install.html 引用的 JS/CSS 会被误判为「非安装路径」而 302 到 /install，
            # 浏览器拿到 HTML 当 JS 解析，安装页直接白板。
            if original_path.startswith("/assets/"):
                file_path = os.path.join(static_dir, original_path.lstrip("/"))
                if os.path.exists(file_path):
                    await FileResponse(file_path)(scope, receive, send)
                else:
                    await HTMLResponse(status_code=404, content="Not Found")(scope, receive, send)
                return

            # 如果未安装且访问的不是安装页面，重定向到安装页面
            if not is_installed and not original_path.startswith("/install"):
                response = RedirectResponse(url="/install", status_code=302)
                await response(scope, receive, send)
                return

            # 已安装却访问安装页 → 直接前往登录页（安装向导仅用于首次/重装场景）
            if is_installed and original_path.startswith("/install"):
                response = RedirectResponse(url="/panel/login", status_code=302)
                await response(scope, receive, send)
                return

            # 处理 /install 路径 - 返回独立的安装页（install.html），而非主 SPA 的 index.html，
            # 保证安装向导是真正独立的页面，不加载主应用 bundle。
            if original_path.startswith("/install"):
                index_path = os.path.join(static_dir, "install.html")
                if os.path.exists(index_path):
                    await FileResponse(index_path)(scope, receive, send)
                else:
                    # 前端未构建时不再提供独立兜底页面（不混入任何 HTML 文件）：
                    # 直接返回纯文本提示，引导先构建前端。
                    await PlainTextResponse(
                        status_code=503,
                        content="系统尚未安装，且前端资源未构建。请先执行：cd web && npm install && npm run build"
                    )(scope, receive, send)
                return

            # 返回前端 index.html（SPA 模式）
            index_path = os.path.join(static_dir, "index.html")
            if os.path.exists(index_path):
                await FileResponse(index_path)(scope, receive, send)
            else:
                # 前端未构建时的兜底（不混入任何 HTML 文件）：
                # - 已安装 → 纯文本提示需要构建前端
                # - 未安装 → 跳回安装向导（正常路径已被前置 302 拦截，此处仅为兜底）
                if is_installed:
                    await PlainTextResponse(
                        status_code=503,
                        content="系统已安装，但前端资源未构建。请先执行：cd web && npm install && npm run build"
                    )(scope, receive, send)
                else:
                    response = RedirectResponse(url="/install", status_code=302)
                    await response(scope, receive, send)
            return

        # 调用实际应用
        await self.app(scope, receive, send)

# 创建包装后的应用
app = ASGIAppWithPrefix(real_app, prefix="/api")
