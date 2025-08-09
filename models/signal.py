from enum import Enum
from typing import Optional, Union
from pydantic import BaseModel, Field, model_validator, validator
import json


class OrderId(Enum):
    BUY = "BUY"
    SELL = "SELL"
    TP = "Close entry(s) order strategy.close_0"
    SL = "SL"
    EXIT_SHORT = "Exit Short"


class CommentData(BaseModel):
    leverage: float
    position_size: float


class Bar(BaseModel):
    time: str
    open: float
    high: float
    low: float
    close: float
    volume: float


class Strategy(BaseModel):
    position_size: float
    order_action: str
    order_contracts: float
    order_price: float
    order_id: OrderId
    market_position: str
    market_position_size: float
    prev_market_position: str
    prev_market_position_size: float


class SignalPayload(BaseModel):
    strategyName: str
    order_type: str
    time: str
    exchange: str
    timeframe: str
    ticker: str
    leverage: str
    comment: str
    bar: Bar
    strategy: Strategy
    passphrase: Optional[str] = ""

    comment_data: Optional[CommentData] = Field(default=None, exclude=True)

    @model_validator(mode="after")
    def pase_comment_json(cls, model):
        if model.comment:
            try:
                parsed = json.loads(model.comment)
                if isinstance(parsed, dict):
                    model.comment_data = CommentData(**parsed)
            except Exception:
                print("Not Json")
        return model
