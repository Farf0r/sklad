from typing import Annotated

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from app.deps import AdminUser, CurrentUser, DbSession, WebUser
from app.errors import AppError
from app.forms import validate_form
from app.schemas.unit import UnitIn, UnitOut
from app.services import units as service
from app.templating import flash, templates

api = APIRouter(prefix="/api/units", tags=["Единицы измерения"])
pages = APIRouter(prefix="/units", include_in_schema=False)


@api.get("", response_model=list[UnitOut])
def list_units(db: DbSession, user: CurrentUser):
    return service.list_units(db)


@api.post("", response_model=UnitOut, status_code=201)
def create_unit(data: UnitIn, db: DbSession, user: CurrentUser):
    return service.create_unit(db, data)


@api.get("/{unit_id}", response_model=UnitOut)
def get_unit(unit_id: int, db: DbSession, user: CurrentUser):
    return service.get_unit(db, unit_id)


@api.put("/{unit_id}", response_model=UnitOut)
def update_unit(unit_id: int, data: UnitIn, db: DbSession, user: CurrentUser):
    return service.update_unit(db, unit_id, data)


@api.delete("/{unit_id}", status_code=204)
def delete_unit(unit_id: int, db: DbSession, user: AdminUser):
    service.delete_unit(db, unit_id)


def render_form(request, user, unit=None, form=None, errors=None, error=None, status_code=200):
    context = {
        "user": user,
        "unit": unit,
        "form": form or {},
        "errors": errors or {},
        "error": error,
    }
    return templates.TemplateResponse(request, "units/form.html", context, status_code=status_code)


@pages.get("")
def units_page(request: Request, db: DbSession, user: WebUser):
    context = {"user": user, "units": service.list_units(db)}
    return templates.TemplateResponse(request, "units/list.html", context)


@pages.get("/new")
def new_unit_page(request: Request, user: WebUser):
    return render_form(request, user)


@pages.post("/new")
def new_unit_submit(
    request: Request,
    db: DbSession,
    user: WebUser,
    name: Annotated[str, Form()] = "",
    short_name: Annotated[str, Form()] = "",
):
    form = {"name": name, "short_name": short_name}
    data, errors = validate_form(UnitIn, form)
    if errors:
        return render_form(request, user, form=form, errors=errors, status_code=422)
    try:
        service.create_unit(db, data)
    except AppError as exc:
        return render_form(request, user, form=form, error=exc.message, status_code=exc.status_code)
    flash(request, "Единица измерения добавлена")
    return RedirectResponse("/units", status_code=303)


@pages.get("/{unit_id}/edit")
def edit_unit_page(request: Request, unit_id: int, db: DbSession, user: WebUser):
    unit = service.get_unit(db, unit_id)
    form = {"name": unit.name, "short_name": unit.short_name}
    return render_form(request, user, unit=unit, form=form)


@pages.post("/{unit_id}/edit")
def edit_unit_submit(
    request: Request,
    unit_id: int,
    db: DbSession,
    user: WebUser,
    name: Annotated[str, Form()] = "",
    short_name: Annotated[str, Form()] = "",
):
    unit = service.get_unit(db, unit_id)
    form = {"name": name, "short_name": short_name}
    data, errors = validate_form(UnitIn, form)
    if errors:
        return render_form(request, user, unit=unit, form=form, errors=errors, status_code=422)
    try:
        service.update_unit(db, unit_id, data)
    except AppError as exc:
        return render_form(
            request, user, unit=unit, form=form, error=exc.message, status_code=exc.status_code
        )
    flash(request, "Изменения сохранены")
    return RedirectResponse("/units", status_code=303)


@pages.post("/{unit_id}/delete")
def delete_unit_submit(request: Request, unit_id: int, db: DbSession, user: WebUser):
    if user.role != "admin":
        flash(request, "Удалять может только администратор", "error")
        return RedirectResponse("/units", status_code=303)
    try:
        service.delete_unit(db, unit_id)
        flash(request, "Единица измерения удалена")
    except AppError as exc:
        flash(request, exc.message, "error")
    return RedirectResponse("/units", status_code=303)
