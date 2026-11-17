"""配置 DeepSeek 语义合规（purpose=semantic）——幂等脚本。

运行：
    # 1) 只检查现状（不写库）
    .venv/Scripts/python tests/setup_deepseek_semantic.py --check

    # 2) 真正配置（需要 API Key，从环境变量或命令行传入，不落明文到脚本）
    DEEPSEEK_API_KEY=sk-xxx .venv/Scripts/python tests/setup_deepseek_semantic.py --apply
    # 或：
    .venv/Scripts/python tests/setup_deepseek_semantic.py --apply --api-key sk-xxx

配置内容（幂等，已存在则复用/更新）：
  1. llm_provider      : DeepSeek / deepseek
  2. llm_model         : deepseek-chat（supports_vision=False）
  3. llm_api_key       : 绑定该模型，存 api_key + endpoint
  4. contentops_llm_provider_config : purpose=semantic → deepseek / deepseek-chat
  5. 平台级语义规则 1 条（type=semantic, owner=NULL）：S5 触发前提，全局可见

注意：
  - 真库 = openGauss，依赖 base.common.database 的三项补丁，开头必须先 import。
  - 不配置视觉（purpose=vision），素材识别继续降级 unavailable。
  - S5 触发还需本租户存在 type=semantic 的规则；无规则时 --check 会提示。
"""
import argparse
import asyncio
import configparser
import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import base.common.database  # noqa: F401  触发 openGauss 三项补丁（必须最先）

PROVIDER_NAME = "DeepSeek"
PROVIDER_NAME_EN = "deepseek"
OFFICIAL_URL = "https://api.deepseek.com"
MODEL_ID = "deepseek-chat"
MODEL_NAME = "DeepSeek Chat"
ENDPOINT = "https://api.deepseek.com"
PURPOSE = "semantic"

ROOT = Path(__file__).resolve().parent.parent


async def get_config():
    from base.common.setting import TORTOISE_ORM
    from tortoise import Tortoise
    import packages.common.cache as cm

    if getattr(cm, "_config", None) is not None:
        cm._config.enabled = False
    cm.RedisCache._instance = None

    await Tortoise.init(config=TORTOISE_ORM)
    return Tortoise


async def check():
    from base.plugins.llm.models.provider import LLMProvider
    from base.plugins.llm.models.model import LLMModel
    from base.plugins.llm.models.api_key import LLMApiKey
    from base.plugins.contentops.models import LLMProviderConfig, ComplianceRule

    provider = await LLMProvider.get_or_none(name_en=PROVIDER_NAME_EN)
    print(f"[check] provider  : {'OK ' + str(provider.id) if provider else 'MISSING'}")

    model = await LLMModel.filter(model_id=MODEL_ID).first()
    print(f"[check] model     : {'OK ' + str(model.id) if model else 'MISSING'}")

    if model:
        key = await LLMApiKey.filter(model_id=model.id).first()
        if key:
            masked = (key.api_key[:6] + "***" + key.api_key[-4:]) if key.api_key and len(key.api_key) > 12 else "(empty)"
            print(f"[check] api_key   : OK {key.id}  key={masked}  endpoint={key.endpoint_url}")
        else:
            print("[check] api_key   : MISSING")

    cfg = await LLMProviderConfig.filter(purpose=PURPOSE, enabled=True).first()
    if cfg:
        print(f"[check] purpose   : OK {cfg.id}  provider={cfg.provider} model={cfg.model} endpoint={cfg.endpoint}")
    else:
        print("[check] purpose   : MISSING")

    sem_rules = await ComplianceRule.filter(type="semantic", enabled=True).count()
    print(f"[check] semantic规则: {sem_rules} 条（S5 触发前提：>0；为 0 时即便配好模型也会 skipped）")


async def apply(api_key: str):
    from base.plugins.llm.models.provider import LLMProvider
    from base.plugins.llm.models.model import LLMModel
    from base.plugins.llm.models.api_key import LLMApiKey
    from base.plugins.contentops.models import LLMProviderConfig, ComplianceRule

    # 1. provider（幂等）
    provider = await LLMProvider.get_or_none(name_en=PROVIDER_NAME_EN)
    if not provider:
        provider = await LLMProvider.create(
            name=PROVIDER_NAME, name_en=PROVIDER_NAME_EN,
            official_url=OFFICIAL_URL, status="active",
            description="DeepSeek 线上大模型（contentops 语义合规）",
        )
        print(f"[apply] 新建 provider id={provider.id}")
    else:
        print(f"[apply] 复用 provider id={provider.id}")

    # 2. model（幂等）
    model = await LLMModel.filter(model_id=MODEL_ID).first()
    if not model:
        model = await LLMModel.create(
            provider=provider, model_id=MODEL_ID, model_name=MODEL_NAME,
            endpoint_url=ENDPOINT, context_length=65536,
            supports_streaming=True, supports_vision=False,
            status="active", description="DeepSeek 纯文本；语义合规判定用",
        )
        print(f"[apply] 新建 model id={model.id}")
    else:
        print(f"[apply] 复用 model id={model.id}")

    # 3. api_key（幂等：按 model 找，存在则更新 key/endpoint）
    key = await LLMApiKey.filter(model_id=model.id).first()
    if not key:
        key = await LLMApiKey.create(
            provider=provider, model=model,
            api_key=api_key, endpoint_url=ENDPOINT,
            call_mode="vendor_sdk", status="active",
            max_quota=1000000, description="DeepSeek 语义合规密钥",
        )
        print(f"[apply] 新建 api_key id={key.id}")
    else:
        key.api_key = api_key
        key.endpoint_url = ENDPOINT
        key.status = "active"
        await key.save()
        print(f"[apply] 更新 api_key id={key.id}")

    # 4. contentops 用途配置（幂等：purpose=semantic 全局记录）
    cfg = await LLMProviderConfig.filter(purpose=PURPOSE, owner_type__isnull=True).first()
    if not cfg:
        cfg = await LLMProviderConfig.create(
            provider=PROVIDER_NAME_EN, model=MODEL_ID, endpoint=ENDPOINT,
            enabled=True, purpose=PURPOSE,
        )
        print(f"[apply] 新建 purpose=semantic 配置 id={cfg.id}")
    else:
        cfg.provider = PROVIDER_NAME_EN
        cfg.model = MODEL_ID
        cfg.endpoint = ENDPOINT
        cfg.enabled = True
        await cfg.save()
        print(f"[apply] 更新 purpose=semantic 配置 id={cfg.id}")

    # 5. 平台级语义规则（幂等）：S5 触发前提，全局可见，不干扰 L1-L3 关键词/正则规则
    sem_rule = await ComplianceRule.filter(type="semantic", owner_type__isnull=True).first()
    if not sem_rule:
        sem_rule = await ComplianceRule.create(
            layer="L4", type="semantic",
            pattern="违法违规、涉政、色情、暴力、诈骗、违禁品、绝对化广告用语、虚假宣传等语义风险",
            risk_level="P1", action="review",
            basis="线上大模型语义审核（平台级兜底规则）",
            suggestion="请人工复核后放行或修改",
            version="1", enabled=True, status="active",
            source="platform", owner_type=None, owner_id=None,
        )
        print(f"[apply] 新建平台级语义规则 id={sem_rule.id}")
    else:
        print(f"[apply] 复用平台级语义规则 id={sem_rule.id}")

    print("[apply] 完成。平台级全局配置（owner 为 NULL），所有租户可见。")


async def smoke():
    """真实调用一次 LLMAdapter.compliance_check，验证线上链路。"""
    from base.plugins.contentops.services.llm_adapter import LLMAdapter
    text = "本产品疗效显著，治愈率百分之百，绝对安全无副作用。"
    try:
        raw, meta = await LLMAdapter.compliance_check(text, "绝对化广告用语/虚假宣传")
        print("[smoke] 线上调用成功")
        print(f"[smoke] provider={meta.get('provider')} model={meta.get('model')} pii_scrubbed={meta.get('pii_scrubbed')}")
        print(f"[smoke] 模型输出:\n{raw}")
    except Exception as e:
        print(f"[smoke] 线上调用失败: {type(e).__name__}: {e}")
        raise


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只检查现状，不写库")
    ap.add_argument("--apply", action="store_true", help="写入配置")
    ap.add_argument("--smoke", action="store_true", help="真实调用一次验证")
    ap.add_argument("--api-key", default=os.environ.get("DEEPSEEK_API_KEY", ""), help="DeepSeek API Key")
    ap.add_argument("--api-key-file", default="", help="INI 文件，读取 [deepseek].api_key（明文不回显）")
    args = ap.parse_args()

    if not (args.check or args.apply or args.smoke):
        ap.print_help()
        return

    # 从文件读取 key（优先级高于 --api-key / 环境变量），全程不回显明文
    api_key = args.api_key.strip()
    if args.api_key_file:
        cp = configparser.ConfigParser()
        cp.read(args.api_key_file, encoding="utf-8")
        try:
            api_key = cp.get("deepseek", "api_key").strip()
        except (configparser.NoSectionError, configparser.NoOptionError):
            print(f"[ERROR] {args.api_key_file} 中缺少 [deepseek].api_key 配置项。")
            return
        masked = (api_key[:6] + "***" + api_key[-4:]) if len(api_key) > 12 else "(短)"
        print(f"[key] 从 {args.api_key_file} 读取 [deepseek].api_key：{masked}（长度={len(api_key)}）")

    tortoise = await get_config()
    try:
        if args.check:
            await check()
        if args.apply:
            if not api_key:
                print("[ERROR] 缺少 API Key。请用 --api-key-file / --api-key 或环境变量 DEEPSEEK_API_KEY 提供。")
                return
            await apply(api_key)
        if args.smoke:
            await smoke()
    finally:
        await tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(main())
