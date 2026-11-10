from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum


class EventType(str, Enum):
    NEW = "NEW"
    AMEND = "AMEND"
    CANCEL = "CANCEL"


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


@dataclass(frozen=True)
class TradeEvent:
    """The fields carried by one trade event."""

    event_id: str
    trade_id: str
    version: int
    type: EventType
    account: str
    symbol: str
    venue: str
    side: Side
    quantity: int
    price: Decimal
    event_time: datetime
