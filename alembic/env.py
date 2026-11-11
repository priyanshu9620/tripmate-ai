"""Alembic env: URL comes from DATABASE_URL (or -x / alembic.ini for manual runs)."""

import os

from alembic import context
from sqlalchemy import engine_from_config, pool

from tripmate.db import Base

config = context.config
url = os.environ.get("DATABASE_URL")
if url:
    config.set_main_option("sqlalchemy.url", url.replace("postgresql://", "postgresql+psycopg://"))
target_metadata = Base.metadata


def run_migrations_online() -> None:
    connectable = engine_from_config(config.get_section(config.config_ini_section, {}), poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
