"""Engine, sessions and schema-version checks for the evidence store."""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


class EvidenceStoreDisabled(RuntimeError):
    pass


class SchemaVersionMismatch(RuntimeError):
    pass


def make_engine(url: str) -> Engine:
    if not url:
        raise EvidenceStoreDisabled("EVIDENCE_DATABASE_URL is not configured")
    engine = create_engine(url, future=True, pool_pre_ping=True)
    if engine.dialect.name == "sqlite":
        @event.listens_for(engine, "connect")
        def _sqlite_foreign_keys(dbapi_conn, _record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    return engine


def make_session_factory(engine: Engine):
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


@contextmanager
def transaction(session_factory):
    """One atomic unit of work: commit on success, roll back on any error."""
    session = session_factory()
    try:
        yield session
        session.commit()
    except BaseException:
        session.rollback()
        raise
    finally:
        session.close()


def alembic_config(url: str):
    from alembic.config import Config
    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return cfg


def head_revision(url: str) -> str:
    from alembic.script import ScriptDirectory
    return ScriptDirectory.from_config(alembic_config(url)).get_current_head()


def current_revision(engine: Engine) -> str | None:
    if "alembic_version" not in inspect(engine).get_table_names():
        return None
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT version_num FROM alembic_version")).fetchall()
    return rows[0][0] if len(rows) == 1 else None


def require_current_schema(engine: Engine) -> None:
    """Fail closed if the database is not exactly at this code's head revision."""
    expected = head_revision(engine.url.render_as_string(hide_password=False))
    actual = current_revision(engine)
    if actual != expected:
        raise SchemaVersionMismatch(
            f"evidence schema is at {actual or 'no revision'}, code expects {expected}")


def upgrade(url: str, revision: str = "head") -> None:
    from alembic import command
    command.upgrade(alembic_config(url), revision)


def downgrade(url: str, revision: str) -> None:
    from alembic import command
    command.downgrade(alembic_config(url), revision)
