import os
from flask import Flask, jsonify
import requests

app = Flask(__name__)

DATA_URL = "https://storage.googleapis.com/hopper-smart-updater/test.json"


def fetch_data():
    resp = requests.get(DATA_URL, timeout=10)
    resp.raise_for_status()
    return resp.json()


def process_records(data):
    records = data.get("records", [])
    seen_ids = set()
    totals_by_currency = {}
    successful_bookings = []

    for record in records:
        # Only process bookings
        if record.get("type") != "booking":
            continue

        # Only confirmed (case-insensitive)
        status = record.get("status")
        if not status or status.lower() != "confirmed":
            continue

        # Deduplicate by ID
        record_id = record.get("id")
        if record_id in seen_ids:
            continue
        seen_ids.add(record_id)

        # Extract amount, handle missing/malformed price
        price = record.get("price", {})
        if not price or not isinstance(price, dict):
            continue

        raw_amount = price.get("amount")
        if raw_amount is None:
            continue

        try:
            amount = float(raw_amount)
        except (ValueError, TypeError):
            continue

        if amount <= 0:
            continue

        currency = price.get("currency", "UNKNOWN")
        totals_by_currency[currency] = round(totals_by_currency.get(currency, 0) + amount, 2)

        # Build a clean booking summary
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
    try:
        data = fetch_data()
        result = process_records(data)
        return jsonify(result)
    except requests.RequestException as e:
        return jsonify({"error": f"Failed to fetch data: {e}"}), 502
    except (ValueError, KeyError) as e:
        return jsonify({"error": f"Failed to process data: {e}"}), 500


@app.route("/")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
