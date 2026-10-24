from sqlalchemy import MetaData, create_engine

metadata = MetaData()


def make_engine(database_url: str):
    return create_engine(
        database_url,
        pool_pre_ping=True,
        hide_parameters=True,
        connect_args={
            "connect_timeout": 5,
            "options": "-c statement_timeout=5000 -c lock_timeout=3000",
        },
    )
