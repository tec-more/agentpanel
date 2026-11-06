"""
客户管理API - 管理员功能
职责：客户CRUD、列表查询、状态管理、会员管理、使用记录、支付记录

注意：认证相关功能（注册、登录、修改密码等）已迁移到 auth.py
"""
from fastapi import APIRouter, Depends, status, Query, Path, Body
from typing import Optional

# 导入响应类
try:
    from base.common.response import SuccessResponse, ErrorResponse
except ImportError:
    # 定义临时响应类，以便在没有base模块的情况下也能工作
    class SuccessResponse:
        def __init__(self, data=None, msg="操作成功"):
            self.data = data
            self.msg = msg
            self.success = True

    class ErrorResponse:
        def __init__(self, msg="操作失败", status_code=400):
            self.msg = msg
            self.success = False
            self.status_code = status_code

# 导入安全相关模块
try:
    from base.common.security import get_current_user_id
except ImportError:
    # 定义临时依赖，以便在没有base模块的情况下也能工作
    from fastapi import HTTPException
    async def get_current_user_id():
        raise HTTPException(status_code=401, detail="未授权")

# 导入Pydantic模式和服务（稍后创建）
try:
    from base.plugins.customer.schemas.customer_schema import (
        CustomerResponse,
        CustomerCreate,
        CustomerUpdate,
        CustomerListQuery,
        CustomerListResponse,
    )
    from base.plugins.customer.services.customer_service import CustomerService
except ImportError:
    # 定义临时模式和服务，以便在没有实现的情况下也能工作
    from pydantic import BaseModel, EmailStr
    from typing import List, Dict, Any

    class CustomerBase(BaseModel):
        username: str
        email: EmailStr
        phone: Optional[str] = None

    class CustomerCreate(CustomerBase):
        password: str

    class CustomerUpdate(BaseModel):
        username: Optional[str] = None
        email: Optional[EmailStr] = None
        phone: Optional[str] = None
        password: Optional[str] = None

    class CustomerResponse(CustomerBase):
        id: int
        is_active: bool

        class Config:
            from_attributes = True

    class CustomerListQuery(BaseModel):
        page: int = 1
        page_size: int = 10
        username: Optional[str] = None
        email: Optional[str] = None
        phone: Optional[str] = None

    class CustomerListResponse(BaseModel):
        total: int
        page: int
        page_size: int
        items: List[CustomerResponse]

    class CustomerService:
        @staticmethod
        async def get_customer_info(customer_id):
            pass

        @staticmethod
        async def update_customer_info(customer_id, customer_data):
            pass

        @staticmethod
        async def get_customer_list(page, page_size, **filters):
            pass

        @staticmethod
        async def toggle_customer_status(customer_id):
            pass

        @staticmethod
        async def delete_customer(customer_id):
            pass

customer_router = APIRouter(
    prefix="",
    tags=["客户管理"]
)


@customer_router.get("/list", summary="获取客户列表(分页)")
async def get_customer_list(
        page: int = Query(1, ge=1, description="页码"),
        page_size: int = Query(10, ge=1, le=2000, description="每页数量"),
        username: Optional[str] = Query(None, description="用户名(模糊搜索)"),
        email: Optional[str] = Query(None, description="邮箱(模糊搜索)"),
        phone: Optional[str] = Query(None, description="手机号(模糊搜索)"),
        is_active: Optional[bool] = Query(None, description="是否激活")
        # 暂时注释掉认证依赖，用于调试
        # current_user_id: int = Depends(get_current_user_id)
):
    """
    获取客户列表(分页)

    Args:
        page: 页码
        page_size: 每页数量
        username: 用户名(模糊搜索)
        email: 邮箱(模糊搜索)
        phone: 手机号(模糊搜索)
        is_active: 是否激活

    Returns:
        客户列表
    """
    try:
        print(f"[GET /list] 收到请求: page={page}, page_size={page_size}, username={username}, email={email}, phone={phone}, is_active={is_active}")

        customers, total = await CustomerService.get_customer_list(
            page=page,
            page_size=page_size,
            username=username,
            email=email,
            phone=phone,
            is_active=is_active
        )

        print(f"[GET /list] 查询成功: 返回 {len(customers)} 条记录，总计 {total} 条")

        # 转换为字典列表
        customer_list = []
        for customer in customers:
            try:
                # 手动构建字典
                customer_dict = {
                    "id": customer.id,
                    "username": customer.username,
                    "nickname": getattr(customer, 'nickname', None),
                    "email": customer.email,
                    "phone": getattr(customer, 'phone', None),
                    "is_active": customer.is_active,
                    "is_verified": getattr(customer, 'is_verified', False),
                    "created_at": customer.created_at.strftime("%Y-%m-%d %H:%M:%S") if customer.created_at else None,
                    "updated_at": customer.updated_at.strftime("%Y-%m-%d %H:%M:%S") if customer.updated_at else None,
                    "last_login": customer.last_login.strftime("%Y-%m-%d %H:%M:%S") if getattr(customer, 'last_login', None) else None,
                    "login_count": getattr(customer, 'login_count', 0),
                }

                customer_list.append(customer_dict)
            except Exception as e:
                print(f"[GET /list] 处理客户数据出错: customer_id={getattr(customer, 'id', 'unknown')}, error={e}")
                import traceback
                traceback.print_exc()

        response_data = {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": customer_list
        }

        return SuccessResponse(data=response_data)
    except Exception as e:
        import traceback
        print(f"[GET /list] ERROR: {e}")
        print(f"[GET /list] TRACEBACK:")
        traceback.print_exc()
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)


# ============ 固定路径路由（必须放在参数化路由之前） ============

# 会员等级、使用记录、支付记录等固定路径路由
# 这些路由必须在参数化路由（/{customer_id}）之前定义，否则会被错误匹配

@customer_router.get("/membership-levels", summary="获取会员等级列表(别名路由)")
async def get_membership_levels_alias(
        active_only: bool = Query(True, description="只显示启用的等级"),
        page: Optional[int] = Query(None, ge=1, description="页码"),
        page_size: Optional[int] = Query(None, ge=1, le=200, description="每页数量")
):
    """获取会员等级列表 (兼容前端调用，支持分页参数但不使用)"""
    try:
        from base.plugins.customer.services.membership_service import MembershipService
        levels = await MembershipService.get_all_levels(active_only=active_only)

        # 现在levels已经是字典列表，直接使用
        return SuccessResponse(data={
            "items": levels,  # 直接使用字典列表
            "total": len(levels),
            "page": page or 1,
            "page_size": page_size or len(levels)
        })
    except Exception as e:
        import traceback
        print(f"[MembershipLevels] ERROR: {e}")
        traceback.print_exc()
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)


@customer_router.get("/usage", summary="获取使用记录列表(别名路由)")
async def get_usage_logs_alias(
        page: int = Query(1, ge=1, description="页码"),
        page_size: int = Query(10, ge=1, le=2000, description="每页数量"),
        customer_id: Optional[int] = Query(None, description="客户ID"),
        service_type: Optional[str] = Query(None, description="服务类型"),
        current_user_id: int = Depends(get_current_user_id)
):
    """获取使用记录列表 (兼容前端调用)"""
    try:
        print(f"[UsageLogs] 开始导入模型...")
        from base.plugins.llm.models.usage import LLMUsageRecord
        from base.plugins.customer.models.customer import Customer

        print(f"[UsageLogs] 模型导入成功")

        query = LLMUsageRecord.all()
        print(f"[UsageLogs] 构建基础查询")

        if customer_id:
            print(f"[UsageLogs] 按客户ID过滤: {customer_id}")
            query = query.filter(customer_id=customer_id)
        else:
            # 没有指定 customer_id，查询当前用户对应的客户
            # T4/M11 改造：identity_link（status=linked）优先，旧列 system_user_id 只读兜底
            print(f"[UsageLogs] 查询当前客户: user_id={current_user_id}")
            from base.plugins.customer.models.identity_link import IdentityLink
            linked_customer_id = None
            link = await IdentityLink.get_or_none(user_id=current_user_id, status="linked")
            if link:
                linked_customer_id = link.customer_id
                print(f"[UsageLogs] identity_link 命中: customer_id={linked_customer_id}")
            else:
                customer = await Customer.get_or_none(system_user_id=current_user_id)
                if customer:
                    linked_customer_id = customer.id
                    print(f"[UsageLogs] 旧列兜底命中: customer_id={linked_customer_id}")
            if linked_customer_id:
                print(f"[UsageLogs] 找到客户: {linked_customer_id}，只返回该客户的记录")
                query = query.filter(customer_id=linked_customer_id)
            else:
                # 当前用户不是客户，可能是管理员，返回所有记录
                print(f"[UsageLogs] 当前用户不是客户，返回所有使用记录")

        if service_type and service_type.strip():
            print(f"[UsageLogs] 按服务类型过滤: {service_type}")
            # 映射服务类型到记录类型
            service_type_map = {
                'text_generation': 'conversation',
                'translation': 'voice',
                'tts': 'tts',
                'voice_clone': 'voice_clone'
            }
            record_type = service_type_map.get(service_type, service_type)
            query = query.filter(record_type=record_type)

        total = await query.count()
        print(f"[UsageLogs] 总记录数: {total}")

        logs = await query.offset((page - 1) * page_size).limit(page_size).order_by("-created_at")
        print(f"[UsageLogs] 查询到 {len(logs)} 条记录")

        log_list = []
        for log in logs:
            # 构建适配的记录字典
            log_dict = {
                "id": log.id,
                "customer_id": log.customer_id,
                "session_id": log.record_id,
                "duration_seconds": log.tokens,  # 使用tokens作为使用量指标
                "service_type": log.record_type,
                "details": log.extra_info or {},
                "characters_count": len(log.input_text) + len(log.output_text) if log.input_text and log.output_text else 0,
                "api_cost": float(log.cost) if log.cost else 0,
                "created_at": log.created_at.strftime("%Y-%m-%d %H:%M:%S") if log.created_at else None,
                "updated_at": log.updated_at.strftime("%Y-%m-%d %H:%M:%S") if log.updated_at else None
            }
            log_list.append(log_dict)

        response_data = {"total": total, "page": page, "page_size": page_size, "items": log_list}
        print(f"[UsageLogs] 返回数据: {len(log_list)} 条记录\n")
        return SuccessResponse(data=response_data)
    except Exception as e:
        print(f"[ERROR] UsageLogs 异常: {e}")
        import traceback
        traceback.print_exc()
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)


@customer_router.post("/usage-logs/test", summary="创建测试使用记录（仅用于测试）")
async def create_test_usage_log(
    current_user_id: int = Depends(get_current_user_id)
):
    """创建测试使用记录（用于演示）"""
    try:
        from base.plugins.llm.models.usage import LLMUsageRecord
        from base.plugins.customer.models.customer import Customer
        import uuid

        print("\n[UsageLogs] 创建测试使用记录")

        # 获取第一个客户
        customer = await Customer.first()
        if not customer:
            return ErrorResponse(msg="没有客户数据，请先创建客户", status_code=status.HTTP_400_BAD_REQUEST)

        print(f"[UsageLogs] 使用客户: {customer.id}")

        # 创建测试记录
        test_logs = [
            {
                "record_id": f"test_{uuid.uuid4().hex[:16]}",
                "customer_id": customer.id,
                "model_id": 1,
                "record_type": "conversation",
                "status": "completed",
                "tokens": 500,
                "cost": 0.0150,
                "input_text": "测试输入文本",
                "output_text": "测试输出文本",
                "extra_info": {
                    "model": "claude-3-opus",
                    "prompt_tokens": 100,
                    "completion_tokens": 400,
                    "total_tokens": 500
                }
            },
            {
                "record_id": f"test_{uuid.uuid4().hex[:16]}",
                "customer_id": customer.id,
                "model_id": 1,
                "record_type": "voice",
                "status": "completed",
                "tokens": 300,
                "cost": 0.0090,
                "input_text": "测试语音输入",
                "output_text": "测试语音输出",
                "extra_info": {
                    "model": "whisper-1",
                    "audio_duration": 10,
                    "language": "zh"
                }
            }
        ]

        # 批量创建记录
        created_logs = []
        for log_data in test_logs:
            log = await LLMUsageRecord.create(**log_data)
            created_logs.append(log)

        print(f"[UsageLogs] 创建了 {len(created_logs)} 条测试记录")
        return SuccessResponse(msg="测试使用记录创建成功")
    except Exception as e:
        print(f"[ERROR] 创建测试使用记录失败: {e}")
        import traceback
        traceback.print_exc()
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)


@customer_router.get("/usage-logs", summary="获取所有使用记录列表(管理员)")
async def get_all_usage_logs(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=2000, description="每页数量"),
    customer_id: Optional[int] = Query(None, description="客户ID"),
    service_type: Optional[str] = Query(None, description="服务类型"),
    current_user_id: int = Depends(get_current_user_id)
):
    """获取所有使用记录列表 (管理员功能)"""
    print("\n[UsageLogs] 获取使用记录列表")
    print(f"[UsageLogs] page={page}, page_size={page_size}")
    print(f"[UsageLogs] customer_id={customer_id}")
    print(f"[UsageLogs] service_type={service_type}")
    print(f"[UsageLogs] current_user_id={current_user_id}")

    try:
        result = await get_usage_logs_alias(
            page=page, page_size=page_size, customer_id=customer_id,
            service_type=service_type, current_user_id=current_user_id
        )
        print(f"[UsageLogs] 查询成功\n")
        return result
    except Exception as e:
        print(f"[ERROR] UsageLogs 查询失败: {e}")
        import traceback
        traceback.print_exc()
        raise


@customer_router.post("/membership-levels", summary="创建会员等级(别名路由)")
async def create_membership_level_alias(
    request_data: dict = Body(...),
    current_user_id: int = Depends(get_current_user_id)
):
    """创建会员等级 - 别名路由"""
    try:
        print(f"[POST membership-levels] 收到创建请求: data={request_data}")
        from base.plugins.customer.services.membership_service import MembershipService
        level = await MembershipService.create_level(request_data)
        print(f"[POST membership-levels] 创建成功: {level}")

        # 手动构建返回数据
        from decimal import Decimal
        level_dict = {
            "id": level.id,
            "level_type": level.level_type,
            "name": level.name,
            "description": level.description,
            "duration_days": level.duration_days,
            "price": float(level.price) if isinstance(level.price, Decimal) else level.price,
            "discount_percentage": level.discount_percentage if hasattr(level, 'discount_percentage') else 0,
            "features": level.features if level.features else [],
            "is_active": level.is_active,
            "created_at": level.created_at.strftime("%Y-%m-%d %H:%M:%S") if level.created_at else None,
            "updated_at": level.updated_at.strftime("%Y-%m-%d %H:%M:%S") if level.updated_at else None,
        }
        return SuccessResponse(data=level_dict, msg="会员等级创建成功")
    except Exception as e:
        print(f"[POST membership-levels] ERROR: {e}")
        import traceback
        traceback.print_exc()
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)


@customer_router.put("/membership-levels/{level_id}", summary="更新会员等级(别名路由)")
async def update_membership_level_alias(
    level_id: int,
    request_data: dict = Body(...),
    current_user_id: int = Depends(get_current_user_id)
):
    """更新会员等级 - 别名路由"""
    try:
        print(f"[PUT membership-levels] 收到更新请求: level_id={level_id}, data={request_data}")
        from base.plugins.customer.services.membership_service import MembershipService
        level = await MembershipService.update_level(level_id, request_data)
        print(f"[PUT membership-levels] 更新成功: {level}")

        if not level:
            return ErrorResponse(msg="会员等级不存在", status_code=status.HTTP_404_NOT_FOUND)

        # 手动构建返回数据，避免 to_dict() 的问题
        from decimal import Decimal
        level_dict = {
            "id": level.id,
            "level_type": level.level_type,
            "name": level.name,
            "description": level.description,
            "duration_days": level.duration_days,
            "price": float(level.price) if isinstance(level.price, Decimal) else level.price,
            "discount_percentage": level.discount_percentage if hasattr(level, 'discount_percentage') else 0,
            "features": level.features if level.features else [],
            "is_active": level.is_active,
            "created_at": level.created_at.strftime("%Y-%m-%d %H:%M:%S") if level.created_at else None,
            "updated_at": level.updated_at.strftime("%Y-%m-%d %H:%M:%S") if level.updated_at else None,
        }
        print(f"[PUT membership-levels] 返回数据: {level_dict}")
        return SuccessResponse(data=level_dict, msg="会员等级更新成功")
    except Exception as e:
        print(f"[PUT membership-levels] ERROR: {e}")
        import traceback
        traceback.print_exc()
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)


@customer_router.delete("/membership-levels/{level_id}", summary="删除会员等级(别名路由)")
async def delete_membership_level_alias(
    level_id: int,
    current_user_id: int = Depends(get_current_user_id)
):
    """删除会员等级 - 别名路由"""
    try:
        from base.plugins.customer.services.membership_service import MembershipService
        success = await MembershipService.delete_level(level_id)
        if not success:
            return ErrorResponse(msg="会员等级不存在", status_code=status.HTTP_404_NOT_FOUND)
        return SuccessResponse(msg="会员等级删除成功")
    except Exception as e:
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)


@customer_router.patch("/membership-levels/{level_id}", summary="切换会员等级状态(别名路由)")
async def toggle_membership_level_status_alias(
    level_id: int,
    request_data: dict = Body(None),
    current_user_id: int = Depends(get_current_user_id)
):
    """切换会员等级状态 - 别名路由"""
    try:
        print(f"[PATCH membership-levels] 收到切换状态请求: level_id={level_id}, data={request_data}")
        from base.plugins.customer.services.membership_service import MembershipService
        if request_data is None:
            request_data = {}
        is_active = request_data.get("is_active", True)
        level = await MembershipService.update_level(level_id, {"is_active": is_active})
        print(f"[PATCH membership-levels] 更新成功: {level}")

        if not level:
            return ErrorResponse(msg="会员等级不存在", status_code=status.HTTP_404_NOT_FOUND)

        # 手动构建返回数据
        from decimal import Decimal
        level_dict = {
            "id": level.id,
            "level_type": level.level_type,
            "name": level.name,
            "description": level.description,
            "duration_days": level.duration_days,
            "price": float(level.price) if isinstance(level.price, Decimal) else level.price,
            "discount_percentage": level.discount_percentage if hasattr(level, 'discount_percentage') else 0,
            "features": level.features if level.features else [],
            "is_active": level.is_active,
            "created_at": level.created_at.strftime("%Y-%m-%d %H:%M:%S") if level.created_at else None,
            "updated_at": level.updated_at.strftime("%Y-%m-%d %H:%M:%S") if level.updated_at else None,
        }
        status_text = "启用" if is_active else "禁用"
        return SuccessResponse(data=level_dict, msg=f"会员等级已{status_text}")
    except Exception as e:
        print(f"[PATCH membership-levels] ERROR: {e}")
        import traceback
        traceback.print_exc()
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)


@customer_router.get("/payment-transactions", summary="获取支付交易记录列表(别名路由)")
async def get_payment_transactions_alias(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=2000, description="每页数量"),
    trade_no: Optional[str] = Query(None, description="交易号(模糊搜索)"),
    payment_method: Optional[str] = Query(None, description="支付方式(wechat/alipay)"),
    payment_status: Optional[str] = Query(None, description="交易状态"),
    current_user_id: int = Depends(get_current_user_id)
):
    """获取支付交易记录列表 (兼容前端调用)"""
    try:
        print("\n[PaymentTransactions] 开始查询支付交易记录")
        print(f"[PaymentTransactions] page={page}, page_size={page_size}")
        print(f"[PaymentTransactions] trade_no={repr(trade_no)}")
        print(f"[PaymentTransactions] payment_method={repr(payment_method)}")
        print(f"[PaymentTransactions] payment_status={repr(payment_status)}")

        from base.plugins.customer.models.payment_transaction import PaymentTransaction
        from base.plugins.sales.models import CustomerOrder

        query = PaymentTransaction.all()
        print(f"[PaymentTransactions] 初始查询构建完成")

        # 处理空字符串
        if trade_no and trade_no.strip():
            print(f"[PaymentTransactions] 按交易号模糊搜索: {trade_no}")
            orders = await CustomerOrder.filter(order_no__icontains=trade_no).values_list('id', flat=True)
            print(f"[PaymentTransactions] 找到 {len(orders)} 个订单")
            if orders:
                query = query.filter(order_id__in=orders)
            else:
                query = query.filter(order_id=-1)

        if payment_method and payment_method.strip():
            print(f"[PaymentTransactions] 按支付方式过滤: {payment_method}")
            query = query.filter(transaction_type=payment_method)

        if payment_status and payment_status.strip():
            print(f"[PaymentTransactions] 按状态过滤: {payment_status}")
            query = query.filter(status=payment_status)

        total = await query.count()
        print(f"[PaymentTransactions] 总记录数: {total}")

        transactions = await query.offset((page - 1) * page_size).limit(page_size).order_by("-processed_at")
        print(f"[PaymentTransactions] 查询到 {len(transactions)} 条记录")

        transaction_list = []
        for transaction in transactions:
            if hasattr(transaction, 'to_dict'):
                trans_dict = await transaction.to_dict()
            elif hasattr(transaction, 'dict'):
                trans_dict = transaction.dict()
            else:
                trans_dict = dict(transaction)

            # 转换 Decimal 为 float（JSON 序列化）
            if 'amount' in trans_dict and trans_dict['amount'] is not None:
                trans_dict['amount'] = float(trans_dict['amount'])

            # 添加订单号（更清晰的字段名）
            if 'transaction_id' in trans_dict:
                trans_dict['qixiang_trade_no'] = trans_dict['transaction_id']

            # 转换支付方式为中文显示
            payment_type_map = {
                'wxpay': '微信支付',
                'wechat': '微信支付',
                'alipay': '支付宝',
                'qixiang_wxpay': '七相-微信',
                'qixiang_alipay': '七相-支付宝',
            }
            trans_type = trans_dict.get('transaction_type', '')
            trans_dict['payment_method_display'] = payment_type_map.get(trans_type, trans_type)

            # 添加支付方式标签和颜色（用于前端显示）
            if trans_type in ['wxpay', 'wechat', 'qixiang_wxpay']:
                trans_dict['payment_method_tag'] = 'success'
                trans_dict['payment_method_icon'] = 'wechat'
            elif trans_type in ['alipay', 'qixiang_alipay']:
                trans_dict['payment_method_tag'] = 'primary'
                trans_dict['payment_method_icon'] = 'alipay'
            else:
                trans_dict['payment_method_tag'] = 'info'
                trans_dict['payment_method_icon'] = 'default'

            # notify_data 中的 Decimal 也要转换
            if 'notify_data' in trans_dict and trans_dict['notify_data']:
                try:
                    # 递归转换 notify_data 中的 Decimal
                    notify_data_str = str(trans_dict['notify_data'])
                    trans_dict['notify_data'] = notify_data_str
                except:
                    pass

            if hasattr(transaction, 'order_id') and transaction.order_id:
                order = await CustomerOrder.get_or_none(id=transaction.order_id)
                if order:
                    trans_dict['order_no'] = order.order_no
                    if hasattr(order, 'customer_id'):
                        trans_dict['customer_id'] = order.customer_id
            transaction_list.append(trans_dict)

        response_data = {"total": total, "page": page, "page_size": page_size, "items": transaction_list}
        print(f"[PaymentTransactions] 查询成功，返回 {len(transaction_list)} 条记录\n")
        return SuccessResponse(data=response_data)
    except Exception as e:
        print(f"\n[ERROR] PaymentTransactions 查询失败: {e}")
        import traceback
        traceback.print_exc()
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)


# ============ 参数化路由（必须放在最后） ============

@customer_router.get("/{customer_id}", summary="获取客户详情")
async def get_customer_detail(
        customer_id: int = Path(..., gt=0, description="客户ID"),
        current_user_id: int = Depends(get_current_user_id)
):
    """
    获取客户详情

    Args:
        customer_id: 客户ID
        current_user_id: 当前客户ID

    Returns:
        客户详细信息
    """
    try:
        customer = await CustomerService.get_customer_info(customer_id)
        if not customer:
            return ErrorResponse(msg="用户不存在", status_code=status.HTTP_404_NOT_FOUND)
        # 使用to_dict方法确保datetime字段被正确转换
        if hasattr(customer, 'to_dict'):
            customer_dict = await customer.to_dict()
        elif hasattr(customer, 'dict'):
            customer_dict = customer.dict()
        else:
            customer_dict = dict(customer)
        return SuccessResponse(data=customer_dict)
    except Exception as e:
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)


@customer_router.put("/{customer_id}", summary="更新客户信息")
async def update_customer(
        customer_id: int = Path(..., gt=0, description="客户ID"),
        customer_data: CustomerUpdate = None,
        current_user_id: int = Depends(get_current_user_id)
):
    """
    更新客户信息(管理员功能)

    Args:
        customer_id: 客户ID
        customer_data: 更新数据
        current_user_id: 当前客户ID

    Returns:
        更新后的客户信息
    """
    try:
        updated_customer = await CustomerService.update_customer_info(customer_id, customer_data)
        if not updated_customer:
            return ErrorResponse(msg="用户不存在", status_code=status.HTTP_404_NOT_FOUND)
        # 使用to_dict方法确保datetime字段被正确转换
        if hasattr(updated_customer, 'to_dict'):
            customer_dict = await updated_customer.to_dict()
        elif hasattr(updated_customer, 'dict'):
            customer_dict = updated_customer.dict()
        else:
            customer_dict = dict(updated_customer)
        return SuccessResponse(data=customer_dict, msg="更新成功")
    except Exception as e:
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)


@customer_router.post("/", summary="创建客户")
async def create_customer(
        customer_data: CustomerCreate,
        current_user_id: int = Depends(get_current_user_id)
):
    """
    创建客户(管理员功能)
    
    Args:
        customer_data: 客户创建数据
        current_user_id: 当前用户ID
        
    Returns:
        创建的客户信息
    """
    try:
        customer = await CustomerService.register_customer(customer_data)
        if not customer:
            return ErrorResponse(msg="创建失败", status_code=status.HTTP_400_BAD_REQUEST)
        # 使用to_dict方法确保datetime字段被正确转换
        if hasattr(customer, 'to_dict'):
            customer_dict = await customer.to_dict()
        elif hasattr(customer, 'dict'):
            customer_dict = customer.dict()
        else:
            customer_dict = dict(customer)
        return SuccessResponse(data=customer_dict, msg="创建成功")
    except Exception as e:
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)


@customer_router.delete("/{customer_id}", summary="删除客户")
async def delete_customer(
        customer_id: int = Path(..., gt=0, description="客户ID"),
        current_user_id: int = Depends(get_current_user_id)
):
    """
    删除客户(管理员功能)

    Args:
        customer_id: 客户ID
        current_user_id: 当前客户ID

    Returns:
        删除结果
    """
    try:
        success = await CustomerService.delete_customer(customer_id)
        if not success:
            return ErrorResponse(msg="用户不存在", status_code=status.HTTP_404_NOT_FOUND)
        return SuccessResponse(msg="删除成功")
    except Exception as e:
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)


@customer_router.delete("/batch", summary="批量删除客户")
async def batch_delete_customer(
        request: dict,
        current_user_id: int = Depends(get_current_user_id)
):
    """
    批量删除客户(管理员功能)
    
    Args:
        request: 包含ids数组的请求体
        current_user_id: 当前用户ID
        
    Returns:
        删除结果
    """
    try:
        ids = request.get("ids", [])
        if not ids:
            return ErrorResponse(msg="请选择要删除的客户", status_code=status.HTTP_400_BAD_REQUEST)
        for customer_id in ids:
            await CustomerService.delete_customer(customer_id)
        return SuccessResponse(msg="批量删除成功")
    except Exception as e:
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)


@customer_router.patch("/{customer_id}/toggle-status", summary="切换客户状态")
async def toggle_customer_status(
        customer_id: int = Path(..., gt=0, description="客户ID"),
        current_user_id: int = Depends(get_current_user_id)
):
    """
    切换客户激活状态(管理员功能)

    Args:
        customer_id: 客户ID
        current_user_id: 当前客户ID

    Returns:
        更新后的客户信息
    """
    try:
        updated_customer = await CustomerService.toggle_customer_status(customer_id)
        if not updated_customer:
            return ErrorResponse(msg="用户不存在", status_code=status.HTTP_404_NOT_FOUND)
        # 使用to_dict方法确保datetime字段被正确转换
        if hasattr(updated_customer, 'to_dict'):
            customer_dict = await updated_customer.to_dict()
        elif hasattr(updated_customer, 'dict'):
            customer_dict = updated_customer.dict()
        else:
            customer_dict = dict(updated_customer)
        status_text = "激活" if updated_customer.is_active else "禁用" if hasattr(updated_customer, 'is_active') else "未知"
        return SuccessResponse(data=customer_dict, msg=f"用户已{status_text}")
    except Exception as e:
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)


@customer_router.patch("/{customer_id}/status", summary="切换客户状态(别名路由)")
async def toggle_customer_status_alias(
        customer_id: int = Path(..., gt=0, description="客户ID"),
        current_user_id: int = Depends(get_current_user_id)
):
    """切换客户激活状态 - 别名路由，兼容前端调用"""
    return await toggle_customer_status(customer_id, current_user_id)


@customer_router.patch("/{customer_id}/points", summary="更新客户积分")
async def update_customer_points(
        customer_id: int = Path(..., gt=0, description="客户ID"),
        request: dict = None,
        current_user_id: int = Depends(get_current_user_id)
):
    """
    更新客户积分(管理员功能)
    
    Args:
        customer_id: 客户ID
        request: 包含points字段的请求体
        current_user_id: 当前用户ID
        
    Returns:
        更新后的客户信息
    """
    try:
        points = request.get("points", 0)
        customer = await CustomerService.update_customer_points(customer_id, points)
        if not customer:
            return ErrorResponse(msg="用户不存在", status_code=status.HTTP_404_NOT_FOUND)
        # 使用to_dict方法确保datetime字段被正确转换
        if hasattr(customer, 'to_dict'):
            customer_dict = await customer.to_dict()
        elif hasattr(customer, 'dict'):
            customer_dict = customer.dict()
        else:
            customer_dict = dict(customer)
        return SuccessResponse(data=customer_dict, msg="积分更新成功")
    except Exception as e:
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)


@customer_router.patch("/{customer_id}/membership", summary="更新客户会员到期日期")
async def update_customer_membership(
        customer_id: int = Path(..., gt=0, description="客户ID"),
        request: dict = None,
        current_user_id: int = Depends(get_current_user_id)
):
    """
    更新客户会员到期日期(管理员功能)

    Args:
        customer_id: 客户ID
        request: 包含membership_expire字段的请求体
        current_user_id: 当前用户ID

    Returns:
        更新后的客户信息
    """
    try:
        membership_expire = request.get("membership_expire")
        customer = await CustomerService.update_customer_membership(customer_id, membership_expire)
        if not customer:
            return ErrorResponse(msg="用户不存在", status_code=status.HTTP_404_NOT_FOUND)
        # 使用to_dict方法确保datetime字段被正确转换
        if hasattr(customer, 'to_dict'):
            customer_dict = await customer.to_dict()
        elif hasattr(customer, 'dict'):
            customer_dict = customer.dict()
        else:
            customer_dict = dict(customer)
        return SuccessResponse(data=customer_dict, msg="会员到期日期更新成功")
    except Exception as e:
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)


@customer_router.post("/{customer_id}/fix-vip", summary="修复用户VIP状态（临时）")
async def fix_user_vip_status(
    customer_id: int = Path(..., description="客户ID")
):
    """
    手动修复用户的VIP状态（临时端点，用于测试）

    将用户的会员等级升级为VIP，并设置过期时间

    Args:
        customer_id: 客户ID

    Returns:
        修复结果
    """
    from base.plugins.customer.models.customer_membership import CustomerMembership
    from base.plugins.customer.models.membership import MembershipLevel
    from datetime import datetime, timedelta, timezone

    try:
        # 查询用户会员信息
        membership = await CustomerMembership.get_or_none(
            customer_id=customer_id
        ).prefetch_related("membership_level")

        if not membership:
            return ErrorResponse(msg=f"用户{customer_id}没有会员记录", status_code=404)

        # 获取VIP会员等级
        vip_level = await MembershipLevel.filter(
            level_type="vip"
        ).first()

        if not vip_level:
            return ErrorResponse(msg="VIP会员等级不存在", status_code=400)

        # 修复前状态
        old_level_type = membership.membership_level.level_type if membership.membership_level else "None"
        old_is_vip = membership.is_vip

        # 更新会员等级为VIP
        membership.membership_level_id = vip_level.id

        # 设置过期时间（VIP有30天有效期）
        now = datetime.now(timezone.utc)
        membership.start_time = now
        membership.expire_time = now + timedelta(days=vip_level.duration_days)

        await membership.save()

        # 重新查询验证
        await membership.fetch_related("membership_level")
        new_level_type = membership.membership_level.level_type
        new_is_vip = membership.is_vip

        return SuccessResponse(data={
            "customer_id": customer_id,
            "fix_applied": True,
            "before": {
                "level_type": old_level_type,
                "is_vip": old_is_vip
            },
            "after": {
                "level_type": new_level_type,
                "is_vip": new_is_vip,
                "membership_level_id": membership.membership_level_id,
                "expire_time": membership.expire_time.isoformat() if membership.expire_time else None
            }
        }, msg="VIP状态修复成功")

    except Exception as e:
        import traceback
        traceback.print_exc()
        return ErrorResponse(msg=f"修复失败: {str(e)}", status_code=500)
