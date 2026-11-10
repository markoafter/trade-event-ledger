import argparse
import sys
from pathlib import Path

from .ingestion import RejectedLine
from .loading import load_ledger


def _display_field(value: str) -> str:
    if value.isascii() and value.isprintable() and " " not in value:
        return value
    return ascii(value)


def _report_rejection(record: RejectedLine) -> None:
    print(f"line {record.line_number}: {record.reason}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description="Print net positions from a trade events file.")
    parser.add_argument("file", type=Path, help="path to the JSONL file")
    args = parser.parse_args()
    try:
        with args.file.open("rb") as source:
            ledger = load_ledger(source, _report_rejection)
    except OSError as error:
        print(f"{ascii(str(args.file))}: {error.strerror}", file=sys.stderr)
        return 1

    for (account, symbol), quantity in sorted(ledger.positions().items()):
        print(_display_field(account), _display_field(symbol), quantity)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
