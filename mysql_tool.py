from sqlalchemy import text


def get_table_list(conn, schema: str) -> list:
    sql = text(
        "SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_COMMENT "
        "FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA = :schema AND TABLE_TYPE = 'BASE TABLE' "
        "ORDER BY TABLE_NAME"
    )
    rows = conn.execute(sql, {"schema": schema}).fetchall()
    return [
        {
            "owner": r[0],
            "table_name": r[1],
            "comment": r[2] or "",
        }
        for r in rows
    ]


def get_table_ddl(conn, schema: str, table_name: str) -> str:
    database, tbl = _resolve_database_and_table(conn, schema, table_name)

    col_sql = text(
        "SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, NUMERIC_PRECISION, NUMERIC_SCALE, "
        "IS_NULLABLE, COLUMN_DEFAULT, COLUMN_COMMENT, COLUMN_TYPE "
        "FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = :database AND TABLE_NAME = :table_name "
        "ORDER BY ORDINAL_POSITION"
    )
    rows = conn.execute(col_sql, {"database": database, "table_name": tbl}).fetchall()

    tbl_sql = text(
        "SELECT TABLE_COMMENT FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA = :database AND TABLE_NAME = :table_name AND TABLE_TYPE = 'BASE TABLE'"
    )
    tbl_row = conn.execute(tbl_sql, {"database": database, "table_name": tbl}).fetchone()
    table_comment = tbl_row[0] if tbl_row else ""

    lines = [f"-- 表: {database}.{tbl}"]
    if table_comment:
        lines[0] += f"  ({table_comment})"
    lines.append(f"CREATE TABLE `{database}`.`{tbl}` (")

    col_defs = []
    for r in rows:
        col_name, data_type, char_max_len, num_prec, num_scale, nullable, default_val, comment, column_type = r
        type_str = _format_type(data_type, char_max_len, num_prec, num_scale, column_type)
        null_str = "NOT NULL" if nullable == "NO" else "NULL"
        default_str = f"DEFAULT {default_val.strip()}" if default_val and default_val.strip() else ""
        comment_str = f"-- {comment}" if comment else ""
        col_defs.append(f"    `{col_name}` {type_str} {null_str} {default_str} {comment_str}".rstrip())

    lines.append(",\n".join(col_defs))
    lines.append(");")

    pk_sql = text(
        "SELECT k.COLUMN_NAME "
        "FROM information_schema.TABLE_CONSTRAINTS t "
        "JOIN information_schema.KEY_COLUMN_USAGE k "
        "ON t.CONSTRAINT_NAME = k.CONSTRAINT_NAME "
        "AND t.TABLE_SCHEMA = k.TABLE_SCHEMA "
        "AND t.TABLE_NAME = k.TABLE_NAME "
        "WHERE t.CONSTRAINT_TYPE = 'PRIMARY KEY' "
        "AND t.TABLE_SCHEMA = :database AND t.TABLE_NAME = :table_name "
        "ORDER BY k.ORDINAL_POSITION"
    )
    pk_rows = conn.execute(pk_sql, {"database": database, "table_name": tbl}).fetchall()
    if pk_rows:
        pk_cols = ", ".join(f"`{r[0]}`" for r in pk_rows)
        lines.append(f"ALTER TABLE `{database}`.`{tbl}` ADD PRIMARY KEY ({pk_cols});")

    return "\n".join(lines)


def get_column_enum(conn, schema: str, table_name: str, column_name: str, keyword: str = "") -> list:
    database, tbl = _resolve_database_and_table(conn, schema, table_name)
    full_table = f"`{database}`.`{tbl}`"

    if keyword:
        sql = text(
            f"SELECT DISTINCT `{column_name}` FROM {full_table} "
            f"WHERE `{column_name}` LIKE :kw AND `{column_name}` IS NOT NULL LIMIT 30"
        )
        rows = conn.execute(sql, {"kw": f"%{keyword}%"}).fetchall()
    else:
        sql = text(
            f"SELECT DISTINCT `{column_name}` FROM {full_table} "
            f"WHERE `{column_name}` IS NOT NULL LIMIT 30"
        )
        rows = conn.execute(sql).fetchall()

    return [str(r[0]) for r in rows]


def get_table_sample(conn, schema: str, table_name: str) -> list:
    database, tbl = _resolve_database_and_table(conn, schema, table_name)
    full_table = f"`{database}`.`{tbl}`"

    sql = text(f"SELECT * FROM {full_table} LIMIT 3")
    result = conn.execute(sql)
    columns = list(result.keys())
    rows = result.fetchall()

    return [dict(zip(columns, row)) for row in rows]


def verify_sql(conn, sql_str: str) -> dict:
    try:
        wrapped = f"SELECT * FROM ({sql_str}) _verify_tmp_ WHERE 1 = 0"
        conn.execute(text(wrapped))
        return {"valid": True, "error": None}
    except Exception as e:
        return {"valid": False, "error": str(e)}


def execute_sql(conn, sql_str: str, dml_allowed: bool = False) -> dict:
    sql_upper = sql_str.strip().upper()
    is_select = sql_upper.startswith("SELECT") or sql_upper.startswith("WITH")

    if not is_select and not dml_allowed:
        return {"success": False, "message": "当前数据库未授权增删改操作，请在管理页面开启授权"}

    if is_select:
        if "LIMIT" not in sql_upper:
            sql_str = sql_str.rstrip(";") + " LIMIT 100"

    try:
        result = conn.execute(text(sql_str))
        if is_select or sql_upper.startswith("WITH"):
            columns = list(result.keys())
            rows = result.fetchall()
            data = [dict(zip(columns, row)) for row in rows]
            return {"success": True, "type": "query", "data": data, "row_count": len(data)}
        else:
            affected = result.rowcount
            return {"success": True, "type": "dml", "affected_rows": affected}
    except Exception as e:
        return {"success": False, "message": str(e)}


def _resolve_database_and_table(conn, schema: str, table_name: str) -> tuple:
    database = schema
    tbl = table_name

    if "." in table_name:
        parts = table_name.split(".", 1)
        database = parts[0]
        tbl = parts[1]
    else:
        chk = text(
            "SELECT TABLE_SCHEMA FROM information_schema.TABLES "
            "WHERE TABLE_NAME = :t AND TABLE_TYPE = 'BASE TABLE' LIMIT 1"
        )
        row = conn.execute(chk, {"t": table_name}).fetchone()
        if row:
            database = row[0]

    return database, tbl


def _format_type(data_type, char_max_len, num_prec, num_scale, column_type):
    if column_type and column_type.upper() != data_type.upper():
        return column_type

    dt = data_type.upper()
    if dt in ("CHAR", "VARCHAR"):
        return f"{dt}({char_max_len})"
    if dt in ("DECIMAL", "NUMERIC"):
        if num_prec is not None and num_scale is not None:
            return f"{dt}({num_prec},{num_scale})"
        return dt
    if dt in ("TINYINT", "SMALLINT", "MEDIUMINT", "INT", "INTEGER", "BIGINT"):
        return dt
    if dt in ("FLOAT", "DOUBLE", "REAL"):
        return dt
    if dt in ("DATE", "DATETIME", "TIMESTAMP", "TIME", "YEAR"):
        return dt
    if dt in ("TINYTEXT", "TEXT", "MEDIUMTEXT", "LONGTEXT",
              "TINYBLOB", "BLOB", "MEDIUMBLOB", "LONGBLOB",
              "JSON", "ENUM", "SET"):
        return dt
    return column_type or dt