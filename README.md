# TRW Forward Tester

Flask webhook service for forwarding TradingView-style JSON alerts to Binance, Bybit, or Hyperliquid and storing every event in MongoDB. A separate Streamlit dashboard reads the same `trading.trades` collection for reporting.

This repo does not decide when to trade. Strategy logic, entries, exits, sizing, and whether an alert is paper or live all come from Pine Script or another webhook sender. This service validates the request, normalizes quantity, routes the order, and records the result.

---

## Setup order

1. Install Python dependencies and create `.env`.
2. Fill in environment variables.
3. Configure MongoDB and set `MONGO_URI`.
4. Expose the webhook server on a public `http://` or `https://` endpoint.
5. Configure TradingView or another sender to `POST` valid JSON to `/webhook`.
6. Run the Flask app.
7. Optionally run the Streamlit dashboard.

---

## Install

### Windows

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.sample .env
```

### macOS and Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.sample .env
```

---

## Environment variables

Edit `.env` before running anything.

| Variable | Used for |
|----------|-----------|
| `API_KEY` | Binance USDT-M and Bybit credentials |
| `API_SECRET` | Secret paired with `API_KEY` |
| `WHITELISTED_IPS` | Comma-separated IPs allowed to call `POST /webhook` |
| `MONGO_URI` | MongoDB connection string |
| `HYPERLIQUID_WALLET_ADDRESS` | Hyperliquid wallet address |
| `HYPERLIQUID_PRIVATE_KEY` | Hyperliquid private key for signed order actions |
| `HYPERLIQUID_SLIPPAGE` | Optional default slippage for Hyperliquid market orders, for example `0.01` |

Notes:

- Binance and Bybit share the same `API_KEY` and `API_SECRET` variable names in this app.
- Only the credentials for the exchange named in a `REAL` webhook need to be valid for that request flow.
- Hyperliquid public info calls use the wallet address only; signed order actions also need the private key.

---

## MongoDB setup

Both the Flask app and the Streamlit dashboard use PyMongo with one `MONGO_URI`. You do not need to create the database or collection manually. The first successful insert creates:

| What | Value |
|------|--------|
| Database name | `trading` |
| Collection name | `trades` |
| Driver | `pymongo` via `MongoClient(os.getenv('MONGO_URI'))` |

Official MongoDB references:

- [Connect to an Atlas cluster](https://www.mongodb.com/docs/atlas/tutorial/connect-to-your-cluster/)
- [Connect via client libraries / drivers](https://www.mongodb.com/docs/atlas/driver-connection/)
- [Get connection string](https://www.mongodb.com/docs/guides/atlas/connection-string/)
- [Add entries to the IP access list](https://www.mongodb.com/docs/atlas/security/ip-access-list/)

### Atlas setup

1. Create a deployment in [MongoDB Atlas](https://www.mongodb.com/cloud/atlas).
2. Open the cluster and click **Connect**.
3. Choose **Connect your application**.
4. Add the correct source IP to the Atlas **IP access list**. For hosted deployments, add the server or platform egress IP, not just your laptop.
5. Create a MongoDB database user under **Database Access** if you do not already have one.
6. Copy the Python connection string, usually an `mongodb+srv://...` URI.
7. Replace `<password>` with the database user password. Percent-encode special characters such as `@`, `:`, and `/` if needed.
8. Put the finished URI into `MONGO_URI` in `.env`.

Notes:

- Atlas requires TLS.
- This app selects `mongo_client.trading` in code, so it does not rely on the database name embedded in the URI path.
- Under strict outbound firewall rules, Atlas expects access to TCP ports `27015` to `27017` on cluster hostnames.

### Local MongoDB options

- MongoDB Community Edition or Docker, for example `mongodb://localhost:27017/`
- Atlas CLI local deployment if you prefer MongoDB's documented Docker-based local flow

### Verify MongoDB

- `mongosh "<your MONGO_URI>"`, then `use trading` and `db.trades.find().limit(1)`
- MongoDB Compass with the same URI, then open `trading` -> `trades`

### MongoDB troubleshooting

| Issue | What to check |
|--------|----------------|
| Cannot connect or timeouts | Wrong URI, local MongoDB not running, blocked outbound access, or source IP missing from the Atlas IP access list |
| Authentication failed | Wrong database user, wrong password, or password not URL-encoded |
| Dashboard says there are no trades | Normal until the webhook has inserted at least one document |

---

## Webhook sender setup

This app expects a JSON `POST` to `/webhook`. TradingView is the common sender, but any system that sends the same JSON shape works.

### TradingView requirements

1. The webhook URL must be publicly reachable. `localhost` is not enough unless you expose it with a tunnel.
2. TradingView only sends webhooks to port `80` or `443`. It rejects URLs that include ports such as `:5000`.
3. TradingView webhooks require [2FA](https://www.tradingview.com/support/solutions/43000572460-how-to-configure-2fa/).
4. TradingView expects your server to respond in about 3 seconds.
5. TradingView webhooks use IPv4 only.

### Allowlist sender IPs

Requests are rejected unless the client IP appears in `WHITELISTED_IPS`.

TradingView currently documents these webhook source IPs:

- `52.89.214.238`
- `34.212.75.30`
- `54.218.53.128`
- `52.32.178.7`

Set `WHITELISTED_IPS` to a comma-separated list containing those IPs and any additional senders or proxies you use. Re-check TradingView's current list here if needed:

- [TradingView webhook docs](https://www.tradingview.com/support/solutions/43000529348-how-to-configure-webhook-alerts/)

### Configure a TradingView alert

1. Open the chart running your Pine strategy.
2. Create or edit an alert.
3. Choose the correct strategy condition.
4. Enable **Webhook URL** and point it to:

   `https://your-domain.com/webhook`

5. Paste a valid JSON message body. Start from `webhook_format.json`.
6. Use TradingView placeholders where needed, for example:
   - `{{ticker}}`
   - `{{interval}}`
   - `{{timenow}}`
   - `{{time}}`
   - `{{strategy.order.action}}`
   - `{{strategy.order.contracts}}`
   - `{{strategy.position_size}}`
7. Set literal values such as `order_type` and `exchange`, or expose them from Pine if you prefer.
8. Save the alert and watch the TradingView alert log if delivery fails.

Keep the message as strict JSON. If the body is not valid JSON, Flask returns `400`.

### Webhook payload

Use `webhook_format.json` as the template. Important fields:

| Field | Purpose |
|--------|---------|
| `order_type` | `PAPER` or `REAL` |
| `exchange` | For `REAL` only: `BINANCE`, `BYBIT`, or `HYPERLIQUID` |
| `ticker` | Symbol, normalized inside the app |
| `leverage` | Passed to exchange helpers where supported |
| `strategy` / `bar` / `strategyName` | Stored with the trade record |

Notes:

- `exchange` is chosen per request. There is no default venue in config.
- If `order_type` is omitted, the app treats the event as `PAPER`.
- If `order_type` is `REAL`, missing or unsupported `exchange` fails the request.

### TradingView troubleshooting

| Symptom | What to check |
|--------|----------------|
| `403` from Forward Tester | Sender IP is not in `WHITELISTED_IPS` |
| `400` invalid JSON | Alert body is malformed JSON |
| TradingView never reaches the server | Wrong port, firewall, reverse proxy, or bad URL |
| Timeouts | Flask app, exchange call, or MongoDB write is taking too long |

---

## Run the webhook server

```bash
python app.py
```

The Flask app listens on `0.0.0.0:5000` with `debug=True`.

For TradingView, do not send alerts directly to `:5000`. Put a reverse proxy or load balancer in front of the app and serve the public endpoint on port `80` or `443`.

---

## Run the dashboard

From the repository root:

```bash
streamlit run dashboard/dashboard.py
```

The dashboard needs `MONGO_URI` and at least one trade in `trading.trades`.

---

## How requests are handled

1. A sender posts JSON to `POST /webhook`.
2. The client IP must be in `WHITELISTED_IPS` or the request gets `403`.
3. Invalid or empty JSON gets `400`.
4. Quantity rules from `config.py` normalize the symbol, enforce minimum quantity, and apply decimal precision where configured.
5. If `order_type` is `PAPER`, no exchange call is made and the event is still saved to MongoDB.
6. If `order_type` is `REAL`, the app routes to `BINANCE`, `BYBIT`, or `HYPERLIQUID` and uses environment-based credentials for that venue.
7. The event is inserted into `trading.trades` with metadata, quantity, side, leverage, and `order_response`.

```mermaid
flowchart LR
  TV[Alert sender e.g. TradingView]
  FT[Forward Tester Flask]
  EX[Binance / Bybit / Hyperliquid]
  DB[(MongoDB trades)]

  TV -->|POST JSON /webhook| FT
  FT -->|REAL| EX
  FT -->|PAPER or after order| DB
  EX --> FT
```

---

## Minimum quantity and precision

Edit `config.py` if a symbol needs exchange-specific quantity handling.

- `minQtyDict`: symbol to minimum contracts
- `precisionDecimalDict`: symbol to decimal precision used for rounding

Keep Pine sizing aligned with those values so the final order size matches exchange constraints.

---

## Switching from paper to live

In the webhook JSON, change:

```json
"order_type": "PAPER"
```

to:

```json
"order_type": "REAL"
```

Then set `exchange` to the correct venue and make sure the matching credentials are configured in `.env`.

---

## Project layout

| Piece | Role |
|--------|------|
| `app.py` | Flask app, `/webhook`, execution routing, MongoDB writes |
| `exchanges/` | Exchange adapters for Binance, Bybit, and Hyperliquid |
| `config.py` | Minimum quantity and precision settings |
| `webhook_format.json` | Example webhook payload |
| `dashboard/dashboard.py` | Streamlit reporting UI |

---

## Tests

```bash
python -m pytest
```

---

## Design split

- TradingView or Pine decides strategy logic, timing, sizing, paper vs live, and which `exchange` value to send.
- This repo handles IP allowlisting, request validation, quantity normalization, exchange execution, persistence, and optional dashboard reporting.
