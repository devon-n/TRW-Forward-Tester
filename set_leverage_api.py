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
        session.set_margin_mode(setMarginMode="ISOLATED_MARGIN")
        session.set_leverage(
            category="linear",
            symbol=symbol,
            buyLeverage=str(leverage),
            sellLeverage=str(leverage),
            )

        print(f"Leverage successfully set to {leverage}x")

    except Exception as e:
        if hasattr(e, "retCode") and e.retCode:
            ret_code = str(e.retCode)
            if "110043" in ret_code:
                print(f"Leverage already set to {leverage}x")
                return
        raise