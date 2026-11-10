from .models import EventType, Side, TradeEvent


class LedgerConflict(ValueError):
    """An event ID or trade version is already in use."""


class TradeLedger:
    """An in-memory ledger for a single event consumer."""

    def __init__(self) -> None:
        self._events_by_id: dict[str, TradeEvent] = {}
        self._events_by_trade: dict[str, dict[int, TradeEvent]] = {}

    def apply(self, event: TradeEvent) -> bool:
        """Store an event, returning False for an exact replay."""
        existing = self._events_by_id.get(event.event_id)
        if existing is not None:
            if existing == event:
                return False
            raise LedgerConflict("event ID already has a different event")

        versions = self._events_by_trade.get(event.trade_id)
        if versions is not None and event.version in versions:
            raise LedgerConflict("trade version already has a different event")

        self._events_by_trade.setdefault(event.trade_id, {})[event.version] = event
        self._events_by_id[event.event_id] = event
        return True

    def history(self, trade_id: str) -> tuple[TradeEvent, ...]:
        """Return accepted events in version order."""
        versions = self._events_by_trade.get(trade_id, {})
        return tuple(versions[version] for version in sorted(versions))

    def current_state(self, trade_id: str) -> TradeEvent | None:
        """Return the first cancellation by version, or the highest active version."""
        versions = self._events_by_trade.get(trade_id)
        if versions is None:
            return None

        cancel_version = min(
            (version for version, event in versions.items() if event.type is EventType.CANCEL),
            default=None,
        )
        if cancel_version is not None:
            return versions[cancel_version]
        return versions[max(versions)]

    def positions(self) -> dict[tuple[str, str], int]:
        """Return nonzero net quantities by (account, symbol), across venues."""
        positions: dict[tuple[str, str], int] = {}
        for trade_id in self._events_by_trade:
            current = self.current_state(trade_id)
            if current is None or current.type is EventType.CANCEL:
                continue

            key = (current.account, current.symbol)
            quantity = current.quantity if current.side is Side.BUY else -current.quantity
            positions[key] = positions.get(key, 0) + quantity

        return {key: quantity for key, quantity in positions.items() if quantity != 0}
