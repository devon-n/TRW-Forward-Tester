import os
from pymongo import MongoClient # type: ignore

_client = None

def get_client():
    global _client
    if _client is None:
        connection_string = os.getenv("MONGO_URI")
        _client = MongoClient(connection_string)
    return _client

def get_db():
    return get_client()["trading"]

def get_trades_collection():
    return get_db()["trades"]
