from sqlalchemy import text


def get_table_list(conn, schema: str) -> list:
    sql = text(
        "SELECT T.OWNER, T.TABLE_NAME, C.COMMENTS "
        "FROM ALL_TABLES T "
        "LEFT JOIN ALL_TAB_COMMENTS C ON T.OWNER = C.OWNER AND T.TABLE_NAME = C.TABLE_NAME "
        "WHERE T.OWNER = :schema "
        "ORDER BY T.TABLE_NAME"
    )
    rows = conn.execute(sql, {"schema": schema.upper()}).fetchall()
    return [
        {
            "owner": r[0],
            "table_name": r[1],
            "comment": r[2] or "",
        }
        for r in rows
    ]


def get_table_ddl(conn, schema: str, table_name: str) -> str:
    owner, tbl = _resolve_owner_and_table(conn, schema, table_name)

    col_sql = text(
        "SELECT COL.COLUMN_NAME, COL.DATA_TYPE, COL.DATA_LENGTH, COL.DATA_PRECISION, COL.DATA_SCALE, "
        "COL.NULLABLE, COL.DATA_DEFAULT, CMT.COMMENTS "
        "FROM ALL_TAB_COLUMNS COL "
        "LEFT JOIN (SELECT OWNER, TABLE_NAME, COLUMN_NAME, MAX(COMMENTS) AS COMMENTS FROM ALL_COL_COMMENTS GROUP BY OWNER, TABLE_NAME, COLUMN_NAME) CMT "
        "ON COL.OWNER = CMT.OWNER AND COL.TABLE_NAME = CMT.TABLE_NAME AND COL.COLUMN_NAME = CMT.COLUMN_NAME "
        "WHERE COL.OWNER = :owner AND COL.TABLE_NAME = :table_name "
        "ORDER BY COL.COLUMN_ID"
    )
    rows = conn.execute(col_sql, {"owner": owner, "table_name": tbl}).fetchall()

    tbl_sql = text(
        "SELECT COMMENTS FROM ALL_TAB_COMMENTS WHERE OWNER = :owner AND TABLE_NAME = :table_name"
    )
    tbl_row = conn.execute(tbl_sql, {"owner": owner, "table_name": tbl}).fetchone()
    table_comment = tbl_row[0] if tbl_row else ""

    lines = [f"-- 表: {owner}.{tbl}"]
    if table_comment:
        lines[0] += f"  ({table_comment})"
    lines.append(f"CREATE TABLE {owner}.{tbl} (")

    col_defs = []
    for r in rows:
        col_name, data_type, data_len, data_prec, data_scale, nullable, default_val, comment = r
        type_str = _format_type(data_type, data_len, data_prec, data_scale)
        null_str = "NOT NULL" if nullable == "N" else "NULL"
        default_str = f"DEFAULT {default_val.strip()}" if default_val and default_val.strip() else ""
        comment_str = f"-- {comment}" if comment else ""
        col_defs.append(f"    {col_name} {type_str} {null_str} {default_str} {comment_str}".rstrip())

    lines.append(",\n".join(col_defs))
    lines.append(");")

    pk_sql = text(
        "SELECT CC.COLUMN_NAME FROM ALL_CONSTRAINTS C "
        "JOIN ALL_CONS_COLUMNS CC ON C.OWNER = CC.OWNER AND C.CONSTRAINT_NAME = CC.CONSTRAINT_NAME "
        "WHERE C.OWNER = :owner AND C.TABLE_NAME = :table_name AND C.CONSTRAINT_TYPE = 'P' "
        "ORDER BY CC.POSITION"
    )
    pk_rows = conn.execute(pk_sql, {"owner": owner, "table_name": tbl}).fetchall()
    if pk_rows:
        pk_cols = ", ".join(r[0] for r in pk_rows)
        lines.append(f"ALTER TABLE {owner}.{tbl} ADD PRIMARY KEY ({pk_cols});")

    return "\n".join(lines)


def get_column_enum(conn, schema: str, table_name: str, column_name: str, keyword: str = "") -> list:
    owner, tbl = _resolve_owner_and_table(conn, schema, table_name)
    full_table = f"{owner}.{tbl}"

    if keyword:
        sql = text(f'SELECT DISTINCT "{column_name}" FROM {full_table} WHERE "{column_name}" LIKE :kw AND "{column_name}" IS NOT NULL LIMIT 30')
        rows = conn.execute(sql, {"kw": f"%{keyword}%"}).fetchall()
    else:
        sql = text(f'SELECT DISTINCT "{column_name}" FROM {full_table} WHERE "{column_name}" IS NOT NULL LIMIT 30')
        rows = conn.execute(sql).fetchall()

    return [str(r[0]) for r in rows]


def get_table_sample(conn, schema: str, table_name: str) -> list:
    owner, tbl = _resolve_owner_and_table(conn, schema, table_name)
    full_table = f"{owner}.{tbl}"

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


def _resolve_owner_and_table(conn, schema: str, table_name: str) -> tuple:
    owner = table_name
    tbl = table_name

    if "." in table_name:
        parts = table_name.split(".", 1)
        owner = parts[0]
        tbl = parts[1]
    else:
        chk = text(
            "SELECT OWNER FROM ALL_TABLES WHERE TABLE_NAME = :t AND OWNER NOT IN ('SYS','SYSTEM','SYSDBA','SYSSSO','SYSAUDITOR') LIMIT 1"
        )
        row = conn.execute(chk, {"t": table_name}).fetchone()
        if row:
            owner = row[0]
        else:
            owner = schema.upper()

    return owner, tbl


def _resolve_owner(conn, schema: str, table_name: str) -> str:
    owner, _ = _resolve_owner_and_table(conn, schema, table_name)
    return owner


def _format_type(data_type, data_len, data_prec, data_scale):
    dt = data_type.upper()
    if dt in ("CHAR", "VARCHAR", "VARCHAR2"):
        return f"{dt}({data_len})"
    if dt == "NUMBER":
        if data_prec is not None:
            if data_scale and data_scale > 0:
                return f"NUMBER({data_prec},{data_scale})"
            return f"NUMBER({data_prec})"
        return "NUMBER"
    if dt in ("DECIMAL", "DEC"):
        if data_prec is not None and data_scale is not None:
            return f"DECIMAL({data_prec},{data_scale})"
        return dt
    if dt == "CLOB" or dt == "BLOB" or dt == "TEXT":
        return dt
    if dt in ("DATE", "TIMESTAMP", "DATETIME", "TIME"):
        return dt
    if dt == "BIGINT":
        return "BIGINT"
    if dt == "INTEGER" or dt == "INT":
        return "INTEGER"
    return dt
