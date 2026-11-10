import unittest
from dataclasses import replace
from pathlib import Path

from trade_ledger.ingestion import RejectedLine, read_events
from trade_ledger.ledger import TradeLedger
from trade_ledger.models import TradeEvent


SAMPLE = Path(__file__).resolve().parents[1] / "trade-events-sample.jsonl"


class TradeEventsSampleTest(unittest.TestCase):
    def setUp(self) -> None:
        with SAMPLE.open("rb") as source:
            self.records = list(read_events(source))
        self.events = [record for record in self.records if isinstance(record, TradeEvent)]
        self.ledger = TradeLedger()
        self.applied = [self.ledger.apply(event) for event in self.events]

    def test_ingestion_rejects_line_three_and_continues(self) -> None:
        self.assertEqual(len(self.records), 8)
        self.assertEqual(self.records[2], RejectedLine(3, "invalid JSON"))
        self.assertEqual(
            [event.event_id for event in self.events],
            ["e-1001", "e-1002", "e-1004", "e-1003", "e-1002", "e-1005", "e-1006"],
        )

    def test_replay_is_applied_once(self) -> None:
        self.assertEqual(self.applied, [True, True, True, True, False, True, True])
        self.assertEqual(
            [event.event_id for event in self.ledger.history("T-2")],
            ["e-1002"],
        )

    def test_history_orders_the_late_amendment_before_cancellation(self) -> None:
        history = self.ledger.history("T-1")
        self.assertEqual(
            [(event.version, event.type.value) for event in history],
            [(1, "NEW"), (2, "AMEND"), (3, "CANCEL")],
        )

    def test_current_state_for_cancelled_active_and_unknown_trades(self) -> None:
        self.assertEqual(self.ledger.current_state("T-1"), self.ledger.history("T-1")[2])
        self.assertEqual(self.ledger.current_state("T-3"), self.ledger.history("T-3")[1])
        self.assertIsNone(self.ledger.current_state("unknown"))

    def test_higher_version_amendment_does_not_reopen_cancelled_trade(self) -> None:
        new, amend, cancel = self.ledger.history("T-1")
        later_amend = replace(amend, event_id="e-1007", version=4, quantity=200)

        for trailing_events in ((cancel, later_amend), (later_amend, cancel)):
            with self.subTest(arrival_order=[event.version for event in trailing_events]):
                ledger = TradeLedger()
                for event in (new, amend, *trailing_events):
                    self.assertTrue(ledger.apply(event))

                self.assertEqual(ledger.current_state("T-1"), cancel)
                self.assertEqual(ledger.history("T-1"), (new, amend, cancel, later_amend))
                self.assertEqual(ledger.positions(), {})

    def test_final_positions(self) -> None:
        self.assertEqual(
            self.ledger.positions(),
            {("ACC-01", "MSFT"): -50, ("ACC-02", "AAPL"): 150},
        )
