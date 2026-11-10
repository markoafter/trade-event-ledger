import csv
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TextIO


@dataclass(frozen=True)
class PositionBreak:
    account: str
    symbol: str
    ours: int
    theirs: int
    difference: int


def read_clearing_positions(source: TextIO) -> dict[tuple[str, str], int]:
    """Read a complete clearing snapshot or raise ValueError for invalid data."""
    reader = csv.reader(source, strict=True)
    positions: dict[tuple[str, str], int] = {}
    try:
        if next(reader, None) != ["account", "symbol", "quantity"]:
            raise ValueError("clearing CSV must start with account,symbol,quantity")

        for row in reader:
            if len(row) != 3:
                raise ValueError(f"clearing CSV line {reader.line_num}: expected three columns")
            account, symbol, quantity_text = row
            if not account.strip() or not symbol.strip():
                raise ValueError(f"clearing CSV line {reader.line_num}: account and symbol are required")

            key = (account, symbol)
            if key in positions:
                raise ValueError(f"clearing CSV line {reader.line_num}: duplicate account and symbol")

            try:
                positions[key] = int(quantity_text)
            except ValueError:
                raise ValueError(f"clearing CSV line {reader.line_num}: quantity must be an integer") from None
    except csv.Error as error:
        raise ValueError(f"clearing CSV line {reader.line_num}: {error}") from None
    return positions


def reconcile(
    ledger_positions: Mapping[tuple[str, str], int],
    clearing_positions: Mapping[tuple[str, str], int],
) -> list[PositionBreak]:
    """Compare both snapshots, treating a missing position as zero."""
    breaks = []
    for account, symbol in sorted(ledger_positions.keys() | clearing_positions.keys()):
        key = (account, symbol)
        ours = ledger_positions.get(key, 0)
        theirs = clearing_positions.get(key, 0)
        if ours != theirs:
            breaks.append(PositionBreak(account, symbol, ours, theirs, ours - theirs))
    return breaks
