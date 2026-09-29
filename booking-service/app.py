from flask import Flask, request, jsonify
import sqlite3
import requests
from datetime import datetime
from saga import release_vehicle

import sys
import os

sys.path.append(
    os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "..",
            "payment-service"
        )
    )
)

from circuit_breaker import CircuitBreaker


app = Flask(__name__)

DATABASE = "booking.db"

# =========================
# SERVICE REGISTRY
# =========================

REGISTRY_URL = "http://localhost:5005"
SERVICE_NAME = "booking-service"
SERVICE_URL = "http://localhost:5003"


# =========================
# PAYMENT CIRCUIT BREAKER
# =========================

payment_circuit_breaker = CircuitBreaker(
    failure_threshold=3,
    recovery_timeout=10
)


# =========================
# DATABASE CONNECTION
# =========================

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


# =========================
# DATABASE INITIALIZATION
# =========================

def init_db():
    conn = get_db_connection()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            vehicle_id INTEGER NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            amount REAL NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


# =========================
# SERVICE REGISTRATION
# =========================

def register_with_registry():
    try:
        response = requests.post(
            f"{REGISTRY_URL}/register",
            json={
                "service_name": SERVICE_NAME,
                "service_url": SERVICE_URL
            },
            timeout=3
        )

        print("Booking Service Registration:", response.json())

    except requests.RequestException as error:
        print("Booking Service Registration Failed:", error)


# =========================
# SERVICE DISCOVERY
# =========================

def get_service_url(service_name):

    try:

        response = requests.get(
            f"{REGISTRY_URL}/services/{service_name}",
            timeout=3
        )

        if response.status_code != 200:
            return None

        data = response.json()

        return data.get("service_url")

    except requests.RequestException:

        return None


# =========================
# HEALTH CHECK
# =========================

@app.route("/health", methods=["GET"])
def health():

    return jsonify({
        "service": "booking-service",
        "status": "UP"
    })


# =========================
# CIRCUIT BREAKER STATUS
# =========================

@app.route(
    "/api/v1/bookings/circuit-breaker",
    methods=["GET"]
)
def circuit_breaker_status():

    return jsonify(
        payment_circuit_breaker.get_status()
    )


# =========================
# GET ALL BOOKINGS
# =========================

@app.route("/api/v1/bookings", methods=["GET"])
def get_bookings():

    conn = get_db_connection()

    bookings = conn.execute(
        "SELECT * FROM bookings ORDER BY id DESC"
    ).fetchall()

    conn.close()

    return jsonify([
        dict(booking)
        for booking in bookings
    ])


# =========================
# GET BOOKING BY ID
# =========================

@app.route(
    "/api/v1/bookings/<int:booking_id>",
    methods=["GET"]
)
def get_booking(booking_id):

    conn = get_db_connection()

    booking = conn.execute(
        "SELECT * FROM bookings WHERE id = ?",
        (booking_id,)
    ).fetchone()

    conn.close()

    if booking is None:

        return jsonify({
            "error": "Booking not found"
        }), 404

    return jsonify(dict(booking))


# =========================
# CREATE BOOKING
# =========================

@app.route("/api/v1/bookings", methods=["POST"])
def create_booking():

    data = request.get_json()

    if not data:

        return jsonify({
            "error": "Request body is required"
        }), 400

    user_id = data.get("user_id")
    vehicle_id = data.get("vehicle_id")
    start_date = data.get("start_date")
    end_date = data.get("end_date")

    if (
        user_id is None
        or vehicle_id is None
        or not start_date
        or not end_date
    ):

        return jsonify({
            "error": (
                "user_id, vehicle_id, start_date "
                "and end_date are required"
            )
        }), 400


    # =====================================
    # STEP 1: DISCOVER USER SERVICE
    # =====================================

    user_service_url = get_service_url(
        "user-service"
    )

    if not user_service_url:

        return jsonify({
            "error": "User Service unavailable"
        }), 503


    # =====================================
    # STEP 2: VERIFY USER
    # =====================================

    try:

        user_response = requests.get(
            f"{user_service_url}/api/v1/users/{user_id}",
            timeout=3
        )

    except requests.RequestException:

        return jsonify({
            "error": (
                "Could not communicate with "
                "User Service"
            )
        }), 503


    if user_response.status_code != 200:

        return jsonify({
            "error": "User not found"
        }), 404


    user = user_response.json()


    # =====================================
    # STEP 3: DISCOVER VEHICLE SERVICE
    # =====================================

    vehicle_service_url = get_service_url(
        "vehicle-service"
    )

    if not vehicle_service_url:

        return jsonify({
            "error": "Vehicle Service unavailable"
        }), 503


    # =====================================
    # STEP 4: GET VEHICLE
    # =====================================

    try:

        vehicle_response = requests.get(
            f"{vehicle_service_url}/api/v1/vehicles/{vehicle_id}",
            timeout=3
        )

    except requests.RequestException:

        return jsonify({
            "error": (
                "Could not communicate with "
                "Vehicle Service"
            )
        }), 503


    if vehicle_response.status_code != 200:

        return jsonify({
            "error": "Vehicle not found"
        }), 404


    vehicle = vehicle_response.json()


    # =====================================
    # STEP 5: CHECK VEHICLE AVAILABILITY
    # =====================================

    if vehicle["status"] != "AVAILABLE":

        return jsonify({
            "error": "Vehicle is not available",
            "vehicle_status": vehicle["status"]
        }), 409


    # Simple one-day rental calculation
    amount = vehicle["price_per_day"]


    # =====================================
    # STEP 6: RESERVE VEHICLE
    # =====================================

    try:

        reserve_response = requests.put(
            f"{vehicle_service_url}/api/v1/vehicles/"
            f"{vehicle_id}/reserve",
            timeout=3
        )

    except requests.RequestException:

        return jsonify({
            "error": "Could not reserve vehicle"
        }), 503


    if reserve_response.status_code != 200:

        return jsonify({
            "error": "Vehicle reservation failed"
        }), 409


    # =====================================
    # STEP 7: CREATE PENDING BOOKING
    # =====================================

    created_at = datetime.now().isoformat()

    conn = get_db_connection()

    cursor = conn.execute(
        """
        INSERT INTO bookings
        (
            user_id,
            vehicle_id,
            start_date,
            end_date,
            amount,
            status,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            vehicle_id,
            start_date,
            end_date,
            amount,
            "PENDING",
            created_at
        )
    )

    conn.commit()

    booking_id = cursor.lastrowid

    conn.close()


    # =====================================
    # STEP 8: DISCOVER PAYMENT SERVICE
    # =====================================

    payment_service_url = get_service_url(
        "payment-service"
    )

    if not payment_service_url:

        # Saga Compensation
        compensation = release_vehicle(
            vehicle_service_url,
            vehicle_id
        )

        conn = get_db_connection()

        conn.execute(
            """
            UPDATE bookings
            SET status = 'CANCELLED'
            WHERE id = ?
            """,
            (booking_id,)
        )

        conn.commit()
        conn.close()

        return jsonify({
            "error": "Payment Service unavailable",
            "booking_id": booking_id,
            "message": "Saga compensation executed",
            "compensation": compensation
        }), 503


    # =====================================
    # STEP 9: CIRCUIT BREAKER CHECK
    # =====================================

    if not payment_circuit_breaker.can_execute():

        # Circuit is OPEN

        compensation = release_vehicle(
            vehicle_service_url,
            vehicle_id
        )

        conn = get_db_connection()

        conn.execute(
            """
            UPDATE bookings
            SET status = 'CANCELLED'
            WHERE id = ?
            """,
            (booking_id,)
        )

        conn.commit()
        conn.close()

        return jsonify({
            "error": "Payment Service unavailable",
            "circuit_breaker": "OPEN",
            "message": (
                "Request rejected by "
                "Circuit Breaker"
            ),
            "compensation": compensation
        }), 503


    # =====================================
    # STEP 10: PROCESS MOCK PAYMENT
    # =====================================

    try:

        payment_response = requests.post(
            f"{payment_service_url}/api/v1/payments",
            json={
                "booking_id": booking_id,
                "user_id": user_id,
                "amount": amount,
                "payment_status": data.get(
                    "payment_status",
                    "SUCCESS"
                )
            },
            timeout=3
        )

        # Payment Service responded.
        # Therefore communication worked.
        payment_circuit_breaker.record_success()

    except requests.RequestException:

        # Payment Service communication failed.
        payment_circuit_breaker.record_failure()

        # Saga Compensation
        compensation = release_vehicle(
            vehicle_service_url,
            vehicle_id
        )

        conn = get_db_connection()

        conn.execute(
            """
            UPDATE bookings
            SET status = 'CANCELLED'
            WHERE id = ?
            """,
            (booking_id,)
        )

        conn.commit()
        conn.close()

        return jsonify({
            "error": (
                "Payment Service "
                "communication failed"
            ),
            "booking_id": booking_id,
            "circuit_breaker":
                payment_circuit_breaker.state,
            "message": (
                "Booking cancelled and "
                "vehicle released"
            ),
            "compensation": compensation
        }), 503


    # =====================================
    # STEP 11: PAYMENT FAILED
    # =====================================

    if payment_response.status_code != 201:

        # Payment Service is alive,
        # but payment was unsuccessful.

        # Saga Compensation
        compensation = release_vehicle(
            vehicle_service_url,
            vehicle_id
        )

        conn = get_db_connection()

        conn.execute(
            """
            UPDATE bookings
            SET status = 'CANCELLED'
            WHERE id = ?
            """,
            (booking_id,)
        )

        conn.commit()

        booking = conn.execute(
            "SELECT * FROM bookings WHERE id = ?",
            (booking_id,)
        ).fetchone()

        conn.close()

        return jsonify({
            "message": "Payment failed",
            "booking": dict(booking),
            "compensation": compensation
        }), 402


    # =====================================
    # STEP 12: PAYMENT SUCCESSFUL
    # =====================================

    conn = get_db_connection()

    conn.execute(
        """
        UPDATE bookings
        SET status = 'CONFIRMED'
        WHERE id = ?
        """,
        (booking_id,)
    )

    conn.commit()

    booking = conn.execute(
        "SELECT * FROM bookings WHERE id = ?",
        (booking_id,)
    ).fetchone()

    conn.close()

    return jsonify({
        "message": "Booking created successfully",
        "booking": dict(booking),
        "user": user,
        "vehicle": vehicle,
        "payment": payment_response.json()
    }), 201


# =========================
# START SERVICE
# =========================

if __name__ == "__main__":

    # Initialize database
    init_db()

    # Register service with Service Registry
    register_with_registry()

    # Start Flask service
    app.run(
        host="0.0.0.0",
        port=5003,
        debug=True
    )