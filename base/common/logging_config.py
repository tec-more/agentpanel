"""增强的错误日志配置"""
import traceback
import logging
from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


async def log_exception(exc: Exception, request: Request = None):
    """记录异常详细信息到控制台"""
    print("\n" + "="*80)
    print("[ERROR] 发生错误")
    print("="*80)

    if request:
        print(f"[INFO] 请求信息:")
        print(f"   方法: {request.method}")
        print(f"   URL: {request.url}")
        print(f"   客户端: {request.client}")

    print(f"\n[INFO] 错误类型: {type(exc).__name__}")
    print(f"[INFO] 错误信息: {str(exc)}")

    print(f"\n[TRACEBACK] 错误堆栈:")
    traceback.print_exc()

    print("="*80 + "\n")


async def DoesNotExistHandle(req: Request, exc: Exception) -> JSONResponse:
    """处理对象不存在异常"""
    await log_exception(exc, req)

    content = dict(
        code=404,
        msg=f"对象不存在: {str(exc)}",
    )
    return JSONResponse(content=content, status_code=404)


async def IntegrityHandle(req: Request, exc: Exception) -> JSONResponse:
    """处理数据库完整性异常"""
    await log_exception(exc, req)

    content = dict(
        code=500,
        msg=f"数据完整性错误: {str(exc)}",
    )
    return JSONResponse(content=content, status_code=500)


async def HttpExcHandle(req: Request, exc: Exception) -> JSONResponse:
    """处理HTTP异常"""
    # 401/403/404 属于正常的客户端行为（鉴权失败、无权限、资源不存在），
    # 不应以 WARNING 级别输出，避免日志噪音（如轮询接口 token 过期时的反复 401）
    if exc.status_code in (401, 403, 404):
        logger.debug("HTTP异常: %s - %s | 请求: %s %s", exc.status_code, exc.detail, req.method, req.url)
    else:
        print(f"\n[WARNING] HTTP异常: {exc.status_code} - {exc.detail}")
        if req:
            print(f"   请求: {req.method} {req.url}")

    # BUG-T15-011：detail 为含业务码 code 的 dict 时业务码提顶层，对齐契约 04-§2.3
    # {code: 业务码, msg: 字符串, data}；存量字符串 detail 行为不变（前端 ElMessage 不再收到嵌套对象）
    detail = exc.detail
    if isinstance(detail, dict) and "code" in detail:
        code = detail["code"]
        msg = detail.get("msg") or detail.get("msg") or ""
        # data：优先 detail.data；否则收拢除 code/msg 外的额外字段（如乐观锁 current_draft_version）
        data = detail["data"] if "data" in detail else (
            {k: v for k, v in detail.items() if k not in ("code", "msg", "msg")} or None
        )
        content = dict(code=code, msg=msg, data=data)
    else:
        content = dict(code=exc.status_code, msg=detail, data=None)
    return JSONResponse(content=content, status_code=exc.status_code)


async def RequestValidationHandle(req: Request, exc: Exception) -> JSONResponse:
    """处理请求验证异常"""
    await log_exception(exc, req)

    # 提取详细的验证错误信息
    errors = []
    for error in exc.errors():
        field = " -> ".join(str(loc) for loc in error["loc"])
        errors.append(f"{field}: {error['msg']}")

    error_detail = "; ".join(errors)

    print(f"\n[ERROR] 请求参数验证失败:")
    print(f"   {error_detail}")

    content = dict(
        code=422,
        msg=f"请求参数验证失败: {error_detail}",
        data={"errors": exc.errors()}
    )
    return JSONResponse(content=content, status_code=422)


async def ResponseValidationHandle(req: Request, exc: Exception) -> JSONResponse:
    """处理响应验证异常"""
    await log_exception(exc, req)

    content = dict(code=500, msg=f"响应验证错误: {str(exc)}")
    return JSONResponse(content=content, status_code=500)


async def GeneralExceptionHandle(req: Request, exc: Exception) -> JSONResponse:
    """处理所有其他未捕获的异常"""
    await log_exception(exc, req)
    
    import traceback
    tb_str = traceback.format_exc()

    content = dict(
        code=500,
        msg=f"服务器内部错误: {type(exc).__name__}: {str(exc)}",
        data={"error": str(exc), "traceback": tb_str} if req.app.debug else None
    )
    return JSONResponse(content=content, status_code=500)


async def NeedApprovalHandle(req: Request, exc: Exception) -> JSONResponse:
    """处理审批门禁抛出的 NeedApprovalError，返回与原中间件一致的 40001 响应。"""
    # 不打印完整堆栈，仅记录基本信息
    content = dict(
        code=40001,
        msg="该操作需要审批",
        require_approval=True,
        instance_id=getattr(exc, "instance_id", None),
        flow_id=getattr(exc, "flow_id", None),
        flow_name=getattr(exc, "flow_name", None),
        business_type=getattr(exc, "business_type", None),
        model=getattr(exc, "model", None),
        action=getattr(exc, "action", None),
    )
    return JSONResponse(content=content, status_code=400)


def register_exceptions_with_logging(app):
    """注册带详细日志的异常处理器"""
    from fastapi.exceptions import HTTPException, RequestValidationError, ResponseValidationError
    from tortoise.exceptions import DoesNotExist, IntegrityError

    app.add_exception_handler(DoesNotExist, DoesNotExistHandle)
    app.add_exception_handler(IntegrityError, IntegrityHandle)
    app.add_exception_handler(HTTPException, HttpExcHandle)
    app.add_exception_handler(RequestValidationError, RequestValidationHandle)
    app.add_exception_handler(ResponseValidationError, ResponseValidationHandle)

    # 添加通用异常处理器（捕获所有异常）
    app.add_exception_handler(Exception, GeneralExceptionHandle)

    # 审批门禁异常（需注册在通用 Exception 处理器之前以获得更具体的匹配）
    try:
        from base.plugins.approval.services.approval_gate import NeedApprovalError
        app.add_exception_handler(NeedApprovalError, NeedApprovalHandle)
    except Exception as e:
        print(f"[WARN] 审批门禁异常处理器注册失败: {e}")

    print("[OK] 已启用详细错误日志")
