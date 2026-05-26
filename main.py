from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import text
import sys
from pathlib import Path

from config import BASE_DIR, RESOURCE_DIR
from database import init_db, get_session
from crypto import encrypt, decrypt
from db_connector import get_engine, dispose_engine
import dm_tool
import mysql_tool

app = FastAPI(title="SmartDB MCP管理系统")

init_db()

STATIC_DIR = RESOURCE_DIR / "static"


class DatabaseCreate(BaseModel):
    name: str
    db_type: str
    host: str = ""
    port: int = 0
    username: str = ""
    password: str = ""
    database: str = ""


class DatabaseUpdate(BaseModel):
    name: str | None = None
    db_type: str | None = None
    host: str | None = None
    port: int | None = None
    username: str | None = None
    password: str | None = None
    database: str | None = None


@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = STATIC_DIR / "index.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


@app.get("/api/databases")
async def list_databases():
    with get_session() as session:
        rows = session.execute(text(
            "SELECT id, name, db_type, host, port, username, database, is_active, dml_allowed, created_at, updated_at FROM database_config ORDER BY id"
        )).fetchall()
        return [
            {
                "id": r[0],
                "name": r[1],
                "db_type": r[2],
                "host": r[3],
                "port": r[4],
                "username": r[5],
                "database": r[6],
                "is_active": bool(r[7]),
                "dml_allowed": bool(r[8]),
                "created_at": str(r[9]),
                "updated_at": str(r[10]),
            }
            for r in rows
        ]


@app.post("/api/databases")
async def add_database(db: DatabaseCreate):
    encrypted_pwd = encrypt(db.password) if db.password else ""
    with get_session() as session:
        try:
            session.execute(text(
                "INSERT INTO database_config (name, db_type, host, port, username, password, database) "
                "VALUES (:name, :db_type, :host, :port, :username, :password, :database)"
            ), {
                "name": db.name,
                "db_type": db.db_type,
                "host": db.host,
                "port": db.port,
                "username": db.username,
                "password": encrypted_pwd,
                "database": db.database,
            })
            return {"success": True, "message": f"数据库 [{db.name}] 添加成功"}
        except Exception as e:
            if "UNIQUE constraint" in str(e):
                raise HTTPException(status_code=400, detail=f"数据库名称 [{db.name}] 已存在")
            raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/databases/{db_id}")
async def update_database(db_id: int, db: DatabaseUpdate):
    with get_session() as session:
        row = session.execute(text("SELECT name FROM database_config WHERE id = :id"), {"id": db_id}).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="数据库配置不存在")

        old_name = row[0]

        updates = []
        params = {"id": db_id}
        for field in ["name", "db_type", "host", "port", "username", "database"]:
            val = getattr(db, field)
            if val is not None:
                updates.append(f"{field} = :{field}")
                params[field] = val

        if db.password is not None:
            updates.append("password = :password")
            params["password"] = encrypt(db.password)

        if not updates:
            return {"success": True, "message": "无更新内容"}

        updates.append("updated_at = CURRENT_TIMESTAMP")
        sql = f"UPDATE database_config SET {', '.join(updates)} WHERE id = :id"
        session.execute(text(sql), params)

        dispose_engine(old_name)
        if db.name and db.name != old_name:
            dispose_engine(db.name)

        return {"success": True, "message": "更新成功"}


@app.delete("/api/databases/{db_id}")
async def remove_database(db_id: int):
    with get_session() as session:
        row = session.execute(text("SELECT name, is_active FROM database_config WHERE id = :id"), {"id": db_id}).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="数据库配置不存在")
        if row[1]:
            session.execute(text("UPDATE database_config SET is_active = 0 WHERE id = :id"), {"id": db_id})
        session.execute(text("DELETE FROM database_config WHERE id = :id"), {"id": db_id})
        return {"success": True, "message": f"数据库 [{row[0]}] 已删除"}


@app.post("/api/databases/{db_id}/activate")
async def activate_database(db_id: int):
    with get_session() as session:
        row = session.execute(text("SELECT name FROM database_config WHERE id = :id"), {"id": db_id}).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="数据库配置不存在")
        session.execute(text("UPDATE database_config SET is_active = 0"))
        session.execute(text("UPDATE database_config SET is_active = 1 WHERE id = :id"), {"id": db_id})
        return {"success": True, "message": f"数据库 [{row[0]}] 已启用MCP"}


@app.post("/api/databases/{db_id}/deactivate")
async def deactivate_database(db_id: int):
    with get_session() as session:
        row = session.execute(text("SELECT name FROM database_config WHERE id = :id"), {"id": db_id}).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="数据库配置不存在")
        session.execute(text("UPDATE database_config SET is_active = 0 WHERE id = :id"), {"id": db_id})
        return {"success": True, "message": f"数据库 [{row[0]}] 已停用MCP"}


@app.post("/api/databases/{db_id}/allow_dml")
async def allow_dml(db_id: int):
    with get_session() as session:
        row = session.execute(text("SELECT name FROM database_config WHERE id = :id"), {"id": db_id}).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="数据库配置不存在")
        session.execute(text("UPDATE database_config SET dml_allowed = 1 WHERE id = :id"), {"id": db_id})
        return {"success": True, "message": f"数据库 [{row[0]}] 已授权增删改"}


@app.post("/api/databases/{db_id}/forbid_dml")
async def forbid_dml(db_id: int):
    with get_session() as session:
        row = session.execute(text("SELECT name FROM database_config WHERE id = :id"), {"id": db_id}).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="数据库配置不存在")
        session.execute(text("UPDATE database_config SET dml_allowed = 0 WHERE id = :id"), {"id": db_id})
        return {"success": True, "message": f"数据库 [{row[0]}] 已禁止增删改"}


SUPPORTED_DB_TYPES = {"dm", "gbase_8a", "gbase_8c", "mysql"}

DB_TYPE_LABELS = {
    "dm": "达梦",
    "gbase_8a": "GBase 8a",
    "gbase_8c": "GBase 8c",
    "mysql": "MySQL",
}


def _get_active_db_config() -> dict:
    with get_session() as session:
        row = session.execute(text(
            "SELECT id, db_type, host, port, username, password, database, name, dml_allowed FROM database_config WHERE is_active = 1"
        )).fetchone()
        if not row:
            raise HTTPException(status_code=400, detail="未启用任何数据库，请先在管理页面启用MCP")
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


def _get_db_config(db_id: int) -> dict:
    with get_session() as session:
        row = session.execute(text(
            "SELECT db_type, host, port, username, password, database, name, dml_allowed FROM database_config WHERE id = :id"
        ), {"id": db_id}).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="数据库配置不存在")
        db_type, host, port, username, encrypted_pwd, database, name, dml_allowed = row
        pwd = decrypt(encrypted_pwd)
        return {
            "db_type": db_type,
            "host": host,
            "port": port,
            "username": username,
            "password": pwd,
            "database": database,
            "name": name,
            "dml_allowed": bool(dml_allowed),
        }


@app.post("/api/databases/{db_id}/test")
async def test_connection(db_id: int):
    config = _get_db_config(db_id)
    try:
        eng = get_engine(config)
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"success": True, "message": "连接测试成功"}
    except Exception as e:
        return {"success": False, "message": f"连接失败: {str(e)}"}


class TableListRequest(BaseModel):
    database_name: str = ""


class TableDDLRequest(BaseModel):
    database_name: str = ""
    table_name: str


class ColumnEnumRequest(BaseModel):
    database_name: str = ""
    table_name: str
    column_name: str
    keyword: str = ""


class TableSampleRequest(BaseModel):
    database_name: str = ""
    table_name: str


class VerifySQLRequest(BaseModel):
    database_name: str = ""
    sql: str


class ExecuteSQLRequest(BaseModel):
    database_name: str = ""
    sql: str


def _resolve_config(database_name: str) -> dict:
    if database_name:
        if database_name.isdigit():
            return _get_db_config(int(database_name))
        return _get_db_config_by_name(database_name)
    return _get_active_db_config()


@app.post("/api/mcp/get_table_list")
async def mcp_get_table_list(req: TableListRequest):
    config = _resolve_config(req.database_name)
    try:
        eng = get_engine(config)
        with eng.connect() as conn:
            if config["db_type"] == "dm":
                data = dm_tool.get_table_list(conn, config["database"])
            elif config["db_type"] in ("mysql", "gbase_8a"):
                data = mysql_tool.get_table_list(conn, config["database"])
            else:
                raise HTTPException(status_code=400, detail=f"数据库类型 [{config['db_type']}] 暂不支持查表列表")
            return {"success": True, "data": data}
    except HTTPException:
        raise
    except Exception as e:
        return {"success": False, "message": str(e)}


@app.post("/api/mcp/get_table_ddl")
async def mcp_get_table_ddl(req: TableDDLRequest):
    config = _resolve_config(req.database_name)
    try:
        eng = get_engine(config)
        with eng.connect() as conn:
            if config["db_type"] == "dm":
                ddl = dm_tool.get_table_ddl(conn, config["database"], req.table_name)
            elif config["db_type"] in ("mysql", "gbase_8a"):
                ddl = mysql_tool.get_table_ddl(conn, config["database"], req.table_name)
            else:
                raise HTTPException(status_code=400, detail=f"数据库类型 [{config['db_type']}] 暂不支持查表结构")
            return {"success": True, "data": ddl}
    except HTTPException:
        raise
    except Exception as e:
        return {"success": False, "message": str(e)}


@app.post("/api/mcp/get_column_enum")
async def mcp_get_column_enum(req: ColumnEnumRequest):
    config = _resolve_config(req.database_name)
    try:
        eng = get_engine(config)
        with eng.connect() as conn:
            if config["db_type"] == "dm":
                values = dm_tool.get_column_enum(conn, config["database"], req.table_name, req.column_name, req.keyword)
            elif config["db_type"] in ("mysql", "gbase_8a"):
                values = mysql_tool.get_column_enum(conn, config["database"], req.table_name, req.column_name, req.keyword)
            else:
                raise HTTPException(status_code=400, detail=f"数据库类型 [{config['db_type']}] 暂不支持查枚举值")
            return {"success": True, "data": ";".join(values)}
    except HTTPException:
        raise
    except Exception as e:
        return {"success": False, "message": str(e)}


@app.post("/api/mcp/get_table_sample")
async def mcp_get_table_sample(req: TableSampleRequest):
    config = _resolve_config(req.database_name)
    try:
        eng = get_engine(config)
        with eng.connect() as conn:
            if config["db_type"] == "dm":
                data = dm_tool.get_table_sample(conn, config["database"], req.table_name)
            elif config["db_type"] in ("mysql", "gbase_8a"):
                data = mysql_tool.get_table_sample(conn, config["database"], req.table_name)
            else:
                raise HTTPException(status_code=400, detail=f"数据库类型 [{config['db_type']}] 暂不支持查样例数据")
            return {"success": True, "data": data}
    except HTTPException:
        raise
    except Exception as e:
        return {"success": False, "message": str(e)}


@app.post("/api/mcp/verify_sql")
async def mcp_verify_sql(req: VerifySQLRequest):
    config = _resolve_config(req.database_name)
    try:
        eng = get_engine(config)
        with eng.connect() as conn:
            if config["db_type"] == "dm":
                result = dm_tool.verify_sql(conn, req.sql)
            elif config["db_type"] in ("mysql", "gbase_8a"):
                result = mysql_tool.verify_sql(conn, req.sql)
            else:
                raise HTTPException(status_code=400, detail=f"数据库类型 [{config['db_type']}] 暂不支持SQL校验")
            return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        return {"success": False, "message": str(e)}


@app.post("/api/mcp/execute_sql")
async def mcp_execute_sql(req: ExecuteSQLRequest):
    config = _resolve_config(req.database_name)
    try:
        eng = get_engine(config)
        with eng.connect() as conn:
            if config["db_type"] == "dm":
                result = dm_tool.execute_sql(conn, req.sql, config.get("dml_allowed", False))
            elif config["db_type"] in ("mysql", "gbase_8a"):
                result = mysql_tool.execute_sql(conn, req.sql, config.get("dml_allowed", False))
            else:
                raise HTTPException(status_code=400, detail=f"数据库类型 [{config['db_type']}] 暂不支持执行SQL")
            return result
    except HTTPException:
        raise
    except Exception as e:
        return {"success": False, "message": str(e)}


def _get_db_config_by_name(name: str) -> dict:
    with get_session() as session:
        row = session.execute(text(
            "SELECT db_type, host, port, username, password, database, name, dml_allowed FROM database_config WHERE name = :name"
        ), {"name": name}).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"数据库配置 [{name}] 不存在")
        db_type, host, port, username, encrypted_pwd, database, n, dml_allowed = row
        pwd = decrypt(encrypted_pwd)
        return {
            "db_type": db_type,
            "host": host,
            "port": port,
            "username": username,
            "password": pwd,
            "database": database,
            "name": n,
            "dml_allowed": bool(dml_allowed),
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8765)
