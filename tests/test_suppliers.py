SUPPLIER = {
    "name": "ООО «СтройБаза»",
    "inn": "7701234567",
    "phone": "+7 495 123-45-67",
    "email": "info@stroybaza.ru",
}


def test_create_supplier(user_client):
    response = user_client.post("/api/suppliers", json=SUPPLIER)
    assert response.status_code == 201
    assert response.json()["inn"] == "7701234567"


def test_supplier_optional_fields(user_client):
    response = user_client.post("/api/suppliers", json={"name": "ИП Петров", "inn": "770123456789"})
    assert response.status_code == 201
    assert response.json()["email"] is None


def test_wrong_inn(user_client):
    for inn in ["123", "77012345ab", "77012345678"]:
        response = user_client.post("/api/suppliers", json={**SUPPLIER, "inn": inn})
        assert response.status_code == 422, inn
        assert response.json()["errors"][0]["field"] == "inn"


def test_wrong_email(user_client):
    response = user_client.post("/api/suppliers", json={**SUPPLIER, "email": "not-an-email"})
    assert response.status_code == 422


def test_duplicate_inn(user_client):
    user_client.post("/api/suppliers", json=SUPPLIER)
    response = user_client.post("/api/suppliers", json={**SUPPLIER, "name": "Другое название"})
    assert response.status_code == 409


def test_update_supplier(user_client):
    supplier_id = user_client.post("/api/suppliers", json=SUPPLIER).json()["id"]
    response = user_client.put(
        f"/api/suppliers/{supplier_id}", json={**SUPPLIER, "phone": "+7 999 000-00-00"}
    )
    assert response.status_code == 200
    assert response.json()["phone"] == "+7 999 000-00-00"


def test_only_admin_can_delete_supplier(user_client, admin_client):
    supplier_id = user_client.post("/api/suppliers", json=SUPPLIER).json()["id"]
    assert user_client.delete(f"/api/suppliers/{supplier_id}").status_code == 403
    assert admin_client.delete(f"/api/suppliers/{supplier_id}").status_code == 204


def test_suppliers_web_page(user_client):
    user_client.post("/suppliers/new", data={"name": "ООО Ромашка", "inn": "5001234567"})
    page = user_client.get("/suppliers")
    assert "ООО Ромашка" in page.text


def test_suppliers_web_form_shows_inn_error(user_client):
    response = user_client.post("/suppliers/new", data={"name": "ООО Ромашка", "inn": "12"})
    assert response.status_code == 422
    assert "ИНН должен состоять из 10 или 12 цифр" in response.text
