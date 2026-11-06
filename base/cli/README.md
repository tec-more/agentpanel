# 插件系统 CLI 工具使用指南

## 简介

`base/cli/command.py` 提供了一套完整的命令行工具，用于管理 AIPanelAdmin 的插件系统。支持创建、列出、启用、禁用和删除插件。

## 可用命令

### 1. 创建插件 (create-plugin)

创建一个新的插件结构，包含完整的目录结构和示例代码。

```bash
python -m base.cli.command create-plugin <插件名称> [选项]
```

**参数：**
- `name`: 插件名称（必需，英文，如 hello_world）

**选项：**
- `-d, --display-name`: 插件显示名称（必需）
- `--description, -desc`: 插件描述（可选）
- `--author, -a`: 作者（可选）
- `--version, -v`: 版本号（默认: 1.0.0）
- `--with-api`: 创建 API 路由目录（默认: True）
- `--with-models`: 创建数据模型目录（默认: True）
- `--with-schemas`: 创建 Schema 目录（默认: True）
- `--with-services`: 创建业务逻辑目录（默认: True）

**示例：**
```bash
# 创建完整插件
python -m base.cli.command create-plugin hello_world -d "Hello World" -a "Your Name"

# 创建仅包含 API 的插件
python -m base.cli.command create-plugin api_plugin -d "API Plugin" --with-models=false --with-schemas=false --with-services=false

# 创建完整插件并指定描述
python -m base.cli.command create-plugin my_plugin -d "My Plugin" -desc "This is my plugin" -a "Author Name" -v "2.0.0"
```

**生成的目录结构：**
```
base/plugins/<插件名称>/
├── __init__.py              # 插件入口文件
├── manifest.json            # 插件元数据
├── api/                     # API 路由（可选）
│   └── v1/
│       ├── __init__.py
│       └── <插件名称>.py    # 示例路由
├── models/                  # 数据模型（可选）
│   ├── __init__.py
│   └── <插件名称>_model.py  # 示例模型
├── schemas/                 # Pydantic Schemas（可选）
│   ├── __init__.py
│   └── <插件名称>_schema.py # 示例 Schema
└── services/                # 业务逻辑（可选）
    ├── __init__.py
    └── <插件名称>_service.py # 示例服务
```

### 2. 列出插件 (list-plugins)

列出所有已安装的插件及其状态。

```bash
python -m base.cli.command list-plugins
```

**输出示例：**
```
[PLUGIN LIST]:

  [ENABLED] hello_world (v1.0.0) - Hello World
  [INSTALLED] my_plugin (v2.0.0) - My Plugin
  [DISABLED] test_plugin (v1.0.0) - Test Plugin
```

**状态说明：**
- `[ENABLED]`: 插件已安装并启用
- `[INSTALLED]`: 插件已安装但未启用
- `[DISABLED]`: 插件未安装

### 3. 启用插件 (enable-plugin)

启用一个已安装的插件。

```bash
python -m base.cli.command enable-plugin <插件名称>
```

**示例：**
```bash
python -m base.cli.command enable-plugin hello_world
```

**注意：** 启用插件后需要重启应用才能生效。

### 4. 禁用插件 (disable-plugin)

禁用一个已启用的插件。

```bash
python -m base.cli.command disable-plugin <插件名称>
```

**示例：**
```bash
python -m base.cli.command disable-plugin hello_world
```

**注意：** 禁用插件后需要重启应用才能生效。

### 5. 删除插件 (delete-plugin)

删除一个插件（会提示确认）。

```bash
python -m base.cli.command delete-plugin <插件名称> [选项]
```

**选项：**
- `-f, --force`: 强制删除，无需确认

**示例：**
```bash
# 删除插件（会提示确认）
python -m base.cli.command delete-plugin hello_world

# 强制删除（不提示确认）
python -m base.cli.command delete-plugin hello_world --force
```

**注意：** 删除操作不可撤销，请谨慎操作。

## 插件开发指南

### 1. 创建插件

使用 CLI 工具创建插件：

```bash
python -m base.cli.command create-plugin my_plugin -d "My Plugin" -a "Your Name"
```

### 2. 编辑插件代码

生成的插件包含示例代码，你可以根据需要修改：

- **API 路由** (`api/v1/my_plugin.py`): 定义 API 端点
- **数据模型** (`models/my_plugin_model.py`): 定义 Tortoise ORM 模型（会自动加载）
- **Schemas** (`schemas/my_plugin_schema.py`): 定义 Pydantic 数据验证模型（**按需导入使用**）
- **服务层** (`services/my_plugin_service.py`): 定义业务逻辑

### 3. Schemas 使用说明

**重要**: Schemas 不会自动加载，需要在代码中按需导入使用。

```python
# 在 API 路由中导入使用
from base.plugins.my_plugin.schemas.my_plugin_schema import MyPluginCreate, MyPluginResponse

@router.post("/", response_model=MyPluginResponse)
async def create_item(data: MyPluginCreate):
    # 使用 schema 进行数据验证
    item = await MyPluginService.create(data.model_dump())
    return item
```

### 4. 启用插件

```bash
python -m base.cli.command enable-plugin my_plugin
```

### 5. 重启应用

重启应用以加载插件。

### 6. 在应用中使用

```python
# 在应用代码中导入插件模块
from base.plugins.my_plugin.models.my_plugin_model import MyPluginModel
from base.plugins.my_plugin.schemas.my_plugin_schema import MyPluginCreate, MyPluginResponse
from base.plugins.my_plugin.services.my_plugin_service import MyPluginService

# 使用插件功能
data = await MyPluginService.get_by_id(1)
```

## 插件 manifest.json 说明

`manifest.json` 是插件的元数据文件，包含以下字段：

```json
{
    "name": "my_plugin",                    // 插件名称（必需）
    "display_name": "My Plugin",            // 显示名称（必需）
    "version": "1.0.0",                     // 版本号（必需）
    "description": "Plugin description",    // 描述（可选）
    "author": "Author Name",                // 作者（可选）
    "is_installed": false,                  // 是否已安装（自动管理）
    "is_enabled": false,                    // 是否已启用（自动管理）
    "routes": ["api/v1/my_plugin"],         // API 路由列表（可选，会自动加载）
    "models": ["my_plugin_model"],          // 数据模型列表（可选，会自动加载）
    "schemas": ["my_plugin_schema"],        // Schema 列表（可选，仅用于文档，不自动加载）
    "dependencies": []                      // 依赖的插件（可选）
}
```

**注意**:
- `routes` 和 `models` 字段中列出的模块会在插件启用时自动加载
- `schemas` 字段仅用于文档说明，不会自动加载，需要在代码中按需 import 使用

## 注意事项

1. **插件命名规范**: 使用英文小写和下划线，如 `my_plugin`
2. **版本号**: 建议使用语义化版本号（Semantic Versioning）
3. **依赖管理**: 如果插件依赖其他插件，在 `dependencies` 字段中声明
4. **重启应用**: 启用或禁用插件后，需要重启应用才能生效
5. **数据迁移**: 如果插件包含数据模型，需要创建并运行数据库迁移
6. **权限控制**: 插件的路由默认继承应用的权限系统

## 高级用法

### 自定义插件钩子

在插件的 `__init__.py` 中可以定义以下钩子函数：

```python
async def on_enable(app) -> bool:
    """插件启用时调用"""
    # 初始化逻辑
    return True

async def on_disable() -> bool:
    """插件禁用时调用"""
    # 清理逻辑
    return True

async def on_startup() -> None:
    """应用启动时调用"""
    # 启动逻辑

async def on_shutdown() -> None:
    """应用关闭时调用"""
    # 关闭逻辑

async def on_uninstall() -> bool:
    """插件卸载时调用"""
    # 卸载逻辑
    return True
```

### 自定义路由

如果 `manifest.json` 中的 `routes` 不够灵活，可以在 `__init__.py` 中导出 `router`：

```python
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/my_plugin", tags=["My Plugin"])

@router.get("/")
async def index():
    return {"message": "Hello from my_plugin"}
```

## 常见问题

**Q: 如何更新插件？**
A: 直接修改插件代码，重启应用即可。如果修改了 manifest.json，需要重新启用插件。

**Q: 如何调试插件？**
A: 查看应用日志，插件加载和运行错误都会记录在日志中。

**Q: 插件之间可以相互调用吗？**
A: 可以，但需要在 `dependencies` 字段中声明依赖关系，确保依赖的插件先加载。

**Q: 如何创建数据库迁移？**
A: 使用 Aerich 创建迁移：
```bash
aerich migrate --name add_my_plugin_models
```

## 相关文档

- [插件管理器文档](../common/plugin_manager.py)
- [插件开发示例](../../plugins/)
- [数据库迁移指南](../../README.md)
