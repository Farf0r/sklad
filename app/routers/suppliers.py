from typing import Annotated

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from app.deps import AdminUser, CurrentUser, DbSession, WebUser
from app.errors import AppError
from app.forms import validate_form
from app.schemas.supplier import SupplierIn, SupplierOut
from app.services import suppliers as service
from app.templating import flash, templates

api = APIRouter(prefix="/api/suppliers", tags=["Поставщики"])
pages = APIRouter(prefix="/suppliers", include_in_schema=False)

FIELDS = ("name", "inn", "phone", "email", "address")


@api.get("", response_model=list[SupplierOut])
def list_suppliers(db: DbSession, user: CurrentUser):
    return service.list_suppliers(db)


@api.post("", response_model=SupplierOut, status_code=201)
def create_supplier(data: SupplierIn, db: DbSession, user: CurrentUser):
    return service.create_supplier(db, data)


@api.get("/{supplier_id}", response_model=SupplierOut)
def get_supplier(supplier_id: int, db: DbSession, user: CurrentUser):
    return service.get_supplier(db, supplier_id)


@api.put("/{supplier_id}", response_model=SupplierOut)
def update_supplier(supplier_id: int, data: SupplierIn, db: DbSession, user: CurrentUser):
    return service.update_supplier(db, supplier_id, data)


@api.delete("/{supplier_id}", status_code=204)
def delete_supplier(supplier_id: int, db: DbSession, user: AdminUser):
    service.delete_supplier(db, supplier_id)


def render_form(request, user, supplier=None, form=None, errors=None, error=None, status_code=200):
    context = {
        "user": user,
        "supplier": supplier,
        "form": form or {},
        "errors": errors or {},
        "error": error,
    }
    return templates.TemplateResponse(
        request, "suppliers/form.html", context, status_code=status_code
    )


@pages.get("")
def suppliers_page(request: Request, db: DbSession, user: WebUser):
    context = {"user": user, "suppliers": service.list_suppliers(db)}
    return templates.TemplateResponse(request, "suppliers/list.html", context)


@pages.get("/new")
def new_supplier_page(request: Request, user: WebUser):
    return render_form(request, user)


@pages.post("/new")
def new_supplier_submit(
    request: Request,
    db: DbSession,
    user: WebUser,
    name: Annotated[str, Form()] = "",
    inn: Annotated[str, Form()] = "",
    phone: Annotated[str, Form()] = "",
    email: Annotated[str, Form()] = "",
    address: Annotated[str, Form()] = "",
):
    form = {"name": name, "inn": inn, "phone": phone, "email": email, "address": address}
    data, errors = validate_form(SupplierIn, form)
    if errors:
        return render_form(request, user, form=form, errors=errors, status_code=422)
    try:
        service.create_supplier(db, data)
    except AppError as exc:
        return render_form(request, user, form=form, error=exc.message, status_code=exc.status_code)
    flash(request, "Поставщик добавлен")
    return RedirectResponse("/suppliers", status_code=303)


@pages.get("/{supplier_id}/edit")
def edit_supplier_page(request: Request, supplier_id: int, db: DbSession, user: WebUser):
    supplier = service.get_supplier(db, supplier_id)
    form = {field: getattr(supplier, field) or "" for field in FIELDS}
    return render_form(request, user, supplier=supplier, form=form)


@pages.post("/{supplier_id}/edit")
def edit_supplier_submit(
    request: Request,
    supplier_id: int,
    db: DbSession,
    user: WebUser,
    name: Annotated[str, Form()] = "",
    inn: Annotated[str, Form()] = "",
    phone: Annotated[str, Form()] = "",
    email: Annotated[str, Form()] = "",
    address: Annotated[str, Form()] = "",
):
    supplier = service.get_supplier(db, supplier_id)
    form = {"name": name, "inn": inn, "phone": phone, "email": email, "address": address}
    data, errors = validate_form(SupplierIn, form)
    if errors:
        return render_form(
            request, user, supplier=supplier, form=form, errors=errors, status_code=422
        )
    try:
        service.update_supplier(db, supplier_id, data)
    except AppError as exc:
        return render_form(
            request,
            user,
            supplier=supplier,
            form=form,
            error=exc.message,
            status_code=exc.status_code,
        )
    flash(request, "Изменения сохранены")
    return RedirectResponse("/suppliers", status_code=303)


@pages.post("/{supplier_id}/delete")
def delete_supplier_submit(request: Request, supplier_id: int, db: DbSession, user: WebUser):
    if user.role != "admin":
        flash(request, "Удалять может только администратор", "error")
        return RedirectResponse("/suppliers", status_code=303)
    try:
        service.delete_supplier(db, supplier_id)
        flash(request, "Поставщик удалён")
    except AppError as exc:
        flash(request, exc.message, "error")
    return RedirectResponse("/suppliers", status_code=303)
