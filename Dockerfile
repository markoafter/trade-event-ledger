FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY trade_ledger/ trade_ledger/
COPY tests/ tests/
COPY trade-events-sample.jsonl clearing-positions-sample.csv ./

USER 10001:10001
EXPOSE 8000

CMD ["python", "-m", "uvicorn", "trade_ledger.api:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
