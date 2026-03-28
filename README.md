# FORWARD TESTER

## Install

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.sample .env
```

Fill in the values in `.env`.

## .env variables

- `API_KEY`: Exchange API key used to place orders. Create it in the exchange account you want this app to trade on, such as Binance or Bybit.
- `API_SECRET`: Secret paired with `API_KEY`. You get it at the same time when creating the exchange API key. Keep it private.
- `WHITELISTED_IPS`: Comma-separated list of IP addresses allowed to call this app. Add the public IPs used by the service sending alerts to this webhook, for example your TradingView relay, server, or proxy.
- `MONGO_URI`: MongoDB connection string used to store trade data. Obtain it from your MongoDB deployment, for example MongoDB Atlas or your own MongoDB server.

## Run

```bash
python app.py
```

- Trading view sends alert to Forward-Tester

- Forward-Tester checks if real trade or not

- If real trade:
    - Executes trade on Binance/Bybit

- Records trade in Mongo DB


# Update Minimum Quantities or Precisions for Binance/Bybit Orders
- Update in `config`
- Add the symbol and the minimum quantity or minimum precision


## Keep all trading logic in TV
The following can change
- Position size?
- When to cut a strategy
- If paper or real strategy
- When implementing in pinescript, take note of order quantity precision from Binance/Bybit

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

# Run tests
```json
"python -m pytest"
```
