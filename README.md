# Data Processing Service

A Flask service that fetches booking data from an external JSON endpoint, processes it, and returns aggregated results. Deployed on Google Cloud Run.

## How to run locally

```bash
pip install -r requirements.txt
python main.py
```

## How to run tests

```bash
pip install pytest
pytest test_main.py -v
```

## How to deploy

```bash
gcloud run deploy data-service \
  --source . \
  --region europe-west1 \
  --allow-unauthenticated \
  --port 8080
```

## Assumptions

- "Successful booking" means type is booking, status is confirmed, and amount is positive
- Duplicate record IDs are data errors; first occurrence wins
- Totals are grouped by currency rather than summed across currencies
