import app as orders


def test_health_and_metrics_endpoints():
    client = orders.app.test_client()

    assert client.get("/healthz").status_code == 200
    assert client.get("/readyz").status_code == 200
    assert client.get("/metrics").status_code == 200


def test_create_order_reserves_requested_quantity(monkeypatch):
    class Response:
        status_code = 200

        @staticmethod
        def raise_for_status():
            pass

    captured = {}

    def reserve(url, json, timeout):
        captured.update(url=url, json=json, timeout=timeout)
        return Response()

    monkeypatch.setattr(orders.requests, "post", reserve)
    client = orders.app.test_client()
    response = client.post(
        "/orders",
        json={"sku": "sku-100", "qty": 3},
    )

    assert response.status_code == 201
    assert response.json["sku"] == "sku-100"
    assert response.json["qty"] == 3
    assert captured["url"].endswith("/stock/sku-100/reserve")
    assert captured["json"] == {"qty": 3}
    assert captured["timeout"] == 2
    order = client.get(f"/orders/{response.json['order_id']}")
    assert order.status_code == 200
    assert order.json["qty"] == 3


def test_create_order_reports_insufficient_stock(monkeypatch):
    class Response:
        status_code = 409

        @staticmethod
        def json():
            return {"available": 0}

    monkeypatch.setattr(orders.requests, "post", lambda *args, **kwargs: Response())
    response = orders.app.test_client().post(
        "/orders",
        json={"sku": "sku-300", "qty": 1},
    )

    assert response.status_code == 409
    assert response.json["available"] == 0


def test_create_order_rejects_invalid_input():
    client = orders.app.test_client()

    assert client.post("/orders", data="not json").status_code == 400
    assert client.post("/orders", json={"sku": "", "qty": 1}).status_code == 400
    assert client.post("/orders", json={"sku": "sku-100", "qty": True}).status_code == 400
    assert client.post("/orders", json={"sku": "sku-100", "qty": 0}).status_code == 400


def test_create_order_reports_inventory_service_failure(monkeypatch):
    def fail(*args, **kwargs):
        raise orders.requests.Timeout("timed out")

    monkeypatch.setattr(orders.requests, "post", fail)
    response = orders.app.test_client().post(
        "/orders",
        json={"sku": "sku-100", "qty": 1},
    )

    assert response.status_code == 503
    assert response.json["error"] == "inventory-service unavailable"
