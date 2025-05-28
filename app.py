import json
import uuid
from math import floor
import os
from flask import Flask, request, jsonify, abort
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
            "leverage": data.get('alert_message', '').split(',')[0],
            "stop_loss": data.get('alert_message', '').split(',')[1],
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
    """Executes a real Binance order or simulates it for paper trading."""
    # print(f"\nOrder: {json.dumps(data)}\n")
    try:
        side = data['strategy']['order_action'][0].upper() + data['strategy']['order_action'][1:]
        quantity = data['strategy']['order_contracts']
        ticker = data['ticker']

        leverage, stop_loss = data.get('alert_message').split(",")
        # leverage = int(data.get('leverage', 0))  # Default leverage to 0 if not provided
        order_type = data.get('order_type', 'PAPER').upper()  # Default to paper trading
        order_price = data['strategy']['order_price']
        order_id = data['strategy']['order_id']
        strategy_name = data['strategyName']
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
            if order_id != "SL":
                # Initialize Bybit HTTP with environment variables
                if strategy_name == "BTCUSDT 1D MACD Confirmation (1D)" or strategy_name == "BTCUSDT 1D Peako Bottom Bidding (1D)" or "Testing":
                    session = HTTP(
                        testnet=False,
                        api_key=os.getenv('API_KEY_0'),
                        api_secret=os.getenv('API_SECRET_0'),
                    )
                    key_information = session.get_api_key_information()
                    uid = key_information['result']['id']
                    try:
                        session.set_leverage(
                            category="linear",
                            symbol=ticker,
                            buyLeverage=leverage,
                            sellLeverage=leverage,
                        )
                    except:
                        print("Leverage already set at level.")
                if strategy_name == "BTCUSDT 15m Impulse BoS Wick (Short) (Tue)":
                    session = HTTP(
                        testnet=False,
                        api_key=os.getenv('API_KEY_1'),
                        api_secret=os.getenv('API_SECRET_1'),
                    )
                    key_information = session.get_api_key_information()
                    uid = key_information['result']['id']
                    try:
                        session.set_leverage(
                            category="linear",
                            symbol=ticker,
                            buyLeverage=leverage,
                            sellLeverage=leverage,
                        )
                    except:
                        print("Leverage already set at level.")
                if strategy_name == "BTCUSDT 15m Impulsive BoS (Short) (Tue/Fri)":
                    session = HTTP(
                        testnet=False,
                        api_key=os.getenv('API_KEY_2'),
                        api_secret=os.getenv('API_SECRET_2'),
                    )
                    key_information = session.get_api_key_information()
                    uid = key_information['result']['id']
                    try:
                        session.set_leverage(
                            category="linear",
                            symbol=ticker,
                            buyLeverage=leverage,
                            sellLeverage=leverage,
                        )
                    except:
                        print("Leverage already set at level.")
                if strategy_name == "BTCUSDT 15m Reversal (Short) (Mon/Thu)":
                    session = HTTP(
                        testnet=False,
                        api_key=os.getenv('API_KEY_3'),
                        api_secret=os.getenv('API_SECRET_3'),
                    )
                    key_information = session.get_api_key_information()
                    uid = key_information['result']['id']
                    try:
                        session.set_leverage(
                            category="linear",
                            symbol=ticker,
                            buyLeverage=leverage,
                            sellLeverage=leverage,
                        )
                    except:
                        print("Leverage already set at level.")
                if strategy_name == "BTCUSDT 15m Daily Open (Short) (Wed/Thu)":
                    session = HTTP(
                        testnet=False,
                        api_key=os.getenv('API_KEY_4'),
                        api_secret=os.getenv('API_SECRET_4'),
                    )
                    key_information = session.get_api_key_information()
                    uid = key_information['result']['id']
                    try:
                        session.set_leverage(
                            category="linear",
                            symbol=ticker,
                            buyLeverage=leverage,
                            sellLeverage=leverage,
                        )
                    except:
                        print("Leverage already set at level.")
                if strategy_name == "BTCUSDT 15m Impulse BoS Wick (Long) (Mon/Tue/Thu)":
                    session = HTTP(
                        testnet=False,
                        api_key=os.getenv('API_KEY_5'),
                        api_secret=os.getenv('API_SECRET_5'),
                    )
                    key_information = session.get_api_key_information()
                    uid = key_information['result']['id']
                    try:
                        session.set_leverage(
                            category="linear",
                            symbol=ticker,
                            buyLeverage=leverage,
                            sellLeverage=leverage,
                        )
                    except:
                        print("Leverage already set at level.")
                if strategy_name == "BTCUSDT 15m MACD Confirmation (Long) (ALL)":
                    session = HTTP(
                        testnet=False,
                        api_key=os.getenv('API_KEY_6'),
                        api_secret=os.getenv('API_SECRET_6'),
                    )
                    key_information = session.get_api_key_information()
                    uid = key_information['result']['id']
                    try:
                        session.set_leverage(
                            category="linear",
                            symbol=ticker,
                            buyLeverage=leverage,
                            sellLeverage=leverage,
                        )
                    except:
                        print("Leverage already set at level.")
                if strategy_name == "BTCUSDT 15m Impulsive BoS (Long) (Mon/Tue/Wed)":
                    session = HTTP(
                        testnet=False,
                        api_key=os.getenv('API_KEY_7'),
                        api_secret=os.getenv('API_SECRET_7'),
                    )
                    key_information = session.get_api_key_information()
                    uid = key_information['result']['id']
                    try:
                        session.set_leverage(
                            category="linear",
                            symbol=ticker,
                            buyLeverage=leverage,
                            sellLeverage=leverage,
                        )
                    except:
                        print("Leverage already set at level.")
                if strategy_name == "BTCUSDT 15m Asia Open (Long) (Mon/Sun)":
                    session = HTTP(
                        testnet=False,
                        api_key=os.getenv('API_KEY_8'),
                        api_secret=os.getenv('API_SECRET_8'),
                    )
                    key_information = session.get_api_key_information()
                    uid = key_information['result']['id']
                    try:
                        session.set_leverage(
                            category="linear",
                            symbol=ticker,
                            buyLeverage=leverage,
                            sellLeverage=leverage,
                        )
                    except:
                        print("Leverage already set at level.")
                if strategy_name == "BTCUSDT 15m London Open (Long) (Mon,Tue,Thu,Fri)":
                    session = HTTP(
                        testnet=False,
                        api_key=os.getenv('API_KEY_9'),
                        api_secret=os.getenv('API_SECRET_9'),
                    )
                    key_information = session.get_api_key_information()
                    uid = key_information['result']['id']
                    try:
                        session.set_leverage(
                            category="linear",
                            symbol=ticker,
                            buyLeverage=leverage,
                            sellLeverage=leverage,
                        )
                    except:
                        print("Leverage already set at level.")
                if strategy_name == "BTCUSDT 15m Reversal (Long) (Mon/Tue)":
                    session = HTTP(
                        testnet=False,
                        api_key=os.getenv('API_KEY_10'),
                        api_secret=os.getenv('API_SECRET_10'),
                    )
                    key_information = session.get_api_key_information()
                    uid = key_information['result']['id']
                    try:
                        session.set_leverage(
                            category="linear",
                            symbol=ticker,
                            buyLeverage=leverage,
                            sellLeverage=leverage,
                        )
                    except:
                        print("Leverage already set at level.")
                if strategy_name == "BTCUSDT 15m BoS Retest in Trend (Long) (Mon/Fri/Sat/Sun)":
                    session = HTTP(
                        testnet=False,
                        api_key=os.getenv('API_KEY_11'),
                        api_secret=os.getenv('API_SECRET_11'),
                    )
                    key_information = session.get_api_key_information()
                    uid = key_information['result']['id']
                    try:
                        session.set_leverage(
                            category="linear",
                            symbol=ticker,
                            buyLeverage=leverage,
                            sellLeverage=leverage,
                        )
                    except:
                        print("Leverage already set at level.")
                if strategy_name == "BTCUSDT 15m NY Open (Long) (Mon/Tue/Sun)":
                    session = HTTP(
                        testnet=False,
                        api_key=os.getenv('API_KEY_12'),
                        api_secret=os.getenv('API_SECRET_12'),
                    )
                    key_information = session.get_api_key_information()
                    uid = key_information['result']['id']
                    try:
                        session.set_leverage(
                            category="linear",
                            symbol=ticker,
                            buyLeverage=leverage,
                            sellLeverage=leverage,
                        )
                    except:
                        print("Leverage already set at level.")
                if strategy_name == "BTCUSDT 15m Daily Open (Long) (Mon/Wed)":
                    session = HTTP(
                        testnet=False,
                        api_key=os.getenv('API_KEY_13'),
                        api_secret=os.getenv('API_SECRET_13'),
                    )
                    key_information = session.get_api_key_information()
                    uid = key_information['result']['id']
                    try:
                        session.set_leverage(
                            category="linear",
                            symbol=ticker,
                            buyLeverage=leverage,
                            sellLeverage=leverage,
                        )
                    except:
                        print("Leverage already set at level.")
                # Initialize Binance client with environment variables
                # client = UMFutures(os.getenv('API_KEY'), os.getenv('API_SECRET'))
                # client.futures_change_leverage(symbol=ticker, leverage=leverage)
                # client.futures_change_margin_type(symbol=ticker, marginType="ISOLATED")
                print(f"\nSending Order: {json.dumps(data)}\n")
                if side == "Buy":
                    order_params = {
                        "category": "linear",
                        "symbol": ticker,
                        "side": side,
                        "orderType": "Limit",
                        "qty": quantity,
                        "price": str(float(order_price) - 0.01)
                    }
                    if stop_loss != "na":
                        order_params["stopLoss"] = stop_loss
                    order_response = session.place_order(**order_params)
                if side == "Sell":
                    order_params = {
                        "category": "linear",
                        "symbol": ticker,
                        "side": side,
                        "orderType": "Limit",
                        "qty": quantity,
                        "price": str(float(order_price) + 0.01)
                    }
                    if stop_loss != "na":
                        order_params["stopLoss"] = stop_loss
                    order_response = session.place_order(**order_params)

                # order_response = client.new_order(
                #    symbol=ticker,
                #    side=side,
                #    type="MARKET",
                #    quantity=quantity
                #    )
                print(f"Real order executed: {order_type} - {side} {quantity} {ticker} | {order_response}")

                # Get order price from trade response
                record_trade(data, order_response)

                if stop_loss == "na":
                    # Better if confirm no trades open.
                    balance_response = session.get_wallet_balance(
                        accountType="UNIFIED",
                        coin="USDT",
                    )
                    balance = float(balance_response["totalEquity"])
                    floor_balance = floor(balance)
                    target_capital = 500
                    excess_capital = abs(floor_balance - target_capital)

                    if floor_balance > target_capital: #Has Excess Capital
                        session.create_universal_transfer(
                            transferId = str(uuid.uuid4()),
                            coin = "USDT",
                            amount = excess_capital,
                            fromMemberId = uid,
                            toMemberId = os.environ.get('MAIN_UID'), #Main UID
                            fromAccountType = "UNIFIED",
                            toAccountType = "UNIFIED",
                        )
                    if floor_balance < target_capital: #Needs More Capital
                        session = HTTP(
                            testnet=False,
                            api_key=os.getenv('API_KEY_0'),
                            api_secret=os.getenv('API_SECRET_0'),
                        )
                        main_balance = session.get_coin_balance(
                            accountType="UNIFIED",
                            coin="USDT",
                            memberId=os.environ.get('MAIN_UID'),
                        )
                        if float(main_balance['result']['balance']['transferBalance']) > excess_capital:
                            session.create_universal_transfer(
                                transferId = str(uuid.uuid4()),
                                coin = "USDT",
                                amount = excess_capital,
                                fromMemberId = os.environ.get('MAIN_UID'),
                                toMemberId = uid,
                                fromAccountType = "UNIFIED",
                                toAccountType = "UNIFIED",
                            )
                        else:
                            print(f"Not enough balance in Main Account to fill Sub Account: {uid}")

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
