"""
SynQ FastAPI Application - Main entry point.
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.database import init_db, get_db, SessionLocal
from app.seed import seed_all


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: init DB and seed demo data
    init_db()
    db = SessionLocal()
    try:
        seed_all(db)
    finally:
        db.close()
    yield
    # Shutdown: nothing needed


app = FastAPI(
    title="SynQ",
    description="Adaptive Production Planning & Disruption Management",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS: for local development this defaults to "*" (any origin). For a real
# deployment, set the CORS_ORIGINS env var to a comma-separated list of the
# exact frontend URL(s), e.g. "https://your-app.vercel.app". The app does not
# use cookies, so allow_credentials is fine either way, but browsers will
# reject a wildcard origin combined with credentials — hence the split below.
_cors_origins_env = os.getenv("CORS_ORIGINS", "*")
_cors_origins = [o.strip() for o in _cors_origins_env.split(",")] if _cors_origins_env != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=(_cors_origins != ["*"]),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import and include routers
from app.api import router as api_router
app.include_router(api_router, prefix="/api")


@app.get("/")
def root():
    return {"name": "SynQ", "tagline": "The factory changes. The plan adapts.", "status": "running"}
