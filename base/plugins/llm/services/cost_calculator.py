"""
幽默对话费用计算器
"""
from decimal import Decimal
from typing import Dict, Optional


class HumorousChatCostCalculator:
    """幽默对话费用计算器"""

    # 价格配置（单位：元）
    PRICES = {
        "asr": {
            "doubao": 0.035,  # 元/分钟
            "alibaba": 0.05,
            "tencent": 0.042,
            "baidu": 0.03,
        },
        "llm": {
            "doubao_lite": {"input": 0.0008, "output": 0.0008},  # 元/1K tokens
            "doubao_pro": {"input": 0.008, "output": 0.008},
            "qwen": {"input": 0.008, "output": 0.008},
            "glm4": {"input": 0.01, "output": 0.01},
            "ernie": {"input": 0.012, "output": 0.012},
            "gpt35": {"input": 0.011, "output": 0.014},
            "gpt4": {"input": 0.22, "output": 0.43},
        },
        "tts": {
            "doubao": 0.006,  # 元/千字
            "alibaba": 0.006,
            "tencent": 0.006,
            "baidu": 0.003,
        }
    }

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """
        估算文本的token数量

        Args:
            text: 文本内容

        Returns:
            估算的token数量
        """
        chinese_chars = len([c for c in text if '\u4e00' <= c <= '\u9fff'])
        english_chars = len(text) - chinese_chars
        return int(chinese_chars / 1.5 + english_chars / 4)

    @staticmethod
    def estimate_text_from_tokens(tokens: int) -> int:
        """
        从token数量估算文本长度（汉字数量）

        Args:
            tokens: token数量

        Returns:
            估算的汉字数量
        """
        # 假设平均1.5个汉字 = 1个token
        return int(tokens * 1.5)

    @staticmethod
    def calculate_asr_cost(duration_seconds: int, provider: str = "doubao") -> Decimal:
        """
        计算ASR费用

        Args:
            duration_seconds: 音频时长（秒）
            provider: 服务提供商

        Returns:
            费用（元）
        """
        if duration_seconds == 0:
            return Decimal("0")

        duration_minutes = duration_seconds / 60
        price_per_minute = HumorousChatCostCalculator.PRICES["asr"].get(
            provider,
            HumorousChatCostCalculator.PRICES["asr"]["doubao"]
        )
        return Decimal(str(round(duration_minutes * price_per_minute, 4)))

    @staticmethod
    def calculate_llm_cost(
        input_text: str,
        output_text: str,
        model: str = "doubao_pro",
        history_tokens: int = 0
    ) -> Decimal:
        """
        计算LLM费用

        Args:
            input_text: 输入文本
            output_text: 输出文本
            model: 模型名称
            history_tokens: 历史对话token数

        Returns:
            费用（元）
        """
        if model not in HumorousChatCostCalculator.PRICES["llm"]:
            model = "doubao_pro"

        input_tokens = HumorousChatCostCalculator.estimate_tokens(input_text) + history_tokens
        output_tokens = HumorousChatCostCalculator.estimate_tokens(output_text)

        prices = HumorousChatCostCalculator.PRICES["llm"][model]
        input_cost = (input_tokens / 1000) * prices["input"]
        output_cost = (output_tokens / 1000) * prices["output"]

        return Decimal(str(round(input_cost + output_cost, 4)))

    @staticmethod
    def calculate_tts_cost(text: str, provider: str = "doubao") -> Decimal:
        """
        计算TTS费用

        Args:
            text: 要合成的文本
            provider: 服务提供商

        Returns:
            费用（元）
        """
        if not text:
            return Decimal("0")

        char_count = len(text)
        price_per_1k = HumorousChatCostCalculator.PRICES["tts"].get(
            provider,
            HumorousChatCostCalculator.PRICES["tts"]["doubao"]
        )
        return Decimal(str(round((char_count / 1000) * price_per_1k, 4)))

    @staticmethod
    def calculate_total_cost(
        input_duration_seconds: int = 0,
        input_text: str = "",
        output_text: str = "",
        asr_provider: str = "doubao",
        llm_model: str = "doubao_pro",
        tts_provider: str = "doubao",
        history_tokens: int = 300,
        enable_asr: bool = True,
        enable_tts: bool = True
    ) -> Dict[str, Decimal]:
        """
        计算单次对话总费用

        Args:
            input_duration_seconds: 输入音频时长（秒）
            input_text: 输入文本
            output_text: 输出文本
            asr_provider: ASR服务提供商
            llm_model: LLM模型
            tts_provider: TTS服务提供商
            history_tokens: 历史对话token数
            enable_asr: 是否启用ASR
            enable_tts: 是否启用TTS

        Returns:
            费用明细字典
        """
        costs = {}

        # ASR费用
        if enable_asr and input_duration_seconds > 0:
            costs["asr"] = HumorousChatCostCalculator.calculate_asr_cost(
                input_duration_seconds, asr_provider
            )
        else:
            costs["asr"] = Decimal("0")

        # LLM费用
        costs["llm"] = HumorousChatCostCalculator.calculate_llm_cost(
            input_text, output_text, llm_model, history_tokens
        )

        # TTS费用
        if enable_tts and output_text:
            costs["tts"] = HumorousChatCostCalculator.calculate_tts_cost(
                output_text, tts_provider
            )
        else:
            costs["tts"] = Decimal("0")

        # 总费用
        costs["total"] = costs["asr"] + costs["llm"] + costs["tts"]

        return costs

    @staticmethod
    def estimate_monthly_cost(
        daily_users: int,
        avg_minutes_per_user: int,
        conversations_per_minute: int = 2,
        avg_input_duration: int = 20,
        avg_input_length: int = 50,
        avg_output_length: int = 100,
        llm_model: str = "doubao_pro"
    ) -> Dict:
        """
        估算月度费用

        Args:
            daily_users: 日活用户数
            avg_minutes_per_user: 每用户平均使用时长（分钟）
            conversations_per_minute: 每分钟对话次数
            avg_input_duration: 平均输入音频时长（秒）
            avg_input_length: 平均输入文本长度（字）
            avg_output_length: 平均输出文本长度（字）
            llm_model: 使用的LLM模型

        Returns:
            月度费用估算
        """
        # 计算单次对话费用
        input_text = "你好" * (avg_input_length // 2)
        output_text = "你好" * (avg_output_length // 2)

        single_cost = HumorousChatCostCalculator.calculate_total_cost(
            input_duration_seconds=avg_input_duration,
            input_text=input_text,
            output_text=output_text,
            llm_model=llm_model
        )

        # 每用户每天费用
        daily_conversations_per_user = avg_minutes_per_user * conversations_per_minute
        daily_cost_per_user = float(single_cost["total"]) * daily_conversations_per_user

        # 月度费用
        monthly_cost = daily_cost_per_user * daily_users * 30

        return {
            "single_conversation_cost": float(single_cost["total"]),
            "daily_conversations_per_user": daily_conversations_per_user,
            "daily_cost_per_user": round(daily_cost_per_user, 2),
            "daily_total_cost": round(daily_cost_per_user * daily_users, 2),
            "monthly_total_cost": round(monthly_cost, 2),
            "cost_breakdown": {
                "asr": float(single_cost["asr"]),
                "llm": float(single_cost["llm"]),
                "tts": float(single_cost["tts"])
            }
        }


# 便捷函数
def calculate_conversation_cost(
    input_text: str,
    output_text: str,
    input_audio_duration: int = 0,
    enable_asr: bool = False,
    enable_tts: bool = True
) -> Dict:
    """
    计算单次对话费用（便捷函数）

    Args:
        input_text: 用户输入文本
        output_text: AI回复文本
        input_audio_duration: 输入音频时长（秒），如果有语音输入
        enable_asr: 是否需要语音识别
        enable_tts: 是否需要语音合成

    Returns:
        费用明细
    """
    return HumorousChatCostCalculator.calculate_total_cost(
        input_duration_seconds=input_audio_duration,
        input_text=input_text,
        output_text=output_text,
        enable_asr=enable_asr,
        enable_tts=enable_tts
    )


def estimate_project_cost(
    users: int,
    daily_minutes: int,
    model: str = "doubao_pro"
) -> Dict:
    """
    估算项目费用（便捷函数）

    Args:
        users: 日活用户数
        daily_minutes: 每用户日均使用分钟数
        model: 使用的模型

    Returns:
        月度费用估算
    """
    return HumorousChatCostCalculator.estimate_monthly_cost(
        daily_users=users,
        avg_minutes_per_user=daily_minutes,
        llm_model=model
    )


if __name__ == "__main__":
    import sys
    import io

    # 设置标准输出编码为UTF-8
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

    # 测试示例
    print("=" * 60)
    print("幽默对话费用计算器 - 测试")
    print("=" * 60)

    # 场景1：语音输入 + 语音输出
    print("\n【场景1】语音输入 + 语音输出")
    cost1 = HumorousChatCostCalculator.calculate_total_cost(
        input_duration_seconds=20,
        input_text="今天天气怎么样啊？我想出去玩！",
        output_text="哈哈，看来你心情不错嘛！想知道天气是吧？让我这个幽默大师来告诉你，今天天气晴朗，温度适宜，简直就是出门浪的好日子！不过别忘了带把伞，毕竟天气预报有时候跟我开玩笑一样不太靠谱~😄",
        enable_asr=True,
        enable_tts=True
    )
    print(f"ASR费用: ¥{cost1['asr']}")
    print(f"LLM费用: ¥{cost1['llm']}")
    print(f"TTS费用: ¥{cost1['tts']}")
    print(f"总计: ¥{cost1['total']}")
    print(f"每分钟费用（2次对话）: ¥{cost1['total'] * 2}")
    print(f"每小时费用: ¥{cost1['total'] * 2 * 60}")

    # 场景2：纯文字对话
    print("\n【场景2】纯文字对话（无ASR和TTS）")
    cost2 = HumorousChatCostCalculator.calculate_total_cost(
        input_text="今天天气怎么样啊？",
        output_text="哈哈，看来你心情不错嘛！今天天气晴朗，温度适宜，简直就是出门浪的好日子！不过别忘了带把伞~😄",
        enable_asr=False,
        enable_tts=False
    )
    print(f"LLM费用: ¥{cost2['llm']}")
    print(f"总计: ¥{cost2['total']}")

    # 场景3：项目费用估算
    print("\n【场景3】项目费用估算（100用户，每人日均30分钟）")
    estimate = HumorousChatCostCalculator.estimate_monthly_cost(
        daily_users=100,
        avg_minutes_per_user=30,
        llm_model="doubao_pro"
    )
    print(f"单次对话成本: ¥{estimate['single_conversation_cost']:.4f}")
    print(f"每用户日均对话次数: {estimate['daily_conversations_per_user']} 次")
    print(f"每用户日均费用: ¥{estimate['daily_cost_per_user']:.2f}")
    print(f"全部用户日均费用: ¥{estimate['daily_total_cost']:.2f}")
    print(f"月度总费用: ¥{estimate['monthly_total_cost']:.2f}")

    # 场景4：不同模型对比
    print("\n【场景4】不同模型价格对比")
    models = ["doubao_lite", "doubao_pro", "qwen", "glm4", "gpt35", "gpt4"]
    print(f"{'模型':<15} {'单次对话费用':<15} {'每小时费用':<15}")
    print("-" * 45)
    for model in models:
        cost = HumorousChatCostCalculator.calculate_total_cost(
            input_duration_seconds=20,
            input_text="你好，今天天气怎么样？",
            output_text="哈哈，今天天气晴朗，适合出去玩！",
            llm_model=model
        )
        hourly = float(cost['total']) * 2 * 60
        print(f"{model:<15} ¥{float(cost['total']):<14.4f} ¥{hourly:<14.2f}")

    print("\n" + "=" * 60)
