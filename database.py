from contextlib import contextmanager
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from config import SQLITE_URL

engine = create_engine(SQLITE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine)

DDL = """
CREATE TABLE IF NOT EXISTS database_config (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL UNIQUE,
    db_type     TEXT    NOT NULL,
    host        TEXT    NOT NULL DEFAULT '',
    port        INTEGER NOT NULL DEFAULT 0,
    username    TEXT    NOT NULL DEFAULT '',
    password    TEXT    NOT NULL DEFAULT '',
    database    TEXT    NOT NULL DEFAULT '',
    is_active   INTEGER NOT NULL DEFAULT 0,
    dml_allowed INTEGER NOT NULL DEFAULT 0,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

MIGRATE_ACTIVE = """
ALTER TABLE database_config ADD COLUMN is_active INTEGER NOT NULL DEFAULT 0;
"""

MIGRATE_DML = """
ALTER TABLE database_config ADD COLUMN dml_allowed INTEGER NOT NULL DEFAULT 0;
"""


def init_db():
    with engine.connect() as conn:
        conn.execute(text(DDL))
        conn.commit()
    for mig in [MIGRATE_ACTIVE, MIGRATE_DML]:
        try:
            with engine.connect() as conn:
                conn.execute(text(mig))
                conn.commit()
        except Exception:
            pass


@contextmanager
def get_session() -> Session:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
