"""SQL 迁移文件管理工具

用法:
    python -m base.common.migration_tool gen <plugin> <action> <table> [field]
    python -m base.common.migration_tool list
    python -m base.common.migration_tool validate

示例:
    python -m base.common.migration_tool gen core seed_data system_menus
    python -m base.common.migration_tool gen approval add_column approval_flow route_patterns
    python -m base.common.migration_tool gen mail seed_data message_subtype
    python -m base.common.migration_tool list
    python -m base.common.migration_tool validate
"""
import sys
from pathlib import Path

# 把项目根加入 sys.path 以便 base 包可导入
_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from base.common.database import (
    generate_migration_filename,
    parse_migration_filename,
    _VALID_ACTIONS,
    MigrationMeta,
)

MIGRATIONS_DIR = _ROOT / "migrations"


def cmd_gen(args: list[str]) -> int:
    """生成新迁移文件。"""
    if len(args) < 3:
        print(f"用法: python -m base.common.migration_tool gen <plugin> <action> <table> [field]")
        print(f"  示例: python -m base.common.migration_tool gen approval add_column approval_flow route_patterns")
        print(f"  可用 actions: {', '.join(_VALID_ACTIONS)}")
        return 1
    plugin, action, table = args[0], args[1], args[2]
    field = args[3] if len(args) > 3 else ""
    if action not in _VALID_ACTIONS:
        print(f"⚠ action '{action}' 不在标准集合内: {', '.join(_VALID_ACTIONS)}")
    filename = generate_migration_filename(plugin, action, table, field)
    filepath = MIGRATIONS_DIR / filename
    if filepath.exists():
        print(f"✗ 文件已存在: {filepath}")
        return 1
    MIGRATIONS_DIR.mkdir(parents=True, exist_ok=True)
    filepath.write_text(f"-- {plugin} | {action} | {table}" + (f" | {field}" if field else "") + "\n-- TODO: 填写迁移 SQL\n", encoding="utf-8")
    print(f"✓ 生成: {filepath}")
    return 0


def cmd_list(_args: list[str]) -> int:
    """列出所有迁移文件。"""
    if not MIGRATIONS_DIR.exists():
        print(f"migrations/ 目录不存在")
        return 1
    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not files:
        print("migrations/ 目录为空")
        return 0
    parsed_ok: list[MigrationMeta] = []
    legacy: list[Path] = []
    for f in files:
        m = parse_migration_filename(f.name)
        if m:
            parsed_ok.append(m)
        else:
            legacy.append(f)
    parsed_ok.sort()

    print(f"\n共 {len(files)} 个迁移文件 ({len(parsed_ok)} 规范, {len(legacy)} 旧格式)\n")
    print(f"  {'时间戳':16} {'插件':12} {'操作':20} {'表名':28} {'字段':20} {'文件'}")
    print(f"  {'─'*100}")
    for m in parsed_ok:
        print(f"  {m.timestamp} {m.plugin:12} {m.action:20} {m.table:28} {str(m.field or ''):20} {m.filename}")
    if legacy:
        print(f"\n  ⚠ 以下 {len(legacy)} 个文件不符合规范（将按旧文件兼容处理）：")
        for f in legacy:
            print(f"    {f.name}")
    print()
    return 0


def cmd_validate(_args: list[str]) -> int:
    """验证所有迁移文件是否符合命名规范。"""
    if not MIGRATIONS_DIR.exists():
        print("migrations/ 目录不存在")
        return 1
    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    issues: list[str] = []
    for f in files:
        m = parse_migration_filename(f.name)
        if not m:
            issues.append(f"  ✗ {f.name} → 不符合命名规范")
    if issues:
        print("发现问题：")
        for i in issues:
            print(i)
        print(f"\n建议格式: {{插件}}_{{操作}}_{{表名}}[__{{字段}}]_{{unix时间戳}}.sql")
        print(f"示例:     approval_add_column_approval_flow__route_patterns_1758648060.sql")
        return 1
    print(f"✓ 全部 {len(files)} 个文件符合规范")
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 0
    cmd = sys.argv[1]
    args = sys.argv[2:]
    if cmd == "gen":
        return cmd_gen(args)
    elif cmd == "list":
        return cmd_list(args)
    elif cmd == "validate":
        return cmd_validate(args)
    else:
        print(f"未知命令: {cmd}")
        print(__doc__)
        return 1


if __name__ == "__main__":
    sys.exit(main())
