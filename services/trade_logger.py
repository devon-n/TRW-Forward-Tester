import json
import traceback
from db import trades_collection


def record_trade(data: bytes, order_response):
    """Records trade to MongoDB with strategy information."""
    try:
        doc = {}
        if order_response and isinstance(order_response, dict):
            doc.update(order_response)
        doc.update(json.loads(data))
        trades_collection.insert_one(doc)
    except Exception as e:
        print(f"Failed Order: An exception occurred: {e}")
        traceback.print_exc()
