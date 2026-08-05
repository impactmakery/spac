import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.db import get_db as get_db_context
from app.routers import admin_users as admin_users_router
from app.routers import auth as auth_router
from app.routers import board_items as board_items_router
from app.routers import categories as categories_router
from app.routers import chat as chat_router
from app.routers import crons as crons_router
from app.routers import department_content as department_content_router
from app.routers import departments as departments_router
from app.routers import files as files_router
from app.routers import invitations as invitations_router
from app.routers import kb_documents as kb_documents_router
from app.routers import municipalities as municipalities_router
from app.routers import stats as stats_router
from app.routers import users as users_router
from app.services.bootstrap import bootstrap_first_admin


def create_app() -> FastAPI:
    # Refuse to start rather than sign sessions with an empty key: PyJWT would
    # otherwise fail deep inside the first login request, and an API serving
    # unsigned sessions is worse than one that will not boot.
    if not get_settings().jwt_secret:
        raise RuntimeError(
            "JWT_SECRET is not set. Copy .env.example to .env and fill it in "
            "(see README), or provide it in the deployment's environment."
        )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if get_settings().bootstrap_admin_email:
            try:
                with next(get_db_context()) as db:
                    bootstrap_first_admin(db)
            except Exception:  # noqa: BLE001 — never block startup on this
                logging.getLogger(__name__).exception("bootstrap admin failed")
        yield

    app = FastAPI(title="Tomorrow Agent Hub API", lifespan=lifespan)
    app.include_router(admin_users_router.router)
    app.include_router(auth_router.router)
    app.include_router(board_items_router.router)
    app.include_router(categories_router.router)
    app.include_router(chat_router.router)
    app.include_router(crons_router.router)
    app.include_router(department_content_router.router)
    app.include_router(departments_router.router)
    app.include_router(files_router.router)
    app.include_router(invitations_router.router)
    app.include_router(kb_documents_router.router)
    app.include_router(municipalities_router.router)
    app.include_router(stats_router.router)
    app.include_router(users_router.router)

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
