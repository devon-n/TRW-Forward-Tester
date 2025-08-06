import json
import os
from flask import Flask, request, jsonify
from services.orders_service import execute_order
from utils.ip_whitelist import whitelist_ip


app = Flask(__name__)


@app.route("/")
def welcome():
    return ""


@app.route("/webhook", methods=["POST"])
@whitelist_ip
def webhook():
    """Handles incoming TradingView alerts via webhook and processes trades."""
    data = json.loads(request.data)
    print(f"\n data: {data}\n")
    # if data['passphrase'] != os.getenv('WEBHOOK_PASSPHRASE'):
    # return jsonify({"code": "error", "message": "Invalid passphrase"}), 403

    # Execute or simulate the order
    success = execute_order(data)

    if success:
        return jsonify({"code": "success", "message": "Order executed"})
    else:
        return jsonify({"code": "error", "message": "Order failed"})


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
