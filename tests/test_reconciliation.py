import unittest
from io import StringIO
from pathlib import Path

from practice.trade_ledger.ingestion import read_events
from practice.trade_ledger.ledger import TradeLedger
from practice.trade_ledger.models import TradeEvent
from practice.trade_ledger.reconciliation import PositionBreak, read_clearing_positions, reconcile


ROOT = Path(__file__).resolve().parents[2]


class ReconciliationTest(unittest.TestCase):
    def test_sample_files_produce_one_break(self) -> None:
        ledger = TradeLedger()
        with (ROOT / "trade-events-sample.jsonl").open("rb") as source:
            for record in read_events(source):
                if isinstance(record, TradeEvent):
                    ledger.apply(record)
        with (ROOT / "clearing-positions-sample.csv").open(encoding="utf-8", newline="") as source:
            clearing_positions = read_clearing_positions(source)

        self.assertEqual(
            reconcile(ledger.positions(), clearing_positions),
            [PositionBreak("ACC-03", "TSLA", 0, 10, -10)],
        )

    def test_reports_ledger_only_and_different_quantities(self) -> None:
        ours = {("ACC-02", "AAPL"): -5, ("ACC-01", "MSFT"): 20}
        theirs = {("ACC-01", "MSFT"): 15}

        self.assertEqual(
            reconcile(ours, theirs),
            [
                PositionBreak("ACC-01", "MSFT", 20, 15, 5),
                PositionBreak("ACC-02", "AAPL", -5, 0, -5),
            ],
        )

    def test_invalid_rows_fail_the_clearing_snapshot(self) -> None:
        header = "account,symbol,quantity\n"
        first_row = "ACC-01,MSFT,-50\n"
        for invalid_row, reason in (
            ("ACC-01,MSFT,50\n", "duplicate account and symbol"),
            ("ACC-02,AAPL,1.5\n", "quantity must be an integer"),
            ("ACC-02,AAPL\n", "expected three columns"),
        ):
            with self.subTest(row=invalid_row):
                with self.assertRaisesRegex(ValueError, f"line 3: {reason}"):
                    read_clearing_positions(StringIO(header + first_row + invalid_row))
