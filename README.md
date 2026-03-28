# FORWARD TESTER
## Install
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.sample .env
```

## .env variables
- `API_KEY`: Binance or Bybit API key. Create it in the exchange account you want this app to trade on.
- `API_SECRET`: Secret paired with `API_KEY`. Create and copy it from the same Binance or Bybit API key setup.
- `WHITELISTED_IPS`: Comma-separated public IPs allowed to call `/webhook`. Add the IPs used by the sender or relay that will post TradingView alerts here.
- `MONGO_URI`: MongoDB connection string for storing trades. Get it from MongoDB Atlas or your own MongoDB server.
- `HYPERLIQUID_WALLET_ADDRESS`: Wallet address used by CCXT for Hyperliquid account actions. Use the wallet address tied to your Hyperliquid trading signer.
- `HYPERLIQUID_PRIVATE_KEY`: Private key for the Hyperliquid wallet or agent wallet that signs orders. Obtain it from your wallet or signer setup and keep it private.
- `HYPERLIQUID_SLIPPAGE`: Optional default slippage for Hyperliquid market orders, passed through CCXT. Example: `0.01`.

## Run
```bash
python app.py
```

- Trading view sends alert to Forward-Tester

- Forward-Tester checks if real trade or not

- If real trade:
    - Executes trade on Binance/Bybit/Hyperliquid

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
