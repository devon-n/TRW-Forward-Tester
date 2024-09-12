
# from binance.client import Client
# from binance.um_futures import UMFutures
# import os
# data = {}
# ticker = 'BTCUSD'
# side = "SELL"
# price = "57800"
# USDAmount = 110

# # STOP LOSSES AND TAKE PROFITS IN TRADING VIEW
# # MIN QUANTITY: CHECK AND PLACE MIN QTY IN TRADING VIEW
# # DON'T DO USD AMOUNT because of min qty
# ticker = ticker + "T" if ticker.endswith("USD") else ticker
# client = UMFutures(os.getenv('API_KEY'), os.getenv('API_SECRET'))

def getTickerPricePrecision(client, symbol):
    resp = client.exchange_info()['symbols']
    for elem in resp:
        if elem['symbol'] == symbol:
            return elem['pricePrecision']

def getTickerQtyPrecision(client, symbol):
    resp = client.exchange_info()['symbols']
    for elem in resp:
        if elem['symbol'] == symbol:
            return elem['quantityPrecision']

def getMinQuantity(client, symbol)->float:
    resp = client.exchange_info()['symbols']
    for elem in resp:
        if elem['symbol'] == symbol:
            filters = elem['filters']
            for filter in filters:
                if filter['filterType'] == 'LOT_SIZE':
                    return float(filter['minQty'])
    return 0.0

# tickerQtyPrecision = getTickerQtyPrecision(ticker)
# quantity = float(round(USDAmount / float(price), tickerQtyPrecision))
# minQty = getMinQuantity(ticker)

# quantity = quantity if quantity > minQty else minQty
# print(minQty)

# print(f"Ticker Precision: f{tickerQtyPrecision}")
# print(f"Quantity: {quantity}\n")
# order_response = client.new_order(
#     symbol=ticker,
#     side=side,
#     type="MARKET",
#     # quantity=quantity,
#     quantity=0.002
#     )
# print(order_response)