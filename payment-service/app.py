from flask import Flask, request, jsonify
import sqlite3
from datetime import datetime

app = Flask(__name__)

DATABASE = "payment.db"


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
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


# =========================
# HEALTH CHECK
# =========================

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "service": "payment-service",
        "status": "UP"
    })


# =========================
# PROCESS MOCK PAYMENT
# =========================

@app.route("/api/v1/payments", methods=["POST"])
def process_payment():

    data = request.get_json()

    if not data:
        return jsonify({
            "error": "Request body is required"
        }), 400

    booking_id = data.get("booking_id")
    user_id = data.get("user_id")
    amount = data.get("amount")
    payment_status = data.get("payment_status")

    if (
        booking_id is None
        or user_id is None
        or amount is None
        or not payment_status
    ):
        return jsonify({
            "error": "booking_id, user_id, amount and payment_status are required"
        }), 400

    payment_status = payment_status.upper()

    if payment_status not in ["SUCCESS", "FAILED"]:
        return jsonify({
            "error": "payment_status must be SUCCESS or FAILED"
        }), 400

    created_at = datetime.now().isoformat()

    conn = get_db_connection()

    cursor = conn.execute(
        """
        INSERT INTO payments
        (booking_id, user_id, amount, status, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            booking_id,
            user_id,
            amount,
            payment_status,
            created_at
        )
    )

    conn.commit()

    payment_id = cursor.lastrowid

    payment = conn.execute(
        "SELECT * FROM payments WHERE id = ?",
        (payment_id,)
    ).fetchone()

    conn.close()

    if payment_status == "FAILED":
        return jsonify({
            "message": "Mock payment failed",
            "payment": dict(payment)
        }), 402

    return jsonify({
        "message": "Mock payment successful",
        "payment": dict(payment)
    }), 201


# =========================
# GET ALL PAYMENTS
# =========================

@app.route("/api/v1/payments", methods=["GET"])
def get_payments():

    conn = get_db_connection()

    payments = conn.execute(
        "SELECT * FROM payments ORDER BY id DESC"
    ).fetchall()

    conn.close()

    return jsonify([
        dict(payment) for payment in payments
    ])


# =========================
# GET PAYMENT BY ID
# =========================

@app.route("/api/v1/payments/<int:payment_id>", methods=["GET"])
def get_payment(payment_id):

    conn = get_db_connection()

    payment = conn.execute(
        "SELECT * FROM payments WHERE id = ?",
        (payment_id,)
    ).fetchone()

    conn.close()

    if payment is None:
        return jsonify({
            "error": "Payment not found"
        }), 404

    return jsonify(dict(payment))


# =========================
# START SERVICE
# =========================

if __name__ == "__main__":
    init_db()

    app.run(
        host="0.0.0.0",
        port=5004,
        debug=True
    )