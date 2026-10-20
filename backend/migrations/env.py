from alembic import context
from jarvis.config import Settings
from jarvis.db import Base
from sqlalchemy import create_engine

settings = Settings()
settings.prepare()
engine = create_engine(settings.db_url)
with engine.connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()
