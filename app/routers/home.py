from fastapi import APIRouter, Request

from app import __version__
from app.deps import DbSession, WebUser
from app.services.materials import list_materials
from app.templating import templates

pages = APIRouter(include_in_schema=False)


@pages.get("/")
def index(request: Request, db: DbSession, user: WebUser):
    context = {
        "user": user,
        "version": __version__,
        "to_order": len(list_materials(db, needs_order=True)),
    }
    return templates.TemplateResponse(request, "index.html", context)
