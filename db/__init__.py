import os
from pymongo import MongoClient  # type: ignore

connection_string = os.getenv("MONGO_URI")
mongo_client = MongoClient(connection_string)
db = mongo_client.trading
trades_collection = db.trades
