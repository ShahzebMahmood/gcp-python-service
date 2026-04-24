import os
from flask import Flask, jsonify
import requests

app = Flask(__name__)

# The external data source we fetch booking records from
DATA_URL = "https://storage.googleapis.com/hopper-smart-updater/test.json"


def fetch_data():
    """Fetch the JSON payload from the external endpoint.
    Raises on HTTP errors so the caller can return a proper error response."""
    resp = requests.get(DATA_URL, timeout=10)
    resp.raise_for_status()
    return resp.json()


def process_records(data):
    """Process raw records and extract totals from successful bookings.

    A "successful booking" is defined as:
      - type == "booking" (excludes refunds, hotels, etc.)
      - status == "confirmed" (case-insensitive, so "CONFIRMED" also matches)
      - has a valid price with a positive amount

    The source data is messy, so this function also handles:
      - Duplicate record IDs (keeps the first occurrence)
      - Amounts stored as strings instead of numbers
      - Missing or null fields (customer, price, status)
      - Negative or zero amounts
      - Alternative field names ("route" instead of "trip")
      - Multiple currencies (totals are grouped per currency)
    """
    records = data.get("records", [])
    seen_ids = set()          # Track IDs we've already processed to skip duplicates
    totals_by_currency = {}   # Running totals per currency, e.g. {"USD": 1066.84, "CAD": 696.25}
    successful_bookings = []  # List of clean booking summaries for the response

    for record in records:
        # Skip non-booking records (refunds, hotels, etc.)
        if record.get("type") != "booking":
            continue

        # Match "confirmed" status, case-insensitive (handles "CONFIRMED", "Confirmed", etc.)
        status = record.get("status")
        if not status or status.lower() != "confirmed":
            continue

        # Skip duplicate IDs -- the dataset has evt-1012 appearing twice
        record_id = record.get("id")
        if record_id in seen_ids:
            continue
        seen_ids.add(record_id)

        # Extract price -- some records have empty price objects {} or missing fields
        price = record.get("price", {})
        if not price or not isinstance(price, dict):
            continue

        # Amount can be a number or a string ("389.99"), so we cast to float
        raw_amount = price.get("amount")
        if raw_amount is None:
            continue

        try:
            amount = float(raw_amount)
        except (ValueError, TypeError):
            continue

        # Skip zero or negative amounts (failed/cancelled bookings)
        if amount <= 0:
            continue

        # Add to the running total for this currency
        currency = price.get("currency", "UNKNOWN")
        totals_by_currency[currency] = round(totals_by_currency.get(currency, 0) + amount, 2)

        # Build a clean summary for this booking
        # Some records have null customer or use "route" instead of "trip"
        customer = record.get("customer") or {}
        trip = record.get("trip") or record.get("route") or {}
        origin = trip.get("origin") or trip.get("from", "N/A")
        destination = trip.get("destination") or trip.get("to", "N/A")

        successful_bookings.append({
            "id": record_id,
            "customer_name": customer.get("name") or "N/A",
            "origin": origin,
            "destination": destination,
            "amount": amount,
            "currency": currency,
        })

    return {
        "total_successful_bookings": len(successful_bookings),
        "totals_by_currency": totals_by_currency,
        "bookings": successful_bookings,
    }


@app.route("/processed-data")
def processed_data():
    """Main endpoint -- fetches data, processes it, returns the result.
    Returns 502 if the external endpoint is unreachable, 500 for processing errors."""
    try:
        data = fetch_data()
        result = process_records(data)
        return jsonify(result)
    except requests.RequestException:
        # External endpoint is unreachable or returned an HTTP error.
        # We use a generic message here to avoid leaking internal URLs or
        # connection details from the exception to the client.
        return jsonify({"error": "Failed to fetch data from external source"}), 502
    except (ValueError, KeyError):
        # JSON was malformed or missing expected structure.
        # Same as above -- keep error messages generic so we don't expose
        # field names or data shapes to the client.
        return jsonify({"error": "Failed to process data"}), 500
    except Exception:
        # Catch-all so we never leak a raw stack trace to the client
        return jsonify({"error": "Internal server error"}), 500


@app.route("/")
def health():
    """Simple health check endpoint."""
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    # Cloud Run sets the PORT env var; default to 8080 for local development
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
