import keep_alive


def test_home_endpoint_returns_metrics_payload():
    client = keep_alive.app.test_client()
    response = client.get("/")
    assert response.status_code == 200

    data = response.get_json()
    assert data["estado"] == "El bot está en línea"
    assert "metricas" in data
    assert "cpu" in data["metricas"]
    assert "ram" in data["metricas"]
    assert "almacenamiento" in data["metricas"]


def test_health_endpoint_returns_heartbeat_fields(monkeypatch):
    monkeypatch.setattr(keep_alive, "_last_heartbeat_ts", 1.0)

    client = keep_alive.app.test_client()
    response = client.get("/health")
    assert response.status_code == 200

    data = response.get_json()
    assert data["estado"] == "ok"
    assert "heartbeat_age_seconds" in data
    assert "cleanup" in data
