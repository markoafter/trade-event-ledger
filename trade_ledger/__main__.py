import argparse
import sys
from pathlib import Path

from .ingestion import RejectedLine, read_events
from .ledger import LedgerConflict, TradeLedger


def _display_field(value: str) -> str:
    if value.isascii() and value.isprintable() and " " not in value:
        return value
    return ascii(value)


def main() -> int:
    parser = argparse.ArgumentParser(description="Print net positions from a trade events file.")
    parser.add_argument("file", type=Path, help="path to the JSONL file")
    args = parser.parse_args()
    ledger = TradeLedger()

    try:
        with args.file.open("rb") as source:
            for line_number, record in enumerate(read_events(source), start=1):
                if isinstance(record, RejectedLine):
                    print(f"line {record.line_number}: {record.reason}", file=sys.stderr)
                    continue
                try:
                    ledger.apply(record)
                except LedgerConflict as error:
                    print(f"line {line_number}: {error}", file=sys.stderr)
    except OSError as error:
        print(f"{ascii(str(args.file))}: {error.strerror}", file=sys.stderr)
        return 1

    for (account, symbol), quantity in sorted(ledger.positions().items()):
        print(_display_field(account), _display_field(symbol), quantity)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
