# FORWARD TESTER
- Trading view sends alert to Forward-Tester

- Forward-Tester checks if real trade or not

- If real trade:
    - Executes trade on Bybit

- Record trade in mongo db


# Update Minimum Quantities or Precisions for Bybit Orders
- Update in `config`
- Add the symbol and the minimum quantity or minimum precision


## Keep all trading logic in TV
The following can change
- Position size?
- When to cut a strategy
- If paper or real strategy
- When implementing in pinescript, take note of order quantity precision from binance

## Keep all reporting and executing logic here
It might be better keeping position sizing and account balances here
- How will stop losses and profit taking be handled?


## Turn paper to real
After a strategy has shown some success

Go to TV and change the strategies alert message
from
```json
"order_type": "PAPER"
```
to
```json
"order_type": "REAL"
```
