from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from app.deps import AdminUser, CurrentUser, DbSession, WebUser
from app.errors import AppError
from app.forms import decimal_input, validate_form
from app.schemas.receipt import ReceiptIn, ReceiptItemIn, ReceiptOut
from app.services import receipts as service
from app.services.materials import list_materials
from app.services.suppliers import list_suppliers
from app.templating import flash, templates

api = APIRouter(prefix="/api/receipts", tags=["Поступления"])
pages = APIRouter(prefix="/receipts", include_in_schema=False)


@api.get("", response_model=list[ReceiptOut])
def list_receipts(
    db: DbSession, user: CurrentUser, status: Literal["draft", "posted"] | None = None
):
    return service.list_receipts(db, status)


@api.post("", response_model=ReceiptOut, status_code=201)
def create_receipt(data: ReceiptIn, db: DbSession, user: CurrentUser):
    return service.create_receipt(db, data, user)


@api.get("/{receipt_id}", response_model=ReceiptOut)
def get_receipt(receipt_id: int, db: DbSession, user: CurrentUser):
    return service.get_receipt(db, receipt_id)


@api.delete("/{receipt_id}", status_code=204)
def delete_receipt(receipt_id: int, db: DbSession, user: AdminUser):
    service.delete_receipt(db, receipt_id)


@api.post("/{receipt_id}/items", response_model=ReceiptOut, status_code=201)
def add_item(receipt_id: int, data: ReceiptItemIn, db: DbSession, user: CurrentUser):
    return service.add_item(db, receipt_id, data)


@api.delete("/{receipt_id}/items/{item_id}", response_model=ReceiptOut)
def remove_item(receipt_id: int, item_id: int, db: DbSession, user: CurrentUser):
    return service.remove_item(db, receipt_id, item_id)


@api.post("/{receipt_id}/post", response_model=ReceiptOut)
def post_receipt(receipt_id: int, db: DbSession, user: CurrentUser):
    return service.post_receipt(db, receipt_id)


def render_new_form(request, db, user, form=None, errors=None, error=None, status_code=200):
    context = {
        "user": user,
        "suppliers": list_suppliers(db),
        "form": form or {"receipt_date": date.today().isoformat()},
        "errors": errors or {},
        "error": error,
    }
    return templates.TemplateResponse(
        request, "receipts/new.html", context, status_code=status_code
    )


def render_detail(request, db, user, receipt, form=None, errors=None, error=None, status_code=200):
    context = {
        "user": user,
        "receipt": receipt,
        "materials": list_materials(db),
        "form": form or {},
        "errors": errors or {},
        "error": error,
    }
    return templates.TemplateResponse(
        request, "receipts/detail.html", context, status_code=status_code
    )


@pages.get("")
def receipts_page(request: Request, db: DbSession, user: WebUser):
    context = {"user": user, "receipts": service.list_receipts(db)}
    return templates.TemplateResponse(request, "receipts/list.html", context)


@pages.get("/new")
def new_receipt_page(request: Request, db: DbSession, user: WebUser):
    return render_new_form(request, db, user)


@pages.post("/new")
def new_receipt_submit(
    request: Request,
    db: DbSession,
    user: WebUser,
    supplier_id: Annotated[str, Form()] = "",
    receipt_date: Annotated[str, Form()] = "",
    comment: Annotated[str, Form()] = "",
):
    form = {"supplier_id": supplier_id, "receipt_date": receipt_date, "comment": comment}
    data, errors = validate_form(ReceiptIn, form)
    if errors:
        return render_new_form(request, db, user, form=form, errors=errors, status_code=422)
    try:
        receipt = service.create_receipt(db, data, user)
    except AppError as exc:
        return render_new_form(
            request, db, user, form=form, error=exc.message, status_code=exc.status_code
        )
    flash(request, "Черновик поступления создан, добавьте строки")
    return RedirectResponse(f"/receipts/{receipt.id}", status_code=303)


@pages.get("/{receipt_id}")
def receipt_page(request: Request, receipt_id: int, db: DbSession, user: WebUser):
    return render_detail(request, db, user, service.get_receipt(db, receipt_id))


@pages.post("/{receipt_id}/items")
def add_item_submit(
    request: Request,
    receipt_id: int,
    db: DbSession,
    user: WebUser,
    material_id: Annotated[str, Form()] = "",
    quantity: Annotated[str, Form()] = "",
    price: Annotated[str, Form()] = "",
):
    receipt = service.get_receipt(db, receipt_id)
    form = {"material_id": material_id, "quantity": quantity, "price": price}
    clean = {**form, "quantity": decimal_input(quantity), "price": decimal_input(price)}
    data, errors = validate_form(ReceiptItemIn, clean)
    if errors:
        return render_detail(request, db, user, receipt, form=form, errors=errors, status_code=422)
    try:
        service.add_item(db, receipt_id, data)
    except AppError as exc:
        return render_detail(
            request, db, user, receipt, form=form, error=exc.message, status_code=exc.status_code
        )
    return RedirectResponse(f"/receipts/{receipt_id}", status_code=303)


@pages.post("/{receipt_id}/items/{item_id}/delete")
def remove_item_submit(
    request: Request, receipt_id: int, item_id: int, db: DbSession, user: WebUser
):
    try:
        service.remove_item(db, receipt_id, item_id)
    except AppError as exc:
        flash(request, exc.message, "error")
    return RedirectResponse(f"/receipts/{receipt_id}", status_code=303)


@pages.post("/{receipt_id}/post")
def post_receipt_submit(request: Request, receipt_id: int, db: DbSession, user: WebUser):
    try:
        service.post_receipt(db, receipt_id)
        flash(request, "Поступление проведено, остатки обновлены")
    except AppError as exc:
        flash(request, exc.message, "error")
    return RedirectResponse(f"/receipts/{receipt_id}", status_code=303)


@pages.post("/{receipt_id}/delete")
def delete_receipt_submit(request: Request, receipt_id: int, db: DbSession, user: WebUser):
    if user.role != "admin":
        flash(request, "Удалять может только администратор", "error")
        return RedirectResponse(f"/receipts/{receipt_id}", status_code=303)
    try:
        service.delete_receipt(db, receipt_id)
    except AppError as exc:
        flash(request, exc.message, "error")
        return RedirectResponse(f"/receipts/{receipt_id}", status_code=303)
    flash(request, "Поступление удалено")
    return RedirectResponse("/receipts", status_code=303)
