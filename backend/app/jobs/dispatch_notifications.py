"""Bounded local batch. No scheduler or live delivery is implicitly enabled."""

from app.core.config import load_settings
from app.core.db import make_engine
from app.modules.notifications.delivery import DeliveryDisabled, get_delivery
from app.modules.notifications.service import dispatch_batch


def main():
    adapter = get_delivery()
    try:
        adapter.require_enabled()
    except DeliveryDisabled:
        raise SystemExit("Notification delivery disabled") from None
    engine = make_engine(load_settings().database_url)
    try:
        print(f"Processed notifications: {dispatch_batch(engine, adapter)}")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
