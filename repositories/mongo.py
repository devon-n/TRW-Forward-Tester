from pymongo import MongoClient
from config.config import AppSettings


class MongoRepository:
    def __init__(self, validate_uri=True):
        self.validate_uri = validate_uri
        self.mongo_client = None
        self.trades_collection = None

    def get_mongo_client(self):
        if self.mongo_client is None:
            settings = AppSettings()
            if self.validate_uri:
                settings.validate_required('MONGO_URI')
            mongo_uri = settings.MONGO_URI
            self.mongo_client = MongoClient(mongo_uri)
        return self.mongo_client

    def get_trades_collection(self):
        if self.trades_collection is None:
            self.trades_collection = self.get_mongo_client().trading.trades
        return self.trades_collection

    def insert_trade(self, trade, collection=None):
        target = self.get_trades_collection() if collection is None else collection
        target.insert_one(trade)

    def get_trades(self):
        return list(self.get_trades_collection().find({}))
