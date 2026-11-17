from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from .config import settings


engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_timeout=3,
    connect_args={"connect_timeout": 3, "options": "-c statement_timeout=15000"},
)


SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
