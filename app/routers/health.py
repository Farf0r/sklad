import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app import __version__
from app.deps import DbSession

logger = logging.getLogger(__name__)

api = APIRouter(tags=["Служебное"])


@api.get("/health")
def health(db: DbSession):
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        logger.exception("проверка работоспособности: БД недоступна")
        return JSONResponse(
            status_code=503,
            content={"status": "error", "db": "unavailable", "version": __version__},
        )
    return {"status": "ok", "db": "ok", "version": __version__}
