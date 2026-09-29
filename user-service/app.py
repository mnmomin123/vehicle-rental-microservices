from flask import Flask, request, jsonify
import sqlite3
import requests

app = Flask(__name__)

DATABASE = "user.db"

REGISTRY_URL = "http://localhost:5005"
SERVICE_NAME = "user-service"
SERVICE_URL = "http://localhost:5001"


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
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            phone TEXT NOT NULL
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

        print("User Service Registration:", response.json())

    except requests.RequestException as error:
        print("User Service Registration Failed:", error)


# =========================
# HEALTH CHECK
# =========================

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "service": "user-service",
        "status": "UP"
    })


# =========================
# GET ALL USERS
# =========================

@app.route("/api/v1/users", methods=["GET"])
def get_users():
    conn = get_db_connection()

    users = conn.execute(
        "SELECT * FROM users"
    ).fetchall()

    conn.close()

    return jsonify([
        dict(user) for user in users
    ])


# =========================
# GET USER BY ID
# =========================

@app.route("/api/v1/users/<int:user_id>", methods=["GET"])
def get_user(user_id):
    conn = get_db_connection()

    user = conn.execute(
        "SELECT * FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()

    conn.close()

    if user is None:
        return jsonify({
            "error": "User not found"
        }), 404

    return jsonify(dict(user))


# =========================
# CREATE USER
# =========================

@app.route("/api/v1/users", methods=["POST"])
def create_user():
    data = request.get_json()

    if not data:
        return jsonify({
            "error": "Request body is required"
        }), 400

    name = data.get("name")
    email = data.get("email")
    phone = data.get("phone")

    if not name or not email or not phone:
        return jsonify({
            "error": "name, email and phone are required"
        }), 400

    conn = get_db_connection()

    try:
        cursor = conn.execute(
            """
            INSERT INTO users (name, email, phone)
            VALUES (?, ?, ?)
            """,
            (name, email, phone)
        )

        conn.commit()

        user_id = cursor.lastrowid

        user = conn.execute(
            "SELECT * FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()

        return jsonify(dict(user)), 201

    except sqlite3.IntegrityError:
        return jsonify({
            "error": "Email already exists"
        }), 409

    finally:
        conn.close()


# =========================
# UPDATE USER
# =========================

@app.route("/api/v1/users/<int:user_id>", methods=["PUT"])
def update_user(user_id):
    data = request.get_json()

    if not data:
        return jsonify({
            "error": "Request body is required"
        }), 400

    name = data.get("name")
    email = data.get("email")
    phone = data.get("phone")

    if not name or not email or not phone:
        return jsonify({
            "error": "name, email and phone are required"
        }), 400

    conn = get_db_connection()

    existing_user = conn.execute(
        "SELECT * FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()

    if existing_user is None:
        conn.close()

        return jsonify({
            "error": "User not found"
        }), 404

    try:
        conn.execute(
            """
            UPDATE users
            SET name = ?, email = ?, phone = ?
            WHERE id = ?
            """,
            (name, email, phone, user_id)
        )

        conn.commit()

        user = conn.execute(
            "SELECT * FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()

        return jsonify(dict(user))

    except sqlite3.IntegrityError:
        return jsonify({
            "error": "Email already exists"
        }), 409

    finally:
        conn.close()


# =========================
# DELETE USER
# =========================

@app.route("/api/v1/users/<int:user_id>", methods=["DELETE"])
def delete_user(user_id):
    conn = get_db_connection()

    existing_user = conn.execute(
        "SELECT * FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()

    if existing_user is None:
        conn.close()

        return jsonify({
            "error": "User not found"
        }), 404

    conn.execute(
        "DELETE FROM users WHERE id = ?",
        (user_id,)
    )

    conn.commit()
    conn.close()

    return jsonify({
        "message": "User deleted successfully"
    })


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
        port=5001,
        debug=True
    )


# =========================
# API SUMMARY
# =========================

# GET     /api/v1/users
# POST    /api/v1/users
# GET     /api/v1/users/1
# PUT     /api/v1/users/1
# DELETE  /api/v1/users/1