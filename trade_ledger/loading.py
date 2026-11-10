from collections.abc import Callable
from typing import BinaryIO

from .ingestion import RejectedLine, read_events
from .ledger import LedgerConflict, TradeLedger


def load_ledger(
    source: BinaryIO,
    report_rejection: Callable[[RejectedLine], None],
) -> TradeLedger:
    """Build a ledger from JSONL and report records that could not be applied."""
    ledger = TradeLedger()
    for line_number, record in enumerate(read_events(source), start=1):
        if isinstance(record, RejectedLine):
            report_rejection(record)
            continue
        try:
            ledger.apply(record)
        except LedgerConflict as error:
            report_rejection(RejectedLine(line_number, str(error)))
    return ledger
