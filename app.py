import json
import threading
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
from datetime import datetime, timezone
import time

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
        print(f"Error while record_trade(): {e}")

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
        # Update min qty and precision
        ticker = ticker.replace('.P', '')
        ticker = ticker + "T" if ticker.endswith("USD") else ticker
        print(f"NEW ALERT\n<<{strategy_name}>> -{order_type} - {side} {quantity} {ticker} with leverage {leverage}")

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
                    print("Leverage already set.")
            else:
                print(f"Strategy '{strategy_name}' not found in strategy_keys.json.")

            if order_id != "SL": # Entry or TP order
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
                print(f"Real order executed: {order_type} - {side} {quantity} {ticker} | {order_response}")

                # Get order price from trade response
                record_trade(data, order_response)

            if stop_loss == "na": #SL or TP order
                #Check if all Trades are Executed
                open_orders = session.get_open_orders(category="linear",limit=1)
                open_order_id = open_orders["result"]["list"][0]["orderId"]
                while open_order_id != "": #Position not filled
                    print("Position still open. Waiting 30 seconds...")
                    time.sleep(30)

                #Check Recent Trade Info And Log It On Google Sheets
                close_pnl = session.get_closed_pnl(category="linear",limit=1)
                last_pnl = close_pnl["result"]["list"][0]  # Access the first item in the list
                print(f"Closed Pnl: {last_pnl}")
                pnl_symbol = last_pnl["symbol"]
                pnl_orderType = last_pnl["orderType"]
                pnl_leverage = last_pnl["leverage"]
                pnl_updatedTime = last_pnl["updatedTime"]
                pnl_side = last_pnl["side"]
                pnl_orderId = last_pnl["orderId"]
                pnl_closedPnl = last_pnl["closedPnl"]
                pnl_avgEntryPrice = last_pnl["avgEntryPrice"]
                pnl_qty = last_pnl["qty"]
                pnl_cumEntryValue = last_pnl["cumEntryValue"]
                pnl_createdTime = last_pnl["createdTime"]
                pnl_orderPrice = last_pnl["orderPrice"]
                pnl_closedSize = last_pnl["closedSize"]
                pnl_avgExitPrice = last_pnl["avgExitPrice"]
                pnl_execType = last_pnl["execType"]
                pnl_fillCount = last_pnl["fillCount"]
                pnl_cumExitValue = last_pnl["cumExitValue"]
                current_date = datetime.now(timezone.utc).strftime("%d/%m/%Y")
                current_time = datetime.now(timezone.utc).strftime("%H:%M:%S")
                # Open the spreadsheet and worksheet
                spreadsheet = client.open("Live Trading")
                sheet = spreadsheet.worksheet("Automated Trades")

                # Sample data to append
                trade_data = [
                    strategy_name,
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
                balance_list = balance_response["result"]["list"][0]
                balance = float(balance_list["totalEquity"])
                floor_balance = floor(balance)
                target_capital = 500
                excess_capital = abs(floor_balance - target_capital)

                if floor_balance > target_capital: #Has Excess Capital
                    try:
                        session.create_universal_transfer(
                            transferId = str(uuid.uuid4()),
                            coin = "USDT",
                            amount = str(excess_capital),
                            fromMemberId = int(uid),
                            toMemberId = int(os.environ.get('MAIN_UID')), #Main UID
                            fromAccountType = "UNIFIED",
                            toAccountType = "UNIFIED",
                        )
                        print(f"Profit Moved to Main Account from UID: {uid}")
                    except Exception as e:
                        print(f"Error while Line 239 Universal Transfer: {e}")
                if floor_balance < target_capital: #Needs More Capital
                    try:
                        session = HTTP(
                            testnet=False,
                            api_key=os.getenv('API_KEY_0'),
                            api_secret=os.getenv('API_SECRET_0'),
                        )
                        main_balance = session.get_coin_balance(
                            accountType="UNIFIED",
                            coin="USDT",
                            memberId=int(os.environ.get('MAIN_UID')),
                        )
                        if float(main_balance['result']['balance']['transferBalance']) > excess_capital:
                            try:
                                session.create_universal_transfer(
                                    transferId = str(uuid.uuid4()),
                                    coin = "USDT",
                                    amount = str(excess_capital),
                                    fromMemberId = int(os.environ.get('MAIN_UID')),
                                    toMemberId = int(uid),
                                    fromAccountType = "UNIFIED",
                                    toAccountType = "UNIFIED",
                                )
                                print(f"Loss Balance Filled from Main Account to UID: {uid}")
                            except Exception as e:
                                print(f"Error while Line 265 Universal Transfer: {e}")
                        else:
                            print(f"Not enough balance in Main Account to fill Sub Account: {uid}")
                    except Exception as e:
                        print(f"Error while Line 251 Universal Transfer: {e}")

        else:
            print(f"Simulated paper order: {order_type} - {side} {quantity} {ticker}")
            record_trade(data, None)
        return True
    except Exception as e:
        record_trade(data, "Failed Real Order?")
        print(f"Error while execute_order(): {e}")
        return False

@app.route('/')
def welcome():
    return ""

@app.route('/webhook', methods=['POST'])
@whitelist_ip
def webhook():
    """Handles incoming TradingView alerts via webhook and processes trades."""
    data = json.loads(request.data)
    #print(f"\n data: {data}\n")
    # if data['passphrase'] != os.getenv('WEBHOOK_PASSPHRASE'):
    # return jsonify({"code": "error", "message": "Invalid passphrase"}), 403

    # Execute or simulate the order
    order_thread = threading.Thread(target=execute_order,args=(data,))
    order_thread.start()
    return "Thread started."

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
