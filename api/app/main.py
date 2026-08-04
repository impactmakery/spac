from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.db import get_db


def create_app() -> FastAPI:
    app = FastAPI(title="Tomorrow Agent Hub API")

    @app.get("/health")
    def health(db: Session = Depends(get_db)) -> dict:
        try:
            db.execute(text("SELECT 1"))
            db_state = "ok"
        except Exception:
            db_state = "error"
        return {"status": "ok" if db_state == "ok" else "degraded", "db": db_state}

    return app


app = create_app()
