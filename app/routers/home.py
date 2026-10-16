from fastapi import APIRouter, Request

from app import __version__
from app.deps import WebUser
from app.templating import templates

pages = APIRouter(include_in_schema=False)


@pages.get("/")
def index(request: Request, user: WebUser):
    return templates.TemplateResponse(request, "index.html", {"user": user, "version": __version__})
