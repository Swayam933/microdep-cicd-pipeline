"""Orders microservice — places orders through the inventory service."""
import os
import re

import requests
from flask import Flask, jsonify, request
from prometheus_flask_exporter import PrometheusMetrics

app = Flask(__name__)
PrometheusMetrics(app)

INVENTORY_URL = os.environ.get("INVENTORY_URL", "http://inventory-service:80")
APP_VERSION = os.environ.get("APP_VERSION", "dev")

# In-memory store — swap for a real DB in production use.
ORDERS = {}
_next_id = 1


@app.get("/healthz")
def healthz():
    return jsonify(status="ok"), 200


@app.get("/readyz")
def readyz():
    return jsonify(status="ready"), 200


@app.post("/orders")
def create_order():
    global _next_id
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify(error="request body must be a JSON object"), 400

    sku = body.get("sku")
    qty = body.get("qty", 1)
    if not isinstance(sku, str) or not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", sku):
        return jsonify(error="sku must contain 1-64 letters, numbers, dots, underscores, or hyphens"), 400
    if type(qty) is not int or qty < 1:
        return jsonify(error="qty must be a positive integer"), 400

    try:
        resp = requests.post(
            f"{INVENTORY_URL}/stock/{sku}/reserve",
            json={"qty": qty},
            timeout=2,
        )
        if resp.status_code == 409:
            return jsonify(error="insufficient stock", available=resp.json().get("available", 0)), 409
        resp.raise_for_status()
    except requests.RequestException:
        app.logger.exception("Inventory reservation request failed")
        return jsonify(error="inventory-service unavailable"), 503

    order_id = _next_id
    _next_id += 1
    ORDERS[order_id] = {"sku": sku, "qty": qty, "status": "confirmed"}
    return jsonify(order_id=order_id, **ORDERS[order_id]), 201


@app.get("/orders/<int:order_id>")
def get_order(order_id):
    order = ORDERS.get(order_id)
    if not order:
        return jsonify(error="not found"), 404
    return jsonify(order_id=order_id, **order)


@app.get("/version")
def version():
    return jsonify(service="orders-service", version=APP_VERSION)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
