import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from trade_ledger.api import create_app


ROOT = Path(__file__).resolve().parents[1]
EVENTS = ROOT / "trade-events-sample.jsonl"
CLEARING = ROOT / "clearing-positions-sample.csv"


class ApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = cls.enterClassContext(TestClient(create_app(EVENTS, CLEARING)))

    def test_health(self) -> None:
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_account_positions(self) -> None:
        response = self.client.get("/accounts/ACC-01/positions")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"account": "ACC-01", "positions": [{"symbol": "MSFT", "quantity": -50}]},
        )

    def test_trade_state_and_history(self) -> None:
        response = self.client.get("/trades/T-1")

        self.assertEqual(response.status_code, 200)
        trade = response.json()
        self.assertEqual(trade["current"], trade["history"][-1])
        self.assertEqual(trade["current"]["type"], "CANCEL")
        self.assertEqual(trade["current"]["price"], "189.20")
        self.assertEqual([event["version"] for event in trade["history"]], [1, 2, 3])

    def test_unknown_trade_returns_404(self) -> None:
        response = self.client.get("/trades/unknown")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "Trade not found"})

    def test_reconciliation(self) -> None:
        response = self.client.get("/reconciliation")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            [{"account": "ACC-03", "symbol": "TSLA", "ours": 0, "theirs": 10, "difference": -10}],
        )

    def test_invalid_clearing_file_prevents_startup(self) -> None:
        with TemporaryDirectory() as directory:
            bad_clearing = Path(directory) / "clearing.csv"
            bad_clearing.write_text("account,symbol,quantity\nACC-03,TSLA,invalid\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "clearing CSV line 2"):
                with TestClient(create_app(EVENTS, bad_clearing)):
                    pass
