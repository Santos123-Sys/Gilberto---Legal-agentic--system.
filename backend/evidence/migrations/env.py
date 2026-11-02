"""Alembic environment for the evidence store.

The database URL is always supplied programmatically (see
``evidence.database.alembic_config``); there is no alembic.ini and no
credential is stored in the repository.
"""
from alembic import context

from evidence.database import make_engine
from evidence.models import Base

config = context.config
target_metadata = Base.metadata


def run_migrations_offline():
    context.configure(url=config.get_main_option("sqlalchemy.url"),
                      target_metadata=target_metadata, literal_binds=True,
                      render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    # make_engine enables SQLite foreign keys in a connect hook. Nothing may
    # run on the connection before begin_transaction(): in SQLAlchemy 2.0 any
    # statement autobegins a transaction, alembic then treats its own as
    # nested and never commits, and the revision row is silently lost.
    connectable = make_engine(config.get_main_option("sqlalchemy.url"))
    try:
        with connectable.connect() as connection:
            # One transaction for the whole upgrade: on PostgreSQL (transactional
            # DDL) a failing migration leaves no partial schema behind.
            context.configure(connection=connection, target_metadata=target_metadata,
                              render_as_batch=True, transaction_per_migration=False)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
