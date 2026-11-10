import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request

from .ingestion import RejectedLine
from .ledger import TradeLedger
from .loading import load_ledger
from .models import TradeEvent
from .reconciliation import PositionBreak, read_clearing_positions, reconcile


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AccountPosition:
    symbol: str
    quantity: int


@dataclass(frozen=True)
class AccountPositions:
    account: str
    positions: list[AccountPosition]


@dataclass(frozen=True)
class TradeDetails:
    current: TradeEvent
    history: tuple[TradeEvent, ...]


def _log_rejection(record: RejectedLine) -> None:
    logger.warning("Trade events line %d: %s", record.line_number, record.reason)


def create_app(
    events_path: Path | None = None,
    clearing_path: Path | None = None,
) -> FastAPI:
    if events_path is None:
        events_path = Path(os.environ.get("TRADE_EVENTS_FILE", "trade-events-sample.jsonl"))
    if clearing_path is None:
        clearing_path = Path(os.environ.get("CLEARING_POSITIONS_FILE", "clearing-positions-sample.csv"))

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        with events_path.open("rb") as source:
            app.state.ledger = load_ledger(source, _log_rejection)
        with clearing_path.open(encoding="utf-8", newline="") as source:
            app.state.clearing_positions = read_clearing_positions(source)
        yield

    app = FastAPI(title="Trade Event Ledger", lifespan=lifespan)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/accounts/{account}/positions")
    def account_positions(account: str, request: Request) -> AccountPositions:
        ledger: TradeLedger = request.app.state.ledger
        positions = [
            AccountPosition(symbol, quantity)
            for (position_account, symbol), quantity in sorted(ledger.positions().items())
            if position_account == account
        ]
        return AccountPositions(account, positions)

    @app.get("/trades/{trade_id}")
    def trade_details(trade_id: str, request: Request) -> TradeDetails:
        ledger: TradeLedger = request.app.state.ledger
        current = ledger.current_state(trade_id)
        if current is None:
            raise HTTPException(status_code=404, detail="Trade not found")
        return TradeDetails(current, ledger.history(trade_id))

    @app.get("/reconciliation")
    def reconciliation(request: Request) -> list[PositionBreak]:
        ledger: TradeLedger = request.app.state.ledger
        return reconcile(ledger.positions(), request.app.state.clearing_positions)

    return app
