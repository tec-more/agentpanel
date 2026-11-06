"""
会员服务 - Fibonacci会员系统实现
"""

from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from decimal import Decimal

from base.plugins.customer.models import (
    MembershipLevel,
    CustomerMembership,
    LevelType
)
class FibonacciMembershipSystem:
    """
    Fibonacci会员系统
    基于Fibonacci数列的无限等级系统

    📢 **混合系统说明**

    此系统现在是混合会员系统的一部分，与三级会员制度（regular/vip/svip）协同工作：

    1. **会员类别**（MembershipLevel）：决定折扣和特权
    2. **Fibonacci动态等级**：基于累计充值总时长计算，用于显示等级称号

    两个系统独立但协同工作：
    - 会员类别影响购买价格（折扣）
    - Fibonacci等级影响显示和荣誉感
    - 购买任何充值包都会增加total_hours，从而提升Fibonacci等级

    详见文档：[MEMBERSHIP_HYBRID_SYSTEM.md](./docs/MEMBERSHIP_HYBRID_SYSTEM.md)

    与Flutter端保持完全一致的等级计算逻辑
    """

    @staticmethod
    def get_fibonacci(n: int) -> int:
        """
        动态计算第n个Fibonacci数（从1开始）

        Args:
            n: 第n个Fibonacci数

        Returns:
            Fibonacci数值

        示例:
            F(1) = 1, F(2) = 1, F(3) = 2, F(4) = 3, F(5) = 5
        """
        if n <= 0:
            return 1
        if n == 1 or n == 2:
            return 1

        a, b = 1, 1
        for _ in range(3, n + 1):
            a, b = b, a + b
        return b

    @classmethod
    def get_level_from_hours(cls, total_hours: int) -> int:
        """
        根据总充值小时数计算等级（与Dart端逻辑一致）

        计算规则：
        - 累加Fibonacci数列直到超过总小时数
        - level = n，当 sum(F(1) to F(n)) <= total_hours < sum(F(1) to F(n+1))

        示例：
        - 0小时 → Level 0
        - 1小时 → Level 1 (F(1)=1, 累计1)
        - 2小时 → Level 2 (F(1)+F(2)=1+1=2)
        - 3-4小时 → Level 3 (1+1+2=4)
        - 5-7小时 → Level 4 (1+1+2+3=7)
        - 8-12小时 → Level 5 (1+1+2+3+5=12)

        Args:
            total_hours: 总充值小时数

        Returns:
            当前等级
        """
        if total_hours <= 0:
            return 0

        level = 0
        accumulated_hours = 0

        while True:
            next_hours = cls.get_fibonacci(level + 1)
            if accumulated_hours + next_hours > total_hours:
                break
            accumulated_hours += next_hours
            level += 1

        return level

    @classmethod
    def get_hours_for_level(cls, level: int) -> int:
        """
        获取达到指定等级所需的累计时长（小时）

        等级n需要 sum(F(1) to F(n)) 小时

        Args:
            level: 等级

        Returns:
            需要的小时数
        """
        if level < 1:
            return 0

        total_hours = 0
        for i in range(1, level + 1):
            total_hours += cls.get_fibonacci(i)
        return total_hours

    @classmethod
    def get_hours_to_next_level(cls, current_level: int, total_hours: int) -> int:
        """
        获取升级到下一等级所需的额外小时数

        Args:
            current_level: 当前等级
            total_hours: 当前总小时数

        Returns:
            距离下一等级还差多少小时
        """
        required_hours = cls.get_hours_for_level(current_level + 1)
        return max(0, required_hours - total_hours)

    @classmethod
    def get_level_progress(cls, total_hours: int) -> float:
        """
        计算当前等级的进度百分比（0.0-1.0）

        Args:
            total_hours: 当前总小时数

        Returns:
            进度百分比（0.0-1.0）
        """
        level = cls.get_level_from_hours(total_hours)
        previous_level_hours = cls.get_hours_for_level(level)
        next_level_hours = cls.get_hours_for_level(level + 1)

        if next_level_hours == previous_level_hours:
            return 1.0

        progress = (total_hours - previous_level_hours) / (next_level_hours - previous_level_hours)
        return max(0.0, min(1.0, progress))

    # 等级称号定义（与Dart端一致）
    LEVEL_TITLES = {
        0: "免费用户",
        range(1, 3): "体验会员",
        range(3, 5): "正式会员",
        range(5, 8): "高级会员",
        range(8, 13): "青铜会员",
        range(13, 21): "白银会员",
        range(21, 34): "黄金会员",
        range(34, 55): "铂金会员",
        range(55, 89): "钻石会员",
        range(89, 144): "至尊会员",
    }

    @classmethod
    def get_level_title(cls, level: int) -> str:
        """
        获取等级称号（与Dart端一致）

        Args:
            level: 等级

        Returns:
            等级称号
        """
        if level >= 144:
            return "传奇会员"

        for level_range, title in cls.LEVEL_TITLES.items():
            if isinstance(level_range, range) and level in level_range:
                return title
        return "免费用户"

    @classmethod
    def get_level_color(cls, level: int) -> str:
        """
        获取等级颜色（十六进制颜色代码，与Dart端一致）

        Args:
            level: 等级

        Returns:
            颜色代码
        """
        if level >= 144:
            return "#FFD700"  # 金色
        elif level >= 89:
            return "#9C27B0"  # 紫色
        elif level >= 55:
            return "#2196F3"  # 蓝色
        elif level >= 34:
            return "#607D8B"  # 铅蓝
        elif level >= 21:
            return "#FFC107"  # 琥珀
        elif level >= 13:
            return "#9E9E9E"  # 灰色
        elif level >= 8:
            return "#795548"  # 棕色
        elif level >= 5:
            return "#4CAF50"  # 绿色
        elif level >= 3:
            return "#03A9F4"  # 浅蓝
        elif level >= 1:
            return "#9E9E9E"  # 浅灰
        else:
            return "#BDBDBD"  # 深灰

    @classmethod
    def get_level_icon(cls, level: int) -> str:
        """
        获取等级图标名称（与Dart端Material Icons对应）

        Args:
            level: 等级

        Returns:
            图标名称
        """
        if level >= 144:
            return "military_tech"
        elif level >= 89:
            return "stars"
        elif level >= 55:
            return "diamond"
        elif level >= 34:
            return "workspace_premium"
        elif level >= 21:
            return "emoji_events"
        elif level >= 13:
            return "card_membership"
        elif level >= 8:
            return "verified"
        elif level >= 5:
            return "star"
        elif level >= 3:
            return "bookmark"
        elif level >= 1:
            return "person"
        else:
            return "person_outline"

    @classmethod
    def get_level_privileges(cls, level: int) -> list:
        """
        获取等级特权列表（与Dart端完全一致）

        Args:
            level: 等级

        Returns:
            特权列表
        """
        base_privileges = ["基础翻译功能"]

        if level >= 1:
            base_privileges.extend([
                "每日100字翻译额度",
                "标准客服支持",
            ])

        if level >= 3:
            base_privileges.extend([
                "每日500字翻译额度",
                "去除主界面广告",
            ])

        if level >= 5:
            base_privileges.extend([
                "每日2000字翻译额度",
                "优先客服支持",
                "多语言互译",
            ])

        if level >= 8:
            base_privileges.extend([
                "每日5000字翻译额度",
                "专属客服支持",
                "离线翻译功能",
            ])

        if level >= 13:
            base_privileges.extend([
                "每日10000字翻译额度",
                "API访问权限",
                "定制化主题",
            ])

        if level >= 21:
            base_privileges.extend([
                "每日20000字翻译额度",
                "优先功能体验",
                "批量翻译",
            ])

        if level >= 34:
            base_privileges.extend([
                "每日50000字翻译额度",
                "多账号管理",
                "团队协作功能",
            ])

        if level >= 55:
            base_privileges.extend([
                "每日100000字翻译额度",
                "专属客户经理",
                "企业级支持",
            ])

        if level >= 89:
            base_privileges.extend([
                "无限翻译额度",
                "7x24小时专属客服",
                "定制开发服务",
            ])

        if level >= 144:
            base_privileges.extend([
                "所有功能永久使用",
                "平台合作权益",
                "品牌联名机会",
            ])

        return base_privileges


# 创建全局实例
# Fibonacci动态等级计算服务（混合系统的一部分）
fibonacci_service = FibonacciMembershipSystem()


class MembershipService:
    model = "membership"
    """会员服务"""

    @staticmethod
    async def get_all_levels(active_only: bool = True) -> List[dict]:
        """获取所有会员等级"""
        query = MembershipLevel.all()
        if active_only:
            query = query.filter(is_active=True)
        # 按ID排序（regular=1, vip=2, svip=3）
        levels = await query.order_by("id")

        # 转换为字典，确保包含所有字段
        return [level.to_dict() for level in levels]

    @staticmethod
    async def get_level_by_id(level_id: int) -> Optional[MembershipLevel]:
        """根据ID获取会员等级"""
        return await MembershipLevel.get_or_none(id=level_id)

    @staticmethod
    async def create_level(level_data: dict) -> MembershipLevel:
        """创建会员等级"""
        return await MembershipLevel.create(**level_data)

    @staticmethod
    async def update_level(level_id: int, level_data: dict) -> Optional[MembershipLevel]:
        """更新会员等级"""
        level = await MembershipLevel.get_or_none(id=level_id)
        if not level:
            return None
        await level.update_from_dict(level_data)
        await level.save()
        return level

    @staticmethod
    async def delete_level(level_id: int) -> bool:
        """删除会员等级"""
        level = await MembershipLevel.get_or_none(id=level_id)
        if not level:
            return False
        await level.delete()
        return True

    @staticmethod
    async def get_customer_membership(customer_id: int) -> Optional[CustomerMembership]:
        """获取客户会员信息"""
        return await CustomerMembership.get_or_none(
            customer_id=customer_id,
            is_active=True
        ).prefetch_related("membership_level")

    @staticmethod
    async def calculate_used_hours_from_logs(customer_id: int) -> float:
        """
        从使用记录表中计算实际已用时长

        Args:
            customer_id: 客户ID

        Returns:
            已用时长（小时）
        """
        from base.plugins.llm.models.usage import LLMUsageRecord

        # 获取所有使用记录并汇总时长
        usage_logs = await LLMUsageRecord.filter(customer_id=customer_id)
        
        # 计算总时长（秒）
        total_seconds = 0
        for log in usage_logs:
            # 对于音频相关记录，使用audio_duration
            if log.audio_duration:
                total_seconds += log.audio_duration
            # 对于对话记录，使用start_time和end_time的差值
            elif log.start_time and log.end_time:
                duration = (log.end_time - log.start_time).total_seconds()
                total_seconds += duration
            # 如果都没有，使用tokens估算（作为备用方案）
            elif log.tokens:
                # 假设100 tokens ≈ 1秒（粗略估算）
                total_seconds += log.tokens / 100
        
        used_hours = total_seconds / 3600.0  # 转换为小时

        print(f"[MembershipService] 计算客户 {customer_id} 的已用时长: {len(usage_logs)} 条记录, 总计 {used_hours:.2f} 小时")
        return used_hours

    @staticmethod
    async def create_customer_membership(
        customer_id: int,
        membership_level_id: int,
        recharge_hours: int
    ) -> CustomerMembership:
        """
        创建或更新客户会员

        新的3级会员系统逻辑：
        - 普通会员: 注册即拥有，无限期，购买无折扣
        - VIP会员: 付费购买，有有效期，累加充值小时数，享受充值折扣
        - SVIP会员: 付费购买，有有效期，累加充值小时数，享受更高折扣

        Args:
            customer_id: 客户ID
            membership_level_id: 会员等级ID（regular/vip/svip）
            recharge_hours: 充值小时数（购买套餐时包含的小时数）

        Returns:
            CustomerMembership: 客户会员对象
        """
        from base.plugins.customer.models.membership import LevelType

        level = await MembershipService.get_level_by_id(membership_level_id)
        if not level:
            raise ValueError(f"会员等级ID {membership_level_id} 不存在")

        now = datetime.now()

        # 从使用记录中计算实际已用时长
        used_hours = await MembershipService.calculate_used_hours_from_logs(customer_id)

        # 检查客户是否已有会员记录
        existing_membership = await CustomerMembership.get_or_none(
            customer_id=customer_id
        ).prefetch_related("membership_level")

        if existing_membership:
            print(f"[MembershipService] 更新现有会员: customer_id={customer_id}")
            print(f"[MembershipService] 当前等级: {existing_membership.membership_level.level_type if existing_membership.membership_level else 'None'}")
            print(f"[MembershipService] 购买等级: {level.level_type}")

            # 累加充值小时数到total_hours
            new_total_hours = existing_membership.total_hours + recharge_hours

            # 重新计算剩余时长
            remaining_hours = new_total_hours - used_hours
            if remaining_hours < 0:
                remaining_hours = 0

            # 更新会员等级
            existing_membership.membership_level_id = membership_level_id

            # 计算新的过期时间
            if level.level_type == 'regular':
                # 普通会员：无限期
                existing_membership.expire_time = None
            else:
                # VIP/SVIP：有有效期
                # 如果当前会员未过期，则延长有效期；否则从现在开始计算
                if existing_membership.expire_time and not existing_membership.is_expired:
                    # 延长有效期
                    from datetime import timedelta
                    existing_membership.expire_time = existing_membership.expire_time + timedelta(days=level.duration_days)
                else:
                    # 重新计算有效期
                    from datetime import timedelta
                    existing_membership.start_time = now
                    existing_membership.expire_time = now + timedelta(days=level.duration_days)

            # 更新小时数
            existing_membership.total_hours = new_total_hours
            existing_membership.used_hours = used_hours
            existing_membership.remaining_hours = remaining_hours
            existing_membership.is_active = True

            # 更新 Fibonacci 动态等级
            existing_membership.update_fibonacci_level()

            await existing_membership.save()

            print(f"[MembershipService] ✅ 会员更新成功")
            print(f"[MembershipService]   会员类别: {level.name}")
            print(f"[MembershipService]   Fibonacci动态等级: Lv{existing_membership.level}")
            print(f"[MembershipService]   充值: +{recharge_hours}h")
            print(f"[MembershipService]   总充值: {new_total_hours}h")
            print(f"[MembershipService]   已用: {used_hours:.2f}h")
            print(f"[MembershipService]   剩余: {remaining_hours:.2f}h")
            print(f"[MembershipService]   过期时间: {existing_membership.expire_time}")

            return existing_membership
        else:
            # 创建新会员
            print(f"[MembershipService] 创建新会员: customer_id={customer_id}")

            # 计算过期时间
            if level.level_type == 'regular':
                # 普通会员：无限期
                expire_time = None
                start_time = None
            else:
                # VIP/SVIP：有有效期
                from datetime import timedelta
                start_time = now
                expire_time = now + timedelta(days=level.duration_days)

            # 计算剩余时长
            remaining_hours = recharge_hours - used_hours
            if remaining_hours < 0:
                remaining_hours = 0

            customer_membership = await CustomerMembership.create(
                customer_id=customer_id,
                membership_level_id=membership_level_id,
                start_time=start_time,
                expire_time=expire_time,
                total_hours=recharge_hours,
                level=0,  # 将在创建后计算
                used_hours=used_hours if used_hours > 0 else 0,
                remaining_hours=remaining_hours,
                is_active=True
            )

            # 计算 Fibonacci 动态等级
            customer_membership.update_fibonacci_level()
            await customer_membership.save()

            print(f"[MembershipService] ✅ 新会员创建成功")
            print(f"[MembershipService]   会员类别: {level.name}")
            print(f"[MembershipService]   Fibonacci动态等级: Lv{customer_membership.level}")
            print(f"[MembershipService]   充值: {recharge_hours}h")
            print(f"[MembershipService]   已用: {used_hours:.2f}h")
            print(f"[MembershipService]   剩余: {remaining_hours:.2f}h")
            print(f"[MembershipService]   过期时间: {expire_time}")

            return customer_membership

    @staticmethod
    async def initialize_regular_member(customer_id: int) -> CustomerMembership:
        """
        为新注册用户初始化普通会员

        普通会员特点：
        - 无限期（expire_time = None）
        - 无充值折扣（discount_percentage = 0）
        - 可以正常使用基础功能
        """
        # 查找或创建普通会员等级
        regular_level = await MembershipLevel.get_or_none(level_type='regular')
        if not regular_level:
            print(f"[MembershipService] ⚠️  普通会员等级不存在，创建默认等级...")
            regular_level = await MembershipLevel.create(
                level_type='regular',
                name='普通会员',
                description='注册即拥有的基础会员',
                duration_days=0,  # 0表示无限期
                price=0,
                discount_percentage=0,  # 无折扣
                features=['基础功能', '正常使用'],
                is_active=True
            )
            print(f"[MembershipService] ✅ 默认普通会员等级创建成功")

        # 检查是否已有会员记录
        existing = await CustomerMembership.get_or_none(customer_id=customer_id)
        if existing:
            print(f"[MembershipService] 客户 {customer_id} 已有会员记录，跳过初始化")
            return existing

        # 创建普通会员记录
        membership = await CustomerMembership.create(
            customer_id=customer_id,
            membership_level_id=regular_level.id,
            start_time=None,  # 普通会员无开始时间
            expire_time=None,  # 普通会员无过期时间
            total_hours=0,
            used_hours=0,
            remaining_hours=0,
            is_active=True
        )

        print(f"[MembershipService] ✅ 客户 {customer_id} 初始化为普通会员")
        return membership

    @staticmethod
    async def update_membership_usage(customer_id: int, used_hours: float) -> bool:
        """更新会员使用时长"""
        membership = await MembershipService.get_customer_membership(customer_id)
        if not membership or not membership.is_vip:
            return False

        new_remaining = float(membership.remaining_hours) - used_hours
        if new_remaining < 0:
            new_remaining = 0

        membership.used_hours = float(membership.used_hours) + used_hours
        membership.remaining_hours = new_remaining

        # 如果剩余时长为0，停用会员
        if new_remaining <= 0:
            membership.is_active = False

        await membership.save()
        return True

    @staticmethod
    async def check_membership_status(customer_id: int) -> dict:
        """
        检查会员状态（实时从使用记录计算）

        Returns:
            会员状态字典，包含从usage_logs实时计算的used_hours
        """
        membership = await MembershipService.get_customer_membership(customer_id)

        if not membership:
            return {
                "is_vip": False,
                "level": 0,
                "remaining_hours": 0,
                "is_expired": True
            }

        # 从使用记录中实时计算已用时长
        used_hours = await MembershipService.calculate_used_hours_from_logs(customer_id)
        remaining_hours = membership.total_hours - used_hours
        if remaining_hours < 0:
            remaining_hours = 0

        return {
            "is_vip": membership.is_vip,
            "level": membership.level,
            "remaining_hours": remaining_hours,
            "is_expired": membership.is_expired,
            "expire_time": membership.expire_time,
            "total_hours": membership.total_hours,
            "used_hours": used_hours
        }

    @staticmethod
    async def calculate_fibonacci_level(hours: int) -> dict:
        """
        计算Fibonacci等级完整信息

        Args:
            hours: 总充值小时数

        Returns:
            包含等级、称号、颜色、图标、特权、进度等信息
        """
        level = fibonacci_service.get_level_from_hours(hours)

        return {
            "level": level,
            "total_hours": hours,
            "title": fibonacci_service.get_level_title(level),
            "color": fibonacci_service.get_level_color(level),
            "icon": fibonacci_service.get_level_icon(level),
            "privileges": fibonacci_service.get_level_privileges(level),
            "progress": fibonacci_service.get_level_progress(hours),
            "hours_to_next_level": fibonacci_service.get_hours_to_next_level(level, hours),
            "next_level_title": fibonacci_service.get_level_title(level + 1),
        }

    @staticmethod
    def is_premium(level: int) -> bool:
        """判断是否为高级会员（等级5+）"""
        return level >= 5

    @staticmethod
    def is_vip(level: int) -> bool:
        """判断是否为VIP会员（等级13+）"""
        return level >= 13

    @staticmethod
    def is_supreme(level: int) -> bool:
        """判断是否为至尊会员（等级89+）"""
        return level >= 89
