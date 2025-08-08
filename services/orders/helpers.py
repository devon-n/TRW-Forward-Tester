from models.signal import SignalPayload
from config import minQtyDict, precisionDecimalDict


def format_position_size(ticker: str, order_contracts: float):
    ticker = ticker.replace(".P", "")
    ticker = ticker + "T" if ticker.endswith("USD") else ticker
    if ticker in minQtyDict and float(order_contracts) < float(
        minQtyDict[ticker]
    ):
        order_contracts = minQtyDict[ticker]
    if ticker in precisionDecimalDict:
        precision = precisionDecimalDict[ticker]
        if precision > 0:
            order_contracts = round(
                float(order_contracts), precision
            )
        else:
            order_contracts = int(order_contracts)
    return order_contracts
