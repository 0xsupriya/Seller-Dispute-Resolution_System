from fastapi import FastAPI, HTTPException

from backend.app.config import settings
from backend.app.database import check_db_connection, create_tables, list_tables

app = FastAPI(
    title="Seller Dispute Resolution API",
    description="MVP for photo-based seller claim assessment",
    version="0.2.0",
)


@app.get("/")
def root() -> dict:
    return {"message": "Seller Dispute Resolution API", "docs": "/docs"}


@app.get("/health")
def health() -> dict:
    """Checks that the app runs and Neon PostgreSQL is reachable."""
    db_ok, db_message = check_db_connection()
    return {
        "status": "ok" if db_ok else "degraded",
        "database": db_message,
        "tables": list_tables() if db_ok else [],
        "ai_provider": settings.ai_provider,
        "storage_path": settings.storage_path,
    }


@app.post("/api/db/init")
def init_database() -> dict:
    """Create tables in Neon (safe to run multiple times)."""
    db_ok, db_message = check_db_connection()
    if not db_ok:
        raise HTTPException(status_code=503, detail=db_message)

    tables = create_tables()
    return {"message": "Tables created or already exist", "tables": tables}
