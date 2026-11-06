"""
邮件服务 - 发送验证码
"""

import random
import string
import asyncio
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
from datetime import datetime, timedelta
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class EmailService:
    """邮件服务类"""

    # 验证码存储（生产环境应使用 Redis）
    _verification_codes = {}
    _code_expire_time = {}

    # 验证码有效期（分钟）
    CODE_EXPIRE_MINUTES = 5

    # 验证码长度
    CODE_LENGTH = 6

    @classmethod
    def generate_code(cls) -> str:
        """生成6位数字验证码"""
        return ''.join(random.choices(string.digits, k=cls.CODE_LENGTH))

    @classmethod
    def store_code(cls, email: str, code: str, code_type: str) -> None:
        """存储验证码"""
        key = f"{code_type}:{email}"
        cls._verification_codes[key] = code
        cls._code_expire_time[key] = datetime.now() + timedelta(minutes=cls.CODE_EXPIRE_MINUTES)
        logger.info(f"[验证码存储] Email: {email}, Type: {code_type}, Code: {code}, Key: {key}")
        logger.info(f"[过期时间] {cls._code_expire_time[key]}")

    @classmethod
    def verify_code(cls, email: str, code: str, code_type: str) -> bool:
        """验证验证码"""
        key = f"{code_type}:{email}"

        logger.info(f"[验证码验证] Email: {email}, Type: {code_type}, Code: {code}, Key: {key}")
        logger.info(f"[当前存储的验证码] {cls._verification_codes}")

        # 检查验证码是否存在
        if key not in cls._verification_codes:
            logger.warning(f"[验证码验证失败] 验证码不存在: {key}")
            return False

        # 检查是否过期
        if datetime.now() > cls._code_expire_time[key]:
            # 清除过期验证码
            logger.warning(f"[验证码验证失败] 验证码已过期: {key}")
            cls._verification_codes.pop(key, None)
            cls._code_expire_time.pop(key, None)
            return False

        # 验证码匹配
        if cls._verification_codes[key] == code:
            logger.info(f"[验证码验证成功] 验证码匹配: {key}")
            # 验证成功后删除验证码
            cls._verification_codes.pop(key, None)
            cls._code_expire_time.pop(key, None)
            return True

        logger.warning(f"[验证码验证失败] 验证码不匹配. 期望: {cls._verification_codes[key]}, 实际: {code}")
        return False

    @classmethod
    async def send_verification_email(cls, email: str, code: str, code_type: str) -> bool:
        """
        发送验证码邮件

        Args:
            email: 邮箱地址
            code: 验证码
            code_type: 验证码类型

        Returns:
            是否发送成功
        """
        from base.common.setting import settings

        # 如果邮件服务未启用或未配置，则只在日志中输出
        if not settings.EMAIL_ENABLED or not settings.SENDER_EMAIL or not settings.SENDER_PASSWORD:
            logger.warning(f"====== 验证码邮件（未配置SMTP，仅输出到日志）=======")
            logger.warning(f"收件人: {email}")
            logger.warning(f"类型: {code_type}")
            logger.warning(f"验证码: {code}")
            logger.warning(f"有效期: {cls.CODE_EXPIRE_MINUTES} 分钟")
            logger.warning(f"==================================================")
            await asyncio.sleep(0.1)
            return True

        try:
            # 根据类型设置邮件内容
            type_names = {
                "register": "注册",
                "login": "登录",
                "reset_password": "重置密码"
            }
            type_name = type_names.get(code_type, code_type)

            # 创建邮件
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"{settings.SENDER_NAME} - {type_name}验证码"
            msg['From'] = formataddr((settings.SENDER_NAME, settings.SENDER_EMAIL))
            msg['To'] = email

            # 邮件正文（HTML格式）
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                    .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                    .code {{ background: white; border: 2px dashed #667eea; padding: 20px; text-align: center; font-size: 32px; font-weight: bold; color: #667eea; letter-spacing: 5px; margin: 20px 0; border-radius: 5px; }}
                    .footer {{ text-align: center; color: #999; font-size: 12px; margin-top: 30px; }}
                    .button {{ display: inline-block; padding: 12px 30px; background: #667eea; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h2>{settings.SENDER_NAME}</h2>
                        <p>{type_name}验证码</p>
                    </div>
                    <div class="content">
                        <p>您好，</p>
                        <p>您正在进行{type_name}操作，您的验证码是：</p>
                        <div class="code">{code}</div>
                        <p><strong>验证码有效期为 {cls.CODE_EXPIRE_MINUTES} 分钟。</strong></p>
                        <p>如果这不是您的操作，请忽略此邮件。</p>
                        <div class="footer">
                            <p>此邮件由系统自动发送，请勿回复。</p>
                            <p>{settings.SENDER_NAME} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                        </div>
                    </div>
                </div>
            </body>
            </html>
            """

            # 添加HTML内容
            html_part = MIMEText(html_content, 'html', 'utf-8')
            msg.attach(html_part)

            # 连接SMTP服务器并发送邮件
            if settings.SMTP_USE_TLS:
                server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT)
                server.starttls()
            else:
                server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT)

            server.login(settings.SENDER_EMAIL, settings.SENDER_PASSWORD)
            server.sendmail(settings.SENDER_EMAIL, [email], msg.as_string())
            server.quit()

            logger.info(f"验证码邮件已发送到 {email}")
            return True

        except Exception as e:
            logger.error(f"发送邮件失败: {str(e)}")
            # 发送失败时，在日志中输出验证码（便于开发调试）
            logger.warning(f"====== 验证码（邮件发送失败，仅输出到日志）=======")
            logger.warning(f"收件人: {email}")
            logger.warning(f"类型: {code_type}")
            logger.warning(f"验证码: {code}")
            logger.warning(f"有效期: {cls.CODE_EXPIRE_MINUTES} 分钟")
            logger.warning(f"==================================================")
            return False

    @classmethod
    async def send_code(cls, email: str, code_type: str) -> tuple[bool, str]:
        """
        发送验证码

        Args:
            email: 邮箱地址
            code_type: 验证码类型 (register/login/reset_password)

        Returns:
            (是否成功, 消息)
        """
        # 生成验证码
        code = cls.generate_code()

        # 存储验证码
        cls.store_code(email, code, code_type)

        # 发送邮件
        success = await cls.send_verification_email(email, code, code_type)

        if success:
            return True, f"验证码已发送到 {email}，{cls.CODE_EXPIRE_MINUTES}分钟内有效"
        else:
            return False, "验证码发送失败，请稍后重试"

    @classmethod
    def cleanup_expired_codes(cls):
        """清理过期验证码（定时任务调用）"""
        now = datetime.now()
        expired_keys = [
            key for key, expire_time in cls._code_expire_time.items()
            if now > expire_time
        ]

        for key in expired_keys:
            cls._verification_codes.pop(key, None)
            cls._code_expire_time.pop(key, None)

        if expired_keys:
            logger.info(f"清理了 {len(expired_keys)} 个过期验证码")
