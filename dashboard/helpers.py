
def calculate_profit(row, strategy_balances):

    strategy = row["strategy_name"]
    current_date = row['time']

    # Initialize strategy balance if not present
    balance = strategy_balances.setdefault(strategy, {
        "assetAmount": 0,
        "USDHigh": 0,
        "USDLow": 0,
        "totalUSDHigh": 0,
        "totalUSDLow": 0,
        "lastTradeDate": current_date,  # Set to minimum timestamp initially
    })

    maker_fee_rate = 0.002 # 0.02%
    taker_fee_rate = 0.005 # 0.05%
    slippage = 0.0001
    notional_value = row["quantity"] * row["order_price"]
    maker_fee = notional_value * maker_fee_rate
    taker_fee = notional_value * taker_fee_rate
    slippage_cost = notional_value * slippage
    # slippage_cost = 0

    # TODO Real trades start where paper trades end in terms of balances
    # Should this change?
    if row["side"] == "BUY":
        balance["assetAmount"] += row["quantity"]
        # For buys, subtract costs including fees and slippage for USDLow
        balance["USDLow"] -= notional_value + taker_fee + slippage_cost
        # Subtract only maker fee for USDHigh
        balance["USDHigh"] -= notional_value + maker_fee
    elif row["side"] == "SELL":
        balance["assetAmount"] -= row["quantity"]
        # For sells, add revenue minus fees and slippage for USDLow
        balance["USDLow"] += notional_value - taker_fee - slippage_cost
        # Add revenue minus only maker fee for USDHigh
        balance["USDHigh"] += notional_value - maker_fee
    else:
        raise ValueError(f"Unrecognized Action: {row['Action']}")

    # Update total USD values based on the updated USD balances and current asset valuation
    balance["totalUSDHigh"] = balance["USDHigh"] + (balance["assetAmount"] * row["order_price"])
    balance["totalUSDLow"] = balance["USDLow"] + (balance["assetAmount"] * row["order_price"])

    # For resetting paper trades to their real trade counterparts
    # # Check if the current trade is the first trade of a new month
    # if current_date.month != balance["lastTradeDate"].month and 'cumulativePnl' in row and pd.notnull(row['cumulativePnl']):
    #     # Reset the TotalUSDHigh and TotalUSDLow to the MonthStart
    #     balance['totalUSDHigh'] = row['cumulativePnl']
    #     balance['totalUSDLow'] = row['cumulativePnl']
    #     balance["USDHigh"] = row['cumulativePnl']
    #     balance["USDLow"] = row['cumulativePnl']
    #     balance["assetAmount"] = 0
    # # Update the lastTradeDate in the balance for this strategy
    balance["lastTradeDate"] = current_date

    strategy_balances[strategy] = balance

    return balance["assetAmount"], balance["USDHigh"], balance["USDLow"], balance["totalUSDHigh"], balance["totalUSDLow"]


# Truncate name
def truncate_name(name, max_len=15):
    return name if len(name) <= max_len else name[:max_len-3] + '...'
