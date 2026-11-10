import json
import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import BinaryIO

from .models import EventType, Side, TradeEvent


MAX_RECORD_BYTES = 64 * 1024
_UTC_TIMESTAMP = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]{1,6})?(?:Z|\+00:00)"
)


@dataclass(frozen=True)
class RejectedLine:
    line_number: int
    reason: str


class _InvalidRecord(ValueError):
    pass


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise _InvalidRecord("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(_: str) -> None:
    raise _InvalidRecord("nonstandard JSON numeric constant")


def _parse_event(line: bytes) -> TradeEvent:
    try:
        record = json.loads(
            line.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except _InvalidRecord:
        raise
    except UnicodeDecodeError:
        raise _InvalidRecord("invalid UTF-8") from None
    except (ValueError, RecursionError):
        raise _InvalidRecord("invalid JSON") from None

    if not isinstance(record, dict):
        raise _InvalidRecord("expected a JSON object")

    strings = {}
    for field in (
        "event_id", "trade_id", "type", "account", "symbol", "venue", "side",
        "price", "event_time",
    ):
        value = record.get(field)
        if not isinstance(value, str) or not value.strip():
            raise _InvalidRecord(f"{field} must be a nonempty string")
        strings[field] = value

    version = record.get("version")
    if type(version) is not int or version < 1:
        raise _InvalidRecord("version must be a positive integer")
    quantity = record.get("quantity")
    if type(quantity) is not int or quantity < 0:
        raise _InvalidRecord("quantity must be a nonnegative integer")

    try:
        event_type = EventType(strings["type"])
    except ValueError:
        raise _InvalidRecord("type must be NEW, AMEND, or CANCEL") from None
    try:
        side = Side(strings["side"])
    except ValueError:
        raise _InvalidRecord("side must be BUY or SELL") from None

    try:
        price = Decimal(strings["price"])
    except InvalidOperation:
        raise _InvalidRecord("price must be a finite decimal string") from None
    if not price.is_finite():
        raise _InvalidRecord("price must be a finite decimal string")

    timestamp = strings["event_time"]
    if not _UTC_TIMESTAMP.fullmatch(timestamp):
        raise _InvalidRecord("event_time must be an ISO 8601 UTC timestamp")
    try:
        event_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        raise _InvalidRecord("event_time must be an ISO 8601 UTC timestamp") from None

    return TradeEvent(
        event_id=strings["event_id"],
        trade_id=strings["trade_id"],
        version=version,
        type=event_type,
        account=strings["account"],
        symbol=strings["symbol"],
        venue=strings["venue"],
        side=side,
        quantity=quantity,
        price=price,
        event_time=event_time,
    )


def read_events(source: BinaryIO) -> Iterator[TradeEvent | RejectedLine]:
    """Yield an event or rejection per line, with a byte cap including the line ending."""
    line_number = 0
    while line := source.readline(MAX_RECORD_BYTES + 1):
        line_number += 1
        if len(line) > MAX_RECORD_BYTES:
            while line and not line.endswith(b"\n"):
                line = source.readline(MAX_RECORD_BYTES + 1)
            yield RejectedLine(line_number, f"record exceeds {MAX_RECORD_BYTES} bytes")
            continue

        try:
            yield _parse_event(line)
        except _InvalidRecord as error:
            yield RejectedLine(line_number, str(error))
