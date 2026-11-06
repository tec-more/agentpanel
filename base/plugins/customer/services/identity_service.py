"""
M11 身份关联服务（L1 身份关联，认人不并资产）

溯源：
- docs/用户侧智能体设计流PRD.md §3.2（D1~D8）与 §3.3（L1~L10，本服务的直接依据）
- docs/arch/02-系统上下文与领域模型.md §2.1 M11、§4.2 identity_link
- docs/arch/04-核心流程与接口契约.md §2.1 identity 四个 API
- docs/arch/06-架构自检与开发基线.md R-04/R-14
- docs/arch/05-可靠性与安全可观测.md §1.1 SMTP/Redis 降级

红线：
- R-14：仅"提示→主动确认→验证"建立映射，本服务不提供任何静默绑定入口
- D5：仅建立映射，不复制/迁移/合并双主体任何资产
"""
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from loguru import logger

from base.common.authz.constants import OwnerType
from base.common.authz.context import OwnerContext
from base.common.cache import RedisCache
from base.common.context import get_current_trace_id
from base.plugins.customer.models.identity_link import IdentityLink

# ===== 状态与配置（PRD §3.3）=====
STATUS_NONE = "none"            # 无可关联对象 / 提示期已过
STATUS_PROMPTED = "prompted"    # 已提示待确认
STATUS_LINKED = "linked"        # 已关联
STATUS_DISMISSED = "dismissed"  # 不再提示（30 天）
STATUS_COOLDOWN = "cooldown"    # 解绑冷却中（30 天）

DISMISS_DAYS = 30          # L7/任务口径：不再提示 30 天
COOLDOWN_DAYS = 30         # L9：解绑冷却 30 天
PROMPT_INTERVAL_DAYS = 30  # L7：同一对主体 30 天最多提示 1 次

VERIFY_MAX_ATTEMPTS = 5        # 验证失败上限（任务口径 5 次）
VERIFY_LOCK_SECONDS = 600      # L6：锁定 10 分钟
SEND_CODE_MIN_INTERVAL = 60    # 验证码发送限频：同主体 60 秒 1 次

CODE_TYPE_IDENTITY = "identity_link"  # 邮箱验证码类型（复用 EmailService 通道）


class IdentityError(Exception):
    """身份关联业务异常（API 层转换为统一失败响应）"""

    def __init__(self, code: str, message: str, data: Optional[dict] = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data or {}


def mask_email(email: Optional[str]) -> Optional[str]:
    """邮箱打码（L3）：保留首字符与域名，如 a***@example.com"""
    if not email or "@" not in email:
        return None
    local, domain = email.split("@", 1)
    return f"{local[0]}***@{domain}"


# ===== 验证失败计数 / 锁定（Redis 优先，不可用退化进程内，同 authz 降级模式）=====
_verify_fail_counters: dict = {}
_verify_locks: dict = {}


def _verify_count_key(identity: str) -> str:
    return f"rl:identity_verify:{identity}"


def _verify_lock_key(identity: str) -> str:
    return f"rl:identity_verify:lock:{identity}"


async def _verify_fail_incr(identity: str) -> int:
    """失败计数 +1（窗口 = 锁定时长）"""
    key = _verify_count_key(identity)
    if RedisCache.is_enabled():
        cache = await RedisCache.get_instance()
        # D2 修复：走封装方法（硬超时+熔断），失败返回 None 退化进程内计数
        count = await cache.incr(key, expire=VERIFY_LOCK_SECONDS)
        if count is not None:
            return count
        logger.warning("[identity] Redis 计数失败，退化进程内计数")
    now = time.monotonic()
    count, expire_ts = _verify_fail_counters.get(key, (0, 0.0))
    if now > expire_ts:
        count, expire_ts = 0, now + VERIFY_LOCK_SECONDS
    count += 1
    _verify_fail_counters[key] = (count, expire_ts)
    return count


async def _set_verify_lock(identity: str) -> None:
    key = _verify_lock_key(identity)
    if RedisCache.is_enabled():
        cache = await RedisCache.get_instance()
        # D2 修复：走封装方法（硬超时+熔断）
        if await cache.set(key, "1", VERIFY_LOCK_SECONDS):
            return
        logger.warning("[identity] Redis 锁定标记写入失败")
    _verify_locks[key] = time.monotonic() + VERIFY_LOCK_SECONDS


async def _verify_lock_remaining(identity: str) -> int:
    """剩余锁定秒数，0 表示未锁定"""
    key = _verify_lock_key(identity)
    if RedisCache.is_enabled():
        cache = await RedisCache.get_instance()
        # D2 修复：走封装方法（硬超时+熔断）
        ttl = await cache.ttl(key)
        if ttl is not None:
            return max(0, ttl) if ttl > 0 else 0
    expire_ts = _verify_locks.get(key, 0.0)
    remaining = int(expire_ts - time.monotonic())
    if remaining > 0:
        return remaining
    _verify_locks.pop(key, None)
    return 0


async def _clear_verify_counter(identity: str) -> None:
    key = _verify_count_key(identity)
    if RedisCache.is_enabled():
        cache = await RedisCache.get_instance()
        # D2 修复：走封装方法（硬超时+熔断）
        if await cache.delete(key):
            return
    _verify_fail_counters.pop(key, None)


async def _send_code_allowed(identity: str) -> bool:
    """验证码发送限频：同主体 60 秒 1 次（Redis SET NX，退化进程内）"""
    key = f"rl:identity_send_code:{identity}"
    if RedisCache.is_enabled():
        cache = await RedisCache.get_instance()
        # D2 修复：走封装方法（硬超时+熔断）；None=失败，退化进程内限频
        ok = await cache.set_nx(key, SEND_CODE_MIN_INTERVAL)
        if ok is not None:
            return ok
    now = time.monotonic()
    expire_ts = _verify_locks.get(key, 0.0)
    if now < expire_ts:
        return False
    _verify_locks[key] = now + SEND_CODE_MIN_INTERVAL
    return True


class IdentityService:
    """L1 身份关联服务：发现与提示、主动确认、对方主体验证、解绑与冷却"""

    # ---------- 基础工具 ----------

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    async def _write_audit_log(
        *,
        operation: str,
        owner_identity: str,
        result: str,
        detail: Optional[dict] = None,
    ) -> None:
        """全量审计落库（L10，复用 audit 插件通道；失败仅记日志不阻断）"""
        try:
            from base.plugins.audit.models.audit_log import AuditLog

            owner_id = None
            if owner_identity and ":" in owner_identity:
                _, oid = owner_identity.split(":", 1)
                owner_id = int(oid) if oid.isdigit() else None

            await AuditLog.create(
                trace_id=get_current_trace_id(),
                user_id=owner_id,
                username=owner_identity,
                module="identity",
                operation=operation,
                method="-",
                path="/v1/u/identity",
                status_code=200 if result == "success" else 400,
                error_message=None if result == "success" else result,
                request_params=detail,
                level="info" if result == "success" else "warning",
            )
        except Exception as e:
            logger.error(f"[identity] 审计写入失败: {e}")

    @staticmethod
    def _append_event(
        link: IdentityLink, action: str, actor: str, detail: Optional[dict] = None
    ) -> None:
        """向 identity_link.audit JSON 数组追加事件（L10）"""
        events = list(link.audit or [])
        events.append({
            "action": action,
            "actor": actor,
            "at": IdentityService._now().isoformat(),
            "trace_id": get_current_trace_id(),
            "detail": detail or {},
        })
        link.audit = events

    @staticmethod
    def _last_event(link: IdentityLink, actions: Tuple[str, ...]) -> Optional[dict]:
        for event in reversed(link.audit or []):
            if event.get("action") in actions:
                return event
        return None

    # ---------- 主体解析 ----------

    @staticmethod
    async def _get_self_principal(owner: OwnerContext):
        """按 token typ/sub 取当前主体（R-04 信任同源）"""
        if owner.owner_type == OwnerType.CUS.value:
            from base.plugins.customer.models.customer import Customer
            return await Customer.get_or_none(id=owner.owner_id)
        from base.core.users.models.users import User
        return await User.get_or_none(id=owner.owner_id)

    @staticmethod
    async def _find_counterpart(owner: OwnerContext, self_email: Optional[str]):
        """按同邮箱查找另一主体（L1 发现；只读，不建立任何映射）"""
        if not self_email:
            return None
        if owner.owner_type == OwnerType.CUS.value:
            from base.core.users.models.users import User
            return await User.get_or_none(email=self_email)
        from base.plugins.customer.models.customer import Customer
        return await Customer.get_or_none(email=self_email)

    @staticmethod
    def _principal_pair(owner: OwnerContext, self_obj, peer_obj) -> Tuple[int, int]:
        """统一转换为 (customer_id, user_id)"""
        if owner.owner_type == OwnerType.CUS.value:
            return self_obj.id, peer_obj.id
        return peer_obj.id, self_obj.id

    @staticmethod
    def _peer_type(owner: OwnerContext) -> str:
        return OwnerType.USR.value if owner.owner_type == OwnerType.CUS.value else OwnerType.CUS.value

    @staticmethod
    def _masked_principal(owner_type: str, obj) -> dict:
        """打码后的主体信息（L3：不展示任何资产数据）"""
        return {
            "owner_type": owner_type,
            "username": getattr(obj, "username", None) or getattr(obj, "nickname", None),
            "masked_email": mask_email(getattr(obj, "email", None)),
            "last_login": obj.last_login.isoformat() if getattr(obj, "last_login", None) else None,
        }

    @staticmethod
    async def _get_link(customer_id: int, user_id: int) -> Optional[IdentityLink]:
        return await IdentityLink.get_or_none(customer_id=customer_id, user_id=user_id)

    # ---------- 验证码验证 ----------

    @staticmethod
    async def _verify_counterpart(
        owner: OwnerContext, peer, verify_via: str, credential: str
    ) -> None:
        """
        验证对方主体归属（L5/L6）
        - cus → usr：后台密码 或 邮箱验证码
        - usr → cus：邮箱验证码（客户已设密码时可改用密码）
        失败计数 +1，累计 VERIFY_MAX_ATTEMPTS 次锁定 10 分钟
        """
        identity = owner.identity
        remaining = await _verify_lock_remaining(identity)
        if remaining > 0:
            raise IdentityError(
                "verify_locked",
                f"验证失败次数过多，已锁定，请 {remaining} 秒后重试",
                {"lock_remaining_seconds": remaining},
            )

        ok = False
        if verify_via == "email_code":
            from base.core.users.services.email_service import EmailService
            ok = EmailService.verify_code(peer.email, credential, CODE_TYPE_IDENTITY)
        elif verify_via == "password":
            peer_password = getattr(peer, "password", None)
            if not peer_password:
                raise IdentityError("invalid_verify_via", "对方主体未设置密码，请使用邮箱验证码验证")
            from base.common.security import verify_password
            ok = verify_password(credential, peer_password)
        else:
            raise IdentityError("invalid_verify_via", "不支持的验证方式（password/email_code）")

        if ok:
            await _clear_verify_counter(identity)
            return

        count = await _verify_fail_incr(identity)
        if count >= VERIFY_MAX_ATTEMPTS:
            await _set_verify_lock(identity)
            await IdentityService._write_audit_log(
                operation="identity.verify_locked",
                owner_identity=identity,
                result="locked",
                detail={"attempts": count, "lock_seconds": VERIFY_LOCK_SECONDS},
            )
            raise IdentityError(
                "verify_locked",
                f"验证失败次数过多，已锁定 {VERIFY_LOCK_SECONDS // 60} 分钟",
                {"lock_remaining_seconds": VERIFY_LOCK_SECONDS},
            )
        raise IdentityError(
            "verify_failed",
            f"验证失败，剩余尝试次数 {VERIFY_MAX_ATTEMPTS - count} 次",
            {"attempts_left": VERIFY_MAX_ATTEMPTS - count},
        )

    # ---------- 对外服务 ----------

    @classmethod
    async def get_link_status(cls, owner: OwnerContext) -> dict:
        """
        关联提示状态检测（L1/L3/L7）
        返回 status: none/prompted/linked/dismissed/cooldown + 对方主体打码信息
        """
        self_obj = await cls._get_self_principal(owner)
        if not self_obj:
            raise IdentityError("principal_not_found", "当前主体不存在")

        peer = await cls._find_counterpart(owner, self_obj.email)
        if not peer:
            return {"status": STATUS_NONE, "should_prompt": False, "peer": None}

        peer_type = cls._peer_type(owner)
        peer_info = cls._masked_principal(peer_type, peer)
        customer_id, user_id = cls._principal_pair(owner, self_obj, peer)
        link = await cls._get_link(customer_id, user_id)

        if link and link.status == STATUS_LINKED:
            return {
                "status": STATUS_LINKED,
                "should_prompt": False,
                "peer": peer_info,
                "linked_at": link.verified_at.isoformat() if link.verified_at else None,
                "verified_via": link.verified_via,
            }

        # 对方已关联他人（异常态）
        peer_link = await cls._link_of_principal(peer_type, peer.id)
        if peer_link and peer_link.status == STATUS_LINKED:
            return {
                "status": STATUS_NONE,
                "should_prompt": False,
                "peer": peer_info,
                "reason": "peer_taken",
                "message": "该账号已关联其他用户，请联系客服处理",
            }

        now = cls._now()
        if link and link.status == STATUS_DISMISSED:
            if link.dismissed_until and link.dismissed_until > now:
                last_unlink = cls._last_event(link, ("unlinked",))
                status = STATUS_COOLDOWN if last_unlink else STATUS_DISMISSED
                return {
                    "status": status,
                    "should_prompt": False,
                    "peer": peer_info,
                    "dismissed_until": link.dismissed_until.isoformat(),
                }
            # 冷却/不再提示期已过，可重新进入提示流程
            link.status = STATUS_PROMPTED
            link.dismissed_until = None

        if link is None:
            link = await IdentityLink.create(
                customer_id=customer_id, user_id=user_id, status=STATUS_PROMPTED, audit=[]
            )

        # L7：同一对主体 30 天最多提示 1 次
        last_prompt = cls._last_event(link, ("prompt_shown",))
        should_prompt = True
        if last_prompt:
            last_at = datetime.fromisoformat(last_prompt["at"])
            should_prompt = (now - last_at) >= timedelta(days=PROMPT_INTERVAL_DAYS)

        if should_prompt:
            cls._append_event(link, "prompt_shown", owner.identity)
            await cls._write_audit_log(
                operation="identity.prompt_shown",
                owner_identity=owner.identity,
                result="success",
                detail={"peer_type": peer_type},
            )
        await link.save()

        return {
            "status": STATUS_PROMPTED,
            "should_prompt": should_prompt,
            "peer": peer_info,
        }

    @classmethod
    async def _link_of_principal(cls, owner_type: str, principal_id: int) -> Optional[IdentityLink]:
        """查询某主体当前唯一的映射记录（D1）"""
        if owner_type == OwnerType.CUS.value:
            return await IdentityLink.get_or_none(customer_id=principal_id)
        return await IdentityLink.get_or_none(user_id=principal_id)

    @classmethod
    async def link(cls, owner: OwnerContext, verify_via: str, credential: str) -> dict:
        """
        用户主动发起关联（D2/L5）：必须验证对方主体归属
        仅建立映射，不合并任何资产（D5/L8）
        """
        self_obj = await cls._get_self_principal(owner)
        if not self_obj:
            raise IdentityError("principal_not_found", "当前主体不存在")

        peer = await cls._find_counterpart(owner, self_obj.email)
        if not peer:
            raise IdentityError("peer_not_found", "未找到可关联的对方主体")

        peer_type = cls._peer_type(owner)
        customer_id, user_id = cls._principal_pair(owner, self_obj, peer)
        link = await cls._get_link(customer_id, user_id)

        # 异常态：重复绑定
        if link and link.status == STATUS_LINKED:
            raise IdentityError(
                "already_linked",
                "已关联，请勿重复绑定",
                {"linked_at": link.verified_at.isoformat() if link.verified_at else None},
            )

        # 解绑冷却期内不允许重新关联
        if (
            link
            and link.status == STATUS_DISMISSED
            and link.dismissed_until
            and link.dismissed_until > cls._now()
            and cls._last_event(link, ("unlinked",))
        ):
            raise IdentityError(
                "cooldown",
                "解绑冷却期内暂不可重新关联",
                {"cooldown_until": link.dismissed_until.isoformat()},
            )

        # 异常态：对方主体被禁用（不透露细节）
        if not getattr(peer, "is_active", True):
            raise IdentityError("peer_disabled", "该账号不可关联，请联系管理员")

        # 异常态：本侧主体已关联其他账号（D1 双向唯一）
        self_link = await cls._link_of_principal(owner.owner_type, self_obj.id)
        if (
            self_link
            and self_link.status == STATUS_LINKED
            and (self_link.customer_id, self_link.user_id) != (customer_id, user_id)
        ):
            raise IdentityError("already_linked", "当前账号已关联其他账号，请先解绑")

        # 异常态：对方已关联其他账号
        peer_link = await cls._link_of_principal(peer_type, peer.id)
        if (
            peer_link
            and peer_link.status == STATUS_LINKED
            and (peer_link.customer_id, peer_link.user_id) != (customer_id, user_id)
        ):
            raise IdentityError("peer_taken", "该账号已关联其他用户，请联系客服处理")

        await cls._write_audit_log(
            operation="identity.link_initiated",
            owner_identity=owner.identity,
            result="success",
            detail={"peer_type": peer_type, "verify_via": verify_via},
        )

        try:
            await cls._verify_counterpart(owner, peer, verify_via, credential)
        except IdentityError as e:
            if link is None:
                link = await IdentityLink.create(
                    customer_id=customer_id, user_id=user_id, status=STATUS_PROMPTED, audit=[]
                )
            cls._append_event(link, "verify_failed", owner.identity, {"via": verify_via})
            await link.save()
            await cls._write_audit_log(
                operation="identity.verify_failed",
                owner_identity=owner.identity,
                result=e.code,
                detail={"via": verify_via},
            )
            raise

        now = cls._now()
        if link is None:
            link = await IdentityLink.create(
                customer_id=customer_id, user_id=user_id, status=STATUS_PROMPTED, audit=[]
            )
        link.status = STATUS_LINKED
        link.verified_via = verify_via
        link.verified_at = now
        link.dismissed_until = None
        cls._append_event(link, "linked", owner.identity, {"via": verify_via})
        await link.save()

        await cls._write_audit_log(
            operation="identity.linked",
            owner_identity=owner.identity,
            result="success",
            detail={"peer_type": peer_type, "via": verify_via},
        )

        return {
            "status": STATUS_LINKED,
            "linked_at": now.isoformat(),
            "peer": cls._masked_principal(peer_type, peer),
            "notice": "关联仅用于身份识别，不共享工作流、知识库、额度与账单",
        }

    @classmethod
    async def dismiss(cls, owner: OwnerContext) -> dict:
        """不再提示（L7）：30 天内关闭提示"""
        self_obj = await cls._get_self_principal(owner)
        if not self_obj:
            raise IdentityError("principal_not_found", "当前主体不存在")

        peer = await cls._find_counterpart(owner, self_obj.email)
        if not peer:
            raise IdentityError("peer_not_found", "未找到可关联的对方主体")

        customer_id, user_id = cls._principal_pair(owner, self_obj, peer)
        link = await cls._get_link(customer_id, user_id)
        if link and link.status == STATUS_LINKED:
            raise IdentityError("already_linked", "已关联账号无需此操作")

        if link is None:
            link = await IdentityLink.create(
                customer_id=customer_id, user_id=user_id, status=STATUS_PROMPTED, audit=[]
            )

        until = cls._now() + timedelta(days=DISMISS_DAYS)
        link.status = STATUS_DISMISSED
        link.dismissed_until = until
        cls._append_event(link, "dismissed", owner.identity, {"until": until.isoformat()})
        await link.save()

        await cls._write_audit_log(
            operation="identity.dismissed",
            owner_identity=owner.identity,
            result="success",
            detail={"until": until.isoformat()},
        )
        return {"status": STATUS_DISMISSED, "dismissed_until": until.isoformat()}

    @classmethod
    async def unlink(cls, owner: OwnerContext, verify_via: str, credential: str) -> dict:
        """
        解绑（L9/D7）：需再次验证对方主体归属；只解除映射，不删除任何一方资产；
        解绑后进入 30 天冷却期，不再提示
        """
        self_obj = await cls._get_self_principal(owner)
        if not self_obj:
            raise IdentityError("principal_not_found", "当前主体不存在")

        peer = await cls._find_counterpart(owner, self_obj.email)
        if not peer:
            raise IdentityError("peer_not_found", "未找到对方主体")

        peer_type = cls._peer_type(owner)
        customer_id, user_id = cls._principal_pair(owner, self_obj, peer)
        link = await cls._get_link(customer_id, user_id)

        if not link or link.status != STATUS_LINKED:
            raise IdentityError("not_linked", "当前未处于已关联状态")

        try:
            await cls._verify_counterpart(owner, peer, verify_via, credential)
        except IdentityError as e:
            cls._append_event(link, "verify_failed", owner.identity, {"via": verify_via, "op": "unlink"})
            await link.save()
            await cls._write_audit_log(
                operation="identity.verify_failed",
                owner_identity=owner.identity,
                result=e.code,
                detail={"via": verify_via, "op": "unlink"},
            )
            raise

        until = cls._now() + timedelta(days=COOLDOWN_DAYS)
        link.status = STATUS_DISMISSED
        link.dismissed_until = until
        cls._append_event(link, "unlinked", owner.identity, {"cooldown_until": until.isoformat()})
        await link.save()

        await cls._write_audit_log(
            operation="identity.unlinked",
            owner_identity=owner.identity,
            result="success",
            detail={"peer_type": peer_type, "cooldown_until": until.isoformat()},
        )
        return {"status": STATUS_COOLDOWN, "cooldown_until": until.isoformat()}

    @classmethod
    async def admin_bind(cls, admin_id: int, customer_id: int, user_id: int) -> dict:
        """管理员手动绑定（管理侧；跳过验证，全量审计）"""
        from base.plugins.customer.models.customer import Customer
        from base.core.users.models.users import User

        customer = await Customer.get_or_none(id=customer_id)
        user = await User.get_or_none(id=user_id)
        if not customer or not user:
            raise IdentityError("principal_not_found", "客户或后台用户不存在")
        if not customer.is_active or not user.is_active:
            raise IdentityError("peer_disabled", "存在被禁用主体，不可绑定")

        now = cls._now()
        link = await cls._get_link(customer_id, user_id)
        if link and link.status == STATUS_LINKED:
            raise IdentityError("already_linked", "该主体对已关联，请勿重复绑定")

        for owner_type, pid in ((OwnerType.CUS.value, customer_id), (OwnerType.USR.value, user_id)):
            existing = await cls._link_of_principal(owner_type, pid)
            if (
                existing
                and existing.status == STATUS_LINKED
                and (existing.customer_id, existing.user_id) != (customer_id, user_id)
            ):
                raise IdentityError("peer_taken", "目标主体已存在关联，请先解绑")

        if link is None:
            link = await IdentityLink.create(
                customer_id=customer_id, user_id=user_id, status=STATUS_PROMPTED, audit=[]
            )
        link.status = STATUS_LINKED
        link.verified_via = "admin"
        link.verified_at = now
        link.dismissed_until = None
        cls._append_event(link, "admin_bind", f"usr:{admin_id}")
        await link.save()

        await cls._write_audit_log(
            operation="identity.admin_bind",
            owner_identity=f"usr:{admin_id}",
            result="success",
            detail={"customer_id": customer_id, "user_id": user_id},
        )
        return {
            "status": STATUS_LINKED,
            "customer_id": customer_id,
            "user_id": user_id,
            "linked_at": now.isoformat(),
        }

    @classmethod
    async def list_links(
        cls,
        *,
        customer_id: Optional[int] = None,
        user_id: Optional[int] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """管理侧查询关联记录"""
        query = IdentityLink.all()
        if customer_id:
            query = query.filter(customer_id=customer_id)
        if user_id:
            query = query.filter(user_id=user_id)
        if status:
            query = query.filter(status=status)
        total = await query.count()
        rows = await query.offset((page - 1) * page_size).limit(page_size).order_by("-updated_at")
        items = [
            {
                "id": r.id,
                "customer_id": r.customer_id,
                "user_id": r.user_id,
                "status": r.status,
                "verified_via": r.verified_via,
                "verified_at": r.verified_at.isoformat() if r.verified_at else None,
                "dismissed_until": r.dismissed_until.isoformat() if r.dismissed_until else None,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in rows
        ]
        return {"total": total, "page": page, "page_size": page_size, "items": items}

    @classmethod
    async def send_link_code(cls, owner: OwnerContext) -> str:
        """
        发送身份关联验证码（复用 EmailService 通道，含限频）
        SMTP 故障返回明确错误（05 §1.1）
        """
        self_obj = await cls._get_self_principal(owner)
        if not self_obj or not self_obj.email:
            raise IdentityError("principal_not_found", "当前主体不存在或未绑定邮箱")

        if not await _send_code_allowed(owner.identity):
            raise IdentityError("send_code_rate_limited", "发送过于频繁，请 60 秒后重试")

        from base.core.users.services.email_service import EmailService
        success, message = await EmailService.send_code(self_obj.email, CODE_TYPE_IDENTITY)
        if not success:
            # SMTP 不可用 → 明确错误（05 §1.1：身份关联流程阻断，提示稍后再试）
            raise IdentityError("smtp_unavailable", "验证码发送失败，请稍后重试")
        return message

    @classmethod
    async def resume(cls, owner: OwnerContext) -> dict:
        """
        重新开启提示（T14+ K2，PRD §3.3 L7）
        仅 dismissed（不再提示）可恢复为 prompted；
        cooldown（解绑冷却）期间必须等期满，不可手动恢复（L9）。
        """
        self_obj = await cls._get_self_principal(owner)
        if not self_obj:
            raise IdentityError("principal_not_found", "当前主体不存在")

        peer = await cls._find_counterpart(owner, self_obj.email)
        if not peer:
            raise IdentityError("peer_not_found", "未找到可关联的对方主体")

        customer_id, user_id = cls._principal_pair(owner, self_obj, peer)
        link = await cls._get_link(customer_id, user_id)

        if not link or link.status != STATUS_DISMISSED:
            raise IdentityError("not_dismissed", "当前不在不再提示状态")

        # cooldown（含 unlinked 事件）不可恢复（L9 30 天冷却约束）
        if cls._last_event(link, ("unlinked",)):
            raise IdentityError(
                "cooldown",
                "解绑冷却期内不可恢复提示",
                {"cooldown_until": link.dismissed_until.isoformat() if link.dismissed_until else None},
            )

        link.status = STATUS_PROMPTED
        link.dismissed_until = None
        cls._append_event(link, "resumed", owner.identity)
        await link.save()

        await cls._write_audit_log(
            operation="identity.resumed",
            owner_identity=owner.identity,
            result="success",
        )
        return {"status": STATUS_PROMPTED}

    @classmethod
    async def get_audit(cls, owner: OwnerContext) -> dict:
        """
        查询当前主体对的操作历史（T14+ K4，PRD §3.3 L10 用户可查）
        无对方主体或无映射记录时返回空列表（不暴露存在性）；
        按 at 倒序返回，防御性上限 100 条。
        """
        self_obj = await cls._get_self_principal(owner)
        if not self_obj:
            raise IdentityError("principal_not_found", "当前主体不存在")

        peer = await cls._find_counterpart(owner, self_obj.email)
        if not peer:
            return {"items": [], "total": 0}

        customer_id, user_id = cls._principal_pair(owner, self_obj, peer)
        link = await cls._get_link(customer_id, user_id)
        if not link:
            return {"items": [], "total": 0}

        events = list(link.audit or [])
        # 按 at 倒序（最新在前）；at 为 ISO 字符串，字典序即时间序
        events.sort(key=lambda e: e.get("at", ""), reverse=True)
        items = events[:100]
        return {"items": items, "total": len(items)}

    @classmethod
    async def has_link_hint(cls, owner_type: str, owner_id: int, email: Optional[str]) -> bool:
        """
        登录响应用轻量检测（RK-14 改造）：
        同邮箱存在另一主体且未建立 linked 映射 → True
        只读检测，不创建/修改任何记录
        """
        if not email:
            return False
        if owner_type == OwnerType.CUS.value:
            from base.core.users.models.users import User
            peer = await User.get_or_none(email=email)
            if not peer:
                return False
            link = await IdentityLink.get_or_none(customer_id=owner_id)
        else:
            from base.plugins.customer.models.customer import Customer
            peer = await Customer.get_or_none(email=email)
            if not peer:
                return False
            link = await IdentityLink.get_or_none(user_id=owner_id)
        return not (link and link.status == STATUS_LINKED)
