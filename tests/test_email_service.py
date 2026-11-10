"""EmailService 验证码存储与频率限制回归测试。

强制进程内降级模式（Redis 关闭），验证：
- 验证码生成格式
- 存储 → 校验一次性消费
- 错误码 / 缺失码拒绝
- 邮箱与 IP 频率限制触发
"""
import pytest

from base.common.setting import settings
from base.core.users.services.email_service import EmailService


@pytest.fixture(autouse=True)
def _in_process_mode():
    # 强制走进程内降级路径，保证本测试不依赖 Redis 可用性
    prev = settings.REDIS_ENABLED
    settings.REDIS_ENABLED = False
    EmailService._redis = None
    # 清空共享状态，避免用例间串扰
    EmailService._verification_codes.clear()
    EmailService._code_expire_time.clear()
    EmailService._rate_store.clear()
    yield
    settings.REDIS_ENABLED = prev
    EmailService._verification_codes.clear()
    EmailService._code_expire_time.clear()
    EmailService._rate_store.clear()


def test_generate_code_format():
    code = EmailService.generate_code()
    assert len(code) == EmailService.CODE_LENGTH
    assert code.isdigit()


async def test_store_and_verify_roundtrip():
    await EmailService.store_code("a@example.com", "123456", "register")
    assert await EmailService.verify_code("a@example.com", "123456", "register") is True
    # 一次性消费：再次校验应失败
    assert await EmailService.verify_code("a@example.com", "123456", "register") is False


async def test_verify_wrong_code_rejected():
    await EmailService.store_code("b@example.com", "654321", "login")
    assert await EmailService.verify_code("b@example.com", "000000", "login") is False
    # 错误码不应消耗正确码
    assert await EmailService.verify_code("b@example.com", "654321", "login") is True


async def test_verify_missing_code_rejected():
    assert await EmailService.verify_code("nobody@example.com", "123456", "register") is False


async def test_send_code_roundtrip():
    ok, msg = await EmailService.send_code("c@example.com", "register")
    # 进程内无 SMTP 配置时不真正发信，但验证码已存储
    assert ok is True
    assert await EmailService.verify_code("c@example.com", EmailService._verification_codes["vc:register:c@example.com"], "register") is True


async def test_rate_limit_per_email():
    email = "rate@example.com"
    results = [await EmailService.check_rate_limit(email, "1.2.3.4") for _ in range(EmailService.RATE_LIMIT_PER_EMAIL_MAX + 1)]
    # 前 N 次通过，第 N+1 次被限流
    assert results[:-1] == [None] * EmailService.RATE_LIMIT_PER_EMAIL_MAX
    assert isinstance(results[-1], str) and "频繁" in results[-1]


async def test_rate_limit_per_ip():
    # 不同邮箱、同一 IP 触发 IP 维度限流
    ip = "9.9.9.9"
    results = []
    for i in range(EmailService.RATE_LIMIT_PER_IP_MAX + 1):
        results.append(await EmailService.check_rate_limit(f"ipuser{i}@example.com", ip))
    assert results[-1] is not None and "频繁" in results[-1]
