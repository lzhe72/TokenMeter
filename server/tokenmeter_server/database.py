"""Database setup and explicitly serialized SQLite write transactions."""
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session


def make_engine(url: str):
    if not url:
        raise ValueError("TOKENMETER_DATABASE_URL must be explicitly configured")
    engine = create_engine(url, pool_pre_ping=True)
    if engine.dialect.name == "sqlite":
        @event.listens_for(engine, "connect")
        def sqlite_connect(connection, _record):
            # Explicit BEGIN makes SQLite DDL transactional as well.
            connection.isolation_level = None
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=10000")
            cursor.close()

        @event.listens_for(engine, "begin")
        def sqlite_begin(connection):
            mode = connection.get_execution_options().get("tokenmeter_write", False)
            connection.exec_driver_sql("BEGIN IMMEDIATE" if mode else "BEGIN")
    return engine


@contextmanager
def transaction(engine, *, write=False):
    with engine.connect().execution_options(tokenmeter_write=write) as connection:
        with connection.begin():
            with Session(bind=connection, expire_on_commit=False) as session:
                yield session
                session.flush()
