import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app import __version__
from app.config import settings
from app.database import Base, engine
from app.errors import register_error_handlers
from app.logging_config import setup_logging
from app.middleware import RequestLogMiddleware
from app.routers import auth, health, home, materials, receipts, suppliers, units

setup_logging(settings.log_level, settings.log_file)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    logger.info("Склад %s запущен, окружение: %s", __version__, settings.app_env)
    yield
    logger.info("Склад остановлен")


app = FastAPI(title="Склад", version=__version__, lifespan=lifespan)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    max_age=settings.session_max_age,
    same_site="lax",
)
app.add_middleware(RequestLogMiddleware)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
register_error_handlers(app)

app.include_router(health.api)
app.include_router(auth.api)
app.include_router(auth.pages)
app.include_router(home.pages)
app.include_router(suppliers.api)
app.include_router(suppliers.pages)
app.include_router(units.api)
app.include_router(units.pages)
app.include_router(materials.api)
app.include_router(materials.pages)
app.include_router(receipts.api)
app.include_router(receipts.pages)