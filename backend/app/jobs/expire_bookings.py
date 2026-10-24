"""Run one bounded local batch; scheduling is external, never implicit."""

from app.core.config import load_settings
from app.core.db import make_engine
from app.modules.bookings.service import expire


def main():
    engine = make_engine(load_settings().database_url)
    try:
        print(f"Expired bookings: {expire(engine)}")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
