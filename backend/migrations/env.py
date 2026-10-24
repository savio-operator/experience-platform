from alembic import context

from app.core.config import load_settings
from app.core.db import make_engine, metadata
from app.modules.customers import models as customer_models  # noqa: F401
from app.modules.identity import models as identity_models  # noqa: F401

settings = load_settings()
engine = make_engine(settings.database_url)
try:
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=metadata)
        with context.begin_transaction():
            context.run_migrations()
finally:
    engine.dispose()
