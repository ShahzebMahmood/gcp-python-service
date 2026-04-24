# Hopper Assessment - Data Processing Service

A lightweight Flask service that fetches booking data from an external endpoint, processes it, and returns aggregated results. Deployed on Google Cloud Run.

## Live URL

```
https://hopper-assessment-518169939968.europe-west1.run.app/processed-data
```

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Health check |
| GET | `/processed-data` | Fetch, process, and return booking data |

## How to run locally

```bash
pip install -r requirements.txt
python main.py
# Service starts on http://localhost:8080
```

## How to deploy

```bash
gcloud run deploy hopper-assessment \
  --source . \
  --region europe-west1 \
  --allow-unauthenticated \
  --port 8080
```

## How to run tests

```bash
pip install pytest
pytest test_main.py -v
```

## Design decisions

**What counts as a "successful booking":**
- `type` must be `"booking"` (excludes refunds, hotel stays, etc.)
- `status` must be `"confirmed"` (case-insensitive, so `"CONFIRMED"` is included)
- Must have a valid positive `amount` in the price object

**Data quality handling:**

The source data contains several inconsistencies that the service handles:

| Issue | Example | How it's handled |
|-------|---------|-----------------|
| Duplicate record IDs | `evt-1012` appears twice | Deduplicated, first occurrence kept |
| Mixed case status | `"confirmed"` vs `"CONFIRMED"` | Case-insensitive comparison |
| String amounts | `"389.99"` instead of `389.99` | Parsed to float |
| Missing/null fields | `customer: null`, `status: null` | Skipped gracefully |
| Negative amounts | `-50` on a cancelled booking | Excluded (amount must be > 0) |
| Empty price object | `"price": {}` | Skipped, no amount to extract |
| Alternative field names | `route.from/to` instead of `trip.origin/destination` | Both patterns supported |
| Non-booking types | `"type": "refund"`, `"type": "hotel"` | Filtered out |
| Zero amounts | Failed booking with `amount: 0` | Excluded |

**Multiple currencies:**
The dataset contains CAD, USD, GBP, and JPY. Rather than assuming a single currency or doing conversion, totals are grouped by currency to avoid data loss.

**No caching:**
Data is fetched fresh on each request. For a production service you'd add caching, but for this scope keeping it simple avoids stale data concerns.

## Assumptions

- "Successful" means confirmed, not pending/cancelled/failed/null
- Amounts that are zero or negative are not meaningful revenue and are excluded
- Duplicate IDs are data errors; first occurrence wins
- Currency conversion is out of scope; totals are per-currency
