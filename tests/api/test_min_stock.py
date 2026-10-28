"""Минимальный остаток и список материалов «К заказу» (ФТ-14, ПР-8)."""

from decimal import Decimal

import pytest


@pytest.fixture
def unit_id(user_client):
    response = user_client.post("/api/units", json={"name": "Килограмм", "short_name": "кг"})
    return response.json()["id"]


def add_material(client, unit_id, name, min_stock=None):
    data = {"name": name, "unit_id": unit_id}
    if min_stock is not None:
        data["min_stock"] = min_stock
    response = client.post("/api/materials", json=data)
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def receive(user_client):
    """Проводит поступление одного материала, чтобы увеличить его остаток."""
    supplier = user_client.post(
        "/api/suppliers", json={"name": "ООО СтройБаза", "inn": "7701234567"}
    ).json()

    def post_receipt(material_id, quantity):
        items = [{"material_id": material_id, "quantity": quantity, "price": "1"}]
        receipt = user_client.post(
            "/api/receipts", json={"supplier_id": supplier["id"], "items": items}
        ).json()
        assert user_client.post(f"/api/receipts/{receipt['id']}/post").status_code == 200

    return post_receipt


def to_order(client):
    response = client.get("/api/materials", params={"needs_order": "true"})
    assert response.status_code == 200
    return [material["name"] for material in response.json()]


def test_min_stock_defaults_to_zero(user_client, unit_id):
    material = add_material(user_client, unit_id, "Цемент")
    assert Decimal(material["min_stock"]) == 0
    assert material["needs_order"] is False
    assert Decimal(material["shortage"]) == 0


def test_update_min_stock(user_client, unit_id):
    material = add_material(user_client, unit_id, "Цемент")
    response = user_client.put(
        f"/api/materials/{material['id']}",
        json={"name": "Цемент", "unit_id": unit_id, "min_stock": "50"},
    )
    assert response.status_code == 200
    body = response.json()
    assert Decimal(body["min_stock"]) == 50
    assert body["needs_order"] is True
    assert Decimal(body["shortage"]) == 50


@pytest.mark.parametrize("min_stock", ["-1", "0.0001", "abc"])
def test_wrong_min_stock(user_client, unit_id, min_stock):
    response = user_client.post(
        "/api/materials", json={"name": "Цемент", "unit_id": unit_id, "min_stock": min_stock}
    )
    assert response.status_code == 422


def test_filter_materials_to_order(user_client, unit_id, receive):
    cement = add_material(user_client, unit_id, "Цемент", "10")
    add_material(user_client, unit_id, "Песок", "5")
    add_material(user_client, unit_id, "Гвозди")  # минимальный остаток не задан
    receive(cement["id"], "10")  # ровно минимум

    assert to_order(user_client) == ["Песок"]
    assert len(user_client.get("/api/materials").json()) == 3


def test_receipt_removes_material_from_order_list(user_client, unit_id, receive):
    sand = add_material(user_client, unit_id, "Песок", "5")
    receive(sand["id"], "4.999")
    assert to_order(user_client) == ["Песок"]
    assert Decimal(user_client.get(f"/api/materials/{sand['id']}").json()["shortage"]) == Decimal(
        "0.001"
    )

    receive(sand["id"], "0.001")
    assert to_order(user_client) == []


def test_min_stock_on_web_pages(user_client, unit_id):
    response = user_client.post(
        "/materials/new",
        data={"name": "Песок", "unit_id": unit_id, "min_stock": "1,5"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    material = user_client.get("/api/materials").json()[0]
    assert Decimal(material["min_stock"]) == Decimal("1.5")

    assert "заказать 1.5" in user_client.get("/materials").text
    page = user_client.get("/materials?needs_order=1")
    assert "Песок" in page.text
    assert "К заказу (1)" in page.text
    assert "Материалов меньше минимального остатка: <b>1</b>" in user_client.get("/").text

    url = f"/materials/{material['id']}/edit"
    assert 'value="1.5"' in user_client.get(url).text
    response = user_client.post(url, data={"name": "Песок", "unit_id": unit_id, "min_stock": "-2"})
    assert response.status_code == 422
    assert "Значение должно быть не меньше 0" in response.text

    # пустое поле — минимальный остаток не отслеживается
    response = user_client.post(
        url, data={"name": "Песок", "unit_id": unit_id, "min_stock": ""}, follow_redirects=False
    )
    assert response.status_code == 303
    assert Decimal(user_client.get(f"/api/materials/{material['id']}").json()["min_stock"]) == 0
    assert (
        "Все материалы в достаточном количестве" in user_client.get("/materials?needs_order=1").text
    )
    assert "Материалов меньше минимального остатка" not in user_client.get("/").text
