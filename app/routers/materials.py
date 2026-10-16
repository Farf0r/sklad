from typing import Annotated

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from app.deps import AdminUser, CurrentUser, DbSession, WebUser
from app.errors import AppError
from app.forms import validate_form
from app.schemas.material import MaterialIn, MaterialOut
from app.services import materials as service
from app.services.units import list_units
from app.templating import flash, templates

api = APIRouter(prefix="/api/materials", tags=["Материалы"])
pages = APIRouter(prefix="/materials", include_in_schema=False)


@api.get("", response_model=list[MaterialOut])
def list_materials(db: DbSession, user: CurrentUser):
    return service.list_materials(db)


@api.post("", response_model=MaterialOut, status_code=201)
def create_material(data: MaterialIn, db: DbSession, user: CurrentUser):
    return service.create_material(db, data)


@api.get("/{material_id}", response_model=MaterialOut)
def get_material(material_id: int, db: DbSession, user: CurrentUser):
    return service.get_material(db, material_id)


@api.put("/{material_id}", response_model=MaterialOut)
def update_material(material_id: int, data: MaterialIn, db: DbSession, user: CurrentUser):
    return service.update_material(db, material_id, data)


@api.delete("/{material_id}", status_code=204)
def delete_material(material_id: int, db: DbSession, user: AdminUser):
    service.delete_material(db, material_id)


def render_form(
    request, db, user, material=None, form=None, errors=None, error=None, status_code=200
):
    context = {
        "user": user,
        "material": material,
        "units": list_units(db),
        "form": form or {},
        "errors": errors or {},
        "error": error,
    }
    return templates.TemplateResponse(
        request, "materials/form.html", context, status_code=status_code
    )


@pages.get("")
def materials_page(request: Request, db: DbSession, user: WebUser):
    context = {"user": user, "materials": service.list_materials(db)}
    return templates.TemplateResponse(request, "materials/list.html", context)


@pages.get("/new")
def new_material_page(request: Request, db: DbSession, user: WebUser):
    return render_form(request, db, user)


@pages.post("/new")
def new_material_submit(
    request: Request,
    db: DbSession,
    user: WebUser,
    name: Annotated[str, Form()] = "",
    unit_id: Annotated[str, Form()] = "",
    description: Annotated[str, Form()] = "",
):
    form = {"name": name, "unit_id": unit_id, "description": description}
    data, errors = validate_form(MaterialIn, form)
    if errors:
        return render_form(request, db, user, form=form, errors=errors, status_code=422)
    try:
        service.create_material(db, data)
    except AppError as exc:
        return render_form(
            request, db, user, form=form, error=exc.message, status_code=exc.status_code
        )
    flash(request, "Материал добавлен")
    return RedirectResponse("/materials", status_code=303)


@pages.get("/{material_id}/edit")
def edit_material_page(request: Request, material_id: int, db: DbSession, user: WebUser):
    material = service.get_material(db, material_id)
    form = {
        "name": material.name,
        "unit_id": material.unit_id,
        "description": material.description or "",
    }
    return render_form(request, db, user, material=material, form=form)


@pages.post("/{material_id}/edit")
def edit_material_submit(
    request: Request,
    material_id: int,
    db: DbSession,
    user: WebUser,
    name: Annotated[str, Form()] = "",
    unit_id: Annotated[str, Form()] = "",
    description: Annotated[str, Form()] = "",
):
    material = service.get_material(db, material_id)
    form = {"name": name, "unit_id": unit_id, "description": description}
    data, errors = validate_form(MaterialIn, form)
    if errors:
        return render_form(
            request, db, user, material=material, form=form, errors=errors, status_code=422
        )
    try:
        service.update_material(db, material_id, data)
    except AppError as exc:
        return render_form(
            request,
            db,
            user,
            material=material,
            form=form,
            error=exc.message,
            status_code=exc.status_code,
        )
    flash(request, "Изменения сохранены")
    return RedirectResponse("/materials", status_code=303)


@pages.post("/{material_id}/delete")
def delete_material_submit(request: Request, material_id: int, db: DbSession, user: WebUser):
    if user.role != "admin":
        flash(request, "Удалять может только администратор", "error")
        return RedirectResponse("/materials", status_code=303)
    try:
        service.delete_material(db, material_id)
        flash(request, "Материал удалён")
    except AppError as exc:
        flash(request, exc.message, "error")
    return RedirectResponse("/materials", status_code=303)
