import os
from pymongo import MongoClient # type: ignore

mongo_client = MongoClient(os.getenv("MONGO_URI"))
db = mongo_client.trading
trades_collection = db.trades
