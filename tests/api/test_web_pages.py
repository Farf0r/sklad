"""Веб-страницы справочников и поступлений: формы, ошибки ввода, права на удаление."""

from datetime import date

import pytest


def get_ok(client, url):
    response = client.get(url)
    assert response.status_code == 200
    return response.text


def submit(client, url, data):
    return client.post(url, data=data, follow_redirects=False)


@pytest.fixture
def unit_id(admin_client):
    return admin_client.post("/api/units", json={"name": "Килограмм", "short_name": "кг"}).json()[
        "id"
    ]


def test_units_pages(admin_client):
    assert "Единицы" in get_ok(admin_client, "/units")
    get_ok(admin_client, "/units/new")
    assert (
        submit(admin_client, "/units/new", {"name": "Метр", "short_name": "м"}).status_code == 303
    )
    response = submit(admin_client, "/units/new", {"name": "Метр", "short_name": "м"})
    assert response.status_code == 409
    response = submit(admin_client, "/units/new", {"name": "", "short_name": "м"})
    assert response.status_code == 422

    unit_id = admin_client.get("/api/units").json()[0]["id"]
    assert "Метр" in get_ok(admin_client, f"/units/{unit_id}/edit")
    response = submit(admin_client, f"/units/{unit_id}/edit", {"name": "Метры", "short_name": "м"})
    assert response.status_code == 303
    assert (
        submit(admin_client, f"/units/{unit_id}/edit", {"name": "", "short_name": ""}).status_code
        == 422
    )
    assert submit(admin_client, f"/units/{unit_id}/delete", {}).status_code == 303
    assert admin_client.get("/api/units").json() == []


def test_unit_edit_conflict(admin_client):
    admin_client.post("/api/units", json={"name": "Метр", "short_name": "м"})
    second = admin_client.post("/api/units", json={"name": "Штука", "short_name": "шт"}).json()
    response = submit(
        admin_client, f"/units/{second['id']}/edit", {"name": "Метр", "short_name": "м"}
    )
    assert response.status_code == 409


def test_used_unit_cannot_be_deleted_from_page(admin_client, unit_id):
    admin_client.post("/api/materials", json={"name": "Цемент", "unit_id": unit_id})
    submit(admin_client, f"/units/{unit_id}/delete", {})
    assert len(admin_client.get("/api/units").json()) == 1


def test_storekeeper_cannot_delete_from_pages(user_client, admin_client, unit_id):
    material = admin_client.post("/api/materials", json={"name": "Цемент", "unit_id": unit_id})
    supplier = admin_client.post(
        "/api/suppliers", json={"name": "ООО Ромашка", "inn": "7701234567"}
    )
    submit(user_client, f"/units/{unit_id}/delete", {})
    submit(user_client, f"/materials/{material.json()['id']}/delete", {})
    submit(user_client, f"/suppliers/{supplier.json()['id']}/delete", {})
    assert len(admin_client.get("/api/units").json()) == 1
    assert len(admin_client.get("/api/materials").json()) == 1
    assert len(admin_client.get("/api/suppliers").json()) == 1


def test_materials_pages(admin_client, unit_id):
    get_ok(admin_client, "/materials/new")
    form = {"name": "Цемент", "unit_id": str(unit_id), "description": "мешки по 50 кг"}
    assert submit(admin_client, "/materials/new", form).status_code == 303
    assert submit(admin_client, "/materials/new", form).status_code == 409

    material_id = admin_client.get("/api/materials").json()[0]["id"]
    assert "Цемент" in get_ok(admin_client, f"/materials/{material_id}/edit")
    form["name"] = "Цемент М500"
    assert submit(admin_client, f"/materials/{material_id}/edit", form).status_code == 303
    assert submit(admin_client, f"/materials/{material_id}/edit", {"name": ""}).status_code == 422
    form["unit_id"] = "999"
    assert submit(admin_client, f"/materials/{material_id}/edit", form).status_code == 404
    assert submit(admin_client, f"/materials/{material_id}/delete", {}).status_code == 303
    assert admin_client.get("/api/materials").json() == []


def test_material_with_stock_cannot_be_deleted_from_page(admin_client, unit_id):
    material = admin_client.post("/api/materials", json={"name": "Цемент", "unit_id": unit_id})
    supplier = admin_client.post(
        "/api/suppliers", json={"name": "ООО Ромашка", "inn": "7701234567"}
    )
    receipt = admin_client.post(
        "/api/receipts",
        json={
            "supplier_id": supplier.json()["id"],
            "items": [{"material_id": material.json()["id"], "quantity": "1", "price": "1"}],
        },
    ).json()
    admin_client.post(f"/api/receipts/{receipt['id']}/post")
    submit(admin_client, f"/materials/{material.json()['id']}/delete", {})
    assert len(admin_client.get("/api/materials").json()) == 1


def test_suppliers_pages(admin_client):
    form = {"name": "ООО Ромашка", "inn": "7701234567", "phone": "", "email": "", "address": ""}
    assert submit(admin_client, "/suppliers/new", form).status_code == 303
    assert submit(admin_client, "/suppliers/new", form).status_code == 409

    supplier_id = admin_client.get("/api/suppliers").json()[0]["id"]
    assert "Ромашка" in get_ok(admin_client, f"/suppliers/{supplier_id}/edit")
    form["email"] = "info@romashka.ru"
    assert submit(admin_client, f"/suppliers/{supplier_id}/edit", form).status_code == 303
    form["inn"] = "123"
    assert submit(admin_client, f"/suppliers/{supplier_id}/edit", form).status_code == 422
    assert submit(admin_client, f"/suppliers/{supplier_id}/delete", {}).status_code == 303
    assert admin_client.get("/api/suppliers").json() == []


def test_supplier_edit_conflict(admin_client):
    admin_client.post("/api/suppliers", json={"name": "ООО Ромашка", "inn": "7701234567"})
    other = admin_client.post("/api/suppliers", json={"name": "ООО Лютик", "inn": "7701234568"})
    form = {"name": "ООО Ромашка", "inn": "7701234568"}
    assert submit(admin_client, f"/suppliers/{other.json()['id']}/edit", form).status_code == 409


def test_supplier_with_receipts_cannot_be_deleted_from_page(admin_client):
    supplier = admin_client.post(
        "/api/suppliers", json={"name": "ООО Ромашка", "inn": "7701234567"}
    )
    admin_client.post("/api/receipts", json={"supplier_id": supplier.json()["id"]})
    submit(admin_client, f"/suppliers/{supplier.json()['id']}/delete", {})
    assert len(admin_client.get("/api/suppliers").json()) == 1


@pytest.fixture
def draft(admin_client, unit_id):
    material = admin_client.post("/api/materials", json={"name": "Цемент", "unit_id": unit_id})
    supplier = admin_client.post(
        "/api/suppliers", json={"name": "ООО Ромашка", "inn": "7701234567"}
    )
    receipt = admin_client.post("/api/receipts", json={"supplier_id": supplier.json()["id"]})
    return {"receipt": receipt.json()["id"], "material": material.json()["id"]}


def test_receipt_pages(admin_client, draft):
    url = f"/receipts/{draft['receipt']}"
    assert "ООО Ромашка" in get_ok(admin_client, url)
    get_ok(admin_client, "/receipts?status=draft")
    get_ok(admin_client, "/receipts/new")

    item = {"material_id": str(draft["material"]), "quantity": "2", "price": "10"}
    assert submit(admin_client, f"{url}/items", item).status_code == 303
    assert submit(admin_client, f"{url}/items", item).status_code == 409

    item_id = admin_client.get(f"/api/receipts/{draft['receipt']}").json()["items"][0]["id"]
    assert submit(admin_client, f"{url}/items/{item_id}/delete", {}).status_code == 303
    assert submit(admin_client, f"{url}/items/{item_id}/delete", {}).status_code == 303
    assert submit(admin_client, f"{url}/post", {}).status_code == 303
    assert admin_client.get(f"/api/receipts/{draft['receipt']}").json()["status"] == "draft"


def test_new_receipt_form_errors(admin_client, draft):
    assert submit(admin_client, "/receipts/new", {"supplier_id": ""}).status_code == 422
    form = {"supplier_id": "999", "receipt_date": str(date.today())}
    assert submit(admin_client, "/receipts/new", form).status_code == 404


def test_delete_receipt_from_page(admin_client, user_client, draft):
    url = f"/receipts/{draft['receipt']}"
    submit(user_client, f"{url}/delete", {})
    assert len(admin_client.get("/api/receipts").json()) == 1
    assert submit(admin_client, f"{url}/delete", {}).headers["location"] == "/receipts"
    assert admin_client.get("/api/receipts").json() == []


def test_posted_receipt_cannot_be_deleted_from_page(admin_client, draft):
    url = f"/receipts/{draft['receipt']}"
    item = {"material_id": str(draft["material"]), "quantity": "2", "price": "10"}
    submit(admin_client, f"{url}/items", item)
    submit(admin_client, f"{url}/post", {})
    assert submit(admin_client, f"{url}/delete", {}).headers["location"] == url
    assert len(admin_client.get("/api/receipts").json()) == 1


def test_logout_page(admin_client):
    response = admin_client.post("/logout", follow_redirects=False)
    assert response.headers["location"] == "/login"
    assert admin_client.get("/", follow_redirects=False).status_code == 303
