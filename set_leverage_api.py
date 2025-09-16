def set_leverage_binance(client,symbol, leverage):
    print(f"\nSetting leverage to {leverage}x\n")
    try:
        client.futures_change_margin_type(symbol=symbol, marginType="ISOLATED")
        client.futures_change_leverage(symbol=symbol, leverage=leverage)

        print(f"Leverage successfully set to {leverage}x")

    except Exception as e:
        print(f"Error while adjusting leverage(Binance): {e}")

def set_leverage_bybit(session, symbol, leverage):
    print(f"\nSetting leverage to {leverage}x\n")
    try:
        lev_response = session.switch_margin_mode(
            category="linear",
            symbol=symbol,
            tradeMode=1, #isolated
            buyLeverage=str(leverage),
            sellLeverage=str(leverage),
            )

        if lev_response["retCode"] == 110043: # Leverage already set to target
            print(f"Leverage already {leverage}x")
            return

        print(f"Leverage successfully set to {leverage}x")

    except Exception as e:
        print(f"Error while adjusting leverage(Bybit): {e}")