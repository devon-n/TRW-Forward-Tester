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
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

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
# Connect to Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", scope)
client = gspread.authorize(creds)

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
    """Executes a real Bybit order or simulates it for paper trading."""
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
            # Initialize Bybit HTTP with environment variables
            with open("strategy_keys.json", "r") as f:
                strategy_keys = json.load(f)
            if strategy_name in strategy_keys:
                key_entry = strategy_keys[strategy_name]
                api_key_env = key_entry['api_key']
                api_secret_env = key_entry['api_secret']

                session = HTTP(
                    testnet=False,
                    api_key=os.getenv(api_key_env),
                    api_secret=os.getenv(api_secret_env),
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
            else:
                print(f"Strategy '{strategy_name}' not found in strategy_keys.json.")

            if order_id != "SL":
                print(f"\nSending Order: {json.dumps(data)}\n")
                if side == "Buy":
                    order_params = {
                        "category": "linear",
                        "symbol": ticker,
                        "side": side,
                        "orderType": "Limit",
                        "qty": quantity,
                        "price": str(float(order_price) - 0.02)
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
                        "price": str(float(order_price) + 0.02)
                    }
                    if stop_loss != "na":
                        order_params["stopLoss"] = stop_loss
                    order_response = session.place_order(**order_params)
                print(f"Real order executed: {order_type} - {side} {quantity} {ticker} | {order_response}")

                # Get order price from trade response
                record_trade(data, order_response)

            if stop_loss == "na": #SL or TP order
                #Check Recent Trade Info And Log It On Google Sheets
                close_pnl = session.get_closed_pnl(category="linear",limit=1)
                print(f"Closed Pnl: {close_pnl}")
                pnl_symbol = close_pnl["result"]["list"]["symbol"]
                pnl_orderType = close_pnl["result"]["list"]["orderType"]
                pnl_leverage = close_pnl["result"]["list"]["leverage"]
                pnl_updatedTime = close_pnl["result"]["list"]["updatedTime"]
                pnl_side = close_pnl["result"]["list"]["side"]
                pnl_orderId = close_pnl["result"]["list"]["orderId"]
                pnl_closedPnl = close_pnl["result"]["list"]["closedPnl"]
                pnl_avgEntryPrice = close_pnl["result"]["list"]["avgEntryPrice"]
                pnl_qty = close_pnl["result"]["list"]["qty"]
                pnl_cumEntryValue = close_pnl["result"]["list"]["cumEntryValue"]
                pnl_createdTime = close_pnl["result"]["list"]["createdTime"]
                pnl_orderPrice = close_pnl["result"]["list"]["orderPrice"]
                pnl_closedSize = close_pnl["result"]["list"]["closedSize"]
                pnl_avgExitPrice = close_pnl["result"]["list"]["avgExitPrice"]
                pnl_execType = close_pnl["result"]["list"]["execType"]
                pnl_fillCount = close_pnl["result"]["list"]["fillCount"]
                pnl_cumExitValue = close_pnl["result"]["list"]["cumExitValue"]
                current_date = datetime. datetime. now(datetime. UTC).strftime("%d/%m/%Y")
                current_time = datetime. datetime. now(datetime. UTC).strftime("%H:%M:%S")
                # Open the spreadsheet and worksheet
                spreadsheet = client.open("Live Trading")
                sheet = spreadsheet.worksheet("Automated Trades")

                # Sample data to append
                trade_data = [
                    current_date,  # date
                    current_time,
                    pnl_symbol,  # symbol
                    pnl_orderType,
                    pnl_leverage,
                    pnl_updatedTime,
                    pnl_side, # direction
                    pnl_orderId,
                    pnl_closedPnl,
                    pnl_avgEntryPrice, # entry
                    pnl_qty, # quantity
                    pnl_cumEntryValue,
                    pnl_createdTime,
                    pnl_orderPrice,
                    pnl_closedSize,
                    pnl_avgExitPrice, # exit
                    pnl_execType,
                    pnl_fillCount,
                    pnl_cumExitValue
                ]
                try:
                    sheet.append_row(trade_data)
                    print(f"Logged Trade Data: {trade_data}")
                except Exception as e:
                    print(f"Failed Logging Trade: {e}")

                # Better if confirm no trades open.
                balance_response = session.get_wallet_balance(
                    accountType="UNIFIED",
                    coin="USDT",
                )
                print(f"Rebalancing: {balance_response}")
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
                    print(f"Profit Moved to Main Account from UID: {uid}")
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
                        print(f"Loss Balance Filled from Main Account to UID: {uid}")
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
