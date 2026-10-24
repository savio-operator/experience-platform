from alembic import context

from app.core.config import load_settings
from app.core.db import make_engine, metadata
from app.modules.audit import models as audit_models  # noqa: F401
from app.modules.bookings import models as booking_models  # noqa: F401
from app.modules.catalogue import models as catalogue_models  # noqa: F401
from app.modules.customers import models as customer_models  # noqa: F401
from app.modules.identity import models as identity_models  # noqa: F401
from app.modules.inventory import models as inventory_models  # noqa: F401
from app.modules.notifications import models as notification_models  # noqa: F401
from app.modules.payments import models as payment_models  # noqa: F401
from app.modules.planning import models as planning_models  # noqa: F401
from app.modules.vendors import models as vendor_models  # noqa: F401

settings = load_settings()
engine = make_engine(settings.database_url)
try:
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=metadata)
        with context.begin_transaction():
            context.run_migrations()
finally:
    engine.dispose()
