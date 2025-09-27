import yfinance as yf

class YahooFinance:
    """
    Fetches current stock data using yfinance.
    """
    def __init__(self, ticker):
        self.ticker = ticker
        self.stock = yf.Ticker(ticker)

    def get_current_data(self):
        data = self.stock.history(period="1d")
        if data.empty:
            return None
        latest = data.iloc[-1]
        return {
            "ticker": self.ticker,
            "time": str(latest.name),
            "open": latest["Open"],
            "high": latest["High"],
            "low": latest["Low"],
            "close": latest["Close"],
            "volume": latest["Volume"]
        }

# Example usage:
# yf_api = YahooFinance("AAPL")
# print(yf_api.get_current_data())
