from fastapi import FastAPI
from fastapi.exceptions import (
    HTTPException,
    RequestValidationError,
    ResponseValidationError,
)
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from tortoise.exceptions import DoesNotExist, IntegrityError



class SettingNotFound(Exception):
    pass


async def DoesNotExistHandle(req: Request, exc: DoesNotExist) -> JSONResponse:
    content = dict(
        code=404,
        msg=f"Object has not found, exc: {exc}, query_params: {req.query_params}",
    )
    return JSONResponse(content=content, status_code=404)


async def IntegrityHandle(_: Request, exc: IntegrityError) -> JSONResponse:
    content = dict(
        code=500,
        msg=f"IntegrityError，{exc}",
    )
    return JSONResponse(content=content, status_code=500)


async def HttpExcHandle(_: Request, exc: HTTPException) -> JSONResponse:
    # BUG-T15-011：detail 为含业务码 code 的 dict 时业务码提顶层，对齐契约 04-§2.3
    # {code: 业务码, msg: 字符串, data}；存量字符串 detail 行为不变
    detail = exc.detail
    if isinstance(detail, dict) and "code" in detail:
        code = detail["code"]
        msg = detail.get("msg") or detail.get("msg") or ""
        data = detail["data"] if "data" in detail else (
            {k: v for k, v in detail.items() if k not in ("code", "msg", "msg")} or None
        )
        content = dict(code=code, msg=msg, data=data)
    else:
        content = dict(code=exc.status_code, msg=detail, data=None)
    return JSONResponse(content=content, status_code=exc.status_code)


async def RequestValidationHandle(_: Request, exc: RequestValidationError) -> JSONResponse:
    # 提取详细的验证错误信息
    errors = []
    for error in exc.errors():
        field = " -> ".join(str(loc) for loc in error["loc"])
        errors.append(f"{field}: {error['msg']}")

    error_detail = "; ".join(errors)
    content = dict(
        code=422,
        msg=f"请求参数验证失败: {error_detail}",
        data={"errors": exc.errors()}
    )
    return JSONResponse(content=content, status_code=422)


async def ResponseValidationHandle(_: Request, exc: ResponseValidationError) -> JSONResponse:
    content = dict(code=500, msg=f"ResponseValidationError, {exc}")
    return JSONResponse(content=content, status_code=500)

def register_exceptions(app: FastAPI):
    app.add_exception_handler(DoesNotExist, DoesNotExistHandle)
    app.add_exception_handler(HTTPException, HttpExcHandle)
    app.add_exception_handler(IntegrityError, IntegrityHandle)
    app.add_exception_handler(RequestValidationError, RequestValidationHandle)
    app.add_exception_handler(ResponseValidationError, ResponseValidationHandle)