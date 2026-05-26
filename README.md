# SmartDB MCP

智能数据库查询 MCP 服务，支持在 AI 编程工具（如 Trae、Claude Desktop）中用自然语言查询数据库。

## 功能特性

- 🔌 **MCP 协议**：标准 stdio 传输，直接集成到 Trae / Claude Desktop 等 AI 工具
- 🌐 **Web 管理后台**：浏览器配置数据库连接，无需改配置文件
- 🛡️ **安全控制**：密码加密存储，增删改需单独授权，查询自动限制 100 行
- 🗄️ **多数据库支持**：达梦 (DM)、MySQL、GBase 8a、GBase 8c
- 📦 **单文件分发**：打包成单个 EXE，拷贝即用

## 📥 直接下载

Windows 用户可直接下载打包好的 EXE，无需安装 Python 环境：

🔗 [smart-db-mcp.exe (v1.1.0)](https://github.com/zhaoran025/smart-db-mcp/releases/download/v1.1.0/smart-db-mcp.exe)

两种使用方式：

**方式一：直接配到 MCP 里用**

在 Trae / Claude Desktop 的 MCP 配置中指向 EXE 即可启用：

```json
{
  "mcpServers": {
    "smart-db-mcp": {
      "command": "C:\\path\\to\\smart-db-mcp.exe",
      "args": []
    }
  }
}
```

配置后如需管理数据库连接，浏览器打开 `http://127.0.0.1:8765` 进入后台。

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/

# 达梦数据库驱动（vendor 目录已提供，离线安装即可）
pip install vendor/dmpython-2.5.32-cp311-cp311-win_amd64.whl vendor/dmsqlalchemy-2.0.12-py3-none-any.whl
```

> 达梦驱动仅支持 Windows x64 + Python 3.11，其他平台请从达梦官方获取对应版本。

### 配置到 Trae

在 Trae 的 MCP 配置中添加：

```json
{
  "mcpServers": {
    "smart-db-mcp": {
      "command": "python",
      "args": ["C:\\path\\to\\run.py"]
    }
  }
}
```

或使用打包好的 EXE：

```json
{
  "mcpServers": {
    "smart-db-mcp": {
      "command": "C:\\path\\to\\smart-db-mcp.exe",
      "args": []
    }
  }
}
```

### 配置数据库

1. 启动服务后，浏览器打开 `http://127.0.0.1:8765`
2. 点击「新增数据库」，填写连接信息
3. 点击「启用」激活 MCP 查询目标
4. 在 AI 对话中即可用自然语言查询

## 打包 EXE

```bash
pip install pyinstaller -i https://mirrors.aliyun.com/pypi/simple/
python -m PyInstaller smart-db-mcp.spec --noconfirm
```

打包产物在 `dist/smart-db-mcp.exe`，单文件可直接分发。

## 智能体提示词

为了让 AI 更好地使用 MCP 工具，建议在智能体中配置以下提示词：

```
你是一个专业的数据库查询助手，擅长根据用户的自然语言需求生成准确的 SQL 语句。你可以通过 MCP 工具访问数据库元数据来辅助生成 SQL。

## 工作流程

当用户提出数据查询需求时，按以下步骤操作：

### 第一步：了解数据库结构
调用 `get_table_list` 获取所有表列表，了解有哪些表可用。根据用户提到的业务关键词（如"合同"、"凭证"、"资产"等）匹配表名或表注释，锁定相关表。

### 第二步：查看表字段详情
对锁定的表调用 `get_table_ddl`，获取完整的字段结构、类型和业务注释。重点关注：
- 字段名和业务含义
- 字段类型（VARCHAR/NUMBER/DATE 等）
- 主键字段
- 注释中的枚举值说明

### 第三步：确认枚举值（如需要）
如果 WHERE 条件涉及状态、类型等字段，且 DDL 注释中未明确枚举值，调用 `get_column_enum` 查询该字段的实际取值范围，避免猜测错误。

### 第四步：查看样例数据（如需要）
如果对字段含义仍有疑问，调用 `get_table_simple_data` 查看前 3 行数据，帮助理解数据格式和内容。

### 第五步：生成 SQL
根据以上信息生成 SQL，并调用 `verify_sql` 校验语法正确性。如果校验失败，根据错误信息修正后重新校验。

### 第六步：执行查询
SQL 校验通过后，调用 `execute_sql` 执行查询，将结果以清晰的表格或列表形式呈现给用户。

## 重要规则

1. **永远不要猜测字段名或枚举值**，必须先查 DDL 和枚举再生成 SQL
2. **表名必须带 OWNER 前缀**，格式为 `OWNER.TABLE_NAME`（如 `DEV.ai_task_result`），从 `get_table_list` 返回的 owner 和 table_name 拼接
3. **SELECT 语句会自动限制 100 行**，无需手动加 LIMIT，除非需要更少的数据
4. **INSERT/UPDATE/DELETE 需要用户明确确认后才能执行**，且需页面已授权增删改，未授权时告知用户去管理页面开启
5. 生成 SQL 时优先使用注释中明确的枚举值作为 WHERE 条件
6. 涉及多表关联时，先分别查 DDL 确认关联字段
7. 如果用户需求模糊，主动追问澄清，不要自行假设
8. 查询结果为空时，建议用户检查筛选条件或查看样例数据确认数据内容

## 输出格式

- 列出查询结果
- 对查询结果做简要分析说明
```

## 项目结构

```
├── run.py              # 统一入口（MCP + Web）
├── mcp_server.py       # MCP 服务（stdio）
├── main.py             # Web 管理后台（FastAPI）
├── config.py           # 配置（路径解析）
├── database.py         # SQLite 配置库
├── db_connector.py     # 数据库连接引擎
├── dm_tool.py          # 达梦数据库工具函数
├── mysql_tool.py       # MySQL 数据库工具函数
├── crypto.py           # 密码加密/解密
├── static/
│   └── index.html      # Web 管理页面
├── requirements.txt    # Python 依赖
├── smart-db-mcp.spec   # PyInstaller 打包配置
└── LICENSE             # MIT 许可证
```

## MCP 工具列表

| 工具 | 说明 |
|------|------|
| `get_table_list` | 获取数据库中所有表列表（含 owner、表名、注释） |
| `get_table_ddl` | 获取指定表的字段结构（含字段名、类型、业务注释） |
| `get_column_enum` | 获取指定字段的枚举/字典值（最多30条） |
| `get_table_simple_data` | 获取指定表的前3行样例数据 |
| `verify_sql` | 校验 SQL 语法正确性 |
| `execute_sql` | 执行 SQL 语句（查询自动限制100行） |

## 支持的数据库

| 数据库 | 类型标识 | 默认端口 |
|--------|----------|----------|
| 达梦 (DM) | `dm` | 5236 |
| MySQL | `mysql` | 3306 |
| GBase 8a | `gbase_8a` | 5258 |
| GBase 8c | `gbase_8c` | 5432 |

## License

[MIT](LICENSE)
