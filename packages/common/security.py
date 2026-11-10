"""服务凭据签名算法（app 侧签发/验签与 编排共用同一实现）。

约定（与 app `base/plugins/harness/services/service_auth.py` 完全一致）：
    secret_hash = SHA-256(明文密钥) 小写十六进制（库中只存该值）
    signature   = HMAC-SHA256(key=secret_hash,
                              msg=timestamp + "\\n" + METHOD + "\\n" + path + "\\n" + sha256(body))
"""
import hashlib
import hmac
from typing import Any

SERVICE_ID_HEADER = "x-service-id"
SERVICE_TIMESTAMP_HEADER = "x-service-timestamp"
SERVICE_SIGNATURE_HEADER = "x-service-signature"


def hash_secret(secret: str) -> str:
    """明文密钥 → 库中存储的 SHA-256 小写十六进制（与 app 客户端凭据一致）。"""
    return hashlib.sha256(str(secret).encode("utf-8")).hexdigest()


def client_ip(request: Any) -> str:
    """请求来源 IP：优先 X-Forwarded-For 首段，其次直连地址。"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""


def signature_payload(timestamp: str, method: str, path: str, body: bytes) -> str:
    body_hash = hashlib.sha256(body or b"").hexdigest()
    return f"{timestamp}\n{method.upper()}\n{path}\n{body_hash}"


def build_signature(
    secret_hash: str, timestamp: str, method: str, path: str, body: bytes = b""
) -> str:
    """生成服务凭据签名（供内部调用方/验证脚本使用）。"""
    payload = signature_payload(timestamp, method, path, body)
    return hmac.new(
        str(secret_hash).encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()
