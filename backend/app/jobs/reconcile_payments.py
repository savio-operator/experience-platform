"""One bounded batch; disabled until a provider is separately approved."""

import asyncio

from app.core.config import load_settings
from app.core.db import make_engine
from app.modules.payments.gateway import GatewayDisabled, get_gateway
from app.modules.payments.service import reconcile_batch


def main():
    gateway = get_gateway()
    try:
        gateway.require_enabled()
    except GatewayDisabled:
        raise SystemExit("Payment gateway disabled") from None
    engine = make_engine(load_settings().database_url)
    try:
        print(f"Reconciled payments: {asyncio.run(reconcile_batch(engine, gateway))}")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
