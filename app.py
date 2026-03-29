import os
from flask import Flask, request, jsonify, abort
from pymongo import MongoClient
from dotenv import load_dotenv
from functools import lru_cache
from config import minQtyDict, precisionDecimalDict

# Import exchanges
from exchanges.binance import place_order_binance
from exchanges.bybit import place_order_bybit
from exchanges.hyperliquid import place_order_hyperliquid

load_dotenv()

app = Flask(__name__)
mongo_client = None
trades_collection = None


@lru_cache(maxsize=1)
def get_whitelisted_ips():
    raw = os.environ.get('WHITELISTED_IPS', '')
    return {ip.strip() for ip in raw.split(',') if ip.strip()}

# Decorator to restrict access to whitelisted IPs only
def whitelist_ip(func):
    def wrapper(*args, **kwargs):
        # Get whitelisted IP addresses from environment variable
        whitelisted_ips = get_whitelisted_ips()
        real_ip = (str(request.headers.get('X-Forwarded-For', request.remote_addr))).split(',')[0].strip()
        if real_ip not in whitelisted_ips:
            message = f"Access denied: Your IP {real_ip} is not allowed."
            abort(403, description=message)
        return func(*args, **kwargs)
    return wrapper


def get_mongo_client():
    """Create the Mongo client lazily so each Gunicorn worker owns its own pool."""
    global mongo_client

    if mongo_client is None:
        mongo_uri = os.getenv('MONGO_URI')
        if not mongo_uri:
            raise RuntimeError("MONGO_URI is not set")
        mongo_client = MongoClient(mongo_uri)
    return mongo_client


def get_trades_collection():
    global trades_collection

    if trades_collection is None:
        trades_collection = get_mongo_client().trading.trades
    return trades_collection

def record_trade(data, order_response):
    """Records trade to MongoDB with strategy information."""
    try:
        get_trades_collection().insert_one({
            "time": data["bar"]["time"],
            "strategy_name": data["strategyName"],
            "symbol": data["ticker"],
            "timeframe":data.get("timeframe"),
            "close":data["bar"]["close"],
            "order_price": data["strategy"]["order_price"],
            "side": data['strategy']['order_action'].upper(),
            "quantity": data['strategy']['order_contracts'],
            "leverage": data["leverage"],
            "order_type": data["order_type"],
            "order_response": order_response,
            "strategy_position_size": data["strategy"]["position_size"],
            "strategy_order_id": data["strategy"]["order_id"],
            "strategy_market_position": data["strategy"]["market_position"],
            "strategy_market_position_size": data["strategy"]["market_position_size"],
            "prev_market_position": data["strategy"]["prev_market_position"],
            "prev_market_position_size": data["strategy"]["prev_market_position_size"]
        })
    except Exception as e:
        print(f"Failed Order: An exception occurred: {e}")

def execute_order(data):
    """Executes a real Bybit/Binance order or simulates it for paper trading."""
    quantity = data['strategy']['order_contracts']
    ticker = data['ticker']
    order_type = data.get('order_type', 'PAPER').upper()  # Default to paper trading
    exchange = (data.get('exchange') or '').upper()

    # Update min qty and precision
    ticker = ticker.replace('.P', '')
    ticker = ticker + "T" if ticker.endswith("USD") else ticker
    if ticker in minQtyDict:
        if float(quantity) < float(minQtyDict[ticker]):
            quantity = minQtyDict[ticker]

    if ticker in precisionDecimalDict:
        quantity = str(round(float(quantity), precisionDecimalDict[ticker]))

    data['strategy']['order_contracts'] = quantity

    if order_type == "REAL":
        if exchange == "BINANCE":
            try:
                order_response = place_order_binance(ticker, quantity, data)
                record_trade(data, order_response)
            except Exception as e:
                record_trade(data, "Failed Real Order?")
                print(f"Failed Order(Binance): {e}")
                return False

        elif exchange == "BYBIT":
            try:
                order_response = place_order_bybit(ticker, quantity, data)
                record_trade(data, order_response)
            except Exception as e:
                record_trade(data, "Failed Real Order?")
                print(f"Failed Order(Bybit): {e}")
                return False
        elif exchange == "HYPERLIQUID":
            try:
                order_response = place_order_hyperliquid(ticker, quantity, data)
                record_trade(data, order_response)
            except Exception as e:
                record_trade(data, "Failed Real Order?")
                print(f"Failed Order(Hyperliquid): {e}")
                return False
        else:
            print("Execution Error: No exchange value matching Binance, Bybit, or Hyperliquid")
            return False
    else:
        side = data['strategy']['order_action'].upper()
        print(f"Simulated paper order: {order_type} - {side} {quantity} {ticker}")
        record_trade(data, None)
    return True


@app.route('/')
def welcome():
    return ""

@app.route('/webhook', methods=['POST'])
@whitelist_ip
def webhook():
    #Handle empty payloads
    if not request.data or request.content_length == 0:
        print("Empty webhook payload received — ignored")
        return jsonify({"status": "ignored", "reason": "empty payload"}), 400

    try:
        data = request.get_json(force=True)
    except Exception as e:
        print("Invalid JSON received")
        print("Error:", e)
        print("Raw body:", request.data)
        return jsonify({"status": "error", "reason": "invalid JSON"}), 400

    print(f"\n data: {data}\n")

    if not data or not isinstance(data, dict):
        print("Empty or invalid webhook data received — ignored")
        return jsonify({"status": "ignored", "reason": "empty payload"}), 400

    success = execute_order(data)

    if success:
        return jsonify({"code": "success", "message": "Order executed"}), 200
    else:
        return jsonify({"code": "error", "message": "Order failed"}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
