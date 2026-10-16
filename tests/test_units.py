def test_create_and_list_units(user_client):
    response = user_client.post("/api/units", json={"name": "Килограмм", "short_name": "кг"})
    assert response.status_code == 201
    assert response.json()["short_name"] == "кг"

    units = user_client.get("/api/units").json()
    assert [u["name"] for u in units] == ["Килограмм"]


def test_units_require_login(client):
    assert client.get("/api/units").status_code == 401


def test_duplicate_unit(user_client):
    user_client.post("/api/units", json={"name": "Килограмм", "short_name": "кг"})
    response = user_client.post("/api/units", json={"name": "Килограмм", "short_name": "kg"})
    assert response.status_code == 409


def test_empty_unit_name(user_client):
    response = user_client.post("/api/units", json={"name": "  ", "short_name": "кг"})
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "name"


def test_update_unit(user_client):
    unit_id = user_client.post("/api/units", json={"name": "Литр", "short_name": "л"}).json()["id"]
    response = user_client.put(f"/api/units/{unit_id}", json={"name": "Литр", "short_name": "л."})
    assert response.status_code == 200
    assert response.json()["short_name"] == "л."


def test_unknown_unit_returns_404(user_client):
    assert user_client.get("/api/units/999").status_code == 404


def test_only_admin_can_delete_unit(user_client, admin_client):
    response = user_client.post("/api/units", json={"name": "Штука", "short_name": "шт"})
    unit_id = response.json()["id"]
    assert user_client.delete(f"/api/units/{unit_id}").status_code == 403
    assert admin_client.delete(f"/api/units/{unit_id}").status_code == 204


def test_cannot_delete_unit_used_by_material(admin_client):
    response = admin_client.post("/api/units", json={"name": "Штука", "short_name": "шт"})
    unit_id = response.json()["id"]
    admin_client.post("/api/materials", json={"name": "Кирпич", "unit_id": unit_id})
    response = admin_client.delete(f"/api/units/{unit_id}")
    assert response.status_code == 409
