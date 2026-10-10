"""Inventory microservice — tracks stock levels, called by orders-service."""
import os
from threading import Lock

from flask import Flask, jsonify, request
from prometheus_flask_exporter import PrometheusMetrics

app = Flask(__name__)
PrometheusMetrics(app)
APP_VERSION = os.environ.get("APP_VERSION", "dev")

# Seed stock — swap for a real DB in production use.
STOCK = {"sku-100": 50, "sku-200": 12, "sku-300": 0}
stock_lock = Lock()


@app.get("/healthz")
def healthz():
    return jsonify(status="ok"), 200


@app.get("/readyz")
def readyz():
    return jsonify(status="ready"), 200


@app.get("/stock/<sku>")
def get_stock(sku):
    with stock_lock:
        available = STOCK.get(sku, 0)
    return jsonify(sku=sku, available=available)


@app.post("/stock/<sku>/reserve")
def reserve_stock(sku):
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify(error="request body must be a JSON object"), 400

    qty = body.get("qty")
    if type(qty) is not int or qty < 1:
        return jsonify(error="qty must be a positive integer"), 400

    with stock_lock:
        available = STOCK.get(sku, 0)
        if available < qty:
            return jsonify(error="out of stock", available=available), 409
        STOCK[sku] = available - qty
        available = STOCK[sku]

    return jsonify(sku=sku, reserved=qty, available=available), 200


@app.post("/stock/<sku>/decrement")
def decrement_stock(sku):
    with stock_lock:
        if sku in STOCK and STOCK[sku] > 0:
            STOCK[sku] -= 1
            return jsonify(sku=sku, available=STOCK[sku])
        return jsonify(error="out of stock"), 409


@app.get("/version")
def version():
    return jsonify(service="inventory-service", version=APP_VERSION)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
