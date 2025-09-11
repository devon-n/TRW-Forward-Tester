import json
import os
from flask import Flask, request, jsonify, abort
from binance.um_futures import UMFutures
from pybit.unified_trading import HTTP
from pymongo import MongoClient  # type: ignore
from dotenv import load_dotenv
from functools import lru_cache
from config import minQtyDict, precisionDecimalDict

load_dotenv()

app = Flask(__name__)


@lru_cache(maxsize=1)
def get_whitelisted_ips():
    return set(os.environ.get('WHITELISTED_IPS', '').split(','))


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


# Connect to MongoDB
mongo_client = MongoClient(os.getenv('MONGO_URI'))
db = mongo_client.trading
trades_collection = db.trades


def record_trade(data, order_response):
    """Records trade to MongoDB with strategy information."""
    try:
        trades_collection.insert_one({
            "time": data["bar"]["time"],
            "strategy_name": data["strategyName"],
            "symbol": data["ticker"],
            "timeframe": data.get("timeframe"),
            "close": data["bar"]["close"],
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
    try:
        side = data['strategy']['order_action'][0].upper() + data['strategy']['order_action'][1:]
        quantity = data['strategy']['order_contracts']
        ticker = data['ticker']
        leverage = int(data.get('leverage', 0))  # Default leverage to 0 if not provided
        order_type = data.get('order_type', 'PAPER').upper()  # Default to paper trading
        exchange = data.get('exchange', 'BINANCE')
        print(f"Preparing order {order_type} - {side} {quantity} {ticker} with leverage {leverage}")

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
            if exchange == "BYBIT":
                # Initialize Bybit HTTP with environment variables
                session = HTTP(
                    testnet=False,
                    api_key=os.getenv('API_KEY'),
                    api_secret=os.getenv('API_SECRET'),
                )
                print(f"\nSending Order: {json.dumps(data)}\n")

                order_response = session.place_order(
                    category="linear",
                    symbol=ticker,
                    side=side,
                    orderType="Market",
                    qty=quantity,
                )
                print(f"Real order executed: {order_type} - {side} {quantity} {ticker} | {order_response}")

                # Get order price from trade response
                record_trade(data, order_response)

            elif exchange == "BINANCE":
                # Initialize Binance client with environment variables
                client = UMFutures(os.getenv('API_KEY'), os.getenv('API_SECRET'))
                # client.futures_change_leverage(symbol=ticker, leverage=leverage)
                # client.futures_change_margin_type(symbol=ticker, marginType="ISOLATED")
                print(f"\nSending Order: {json.dumps(data)}\n")

                order_response = client.new_order(
                    symbol=ticker,
                    side=side,
                    type="MARKET",
                    quantity=quantity
                    )
                print(f"Real order executed: {order_type} - {side} {quantity} {ticker} | {order_response}")

                # Get order price from trade response
                record_trade(data, order_response)
            else:
                print("Execution Error: No exchange value matching Bybit or Binance")
        else:
            print(f"Simulated paper order: {order_type} - {side} {quantity} {ticker}")
            record_trade(data, None)
        return True
    except Exception as e:
        record_trade(data, "Failed Real Order?")
        print(f"Failed Order: An exception occurred: {e}")
        return False


@app.route('/')
def welcome():
    return ""


@app.route('/webhook', methods=['POST'])
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


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)