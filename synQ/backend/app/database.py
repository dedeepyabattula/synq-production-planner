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
    _ensure_schema_patches()


def _ensure_schema_patches():
    """
    Small, idempotent, additive column patches for fields added to a model
    after a database was first created.

    This project doesn't use a migration framework (Alembic) — normally
    that's fine, because `create_all()` above creates any missing TABLES on
    every startup. But it does NOT add new columns to a table that already
    exists, and on a persistent database (Postgres on Vercel, unlike the
    local SQLite file which effectively starts fresh) that matters: once the
    `machines` table has been created once, later model changes like the
    `repair_duration_minutes` column would otherwise never actually appear in
    the live database, and every query touching it would fail.

    Safe to call on every startup: it inspects the live schema first and only
    adds a column if it's actually missing.
    """
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    if "machines" not in inspector.get_table_names():
        return  # create_all() above just created it fresh, column included

    existing_cols = {c["name"] for c in inspector.get_columns("machines")}
    if "repair_duration_minutes" in existing_cols:
        return

    with engine.begin() as conn:
        if engine.dialect.name == "postgresql":
            conn.execute(text("ALTER TABLE machines ADD COLUMN IF NOT EXISTS repair_duration_minutes FLOAT"))
        elif engine.dialect.name == "sqlite":
            conn.execute(text("ALTER TABLE machines ADD COLUMN repair_duration_minutes FLOAT"))
        # Other dialects aren't used by this project; intentionally not handled.
