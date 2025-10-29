# tests/integration/test_health_endpoint.py

def test_health_ok(client, app):
    resp = client.get("/health")
    assert resp.status_code == 200

    data = resp.get_json()
    assert data["ok"] is True
    assert data["env"] == app.config["CONFIG_NAME"]
    assert isinstance(data["dry_run"], bool)
    assert data["graph_version"] == app.config.get("GRAPH_VERSION", "v22.0")
