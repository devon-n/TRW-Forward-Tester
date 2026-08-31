import hmac
import os
from functools import lru_cache

from dotenv import load_dotenv
from flask import (
    Flask,
    abort,
    jsonify,
    request,
)
from pymongo import MongoClient

from config import (
    minQtyDict,
    precisionDecimalDict,
)

# Import exchanges
from exchanges.binance import place_order_binance
from exchanges.bybit import place_order_bybit
from exchanges.hyperliquid import place_order_hyperliquid
from errors import (
    ExchangeSubmissionError,
    InvalidFieldTypeError,
    MissingRequiredFieldError,
    PersistenceError,
    UnsupportedExchangeError,
)
from logging_utils import sanitize_dict

load_dotenv()

app = Flask(__name__)
mongo_client = None
trades_collection = None


REQUIRED_WEBHOOK_FIELDS = (
    ('strategyName',),
    ('ticker',),
    ('bar', 'time'),
    ('bar', 'close'),
    ('strategy', 'order_action'),
    ('strategy', 'order_contracts'),
    ('strategy', 'order_price'),
    ('strategy', 'position_size'),
    ('strategy', 'order_id'),
    ('strategy', 'market_position'),
    ('strategy', 'market_position_size'),
    ('strategy', 'prev_market_position'),
    ('strategy', 'prev_market_position_size'),
    ('leverage',),
)


@lru_cache(maxsize=1)
def get_whitelisted_ips():
    raw = os.environ.get('WHITELISTED_IPS', '')
    return {ip.strip() for ip in raw.split(',') if ip.strip()}


def get_webhook_secret():
    return os.environ.get('WEBHOOK_SECRET', '').strip()


def validate_webhook_payload(data):
    """Validate fields already required by execution and persistence paths."""
    for path in REQUIRED_WEBHOOK_FIELDS:
        current = data
        traversed = []
        for key in path:
            traversed.append(key)
            if not isinstance(current, dict):
                field = '.'.join(traversed[:-1])
                return InvalidFieldTypeError(field, "an object")
            if key not in current:
                return MissingRequiredFieldError('.'.join(path))
            current = current[key]

    quantity = data['strategy']['order_contracts']
    try:
        float(quantity)
    except (TypeError, ValueError):
        return InvalidFieldTypeError("strategy.order_contracts", "numeric")

    return None

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

def record_trade(data, order_response, failure=None):
    """Records trade to MongoDB with strategy information."""
    try:
        trade = {
            "time": data["bar"]["time"],
            "strategy_name": data["strategyName"],
            "symbol": data["ticker"],
            "timeframe":data.get("timeframe"),
            "close":data["bar"]["close"],
            "order_price": data["strategy"]["order_price"],
            "side": data['strategy']['order_action'].upper(),
            "quantity": data['strategy']['order_contracts'],
            "leverage": data["leverage"],
            "order_type": data.get("order_type", "PAPER"),
            "order_response": order_response,
            "strategy_position_size": data["strategy"]["position_size"],
            "strategy_order_id": data["strategy"]["order_id"],
            "strategy_market_position": data["strategy"]["market_position"],
            "strategy_market_position_size": data["strategy"]["market_position_size"],
            "prev_market_position": data["strategy"]["prev_market_position"],
            "prev_market_position_size": data["strategy"]["prev_market_position_size"]
        }
        if failure is not None:
            trade["failure"] = failure.to_dict() if hasattr(failure, "to_dict") else failure
        get_trades_collection().insert_one(trade)
        return True
    except Exception as e:
        PersistenceError().log(e)
        return False

def execute_order(data):
    """Executes a real Bybit/Binance order or simulates it for paper trading."""
    data.pop('passphrase', None)
    quantity = data['strategy']['order_contracts']
    ticker = data['ticker']
    order_type = str(data.get('order_type', 'PAPER')).upper()
    exchange = (data.get('exchange') or '').upper()
    data['order_type'] = order_type

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
                failure = ExchangeSubmissionError()
                record_trade(data, "Failed Real Order?", failure.to_dict())
                failure.log(e)
                return False

        elif exchange == "BYBIT":
            try:
                order_response = place_order_bybit(ticker, quantity, data)
                record_trade(data, order_response)
            except Exception as e:
                failure = ExchangeSubmissionError()
                record_trade(data, "Failed Real Order?", failure.to_dict())
                failure.log(e)
                return False
        elif exchange == "HYPERLIQUID":
            try:
                order_response = place_order_hyperliquid(ticker, quantity, data)
                record_trade(data, order_response)
            except Exception as e:
                failure = ExchangeSubmissionError()
                record_trade(data, "Failed Real Order?", failure.to_dict())
                failure.log(e)
                return False
        else:
            UnsupportedExchangeError().log()
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
        print(f"Raw body length: {len(request.data)} bytes")
        return jsonify({"status": "error", "reason": "invalid JSON"}), 400

    if not data or not isinstance(data, dict):
        print("Empty or invalid webhook data received — ignored")
        return jsonify({"status": "ignored", "reason": "empty payload"}), 400

    webhook_secret = get_webhook_secret()
    passphrase = data.get('passphrase', '')
    
    # Authentication: Only enforce if WEBHOOK_SECRET is configured in environment
    if (
        webhook_secret and (
            not isinstance(passphrase, str)
            or not hmac.compare_digest(passphrase, webhook_secret)
        )
    ):
        print("Unauthorized webhook request rejected")
        return jsonify({"status": "error", "message": "Invalid Passphrase"}), 401

    print(f"\n data: {sanitize_dict(data)}\n")

    data = dict(data)
    data.pop('passphrase', None)

    failure = validate_webhook_payload(data)
    if failure is not None:
        failure.log()
        return jsonify({"status": "error", "reason": "invalid payload", "failure": failure.to_dict()}), 400

    success = execute_order(data)

    if success:
        return jsonify({"code": "success", "message": "Order executed"}), 200
    else:
        return jsonify({"code": "error", "message": "Order failed"}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
