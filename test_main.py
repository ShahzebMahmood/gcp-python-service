import pytest
from main import app, process_records


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def make_booking(id="evt-1", status="confirmed", amount=100, currency="USD", **overrides):
    record = {
        "id": id,
        "type": "booking",
        "status": status,
        "customer": {"id": "cus-1", "name": "Test User", "email": "test@example.com"},
        "trip": {"origin": "YUL", "destination": "JFK", "departure_date": "2026-04-01"},
        "price": {"amount": amount, "currency": currency},
        "created_at": "2026-03-15T14:00:00Z",
    }
    record.update(overrides)
    return record


def test_confirmed_booking_counted():
    data = {"records": [make_booking()]}
    result = process_records(data)
    assert result["total_successful_bookings"] == 1
    assert result["totals_by_currency"]["USD"] == 100


def test_pending_booking_excluded():
    data = {"records": [make_booking(status="pending")]}
    result = process_records(data)
    assert result["total_successful_bookings"] == 0


def test_cancelled_booking_excluded():
    data = {"records": [make_booking(status="cancelled")]}
    result = process_records(data)
    assert result["total_successful_bookings"] == 0


def test_case_insensitive_status():
    data = {"records": [make_booking(status="CONFIRMED")]}
    result = process_records(data)
    assert result["total_successful_bookings"] == 1


def test_null_status_excluded():
    data = {"records": [make_booking(status=None)]}
    result = process_records(data)
    assert result["total_successful_bookings"] == 0


def test_non_booking_type_excluded():
    data = {"records": [make_booking(type="refund"), make_booking(type="hotel")]}
    result = process_records(data)
    assert result["total_successful_bookings"] == 0


def test_duplicate_ids_deduplicated():
    data = {"records": [
        make_booking(id="evt-dup", amount=200),
        make_booking(id="evt-dup", amount=300),
    ]}
    result = process_records(data)
    assert result["total_successful_bookings"] == 1
    assert result["totals_by_currency"]["USD"] == 200


def test_string_amount_parsed():
    data = {"records": [make_booking(amount="249.99")]}
    result = process_records(data)
    assert result["totals_by_currency"]["USD"] == 249.99


def test_negative_amount_excluded():
    data = {"records": [make_booking(amount=-50)]}
    result = process_records(data)
    assert result["total_successful_bookings"] == 0


def test_zero_amount_excluded():
    data = {"records": [make_booking(amount=0)]}
    result = process_records(data)
    assert result["total_successful_bookings"] == 0


def test_empty_price_excluded():
    data = {"records": [make_booking(price={})]}
    result = process_records(data)
    assert result["total_successful_bookings"] == 0


def test_null_customer_handled():
    data = {"records": [make_booking(customer=None)]}
    result = process_records(data)
    assert result["total_successful_bookings"] == 1
    assert result["bookings"][0]["customer_name"] == "N/A"


def test_route_field_used_as_fallback():
    record = make_booking()
    del record["trip"]
    record["route"] = {"from": "SEA", "to": "LAS"}
    data = {"records": [record]}
    result = process_records(data)
    assert result["bookings"][0]["origin"] == "SEA"
    assert result["bookings"][0]["destination"] == "LAS"


def test_multiple_currencies_grouped():
    data = {"records": [
        make_booking(id="evt-1", amount=100, currency="USD"),
        make_booking(id="evt-2", amount=200, currency="CAD"),
        make_booking(id="evt-3", amount=150, currency="USD"),
    ]}
    result = process_records(data)
    assert result["totals_by_currency"]["USD"] == 250
    assert result["totals_by_currency"]["CAD"] == 200


def test_empty_records():
    data = {"records": []}
    result = process_records(data)
    assert result["total_successful_bookings"] == 0
    assert result["totals_by_currency"] == {}


def test_processed_data_endpoint(client):
    resp = client.get("/processed-data")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "total_successful_bookings" in data
    assert "totals_by_currency" in data
    assert "bookings" in data


def test_health_endpoint(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"
