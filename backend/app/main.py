from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.config import settings
from backend.app.database import check_db_connection, create_tables, list_tables
from backend.app.routers import disputes

app = FastAPI(
    title="Seller Dispute Resolution API",
    description="MVP for photo-based seller claim assessment",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(disputes.router)

storage_dir = Path(settings.storage_path)
storage_dir.mkdir(parents=True, exist_ok=True)
app.mount("/files", StaticFiles(directory=str(storage_dir)), name="files")

frontend_dir = Path(__file__).resolve().parents[2] / "frontend"
if frontend_dir.exists():
    app.mount("/ui", StaticFiles(directory=str(frontend_dir), html=True), name="ui")


@app.get("/")
def root() -> dict:
    return {"message": "Seller Dispute Resolution API", "docs": "/docs"}


@app.get("/health")
def health() -> dict:
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
    db_ok, db_message = check_db_connection()
    if not db_ok:
        raise HTTPException(status_code=503, detail=db_message)

    tables = create_tables()
    return {"message": "Tables created or already exist", "tables": tables}
