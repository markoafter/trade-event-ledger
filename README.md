# Trade Event Ledger

A read-only API that replays trade events, calculates net positions, and compares them with a clearing snapshot.

## Run and test

From the repository root, with Docker and Compose running, build and start the API:

```sh
docker compose up --build
```

Open the [API docs](http://127.0.0.1:8000/docs). If port 8000 is already in use, run `LEDGER_PORT=8001 docker compose up --build` and open port 8001 instead.

Build the image and run the automated tests:

```sh
docker compose run --build --rm ledger python -m unittest discover -s tests -v
```

| Endpoint | Sample result |
| --- | --- |
| `GET /health` | Ready after both files load |
| `GET /accounts/ACC-01/positions` | −50 MSFT |
| `GET /trades/T-1` | `CANCEL v3` with version-ordered history |
| `GET /reconciliation` | `ACC-03 / TSLA`, ledger 0, clearing 10, difference −10 |

The sample JSONL intentionally has a malformed record on line 3. Expect a startup warning for it. To use other inputs, mount them read-only and set the paths inside the container:

```sh
docker compose run --build --rm --service-ports \
  -v "/absolute/path/events.jsonl:/inputs/events.jsonl:ro" \
  -v "/absolute/path/positions.csv:/inputs/positions.csv:ro" \
  -e TRADE_EVENTS_FILE=/inputs/events.jsonl \
  -e CLEARING_POSITIONS_FILE=/inputs/positions.csv ledger
```

## Assumptions and trade-offs

- Each event is a full snapshot. An amendment can contribute before its `NEW` arrives. Cancellation is terminal, and later versions remain in history.
- Exact replays are ignored. If an event ID or trade version conflicts, the first accepted event stays in the ledger and the conflicting line is logged and skipped.
- Missing positions count as zero in reconciliation. The difference is ledger quantity minus clearing quantity. A malformed or duplicate row in the clearing CSV fails startup because an incomplete snapshot could produce misleading breaks.
- Events are held in memory and replayed at startup. Deriving balances from history keeps the exercise simple. For live ingestion or multiple service processes, the next step would be durable event storage with uniqueness constraints and a shared, rebuildable view of positions.

In production, alert on failed or stale input loads, spikes in rejected records or version conflicts, and reconciliation breaks that remain open near the clearing deadline. Track API error rate and latency separately from data-quality alerts.
