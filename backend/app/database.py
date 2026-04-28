"""Database engine and session factory."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.config import get_settings
from app.models.db import Base


settings = get_settings()
_url = settings.database_url
_is_sqlite = _url.startswith("sqlite")

if _is_sqlite:
    engine = create_engine(_url, connect_args={"check_same_thread": False})
else:
    # Supabase's transaction-mode pooler (port 6543) recycles connections
    # aggressively; pool_pre_ping avoids "server closed the connection" on
    # idle checkouts. Keep the pool small to stay under the pooler's limits.
    engine = create_engine(
        _url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        pool_recycle=300,
    )
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
