import hmac
from functools import lru_cache

from flask import (
    Flask,
    abort,
    jsonify,
    request,
)
from config.settings import (
    minQtyDict,
    precisionDecimalDict,
)
from config.config import AppSettings

# Import exchanges
from exchanges.binance import place_order_binance
from exchanges.bybit import place_order_bybit
from exchanges.hyperliquid import place_order_hyperliquid
from repositories.mongo import MongoRepository
from utils.errors import (
    ExchangeSubmissionError,
    InvalidPositiveQuantityError,
    MissingCredentialError,
    PersistenceError,
    TRWError,
)
from utils.logging_utils import sanitize_dict
from models.enums import (
    Exchange,
    OrderType,
)
from models.webhook import WebhookPayload

app_settings = AppSettings()
app_settings.validate_required('MONGO_URI', 'WHITELISTED_IPS')

app = Flask(__name__)
mongo_client = None
trades_collection = None
mongo_repository = MongoRepository()


@lru_cache(maxsize=1)
def get_whitelisted_ips():
    return {ip.strip() for ip in app_settings.WHITELISTED_IPS.split(',') if ip.strip()}


def get_webhook_secret():
    return (app_settings.WEBHOOK_SECRET or '').strip()


def _normalize_ticker(ticker):
    normalized = ticker.replace('.P', '')
    return normalized + "T" if normalized.endswith("USD") else normalized


def _quantity_validation_failure(quantity):
    try:
        number = WebhookPayload.parse_finite_number(quantity, "strategy.order_contracts")
    except TRWError as failure:
        return failure
    if number <= 0:
        return InvalidPositiveQuantityError()
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
        mongo_client = mongo_repository.get_mongo_client()
    return mongo_client


def get_trades_collection():
    global trades_collection

    if trades_collection is None:
        trades_collection = mongo_repository.get_trades_collection()
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
        mongo_repository.insert_trade(trade, collection=get_trades_collection())
        return True
    except Exception as e:
        PersistenceError().log(e)
        return False

def execute_order(data):
    """Executes a real Bybit/Binance order or simulates it for paper trading."""
    try:
        payload = WebhookPayload.from_dict(data)
    except TRWError as failure:
        failure.log()
        return False

    data.clear()
    data.update(payload.to_execution_dict())

    quantity = data['strategy']['order_contracts']
    ticker = data['ticker']
    order_type = payload.order_type
    exchange = payload.exchange

    failure = _quantity_validation_failure(quantity)
    if failure is not None:
        failure.log()
        return False
    side = payload.order_action

    # Update min qty and precision
    ticker = _normalize_ticker(ticker)
    if ticker in minQtyDict:
        if float(quantity) < float(minQtyDict[ticker]):
            quantity = minQtyDict[ticker]

    if ticker in precisionDecimalDict:
        quantity = str(round(float(quantity), precisionDecimalDict[ticker]))

    failure = _quantity_validation_failure(quantity)
    if failure is not None:
        failure.log()
        return False

    data['strategy']['order_contracts'] = quantity

    if order_type == OrderType.REAL:
        if exchange == Exchange.BINANCE:
            try:
                order_response = place_order_binance(ticker, quantity, data)
                record_trade(data, order_response)
            except MissingCredentialError as failure:
                record_trade(data, "Failed Real Order?", failure.to_dict())
                failure.log()
                return False
            except Exception as e:
                failure = ExchangeSubmissionError()
                record_trade(data, "Failed Real Order?", failure.to_dict())
                failure.log(e)
                return False

        elif exchange == Exchange.BYBIT:
            try:
                order_response = place_order_bybit(ticker, quantity, data)
                record_trade(data, order_response)
            except MissingCredentialError as failure:
                record_trade(data, "Failed Real Order?", failure.to_dict())
                failure.log()
                return False
            except Exception as e:
                failure = ExchangeSubmissionError()
                record_trade(data, "Failed Real Order?", failure.to_dict())
                failure.log(e)
                return False
        elif exchange == Exchange.HYPERLIQUID:
            try:
                order_response = place_order_hyperliquid(ticker, quantity, data)
                record_trade(data, order_response)
            except MissingCredentialError as failure:
                record_trade(data, "Failed Real Order?", failure.to_dict())
                failure.log()
                return False
            except Exception as e:
                failure = ExchangeSubmissionError()
                record_trade(data, "Failed Real Order?", failure.to_dict())
                failure.log(e)
                return False
        else:
            return False
    else:
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

    try:
        payload = WebhookPayload.from_dict(data)
    except TRWError as failure:
        failure.log()
        return jsonify({"status": "error", "reason": "invalid payload", "failure": failure.to_dict()}), 400

    success = execute_order(payload.to_execution_dict())

    if success:
        return jsonify({"code": "success", "message": "Order executed"}), 200
    else:
        return jsonify({"code": "error", "message": "Order failed"}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
