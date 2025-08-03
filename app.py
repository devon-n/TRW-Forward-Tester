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

        timeframe = data['timeframe']
        entry_tp_sl, leverage, stop_loss = data.get('alert_message').split(",")
        # leverage = int(data.get('leverage', 0))  # Default leverage to 0 if not provided
        order_type = data.get('order_type', 'PAPER').upper()  # Default to paper trading
        order_price = data['strategy']['order_price']
        order_id = data['strategy']['order_id']
        strategy_name = data['strategyName']
        # Update min qty and precision
        ticker = ticker.replace('.P', '')
        ticker = ticker + "T" if ticker.endswith("USD") else ticker
        print(f"NEW ALERT: {strategy_name}\n{side} {quantity} {ticker}\n{leverage}x Leverage")

        #if ticker in minQtyDict:
            #if float(quantity) < float(minQtyDict[ticker]):
                #quantity = minQtyDict[ticker]

        #if ticker in precisionDecimalDict:
            #quantity = str(round(float(quantity), precisionDecimalDict[ticker]))

        #data['strategy']['order_contracts'] = quantity

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
                account_balance = session.get_coin_balance(
                    accountType="UNIFIED",
                    coin="USDT",
                )
                initial_uid =account_balance['result']['memberId']
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

            print(f"\nSending Order: {json.dumps(data)}\n")
            if entry_tp_sl == "Entry":
                if side == "Buy":
                    order_params = {
                        "category": "linear",
                        "symbol": ticker,
                        "side": side,
                        "orderType": "Limit",
                        "qty": quantity,
                        "price": str(float(order_price) - 0.01),
                        "timeInForce": "PostOnly"
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
                        "price": str(float(order_price) + 0.01),
                        "timeInForce": "PostOnly"
                    }
                    if stop_loss != "na":
                        order_params["stopLoss"] = stop_loss
                    order_response = session.place_order(**order_params)
                print(f"<<Entry>> order executed: {order_type} - {side} {quantity} {ticker} | {order_response}")

                # Start Logging
                print("Waiting 30 seconds to log trade on Google Sheets...")
                time.sleep(30)
                order_history = session.get_order_history(
                    category="linear",
                    symbol=ticker,
                    limit=1,
                )
                last_order = order_history["result"]["list"][0]  # Access the first item in the list
                # print(f"Order History: {last_order}")
                current_date = datetime.now(timezone.utc).strftime("%d/%m/%Y")
                current_time = datetime.now(timezone.utc).strftime("%H:%M:%S")
                # Open the spreadsheet and worksheet

                spreadsheet = client.open("Live Trading")
                sheet = spreadsheet.worksheet("Order History (A)")

                # Sample data to append
                order_data = [
                    timeframe,
                    strategy_name,
                    current_date,  # date
                    current_time,
                    last_order["orderId"],
                    last_order["orderLinkId"],
                    last_order["blockTradeId"],
                    last_order["symbol"],  # symbol
                    last_order["price"],
                    last_order["qty"],  # quantity
                    last_order["side"],  # direction
                    last_order["isLeverage"],
                    last_order["positionIdx"],
                    last_order["orderStatus"],
                    last_order["cancelType"],
                    last_order["rejectReason"],
                    last_order["avgPrice"],
                    last_order["leavesQty"],
                    last_order["leavesValue"],
                    last_order["cumExecQty"],
                    last_order["cumExecValue"],
                    last_order["cumExecFee"],
                    last_order["timeInForce"],
                    last_order["orderType"],
                    last_order["stopOrderType"],
                    last_order["orderIv"],
                    last_order["triggerPrice"],
                    last_order["takeProfit"],
                    last_order["stopLoss"],
                    last_order["tpTriggerBy"],
                    last_order["slTriggerBy"],
                    last_order["triggerDirection"],
                    last_order["triggerBy"],
                    last_order["lastPriceOnCreated"],
                    last_order["reduceOnly"],
                    last_order["closeOnTrigger"],
                    last_order["smpType"],
                    last_order["smpGroup"],
                    last_order["smpOrderId"],
                    last_order["tpslMode"],
                    last_order["tpLimitPrice"],
                    last_order["slLimitPrice"],
                    last_order["placeType"],
                    last_order["slippageToleranceType"],
                    last_order["slippageTolerance"],
                    last_order["createdTime"],
                    last_order["updatedTime"],
                    last_order["extraFees"]
                ]
                try:
                    sheet.append_row(order_data)
                    # print(f"Logged Trade Data: {order_data}")
                except Exception as e:
                    print(f"Error While Logging Trade: {e}")

                # Check Recent Trade Info And Log It On Google Sheets
                trade_history = session.get_executions(
                    category="linear",
                    symbol=ticker,
                    limit=1,
                )
                last_trade = trade_history["result"]["list"][0]  # Access the first item in the list
                # print(f"Trade History: {last_trade}")
                current_date = datetime.now(timezone.utc).strftime("%d/%m/%Y")
                current_time = datetime.now(timezone.utc).strftime("%H:%M:%S")
                # Open the spreadsheet and worksheet
                # spreadsheet = client.open("Live Trading")
                sheet = spreadsheet.worksheet("Trade History (A)")

                # Sample data to append
                trade_data = [
                    timeframe,
                    strategy_name,
                    current_date,  # date
                    current_time,
                    last_trade["symbol"],  # symbol
                    last_trade["orderType"],
                    last_trade["underlyingPrice"],
                    last_trade["orderLinkId"],
                    last_trade["side"],  # direction
                    last_trade["indexPrice"],
                    last_trade["orderId"],
                    last_trade["stopOrderType"],  # entry
                    last_trade["leavesQty"],  # quantity
                    last_trade["execTime"],
                    last_trade["feeCurrency"],
                    last_trade["isMaker"],
                    last_trade["execFee"],
                    last_trade["feeRate"],  # exit
                    last_trade["execId"],
                    last_trade["tradeIv"],
                    last_trade["blockTradeId"],
                    last_trade["markPrice"],
                    last_trade["execPrice"],
                    last_trade["markIv"],
                    last_trade["orderQty"],
                    last_trade["orderPrice"],
                    last_trade["execValue"],
                    last_trade["execType"],
                    last_trade["execQty"],
                    last_trade["closedSize"],
                    last_trade["extraFees"],
                    last_trade["seq"],
                ]
                try:
                    sheet.append_row(trade_data)
                    # print(f"Logged Trade Data: {trade_data}")
                except Exception as e:
                    print(f"Error While Logging Trade: {e}")




            if entry_tp_sl == "TP":
                if side == "Buy":
                    order_params = {
                        "category": "linear",
                        "symbol": ticker,
                        "side": side,
                        "orderType": "Limit",
                        "qty": quantity,
                        "price": str(float(order_price) - 0.01),
                        "reduceOnly": bool(1)
                    }
                    order_response = session.place_order(**order_params)
                if side == "Sell":
                    order_params = {
                        "category": "linear",
                        "symbol": ticker,
                        "side": side,
                        "orderType": "Limit",
                        "qty": quantity,
                        "price": str(float(order_price) + 0.01),
                        "reduceOnly": bool(1)
                    }
                    order_response = session.place_order(**order_params)
                print(f"<<Take Profit>> order executed: {order_type} - {side} {quantity} {ticker} | {order_response}")

                #Start Logging
                print("Waiting 30 seconds to log trade on Google Sheets...")
                time.sleep(30)

                # Check Recent Order Info And Log It On Google Sheets
                order_history = session.get_order_history(
                    category="linear",
                    symbol=ticker,
                    limit=1,
                )
                last_order = order_history["result"]["list"][0]  # Access the first item in the list
                # print(f"Logging Order History: {last_pnl}")
                current_date = datetime.now(timezone.utc).strftime("%d/%m/%Y")
                current_time = datetime.now(timezone.utc).strftime("%H:%M:%S")
                # Open the spreadsheet and worksheet
                spreadsheet = client.open("Live Trading")
                sheet = spreadsheet.worksheet("Order History (A)")

                # Sample data to append
                order_data = [
                    timeframe,
                    strategy_name,
                    current_date,  # date
                    current_time,
                    last_order["orderId"],
                    last_order["orderLinkId"],
                    last_order["blockTradeId"],
                    last_order["symbol"],  # symbol
                    last_order["price"],
                    last_order["qty"],  # quantity
                    last_order["side"],  # direction
                    last_order["isLeverage"],
                    last_order["positionIdx"],
                    last_order["orderStatus"],
                    last_order["cancelType"],
                    last_order["rejectReason"],
                    last_order["avgPrice"],
                    last_order["leavesQty"],
                    last_order["leavesValue"],
                    last_order["cumExecQty"],
                    last_order["cumExecValue"],
                    last_order["cumExecFee"],
                    last_order["timeInForce"],
                    last_order["orderType"],
                    last_order["stopOrderType"],
                    last_order["orderIv"],
                    last_order["triggerPrice"],
                    last_order["takeProfit"],
                    last_order["stopLoss"],
                    last_order["tpTriggerBy"],
                    last_order["slTriggerBy"],
                    last_order["triggerDirection"],
                    last_order["triggerBy"],
                    last_order["lastPriceOnCreated"],
                    last_order["reduceOnly"],
                    last_order["closeOnTrigger"],
                    last_order["smpType"],
                    last_order["smpGroup"],
                    last_order["smpOrderId"],
                    last_order["tpslMode"],
                    last_order["tpLimitPrice"],
                    last_order["slLimitPrice"],
                    last_order["placeType"],
                    last_order["slippageToleranceType"],
                    last_order["slippageTolerance"],
                    last_order["createdTime"],
                    last_order["updatedTime"],
                    last_order["extraFees"]
                ]

                try:
                    sheet.append_row(order_data)
                    # print(f"Logged Trade Data: {order_data}")
                except Exception as e:
                    print(f"Error While Logging Trade: {e}")

                # Check Recent Trade Info And Log It On Google Sheets
                trade_history = session.get_executions(
                    category="linear",
                    symbol=ticker,
                    limit=1,
                )
                last_trade = trade_history["result"]["list"][0]  # Access the first item in the list
                # print(f"Closed Pnl: {last_trade}")
                current_date = datetime.now(timezone.utc).strftime("%d/%m/%Y")
                current_time = datetime.now(timezone.utc).strftime("%H:%M:%S")
                # Open the spreadsheet and worksheet
                # spreadsheet = client.open("Live Trading")
                sheet = spreadsheet.worksheet("Trade History (A)")

                # Sample data to append
                trade_data = [
                    timeframe,
                    strategy_name,
                    current_date,  # date
                    current_time,
                    last_trade["symbol"],  # symbol
                    last_trade["orderType"],
                    last_trade["underlyingPrice"],
                    last_trade["orderLinkId"],
                    last_trade["side"],  # direction
                    last_trade["indexPrice"],
                    last_trade["orderId"],
                    last_trade["stopOrderType"],  # entry
                    last_trade["leavesQty"],  # quantity
                    last_trade["execTime"],
                    last_trade["feeCurrency"],
                    last_trade["isMaker"],
                    last_trade["execFee"],
                    last_trade["feeRate"],  # exit
                    last_trade["execId"],
                    last_trade["tradeIv"],
                    last_trade["blockTradeId"],
                    last_trade["markPrice"],
                    last_trade["execPrice"],
                    last_trade["markIv"],
                    last_trade["orderQty"],
                    last_trade["orderPrice"],
                    last_trade["execValue"],
                    last_trade["execType"],
                    last_trade["execQty"],
                    last_trade["closedSize"],
                    last_trade["extraFees"],
                    last_trade["seq"],
                ]
                try:
                    sheet.append_row(trade_data)
                    # print(f"Logged Trade Data: {trade_data}")
                except Exception as e:
                    print(f"Error While Logging Trade: {e}")

                # Check Recent PnL And Log It On Google Sheets
                close_pnl = session.get_closed_pnl(
                    category="linear",
                    symbol=ticker,
                    limit=1,
                )
                last_pnl = close_pnl["result"]["list"][0]  # Access the first item in the list
                # print(f"Closed Pnl: {last_pnl}")
                current_date = datetime.now(timezone.utc).strftime("%d/%m/%Y")
                current_time = datetime.now(timezone.utc).strftime("%H:%M:%S")
                # Open the spreadsheet and worksheet
                # spreadsheet = client.open("Live Trading")
                sheet = spreadsheet.worksheet("PnL (A)")

                # Sample data to append
                trade_data = [
                    timeframe,
                    strategy_name,
                    current_date,  # date
                    current_time,
                    last_pnl["symbol"],  # symbol
                    last_pnl["orderType"],
                    last_pnl["leverage"],
                    last_pnl["updatedTime"],
                    last_pnl["side"],  # direction
                    last_pnl["orderId"],
                    last_pnl["closedPnl"],
                    last_pnl["avgEntryPrice"],  # entry
                    last_pnl["qty"],  # quantity
                    last_pnl["cumEntryValue"],
                    last_pnl["createdTime"],
                    last_pnl["orderPrice"],
                    last_pnl["closedSize"],
                    last_pnl["avgExitPrice"],  # exit
                    last_pnl["execType"],
                    last_pnl["fillCount"],
                    last_pnl["cumExitValue"]
                ]
                try:
                    sheet.append_row(trade_data)
                    # print(f"Logged Trade Data: {trade_data}")
                except Exception as e:
                    print(f"Error While Logging Trade: {e}")

                if initial_uid != os.getenv('MAIN_UID'):
                    # Better if confirm no trades open.
                    balance_response = session.get_wallet_balance(
                        accountType="UNIFIED",
                        coin="USDT",
                    )
                    # print(f"Rebalancing: {balance_response}")
                    balance_list = balance_response["result"]["list"][0]
                    balance = float(balance_list["totalEquity"])
                    floor_balance = floor(balance)
                    target_capital = 200
                    excess_capital = abs(floor_balance - target_capital)

                    sub_account_balance = session.get_coin_balance(
                        accountType="UNIFIED",
                        coin="USDT",
                    )
                    uid = sub_account_balance['result']['memberId']
                    # print(f"Fetched Sub account uid: {uid}")
                    transferId = str(uuid.uuid4())
                    if floor_balance > target_capital:  # Has Excess Capital
                        try:
                            session.create_universal_transfer(
                                transferId=transferId,
                                coin="USDT",
                                amount=str(excess_capital),
                                fromMemberId=int(uid),
                                toMemberId=int(os.getenv('MAIN_UID')),  # Main UID
                                fromAccountType="UNIFIED",
                                toAccountType="UNIFIED",
                            )
                            print(f"Profit({excess_capital} USDT) Moved to Main Account from UID: {uid}")
                        except Exception as e:
                            print(f"Error while Line 481 Universal Transfer: {e}")
                    if floor_balance < target_capital:  # Needs More Capital
                        try:
                            session = HTTP(
                                testnet=False,
                                api_key=os.getenv('API_KEY_0'),
                                api_secret=os.getenv('API_SECRET_0'),
                            )
                            main_balance = session.get_coin_balance(
                                accountType="UNIFIED",
                                coin="USDT",
                                memberId=int(os.getenv('MAIN_UID')),
                            )
                            # print(f"Fetched Main Account Balance: {main_balance}")
                            if float(main_balance['result']['balance']['transferBalance']) > excess_capital:
                                try:

                                    # print(f"The printed uuid: {transferId}")
                                    # print(f"The original variable uid{uid}")
                                    session.create_universal_transfer(
                                        transferId=transferId,
                                        coin="USDT",
                                        amount=str(excess_capital),
                                        fromMemberId=int(os.getenv('MAIN_UID')),
                                        toMemberId=int(uid),
                                        fromAccountType="UNIFIED",
                                        toAccountType="UNIFIED",
                                    )
                                    print(f"Loss Balance({excess_capital} USDT) Filled from Main Account to UID: {uid}")
                                except Exception as e:
                                    print(f"Error while Line 508 Universal Transfer: {e}")
                            else:
                                print(f"Not enough balance in Main Account to fill Sub Account: {uid}")
                        except Exception as e:
                            print(f"Error while Line 496 Universal Transfer: {e}")






            if entry_tp_sl == "SL":
                #open_orders = session.get_open_orders(category="linear", limit=1)
                #open_order_id = open_orders["result"]["list"][0]["orderId"]

                #if open_order_id == "": #No open positions
                print("SL Triggered. Loggging trade on Google Sheets...")

                # Check Recent Order Info And Log It On Google Sheets
                order_history = session.get_order_history(
                    category="linear",
                    symbol=ticker,
                    limit=1,
                )
                last_order = order_history["result"]["list"][0]  # Access the first item in the list
                # print(f"Logging Order History: {last_pnl}")
                current_date = datetime.now(timezone.utc).strftime("%d/%m/%Y")
                current_time = datetime.now(timezone.utc).strftime("%H:%M:%S")
                # Open the spreadsheet and worksheet
                spreadsheet = client.open("Live Trading")
                sheet = spreadsheet.worksheet("Order History (A)")

                # Sample data to append
                order_data = [
                    timeframe,
                    strategy_name,
                    current_date,  # date
                    current_time,
                    last_order["orderId"],
                    last_order["orderLinkId"],
                    last_order["blockTradeId"],
                    last_order["symbol"],  # symbol
                    last_order["price"],
                    last_order["qty"],  # quantity
                    last_order["side"],  # direction
                    last_order["isLeverage"],
                    last_order["positionIdx"],
                    last_order["orderStatus"],
                    last_order["cancelType"],
                    last_order["rejectReason"],
                    last_order["avgPrice"],
                    last_order["leavesQty"],
                    last_order["leavesValue"],
                    last_order["cumExecQty"],
                    last_order["cumExecValue"],
                    last_order["cumExecFee"],
                    last_order["timeInForce"],
                    last_order["orderType"],
                    last_order["stopOrderType"],
                    last_order["orderIv"],
                    last_order["triggerPrice"],
                    last_order["takeProfit"],
                    last_order["stopLoss"],
                    last_order["tpTriggerBy"],
                    last_order["slTriggerBy"],
                    last_order["triggerDirection"],
                    last_order["triggerBy"],
                    last_order["lastPriceOnCreated"],
                    last_order["reduceOnly"],
                    last_order["closeOnTrigger"],
                    last_order["smpType"],
                    last_order["smpGroup"],
                    last_order["smpOrderId"],
                    last_order["tpslMode"],
                    last_order["tpLimitPrice"],
                    last_order["slLimitPrice"],
                    last_order["placeType"],
                    last_order["slippageToleranceType"],
                    last_order["slippageTolerance"],
                    last_order["createdTime"],
                    last_order["updatedTime"],
                    last_order["extraFees"]
                ]

                try:
                    sheet.append_row(order_data)
                    #print(f"Logged Trade Data: {order_data}")
                except Exception as e:
                    print(f"Error While Logging Trade: {e}")

                # Check Recent Trade Info And Log It On Google Sheets
                trade_history = session.get_executions(
                    category="linear",
                    symbol=ticker,
                    limit=1,
                )
                last_trade = trade_history["result"]["list"][0]  # Access the first item in the list
                # print(f"Closed Pnl: {last_trade}")
                current_date = datetime.now(timezone.utc).strftime("%d/%m/%Y")
                current_time = datetime.now(timezone.utc).strftime("%H:%M:%S")
                # Open the spreadsheet and worksheet
                #spreadsheet = client.open("Live Trading")
                sheet = spreadsheet.worksheet("Trade History (A)")

                # Sample data to append
                trade_data = [
                    timeframe,
                    strategy_name,
                    current_date,  # date
                    current_time,
                    last_trade["symbol"],  # symbol
                    last_trade["orderType"],
                    last_trade["underlyingPrice"],
                    last_trade["orderLinkId"],
                    last_trade["side"],  # direction
                    last_trade["indexPrice"],
                    last_trade["orderId"],
                    last_trade["stopOrderType"],  # entry
                    last_trade["leavesQty"],  # quantity
                    last_trade["execTime"],
                    last_trade["feeCurrency"],
                    last_trade["isMaker"],
                    last_trade["execFee"],
                    last_trade["feeRate"],  # exit
                    last_trade["execId"],
                    last_trade["tradeIv"],
                    last_trade["blockTradeId"],
                    last_trade["markPrice"],
                    last_trade["execPrice"],
                    last_trade["markIv"],
                    last_trade["orderQty"],
                    last_trade["orderPrice"],
                    last_trade["execValue"],
                    last_trade["execType"],
                    last_trade["execQty"],
                    last_trade["closedSize"],
                    last_trade["extraFees"],
                    last_trade["seq"],
                ]
                try:
                    sheet.append_row(trade_data)
                    #print(f"Logged Trade Data: {trade_data}")
                except Exception as e:
                    print(f"Error While Logging Trade: {e}")


                #Check Recent PnL And Log It On Google Sheets
                close_pnl = session.get_closed_pnl(
                    category="linear",
                    symbol=ticker,
                    limit=1,
                )
                last_pnl = close_pnl["result"]["list"][0]  # Access the first item in the list
                #print(f"Closed Pnl: {last_pnl}")
                current_date = datetime.now(timezone.utc).strftime("%d/%m/%Y")
                current_time = datetime.now(timezone.utc).strftime("%H:%M:%S")
                # Open the spreadsheet and worksheet
                #spreadsheet = client.open("Live Trading")
                sheet = spreadsheet.worksheet("PnL (A)")

                # Sample data to append
                trade_data = [
                    timeframe,
                    strategy_name,
                    current_date,  # date
                    current_time,
                    last_pnl["symbol"],  # symbol
                    last_pnl["orderType"],
                    last_pnl["leverage"],
                    last_pnl["updatedTime"],
                    last_pnl["side"], # direction
                    last_pnl["orderId"],
                    last_pnl["closedPnl"],
                    last_pnl["avgEntryPrice"], # entry
                    last_pnl["qty"], # quantity
                    last_pnl["cumEntryValue"],
                    last_pnl["createdTime"],
                    last_pnl["orderPrice"],
                    last_pnl["closedSize"],
                    last_pnl["avgExitPrice"], # exit
                    last_pnl["execType"],
                    last_pnl["fillCount"],
                    last_pnl["cumExitValue"]
                ]
                try:
                    sheet.append_row(trade_data)
                    #print(f"Logged Trade Data: {trade_data}")
                except Exception as e:
                    print(f"Error While Logging Trade: {e}")

                if initial_uid != os.getenv('MAIN_UID'):
                    # Better if confirm no trades open.
                    balance_response = session.get_wallet_balance(
                        accountType="UNIFIED",
                        coin="USDT",
                    )
                    #print(f"Rebalancing: {balance_response}")
                    balance_list = balance_response["result"]["list"][0]
                    balance = float(balance_list["totalEquity"])
                    floor_balance = floor(balance)
                    target_capital = 200
                    excess_capital = abs(floor_balance - target_capital)

                    sub_account_balance = session.get_coin_balance(
                        accountType="UNIFIED",
                        coin="USDT",
                    )
                    uid = sub_account_balance['result']['memberId']
                    #print(f"Fetched Sub account uid: {uid}")
                    transferId = str(uuid.uuid4())
                    if floor_balance > target_capital: #Has Excess Capital
                        try:
                            session.create_universal_transfer(
                                transferId = transferId,
                                coin = "USDT",
                                amount = str(excess_capital),
                                fromMemberId = int(uid),
                                toMemberId = int(os.getenv('MAIN_UID')), #Main UID
                                fromAccountType = "UNIFIED",
                                toAccountType = "UNIFIED",
                            )
                            print(f"Profit({excess_capital} USDT) Moved to Main Account from UID: {uid}")
                        except Exception as e:
                            print(f"Error while Line 481 Universal Transfer: {e}")
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
                                memberId=int(os.getenv('MAIN_UID')),
                            )
                            #print(f"Fetched Main Account Balance: {main_balance}")
                            if float(main_balance['result']['balance']['transferBalance']) > excess_capital:
                                try:

                                    #print(f"The printed uuid: {transferId}")
                                    #print(f"The original variable uid{uid}")
                                    session.create_universal_transfer(
                                        transferId = transferId,
                                        coin = "USDT",
                                        amount = str(excess_capital),
                                        fromMemberId = int(os.getenv('MAIN_UID')),
                                        toMemberId = int(uid),
                                        fromAccountType = "UNIFIED",
                                        toAccountType = "UNIFIED",
                                    )
                                    print(f"Loss Balance({excess_capital} USDT) Filled from Main Account to UID: {uid}")
                                except Exception as e:
                                    print(f"Error while Line 508 Universal Transfer: {e}")
                            else:
                                print(f"Not enough balance in Main Account to fill Sub Account: {uid}")
                        except Exception as e:
                            print(f"Error while Line 496 Universal Transfer: {e}")

        else:
            print(f"Simulated paper order: {order_type} - {side} {quantity} {ticker}")
            record_trade(data, None)
        return True
    except Exception as e:
        #record_trade(data, "Failed Real Order?")
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
    success = execute_order(data)

    if success:
        return jsonify({"code": "success", "message": "Order executed"})
    else:
        return jsonify({"code": "error", "message": "Order failed"})
    #order_thread = threading.Thread(target=execute_order,args=(data,))
    #order_thread.start()
    #return "Thread started."

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
