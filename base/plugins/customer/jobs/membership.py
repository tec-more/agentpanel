"""客户插件作业：会员数据更新（单轮，W2-3）。

由 ``manifest.jobs`` 声明并带 ``requires_plugins: ["llm"]``，实现原启动期
「customer 且 llm 同时启用才启动」的 AND 门控。任务体自
``base/start.py::update_membership_data_task`` 机械平移（含全部 print 文案），
仅剥离 while 循环 / sleep / 取消与异常处理外壳（由平台调度器统一承担）。
"""
from __future__ import annotations


async def run() -> None:
    """重新计算已用时长、剩余时长、过期状态，停用剩余时长为 0 的会员。"""

    from base.plugins.customer.models.customer_membership import CustomerMembership
    from base.plugins.llm.models.usage import LLMUsageRecord
    from datetime import datetime

    print("\n" + "="*70)
    print(f"[定时任务] 🔔 开始更新会员数据 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)

    # 获取所有激活的会员（预加载membership_level关联）
    memberships = await CustomerMembership.filter(is_active=True).select_related('membership_level')
    print(f"[信息] 找到 {len(memberships)} 个激活的会员\n")

    if not memberships:
        print("[信息] 没有激活的会员，跳过更新")
        return

    updated_count = 0
    deactivated_count = 0
    skipped_count = 0
    error_count = 0

    for idx, membership in enumerate(memberships, 1):
        try:
            print(f"{'─'*70}")
            print(f"[{idx}/{len(memberships)}] 💎 客户 {membership.customer_id} - 会员数据更新")
            print(f"{'─'*70}")

            # ===== 关键指标展示 =====
            print(f"📊 【当前会员数据】")
            print(f"  💰 充值总时长: {membership.total_hours} 小时")
            print(f"  ⏱️  已用时长: {float(membership.used_hours):.2f} 小时")
            print(f"  ⏳ 剩余时长: {float(membership.remaining_hours):.2f} 小时")
            print(f"  🏆 Fibonacci等级: Lv{membership.level}")
            print(f"  📅 过期时间: {membership.expire_time}")
            print(f"  ✅ 激活状态: {'是' if membership.is_active else '否'}")
            print()

            # 从使用记录计算实际已用时长
            usage_logs = await LLMUsageRecord.filter(customer_id=membership.customer_id)

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

            used_hours = total_seconds / 3600.0

            print(f"📋 【使用记录汇总】")
            print(f"  记录数量: {len(usage_logs)} 条")
            print(f"  总时长: {total_seconds} 秒")
            print(f"  💵 实际已用时长: {used_hours:.2f} 小时")

            if usage_logs:
                print(f"  📝 最近3条记录:")
                for log in usage_logs[:3]:
                    duration_str = ""
                    if log.audio_duration:
                        duration_str = f"{log.audio_duration}秒"
                    elif log.start_time and log.end_time:
                        duration = (log.end_time - log.start_time).total_seconds()
                        duration_str = f"{duration:.1f}秒"
                    else:
                        duration_str = f"{log.tokens} tokens"
                    print(f"    - {log.created_at.strftime('%Y-%m-%d %H:%M:%S')}: {log.record_type}, {duration_str}, ${float(log.cost):.4f}")
            print()

            # 计算剩余时长
            total_hours = membership.total_hours
            old_remaining = float(membership.remaining_hours)
            new_remaining = total_hours - used_hours
            if new_remaining < 0:
                new_remaining = 0

            print(f"🧮 【时长计算】")
            print(f"  📐 公式: 剩余时长 = 充值总时长 - 已用时长")
            print(f"  📊 充值总时长: {total_hours} 小时")
            print(f"  💵 已用时长: {used_hours:.2f} 小时")
            print(f"  📈 新剩余时长: {new_remaining:.2f} 小时")
            print(f"  📉 原剩余时长: {old_remaining:.2f} 小时")
            print(f"  🔄 变化幅度: {new_remaining - old_remaining:+.2f} 小时")
            print()

            # 检查是否需要更新
            if abs(new_remaining - old_remaining) > 0.01:
                membership.used_hours = used_hours
                membership.remaining_hours = new_remaining
                await membership.save()
                print(f"  ✅ [已更新] 会员数据已更新到数据库")
                updated_count += 1
            else:
                print(f"  ⏭️  [跳过] 无需更新（差异 < 0.01小时）")
                skipped_count += 1

            # 检查是否需要停用（剩余时长为0）
            if new_remaining <= 0:
                membership.is_active = False
                await membership.save()
                print(f"  ⛔ [已停用] 剩余时长已用完，会员已停用")
                deactivated_count += 1

            # 检查是否过期
            if membership.is_expired:
                print(f"  ⚠️  [已过期] 会员已过期")
            else:
                print(f"  ✅ [有效期] 会员在有效期内")

            # 混合系统信息
            membership_level = membership.membership_level.level_type if membership.membership_level else "unknown"
            print(f"  ✅ [会员类别] {membership_level}")
            print(f"  ✅ [VIP状态] {'是' if membership.is_vip else '否'}")
            print(f"  ✅ [SVIP状态] {'是' if membership.is_svip else '否'}")
            print(f"  ✅ [Fibonacci动态等级] Lv{membership.level}")

            # Fibonacci等级验证
            from base.plugins.customer.services.membership_service import fibonacci_service
            expected_level = fibonacci_service.get_level_from_hours(total_hours)
            if membership.level == expected_level:
                print(f"  ✅ [等级正确] Lv{membership.level}")
            else:
                print(f"  ⚠️  [等级异常] 当前Lv{membership.level}, 应该Lv{expected_level}")

        except Exception as e:
            print(f"  ❌ [错误] 处理失败: {e}")
            error_count += 1
            import traceback
            traceback.print_exc()

        print()  # 空行分隔

    # 输出统计信息
    print("="*70)
    print(f"[定时任务] ✅ 执行完成")
    print(f"  处理会员总数: {len(memberships)}")
    print(f"  更新会员数: {updated_count}")
    print(f"  跳过会员数: {skipped_count}")
    print(f"  停用会员数: {deactivated_count}")
    print(f"  错误数量: {error_count}")
    print("="*70 + "\n")
