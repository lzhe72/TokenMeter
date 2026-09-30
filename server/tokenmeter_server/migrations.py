from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text

from .database import make_engine

SCHEMA_VERSION = "0001"


def migrate(database_url: str, revision: str = "head") -> None:
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).parents[1] / "migrations"))
    engine = make_engine(database_url)
    try:
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, revision)
    finally:
        engine.dispose()


def assert_schema(engine) -> None:
    with engine.connect() as connection:
        version = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    if version != SCHEMA_VERSION:
        raise RuntimeError("Database schema does not match this server; run the migration CLI")
