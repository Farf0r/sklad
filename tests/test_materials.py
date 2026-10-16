from decimal import Decimal

import pytest


@pytest.fixture
def unit_id(user_client):
    response = user_client.post("/api/units", json={"name": "Килограмм", "short_name": "кг"})
    return response.json()["id"]


def test_create_material(user_client, unit_id):
    response = user_client.post("/api/materials", json={"name": "Цемент М500", "unit_id": unit_id})
    assert response.status_code == 201
    body = response.json()
    assert body["unit"]["short_name"] == "кг"
    assert Decimal(body["stock"]) == 0


def test_new_material_has_zero_stock_even_if_sent(user_client, unit_id):
    response = user_client.post(
        "/api/materials", json={"name": "Песок", "unit_id": unit_id, "stock": 100}
    )
    assert response.status_code == 201
    assert Decimal(response.json()["stock"]) == 0


def test_material_with_unknown_unit(user_client):
    response = user_client.post("/api/materials", json={"name": "Песок", "unit_id": 999})
    assert response.status_code == 404


def test_duplicate_material(user_client, unit_id):
    user_client.post("/api/materials", json={"name": "Песок", "unit_id": unit_id})
    response = user_client.post("/api/materials", json={"name": "Песок", "unit_id": unit_id})
    assert response.status_code == 409


def test_update_material(user_client, unit_id):
    material_id = user_client.post(
        "/api/materials", json={"name": "Песок", "unit_id": unit_id}
    ).json()["id"]
    response = user_client.put(
        f"/api/materials/{material_id}",
        json={"name": "Песок речной", "unit_id": unit_id, "description": "мытый"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Песок речной"


def test_delete_material(admin_client):
    unit_id = admin_client.post("/api/units", json={"name": "Метр", "short_name": "м"}).json()["id"]
    material_id = admin_client.post(
        "/api/materials", json={"name": "Кабель", "unit_id": unit_id}
    ).json()["id"]
    assert admin_client.delete(f"/api/materials/{material_id}").status_code == 204
    assert admin_client.get(f"/api/materials/{material_id}").status_code == 404


def test_materials_web_page(user_client, unit_id):
    user_client.post("/materials/new", data={"name": "Гвозди", "unit_id": unit_id})
    page = user_client.get("/materials")
    assert page.status_code == 200
    assert "Гвозди" in page.text


def test_materials_web_form_shows_errors(user_client, unit_id):
    response = user_client.post("/materials/new", data={"name": "", "unit_id": ""})
    assert response.status_code == 422
    assert "Поле не может быть пустым" in response.text
