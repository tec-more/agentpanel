from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class Customer(BaseModel, TimestampMixin):
    verbose_name = "客户"
    """Customer model"""

    # 系统关联
    # T1：本列语义已废弃（Q-C），身份关联迁移至 identity_link 表；保留列只读，禁止新代码写入
    system_user_id = fields.BigIntField(unique=True, null=True, description="关联的系统用户ID（已废弃只读，见 identity_link）")

    # 基本信息
    openid = fields.CharField(max_length=100, unique=True, description="OpenID for WeChat", null=True)
    unionid = fields.CharField(max_length=100, unique=True, description="UnionID for WeChat", null=True)
    phone = fields.CharField(max_length=20, unique=True, description="Phone number", null=True)
    email = fields.CharField(max_length=100, unique=True, description="Email", null=True)
    nickname = fields.CharField(max_length=100, description="Nickname", null=True)
    avatar = fields.CharField(max_length=500, description="Avatar URL", null=True)

    # 认证信息
    username = fields.CharField(max_length=50, unique=True, null=True, description="用户名")
    password = fields.CharField(max_length=128, null=True, description="密码(加密)")

    # 状态
    is_active = fields.BooleanField(default=True, description="是否激活")
    is_verified = fields.BooleanField(default=False, description="是否已验证")

    # 统计信息
    last_login = fields.DatetimeField(null=True, description="最后登录时间")
    login_count = fields.IntField(default=0, description="登录次数")

    class Meta:
        table = "customer"
        table_description = "Customer table"

    def __str__(self):
        return self.nickname or self.username or self.phone or self.email or str(self.id)

    async def to_dict(self):
        """
        转换为字典（包含会员信息）

        混合系统设计：
        1. 会员类别（MembershipLevel）：regular/vip/svip - 决定折扣和特权
        2. Fibonacci动态等级：基于累计充值总小时数计算 - 用于显示等级称号

        会员数据计算规则：
        - total_hours: 累计充值总时长（从会员表）
        - level: 基于total_hours的Fibonacci动态等级
        - membership_level_type: 会员类别（regular/vip/svip）
        - used_hours: 从usage_logs表实时汇总计算
        - remaining_hours: total_hours - used_hours
        """
        # 预加载会员信息
        from base.plugins.customer.models.customer_membership import CustomerMembership
        from base.plugins.llm.models.usage import LLMUsageRecord

        print(f"\n{'='*70}")
        print(f"[Customer.to_dict] 🔔 开始转换客户信息")
        print(f"[Customer.to_dict] 客户ID: {self.id}")
        print(f"[Customer.to_dict] 客户名称: {self.nickname or self.username or self.phone or self.email}")
        print(f"{'='*70}\n")

        # 获取会员信息（不限制激活状态，优先返回激活的）
        # 先尝试获取激活的会员记录
        membership = await CustomerMembership.filter(
            customer_id=self.id,
            is_active=True
        ).prefetch_related("membership_level").first()

        # 如果没有激活的会员记录，获取任意会员记录
        if not membership:
            membership = await CustomerMembership.filter(
                customer_id=self.id
            ).prefetch_related("membership_level").first()

        print(f"[Customer.to_dict] 📊 会员记录查询:")
        if membership:
            print(f"[Customer.to_dict]   ✅ 找到激活的会员记录")
            print(f"[Customer.to_dict]   会员ID: {membership.id}")
            print(f"[Customer.to_dict]   充值总时长: {membership.total_hours} 小时")
            print(f"[Customer.to_dict]   Fibonacci动态等级: Lv{membership.level}")
            membership_level_type = membership.membership_level.level_type if membership.membership_level else "unknown"
            print(f"[Customer.to_dict]   会员类别: {membership_level_type}")
            print(f"[Customer.to_dict]   激活状态: {'是' if membership.is_active else '否'}")
            print(f"[Customer.to_dict]   过期状态: {'是' if membership.is_expired else '否'}")
        else:
            print(f"[Customer.to_dict]   ⚠️  未找到激活的会员记录")
        print()

        # 从使用记录中实时计算已用时长
        from base.plugins.llm.models.usage import LLMUsageRecord
        usage_logs = await LLMUsageRecord.filter(customer_id=self.id)
        
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

        print(f"[Customer.to_dict] 📊 使用记录汇总:")
        print(f"[Customer.to_dict]   记录数量: {len(usage_logs)} 条")
        print(f"[Customer.to_dict]   总时长: {total_seconds} 秒")
        print(f"[Customer.to_dict]   已用时长: {used_hours:.2f} 小时")

        if usage_logs:
            print(f"[Customer.to_dict]   最近3条记录:")
            for log in usage_logs[:3]:
                duration_str = ""
                if log.audio_duration:
                    duration_str = f"{log.audio_duration}秒"
                elif log.start_time and log.end_time:
                    duration = (log.end_time - log.start_time).total_seconds()
                    duration_str = f"{duration:.1f}秒"
                else:
                    duration_str = f"{log.tokens} tokens"
                print(f"[Customer.to_dict]     - {log.created_at.strftime('%Y-%m-%d %H:%M:%S')}: {log.record_type}, {duration_str}, ${float(log.cost):.4f}")
        print()

        # 构建基础数据
        data = {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "phone": self.phone,
            "nickname": self.nickname,
            "avatar": self.avatar,
            "is_active": self.is_active,
            "is_verified": self.is_verified,
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "login_count": self.login_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            # 会员信息
            "membership": None,
            "level": 0,                  # Fibonacci动态等级
            "remaining_hours": 0,
            "is_vip": False,
            "is_svip": False,
            "membership_level": "regular",  # 会员类别
        }

        # 如果有会员信息，添加到数据中
        if membership:
            try:
                # 重新计算剩余时长 = 总时长 - 已用时长（从日志汇总）
                total_hours = membership.total_hours
                remaining_hours = total_hours - used_hours
                if remaining_hours < 0:
                    remaining_hours = 0

                print(f"[Customer.to_dict] 🧮 会员数据计算:")
                print(f"[Customer.to_dict]   充值总时长: {total_hours} 小时")
                print(f"[Customer.to_dict]   Fibonacci动态等级: Lv{membership.level}")
                print(f"[Customer.to_dict]   已用时长: {used_hours:.2f} 小时")
                print(f"[Customer.to_dict]   剩余时长: {remaining_hours:.2f} 小时")
                print()

                # 获取会员类别信息
                membership_level_type = membership.membership_level.level_type if membership.membership_level else "regular"
                is_vip = membership.is_vip and not membership.is_expired
                is_svip = membership.is_svip and not membership.is_expired

                data["membership"] = {
                    "id": membership.id,
                    "level": membership.level,  # Fibonacci动态等级
                    "total_hours": membership.total_hours or 0,
                    "used_hours": used_hours or 0,
                    "remaining_hours": remaining_hours or 0,
                    "is_active": membership.is_active,
                    "is_expired": membership.is_expired,
                    "is_vip": is_vip,
                    "is_svip": is_svip,
                    "start_time": membership.start_time.isoformat() if membership.start_time else None,
                    "expire_time": membership.expire_time.isoformat() if membership.expire_time else None,
                    "membership_level": membership_level_type,  # 会员类别
                    "level_name": membership.membership_level.name if membership.membership_level else None,
                    "level_description": membership.membership_level.description if membership.membership_level else None,
                }
                data["level"] = membership.level  # Fibonacci动态等级
                data["remaining_hours"] = remaining_hours
                data["is_vip"] = is_vip
                data["is_svip"] = is_svip
                data["membership_level"] = membership_level_type  # 会员类别

                print(f"[Customer.to_dict] ✅ 会员信息已添加到返回数据:")
                print(f"[Customer.to_dict]   Fibonacci动态等级: Lv{data['level']}")
                print(f"[Customer.to_dict]   会员类别: {data['membership_level']}")
                print(f"[Customer.to_dict]   total_hours: {data['membership']['total_hours']}h")
                print(f"[Customer.to_dict]   used_hours: {data['membership']['used_hours']:.2f}h")
                print(f"[Customer.to_dict]   remaining_hours: {data['remaining_hours']:.2f}h")
                print(f"[Customer.to_dict]   is_vip: {data['is_vip']}")
                print(f"[Customer.to_dict]   is_svip: {data['is_svip']}")
                print()

            except Exception as e:
                print(f"[Customer.to_dict] ❌ ERROR: 添加会员信息失败: {e}")
                import traceback
                traceback.print_exc()

        else:
            print(f"[Customer.to_dict] ⚠️  无会员信息，返回默认值:")
            print(f"[Customer.to_dict]   Fibonacci动态等级: Lv0")
            print(f"[Customer.to_dict]   会员类别: regular")
            print(f"[Customer.to_dict]   remaining_hours: 0.00h")
            print(f"[Customer.to_dict]   is_vip: False")
            print(f"[Customer.to_dict]   is_svip: False")
            print()

        print(f"[Customer.to_dict] ✅ 转换完成")
        print(f"{'='*70}\n")

        return data
