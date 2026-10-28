from decimal import Decimal

import pytest


@pytest.fixture
def refs(user_client):
    unit = user_client.post("/api/units", json={"name": "Килограмм", "short_name": "кг"}).json()
    cement = user_client.post("/api/materials", json={"name": "Цемент", "unit_id": unit["id"]})
    sand = user_client.post("/api/materials", json={"name": "Песок", "unit_id": unit["id"]})
    supplier = user_client.post(
        "/api/suppliers", json={"name": "ООО СтройБаза", "inn": "7701234567"}
    )
    return {
        "cement": cement.json()["id"],
        "sand": sand.json()["id"],
        "supplier": supplier.json()["id"],
    }


def new_receipt(client, refs, items=None):
    if items is None:
        items = [
            {"material_id": refs["cement"], "quantity": "10", "price": "450.50"},
            {"material_id": refs["sand"], "quantity": "2.5", "price": "100"},
        ]
    response = client.post("/api/receipts", json={"supplier_id": refs["supplier"], "items": items})
    assert response.status_code == 201, response.text
    return response.json()


def stock(client, material_id) -> Decimal:
    return Decimal(client.get(f"/api/materials/{material_id}").json()["stock"])


def test_create_receipt_is_draft(user_client, refs):
    receipt = new_receipt(user_client, refs)
    assert receipt["status"] == "draft"
    assert receipt["created_by"]["username"] == "ivanov"
    assert Decimal(receipt["total"]) == Decimal("4755.00")


def test_draft_does_not_change_stock(user_client, refs):
    new_receipt(user_client, refs)
    assert stock(user_client, refs["cement"]) == 0


def test_post_receipt_increases_stock(user_client, refs):
    receipt = new_receipt(user_client, refs)
    response = user_client.post(f"/api/receipts/{receipt['id']}/post")
    assert response.status_code == 200
    assert response.json()["status"] == "posted"
    assert response.json()["posted_at"] is not None
    assert stock(user_client, refs["cement"]) == Decimal("10")
    assert stock(user_client, refs["sand"]) == Decimal("2.5")


def test_stock_accumulates_over_receipts(user_client, refs):
    for _ in range(2):
        receipt = new_receipt(user_client, refs)
        user_client.post(f"/api/receipts/{receipt['id']}/post")
    assert stock(user_client, refs["cement"]) == Decimal("20")


def test_cannot_post_twice(user_client, refs):
    receipt = new_receipt(user_client, refs)
    user_client.post(f"/api/receipts/{receipt['id']}/post")
    response = user_client.post(f"/api/receipts/{receipt['id']}/post")
    assert response.status_code == 409
    assert stock(user_client, refs["cement"]) == Decimal("10")


def test_cannot_post_empty_receipt(user_client, refs):
    receipt = new_receipt(user_client, refs, items=[])
    response = user_client.post(f"/api/receipts/{receipt['id']}/post")
    assert response.status_code == 409


def test_posted_receipt_is_read_only(user_client, admin_client, refs):
    receipt = new_receipt(user_client, refs, items=[])
    user_client.post(
        f"/api/receipts/{receipt['id']}/items",
        json={"material_id": refs["cement"], "quantity": "1", "price": "1"},
    )
    user_client.post(f"/api/receipts/{receipt['id']}/post")

    response = user_client.post(
        f"/api/receipts/{receipt['id']}/items",
        json={"material_id": refs["sand"], "quantity": "1", "price": "1"},
    )
    assert response.status_code == 409
    assert admin_client.delete(f"/api/receipts/{receipt['id']}").status_code == 409


def test_add_and_remove_item(user_client, refs):
    receipt = new_receipt(user_client, refs, items=[])
    response = user_client.post(
        f"/api/receipts/{receipt['id']}/items",
        json={"material_id": refs["cement"], "quantity": "3", "price": "10"},
    )
    assert response.status_code == 201
    item_id = response.json()["items"][0]["id"]

    response = user_client.delete(f"/api/receipts/{receipt['id']}/items/{item_id}")
    assert response.status_code == 200
    assert response.json()["items"] == []


def test_same_material_twice(user_client, refs):
    items = [
        {"material_id": refs["cement"], "quantity": "1", "price": "1"},
        {"material_id": refs["cement"], "quantity": "2", "price": "1"},
    ]
    response = user_client.post(
        "/api/receipts", json={"supplier_id": refs["supplier"], "items": items}
    )
    assert response.status_code == 409
    # сообщение от проверки в коде, а не общий отказ базы
    assert response.json()["detail"] == "Этот материал уже есть в поступлении"


@pytest.mark.parametrize(
    ("quantity", "price"),
    [("0", "10"), ("-5", "10"), ("1", "-1"), ("abc", "10"), ("1.2345", "10")],
)
def test_wrong_item_values(user_client, refs, quantity, price):
    receipt = new_receipt(user_client, refs, items=[])
    response = user_client.post(
        f"/api/receipts/{receipt['id']}/items",
        json={"material_id": refs["cement"], "quantity": quantity, "price": price},
    )
    assert response.status_code == 422


def test_unknown_supplier_and_material(user_client, refs):
    response = user_client.post("/api/receipts", json={"supplier_id": 999})
    assert response.status_code == 404
    items = [{"material_id": 999, "quantity": "1", "price": "1"}]
    response = user_client.post(
        "/api/receipts", json={"supplier_id": refs["supplier"], "items": items}
    )
    assert response.status_code == 404


def test_filter_by_status(user_client, refs):
    posted = new_receipt(user_client, refs)
    user_client.post(f"/api/receipts/{posted['id']}/post")
    new_receipt(user_client, refs)
    drafts = user_client.get("/api/receipts", params={"status": "draft"}).json()
    assert len(drafts) == 1
    assert user_client.get("/api/receipts", params={"status": "wrong"}).status_code == 422


def test_only_admin_deletes_draft(user_client, admin_client, refs):
    receipt = new_receipt(user_client, refs)
    assert user_client.delete(f"/api/receipts/{receipt['id']}").status_code == 403
    assert admin_client.delete(f"/api/receipts/{receipt['id']}").status_code == 204


def test_cannot_delete_supplier_or_material_with_receipts(admin_client, refs):
    new_receipt(admin_client, refs)
    response = admin_client.delete(f"/api/suppliers/{refs['supplier']}")
    assert response.status_code == 409
    response = admin_client.delete(f"/api/materials/{refs['cement']}")
    assert response.status_code == 409


def test_web_receipt_flow(user_client, refs):
    response = user_client.post(
        "/receipts/new",
        data={"supplier_id": refs["supplier"], "receipt_date": "2026-10-16"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    url = response.headers["location"]

    user_client.post(
        f"{url}/items", data={"material_id": refs["cement"], "quantity": "1,5", "price": "200"}
    )
    user_client.post(f"{url}/post")

    page = user_client.get(url)
    assert "проведено" in page.text
    assert stock(user_client, refs["cement"]) == Decimal("1.5")
