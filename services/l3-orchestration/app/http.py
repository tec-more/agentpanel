"""HTTP 传输层：响应封装与异常映射（与 L2 契约同形）。

只承载传输层契约，不含业务逻辑；L2 侧对应实现位于 `base/common/response.py`
与 `base/common/exceptions.py`（P4 收口时再合并到共享包 platform/）。
"""
from datetime import datetime
from typing import Any

from fastapi import FastAPI, status
from fastapi.exceptions import (
    HTTPException as FastAPIHTTPException,
    RequestValidationError,
    ResponseValidationError,
)
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from tortoise.exceptions import DoesNotExist, IntegrityError

RET_OK_CODE = 0
RET_OK_MSG = "成功"


class ResponseSchema(BaseModel):
    code: int = Field(default=RET_OK_CODE, description="业务状态码")
    msg: str = Field(default=RET_OK_MSG, description="响应消息")
    data: Any = Field(default=None, description="响应数据")
    status_code: int = Field(default=status.HTTP_200_OK, description="HTTP状态码")
    success: bool = Field(default=True, description="操作是否成功")


def _serialize_datetime(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _serialize_datetime(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_serialize_datetime(item) for item in obj]
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    if hasattr(obj, "model_dump"):
        return _serialize_datetime(obj.model_dump())
    if hasattr(obj, "_meta") and hasattr(obj, "pk"):
        data = {}
        for key, value in obj.__dict__.items():
            if not key.startswith("_"):
                data[key] = _serialize_datetime(value)
        return data
    if hasattr(obj, "__dict__"):
        return _serialize_datetime(obj.__dict__)
    return str(obj)


def success_response(
    data: Any = None,
    msg: str = RET_OK_MSG,
    code: int = RET_OK_CODE,
    status_code: int = status.HTTP_200_OK,
    success: bool = True,
) -> JSONResponse:
    content = ResponseSchema(
        code=code,
        msg=msg,
        data=_serialize_datetime(data),
        status_code=status_code,
        success=success,
    ).model_dump()
    return JSONResponse(content=content, status_code=status_code)


async def _does_not_exist_handler(req: Request, exc: DoesNotExist) -> JSONResponse:
    return JSONResponse(
        content=dict(
            code=404,
            msg=f"Object has not found, exc: {exc}, query_params: {req.query_params}",
        ),
        status_code=404,
    )


async def _integrity_handler(_: Request, exc: IntegrityError) -> JSONResponse:
    return JSONResponse(content=dict(code=500, msg=f"IntegrityError，{exc}"), status_code=500)


async def _http_exception_handler(_: Request, exc: FastAPIHTTPException) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, dict) and "code" in detail:
        code = detail["code"]
        msg = detail.get("msg") or ""
        data = detail["data"] if "data" in detail else (
            {k: v for k, v in detail.items() if k not in ("code", "msg")} or None
        )
        content = dict(code=code, msg=msg, data=data)
    else:
        content = dict(code=exc.status_code, msg=detail, data=None)
    return JSONResponse(content=content, status_code=exc.status_code)


async def _request_validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    errors = []
    for error in exc.errors():
        field = " -> ".join(str(loc) for loc in error["loc"])
        errors.append(f"{field}: {error['msg']}")
    return JSONResponse(
        content=dict(
            code=422,
            msg=f"请求参数验证失败: {'; '.join(errors)}",
            data={"errors": exc.errors()},
        ),
        status_code=422,
    )


async def _response_validation_handler(_: Request, exc: ResponseValidationError) -> JSONResponse:
    return JSONResponse(
        content=dict(code=500, msg=f"ResponseValidationError, {exc}"), status_code=500
    )


def register_exceptions(app: FastAPI) -> None:
    app.add_exception_handler(DoesNotExist, _does_not_exist_handler)
    app.add_exception_handler(FastAPIHTTPException, _http_exception_handler)
    app.add_exception_handler(IntegrityError, _integrity_handler)
    app.add_exception_handler(RequestValidationError, _request_validation_handler)
    app.add_exception_handler(ResponseValidationError, _response_validation_handler)
