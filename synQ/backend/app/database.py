from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./synq.db")

# Vercel Postgres / Neon / Supabase / Heroku-style providers commonly hand out
# a URL starting with "postgres://", but SQLAlchemy 2.x requires the
# "postgresql://" scheme (and psycopg2 as the driver) — normalize it here so
# whatever the provider gives you works without editing the URL by hand.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

_is_sqlite = DATABASE_URL.startswith("sqlite")

# check_same_thread is a SQLite-specific connect arg; passing it to a
# Postgres driver would raise a TypeError, so it's only included for sqlite
# URLs. For Postgres we also use pool_pre_ping so a connection that's gone
# stale (common with serverless functions and managed Postgres connection
# limits) is detected and replaced instead of surfacing as a 500.
if _is_sqlite:
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=False,
    )
else:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        echo=False,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
