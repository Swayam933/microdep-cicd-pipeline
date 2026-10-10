from concurrent.futures import ThreadPoolExecutor

import app as inventory


def setup_function():
    with inventory.stock_lock:
        inventory.STOCK.clear()
        inventory.STOCK.update({"sku-100": 50, "sku-200": 12, "sku-300": 0})


def test_health_and_metrics_endpoints():
    client = inventory.app.test_client()

    assert client.get("/healthz").status_code == 200
    assert client.get("/readyz").status_code == 200
    assert client.get("/metrics").status_code == 200


def test_reserve_decrements_stock_by_requested_quantity():
    response = inventory.app.test_client().post(
        "/stock/sku-100/reserve",
        json={"qty": 4},
    )

    assert response.status_code == 200
    assert response.json == {"sku": "sku-100", "reserved": 4, "available": 46}
    assert inventory.app.test_client().get("/stock/sku-100").json["available"] == 46


def test_reserve_rejects_insufficient_stock_without_changing_it():
    response = inventory.app.test_client().post(
        "/stock/sku-200/reserve",
        json={"qty": 13},
    )

    assert response.status_code == 409
    assert response.json["available"] == 12
    assert inventory.app.test_client().get("/stock/sku-200").json["available"] == 12


def test_concurrent_reservations_do_not_oversell():
    with inventory.stock_lock:
        inventory.STOCK["sku-200"] = 5

    def reserve():
        return inventory.app.test_client().post(
            "/stock/sku-200/reserve",
            json={"qty": 4},
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = list(executor.map(lambda _: reserve(), range(2)))

    assert sorted(statuses) == [200, 409]
    assert inventory.app.test_client().get("/stock/sku-200").json["available"] == 1


def test_reserve_rejects_invalid_input():
    client = inventory.app.test_client()

    assert client.post("/stock/sku-100/reserve", data="not json").status_code == 400
    assert client.post("/stock/sku-100/reserve", json={"qty": True}).status_code == 400
    assert client.post("/stock/sku-100/reserve", json={"qty": -1}).status_code == 400
