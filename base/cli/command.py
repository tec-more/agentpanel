"""
CLI 命令行工具
使用 typer 实现命令行交互
"""
import json
from pathlib import Path
from typing import Optional

import typer

from base.common.log import log
from base.common.setting import settings

app = typer.Typer(
    name="aipanel",
    help="AIPanelAdmin 命令行工具",
    no_args_is_help=True,
)


@app.command()
def create_plugin(
    name: str = typer.Argument(..., help="插件名称（英文，如 hello_world）"),
    display_name: str = typer.Option(..., "--display-name", "-d", help="插件显示名称"),
    description: str = typer.Option("", "--description", "-desc", help="插件描述"),
    author: str = typer.Option("", "--author", "-a", help="作者"),
    version: str = typer.Option("1.0.0", "--version", "-v", help="版本号"),
    with_api: bool = typer.Option(True, "--with-api", help="创建 API 路由目录"),
    with_models: bool = typer.Option(True, "--with-models", help="创建数据模型目录"),
    with_schemas: bool = typer.Option(True, "--with-schemas", help="创建 Schema 目录"),
    with_services: bool = typer.Option(True, "--with-services", help="创建业务逻辑目录"),
):
    """
    创建新插件结构

    示例：
        python -m base.cli.command create-plugin hello_world -d "Hello World" -a "Your Name"
    """
    plugins_dir = settings.base_path / "base" / "plugins"
    plugin_dir = plugins_dir / name

    # 检查插件是否已存在
    if plugin_dir.exists():
        typer.echo(f"[ERROR] Plugin '{name}' already exists at {plugin_dir}")
        raise typer.Exit(1)

    # 创建插件目录结构
    typer.echo(f"[+] Creating plugin: {name}")
    plugin_dir.mkdir(parents=True, exist_ok=True)

    # 创建 __init__.py
    init_file = plugin_dir / "__init__.py"
    init_file.write_text(
        f'"""\n{display_name}\n{description}\n"""\n\n__version__ = "{version}"\n',
        encoding="utf-8",
    )
    typer.echo(f"  [*] Created {init_file.relative_to(settings.base_path)}")

    # 创建 manifest.json
    manifest = {
        "name": name,
        "display_name": display_name,
        "version": version,
        "description": description,
        "author": author,
        "is_installed": False,
        "is_enabled": False,
    }

    # 添加可选字段
    if with_api:
        api_dir = plugin_dir / "api" / "v1"
        api_dir.mkdir(parents=True, exist_ok=True)
        (api_dir / "__init__.py").write_text("", encoding="utf-8")

        # 创建示例路由文件
        example_route = api_dir / f"{name}.py"
        example_route.write_text(
            f'''"""
{name} API 路由
"""
from fastapi import APIRouter
from base.common.response import SuccessResponse

router = APIRouter(prefix="/api/v1/{name}", tags=["{display_name}"])


@router.get("/")
async def index():
    """{display_name} 首页"""
    return SuccessResponse(data={{"message": "Welcome to {display_name} plugin"}})


@router.get("/health")
async def health():
    """健康检查"""
    return SuccessResponse(data={{"status": "ok"}})
''',
            encoding="utf-8",
        )
        typer.echo(f"  [*] Created {example_route.relative_to(settings.base_path)}")

        manifest["routes"] = [f"api/v1/{name}"]

    if with_models:
        models_dir = plugin_dir / "models"
        models_dir.mkdir(parents=True, exist_ok=True)
        (models_dir / "__init__.py").write_text("", encoding="utf-8")

        # 创建示例模型文件
        example_model = models_dir / f"{name}_model.py"
        example_model.write_text(
            f'''"""
{name} Data Models
"""
from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class {name.title().replace("_", "")}Model(BaseModel, TimestampMixin):
    """{display_name} Model Example"""

    name = fields.CharField(max_length=100, description="Name")
    description = fields.TextField(description="Description", null=True)
    is_active = fields.BooleanField(default=True, description="Is Active")

    class Meta:
        table = "{name}_model"
        table_description = "{display_name} Model"
''',
            encoding="utf-8",
        )
        typer.echo(f"  [*] Created {example_model.relative_to(settings.base_path)}")

        manifest["models"] = [f"{name}_model"]

    if with_schemas:
        schemas_dir = plugin_dir / "schemas"
        schemas_dir.mkdir(parents=True, exist_ok=True)
        (schemas_dir / "__init__.py").write_text("", encoding="utf-8")

        # 创建示例 Schema 文件
        example_schema = schemas_dir / f"{name}_schema.py"
        example_schema.write_text(
            f'''"""
{name} Pydantic Schemas
"""
from pydantic import BaseModel, Field
from typing import Optional


class {name.title().replace("_", "")}Base(BaseModel):
    """{display_name} 基础 Schema"""
    name: str = Field(..., description="名称", min_length=1, max_length=100)
    description: Optional[str] = Field(None, description="描述")
    is_active: bool = Field(True, description="是否激活")


class {name.title().replace("_", "")}Create({name.title().replace("_", "")}Base):
    """创建 {display_name}"""
    pass


class {name.title().replace("_", "")}Update(BaseModel):
    """更新 {display_name}"""
    name: Optional[str] = Field(None, description="名称", min_length=1, max_length=100)
    description: Optional[str] = Field(None, description="描述")
    is_active: Optional[bool] = Field(None, description="是否激活")


class {name.title().replace("_", "")}Response({name.title().replace("_", "")}Base):
    """{display_name} 响应 Schema"""
    id: int
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True
''',
            encoding="utf-8",
        )
        typer.echo(f"  [*] Created {example_schema.relative_to(settings.base_path)}")

        manifest["schemas"] = [f"{name}_schema"]

    if with_services:
        services_dir = plugin_dir / "services"
        services_dir.mkdir(parents=True, exist_ok=True)
        (services_dir / "__init__.py").write_text("", encoding="utf-8")

        # 创建示例服务文件
        example_service = services_dir / f"{name}_service.py"
        example_service.write_text(
            f'''"""
{name} 业务逻辑层
"""
from typing import List, Tuple, Optional
from base.common.log import log


class {name.title().replace("_", "")}Service:
    """{display_name} 服务类"""

    @staticmethod
    async def get_by_id(item_id: int) -> Optional[dict]:
        """根据ID获取项"""
        # TODO: 实现获取逻辑
        log.info(f"获取 {name} ID: {{item_id}}")
        return {{"id": item_id, "name": "Example"}}

    @staticmethod
    async def get_list(page: int = 1, page_size: int = 10) -> Tuple[List[dict], int]:
        """获取列表"""
        # TODO: 实现列表查询逻辑
        log.info(f"获取 {name} 列表: page={{page}}, page_size={{page_size}}")
        items = [
            {{"id": 1, "name": "Item 1"}},
            {{"id": 2, "name": "Item 2"}},
        ]
        total = 2
        return items, total

    @staticmethod
    async def create(item_data: dict) -> dict:
        """创建项"""
        # TODO: 实现创建逻辑
        log.info(f"创建 {name}: {{item_data}}")
        return {{"id": 1, **item_data}}

    @staticmethod
    async def update(item_id: int, item_data: dict) -> bool:
        """更新项"""
        # TODO: 实现更新逻辑
        log.info(f"更新 {name} ID {{item_id}}: {{item_data}}")
        return True

    @staticmethod
    async def delete(item_id: int) -> bool:
        """删除项"""
        # TODO: 实现删除逻辑
        log.info(f"删除 {name} ID: {{item_id}}")
        return True
''',
            encoding="utf-8",
        )
        typer.echo(f"  [*] Created {example_service.relative_to(settings.base_path)}")

    # 写入 manifest.json
    manifest_file = plugin_dir / "manifest.json"
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=4)
    typer.echo(f"  [*] Created {manifest_file.relative_to(settings.base_path)}")

    typer.echo(f"\n[OK] Plugin '{name}' created successfully!")
    typer.echo(f"\n[PATH] Plugin location: {plugin_dir}")
    typer.echo(
        f"\n[NEXT STEPS]:\n"
        f"   1. Edit plugin code\n"
        f"   2. Enable plugin: python -m base.cli.command enable-plugin {name}\n"
        f"   3. Import in app: from base.plugins.{name} import *"
    )


@app.command()
def list_plugins():
    """列出所有插件"""
    plugins_dir = settings.base_path / "base" / "plugins"

    if not plugins_dir.exists():
        typer.echo("[ERROR] Plugins directory does not exist")
        raise typer.Exit(1)

    plugins = []
    for item in plugins_dir.iterdir():
        if item.is_dir() and not item.name.startswith("_") and item.name != "__pycache__":
            manifest_file = item / "manifest.json"
            if manifest_file.exists():
                with open(manifest_file, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                    plugins.append(
                        {
                            "name": manifest.get("name", item.name),
                            "display_name": manifest.get("display_name", item.name),
                            "version": manifest.get("version", "1.0.0"),
                            "is_installed": manifest.get("is_installed", False),
                            "is_enabled": manifest.get("is_enabled", False),
                        }
                    )

    if not plugins:
        typer.echo("[INFO] No plugins found")
        return

    typer.echo("\n[PLUGIN LIST]:\n")
    for plugin in plugins:
        status = "[ENABLED]" if plugin["is_enabled"] else "[INSTALLED]" if plugin["is_installed"] else "[DISABLED]"
        typer.echo(
            f"  {status} {plugin['name']} (v{plugin['version']}) - {plugin['display_name']}"
        )


@app.command()
def enable_plugin(name: str = typer.Argument(..., help="插件名称")):
    """
    启用插件（仅更新 manifest.json，实际加载需要在应用启动时完成）

    示例：
        python -m base.cli.command enable-plugin hello_world
    """
    plugins_dir = settings.base_path / "base" / "plugins"
    manifest_file = plugins_dir / name / "manifest.json"

    if not manifest_file.exists():
        typer.echo(f"[ERROR] Plugin '{name}' does not exist")
        raise typer.Exit(1)

    with open(manifest_file, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    manifest["is_installed"] = True
    manifest["is_enabled"] = True

    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=4)

    typer.echo(f"[OK] Plugin '{manifest.get('display_name', name)}' enabled")
    typer.echo(f"[INFO] Restart application to load the plugin")


@app.command()
def disable_plugin(name: str = typer.Argument(..., help="插件名称")):
    """
    禁用插件

    示例：
        python -m base.cli.command disable-plugin hello_world
    """
    plugins_dir = settings.base_path / "base" / "plugins"
    manifest_file = plugins_dir / name / "manifest.json"

    if not manifest_file.exists():
        typer.echo(f"[ERROR] Plugin '{name}' does not exist")
        raise typer.Exit(1)

    with open(manifest_file, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    manifest["is_enabled"] = False

    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=4)

    typer.echo(f"[OK] Plugin '{manifest.get('display_name', name)}' disabled")
    typer.echo(f"[INFO] Restart application to apply changes")


@app.command()
def delete_plugin(
    name: str = typer.Argument(..., help="插件名称"),
    force: bool = typer.Option(False, "--force", "-f", help="强制删除，无需确认"),
):
    """
    删除插件

    示例：
        python -m base.cli.command delete-plugin hello_world
        python -m base.cli.command delete-plugin hello_world --force
    """
    plugins_dir = settings.base_path / "base" / "plugins"
    plugin_dir = plugins_dir / name

    if not plugin_dir.exists():
        typer.echo(f"[ERROR] Plugin '{name}' does not exist")
        raise typer.Exit(1)

    manifest_file = plugin_dir / "manifest.json"
    if manifest_file.exists():
        with open(manifest_file, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        display_name = manifest.get("display_name", name)
    else:
        display_name = name

    if not force:
        confirm = typer.confirm(f"[WARNING] Are you sure you want to delete plugin '{display_name}'? This cannot be undone!")
        if not confirm:
            typer.echo("[CANCELLED] Delete operation cancelled")
            raise typer.Exit()

    import shutil

    shutil.rmtree(plugin_dir)
    typer.echo(f"[OK] Plugin '{display_name}' deleted")


if __name__ == "__main__":
    app()
