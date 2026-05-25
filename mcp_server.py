import sys
import os
import json
from mcp.server.fastmcp import FastMCP

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import init_db, get_session
from crypto import decrypt
from db_connector import get_engine
from sqlalchemy import text
import dm_tool

init_db()

mcp = FastMCP("SmartDB")

_CONFIG_SQL = "SELECT id, db_type, host, port, username, password, database, name, dml_allowed FROM database_config"


def _row_to_config(row) -> dict:
    db_id, db_type, host, port, username, encrypted_pwd, database, name, dml_allowed = row
    pwd = decrypt(encrypted_pwd)
    return {
        "id": db_id,
        "db_type": db_type,
        "host": host,
        "port": port,
        "username": username,
        "password": pwd,
        "database": database,
        "name": name,
        "dml_allowed": bool(dml_allowed),
    }


def _get_active_config() -> dict:
    with get_session() as session:
        row = session.execute(text(f"{_CONFIG_SQL} WHERE is_active = 1")).fetchone()
        if not row:
            raise ValueError("未启用任何数据库，请先在管理页面启用MCP")
        return _row_to_config(row)


def _get_config_by_id(db_id: int) -> dict:
    with get_session() as session:
        row = session.execute(text(f"{_CONFIG_SQL} WHERE id = :id"), {"id": db_id}).fetchone()
        if not row:
            raise ValueError(f"数据库配置ID [{db_id}] 不存在")
        return _row_to_config(row)


def _get_config_by_name(name: str) -> dict:
    with get_session() as session:
        row = session.execute(text(f"{_CONFIG_SQL} WHERE name = :name"), {"name": name}).fetchone()
        if not row:
            raise ValueError(f"数据库配置 [{name}] 不存在")
        return _row_to_config(row)


def _resolve_config(database_name: str = "") -> dict:
    if database_name:
        if database_name.isdigit():
            return _get_config_by_id(int(database_name))
        return _get_config_by_name(database_name)
    return _get_active_config()


@mcp.tool()
def get_table_list(database_name: str = "") -> str:
    """查询数据库中所有表的列表。
    返回每个表的 owner、表名和注释，用于了解数据库中有哪些表。

    Args:
        database_name: 数据库名称或ID，为空则使用当前启用的数据库

    Returns:
        表列表，每项包含 owner（所属模式）、table_name（表名）、comment（表注释）
    """
    config = _resolve_config(database_name)
    eng = get_engine(config)
    with eng.connect() as conn:
        if config["db_type"] == "dm":
            data = dm_tool.get_table_list(conn, config["database"])
        else:
            return json.dumps({"error": f"数据库类型 [{config['db_type']}] 暂不支持查表列表"}, ensure_ascii=False)
        return json.dumps(data, ensure_ascii=False)


@mcp.tool()
def get_table_ddl(table_name: str, database_name: str = "") -> str:
    """获取指定表的字段结构（DDL），包含字段名、类型和业务含义描述。
    拿到字段信息后可用于生成 SQL 的 SELECT 字句和 WHERE 条件。

    Args:
        table_name: 表名（中文或英文均可，支持 OWNER.TABLE 格式）
        database_name: 数据库名称或ID，为空则使用当前启用的数据库

    Returns:
        DDL 文本，包含所有字段定义和业务描述注释
    """
    config = _resolve_config(database_name)
    eng = get_engine(config)
    with eng.connect() as conn:
        if config["db_type"] == "dm":
            ddl = dm_tool.get_table_ddl(conn, config["database"], table_name)
        else:
            return f"数据库类型 [{config['db_type']}] 暂不支持查表结构"
        return ddl


@mcp.tool()
def get_column_enum(table_name: str, column_name: str, database_name: str = "", column_value: str = "") -> str:
    """查询指定字段的枚举/字典值（最多返回30条去重值）。
    用于在生成 SQL 的 WHERE 条件时确认字段的合法取值范围。
    字段的枚举信息通常也会附在 DDL 的注释中，若 DDL 中已有则无需重复调用。

    Args:
        table_name: 表名
        column_name: 字段名（从 get_table_ddl 返回的字段中选取）
        database_name: 数据库名称或ID，为空则使用当前启用的数据库
        column_value: 可选，枚举值关键字，有值时直接用该值 LIKE 过滤结果

    Returns:
        字段枚举值列表（格式：值1;值2;值3...），最多30条
    """
    config = _resolve_config(database_name)
    eng = get_engine(config)
    with eng.connect() as conn:
        if config["db_type"] == "dm":
            values = dm_tool.get_column_enum(conn, config["database"], table_name, column_name, column_value)
        else:
            return f"数据库类型 [{config['db_type']}] 暂不支持查枚举值"
        return ";".join(values)


@mcp.tool()
def get_table_simple_data(table_name: str, database_name: str = "") -> str:
    """获取指定表的前三行数据

    Args:
        table_name: 表名（中文） 必填
        database_name: 数据库名 必填，为空则使用当前启用的数据库

    Returns:
        data: 数据
    """
    config = _resolve_config(database_name)
    eng = get_engine(config)
    with eng.connect() as conn:
        if config["db_type"] == "dm":
            data = dm_tool.get_table_sample(conn, config["database"], table_name)
        else:
            return json.dumps({"error": f"数据库类型 [{config['db_type']}] 暂不支持查样例数据"}, ensure_ascii=False)
        return json.dumps(data, ensure_ascii=False, default=str)


@mcp.tool()
def verify_sql(sql: str, database_name: str = "") -> str:
    """验证sql 正确性

    Args:
        sql: 生成的sql
        database_name: 数据库名称或ID，为空则使用当前启用的数据库

    Returns:
        data: 数据
    """
    config = _resolve_config(database_name)
    eng = get_engine(config)
    with eng.connect() as conn:
        if config["db_type"] == "dm":
            result = dm_tool.verify_sql(conn, sql)
        else:
            return json.dumps({"valid": False, "error": f"数据库类型 [{config['db_type']}] 暂不支持SQL校验"}, ensure_ascii=False)
        return json.dumps(result, ensure_ascii=False)


@mcp.tool()
def execute_sql(sql: str, database_name: str = "") -> str:
    """直接执行SQL语句，支持增删改查。
    - 查询语句（SELECT/WITH）自动限制最多返回100行
    - 增删改语句（INSERT/UPDATE/DELETE）需要在管理页面先授权，否则会被拒绝

    Args:
        sql: 要执行的SQL语句
        database_name: 数据库名称或ID，为空则使用当前启用的数据库

    Returns:
        查询返回数据列表和行数，增删改返回影响行数，未授权返回错误信息
    """
    config = _resolve_config(database_name)
    eng = get_engine(config)
    with eng.connect() as conn:
        if config["db_type"] == "dm":
            result = dm_tool.execute_sql(conn, sql, config.get("dml_allowed", False))
        else:
            return json.dumps({"success": False, "message": f"数据库类型 [{config['db_type']}] 暂不支持执行SQL"}, ensure_ascii=False)
        return json.dumps(result, ensure_ascii=False, default=str)


if __name__ == "__main__":
    mcp.run(transport="stdio")
