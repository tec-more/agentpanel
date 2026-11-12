"""插件启停门控：全平台唯一判定入口。

PLR-03 要求「门控判定集中在一处，禁止各插件自行实现」。
此前分散在 router.py / setting.py / common.py / plugin_manager.py /
start.py / harness/policy_service.py 的重复判定统一收敛到这里。

判定口径：**已安装 且 已启用**（双真），以 manifest.json 为唯一状态源；
数据库 Plugin 表由 plugin_manager 在状态变更时同步，不参与实时门控。
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Optional

from base.common.plugin_contract import BROWSER_API_PREFIX

_PLUGINS_DIR = Path(__file__).resolve().parent.parent / "plugins"
_cache: dict[str, tuple[float, bool]] = {}
_lock = threading.Lock()


def plugins_dir() -> Path:
    return _PLUGINS_DIR


def invalidate(name: Optional[str] = None) -> None:
    """状态写入后调用，避免缓存返回旧值。"""
    with _lock:
        if name is None:
            _cache.clear()
        else:
            _cache.pop(name, None)


def read_manifest(name: str) -> Optional[dict]:
    path = _PLUGINS_DIR / name / "manifest.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def is_plugin_active(name: str) -> bool:
    """仅「已安装且已启用」返回 True。"""
    manifest_path = _PLUGINS_DIR / name / "manifest.json"
    if not manifest_path.exists():
        return False
    try:
        mtime = manifest_path.stat().st_mtime
    except OSError:
        return False

    with _lock:
        cached = _cache.get(name)
    if cached and cached[0] == mtime:
        return cached[1]

    manifest = read_manifest(name) or {}
    active = bool(manifest.get("is_installed")) and bool(manifest.get("is_enabled"))
    with _lock:
        _cache[name] = (mtime, active)
    return active


def active_plugin_names() -> list[str]:
    """返回所有双真插件名（供 /v1/common/system-config 下发前端）。"""
    if not _PLUGINS_DIR.exists():
        return []
    result = []
    for plugin_dir in sorted(_PLUGINS_DIR.iterdir()):
        if plugin_dir.is_dir() and is_plugin_active(plugin_dir.name):
            result.append(plugin_dir.name)
    return result


def browser_api_path(internal_path: str) -> str:
    """把应用内路径转换为浏览器请求路径（唯一拼接点）。"""
    if not internal_path.startswith("/"):
        internal_path = "/" + internal_path
    if internal_path.startswith(BROWSER_API_PREFIX):
        return internal_path
    return BROWSER_API_PREFIX + internal_path
