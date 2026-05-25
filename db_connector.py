from urllib.parse import quote_plus
from sqlalchemy import create_engine, text
from sqlalchemy.dialects import registry

registry.register("dm", "dmSQLAlchemy.dmPython", "DMDialect_dmPython")
registry.register("dm.dmPython", "dmSQLAlchemy.dmPython", "DMDialect_dmPython")

_engine_cache = {}


def _build_url_and_args(db_type: str, host: str, port: int, username: str, pwd: str, database: str) -> tuple:
    if db_type == "dm":
        url = f"dm+dmPython://{quote_plus(username)}:{quote_plus(pwd)}@{host}:{port}"
        return url, {"schema": database, "local_code": 1}
    if db_type == "gbase_8a":
        url = f"mysql+pymysql://{quote_plus(username)}:{quote_plus(pwd)}@{host}:{port}/{database}?charset=utf8mb4"
        return url, {}
    if db_type == "gbase_8c":
        url = f"postgresql+psycopg2://{quote_plus(username)}:{quote_plus(pwd)}@{host}:{port}/{database}"
        return url, {}
    raise ValueError(f"不支持的数据库类型: {db_type}")


def get_engine(db_config: dict):
    key = db_config["name"]
    if key in _engine_cache:
        return _engine_cache[key]

    url, connect_args = _build_url_and_args(
        db_config["db_type"],
        db_config["host"],
        db_config["port"],
        db_config["username"],
        db_config["password"],
        db_config["database"],
    )
    eng = create_engine(url, pool_pre_ping=True, connect_args=connect_args, pool_size=5, pool_recycle=1800)
    _engine_cache[key] = eng
    return eng


def dispose_engine(name: str):
    if name in _engine_cache:
        _engine_cache[name].dispose()
        del _engine_cache[name]
