import threading
from decimal import Decimal

from tests.conftest import logged_in_client


def test_parallel_posting_increases_stock_once():
    admin = logged_in_client("admin", "admin")
    unit = admin.post("/api/units", json={"name": "Килограмм", "short_name": "кг"}).json()
    material = admin.post("/api/materials", json={"name": "Цемент", "unit_id": unit["id"]}).json()
    supplier = admin.post("/api/suppliers", json={"name": "ООО СтройБаза", "inn": "7701234567"})
    receipt = admin.post(
        "/api/receipts",
        json={
            "supplier_id": supplier.json()["id"],
            "items": [{"material_id": material["id"], "quantity": "10", "price": "100"}],
        },
    ).json()

    clients = [logged_in_client(f"user{i}", "storekeeper") for i in range(5)]
    start = threading.Barrier(len(clients))
    statuses = []

    def post(client):
        start.wait()
        response = client.post(f"/api/receipts/{receipt['id']}/post")
        statuses.append(response.status_code)

    threads = [threading.Thread(target=post, args=(client,)) for client in clients]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(statuses) == [200, 409, 409, 409, 409]
    stock = admin.get(f"/api/materials/{material['id']}").json()["stock"]
    assert Decimal(stock) == Decimal("10")
