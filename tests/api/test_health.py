from app import __version__


def test_health_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "ok", "version": __version__}


def test_response_has_request_id(client):
    response = client.get("/health")
    assert response.headers.get("X-Request-ID")


def test_unknown_api_route_returns_json_404(client):
    response = client.get("/api/nothing-here")
    assert response.status_code == 404
    assert response.json()["detail"] == "Не найдено"
