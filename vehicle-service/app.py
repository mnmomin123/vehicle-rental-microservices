from flask import Flask, request, jsonify
import sqlite3
import requests

app = Flask(__name__)

DATABASE = "vehicle.db"

# ==============================
# SERVICE REGISTRY CONFIG
# ==============================

REGISTRY_URL = "http://localhost:5005"
SERVICE_NAME = "vehicle-service"
SERVICE_URL = "http://localhost:5002"


# ==============================
# DATABASE
# ==============================

def get_db_connection():
    conn = sqlite3.connect(
        DATABASE,
        timeout=10
    )
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS vehicles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            vehicle_number TEXT UNIQUE NOT NULL,
            vehicle_type TEXT NOT NULL,
            price_per_day REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'AVAILABLE'
        )
    """)

    conn.commit()
    conn.close()


# ==============================
# AUTOMATIC SERVICE REGISTRATION
# ==============================

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

        print("Vehicle Service Registration:", response.json())

    except requests.RequestException as error:
        print("Vehicle Service Registration Failed:", error)


# ==============================
# HEALTH CHECK
# ==============================

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "service": "vehicle-service",
        "status": "UP"
    })


# ==============================
# V1 - GET ALL VEHICLES
# ==============================

@app.route("/api/v1/vehicles", methods=["GET"])
def get_vehicles():

    conn = get_db_connection()

    vehicles = conn.execute(
        "SELECT * FROM vehicles"
    ).fetchall()

    conn.close()

    return jsonify([dict(vehicle) for vehicle in vehicles])


# ==============================
# V1 - GET VEHICLE BY ID
# ==============================

@app.route("/api/v1/vehicles/<int:vehicle_id>", methods=["GET"])
def get_vehicle(vehicle_id):

    conn = get_db_connection()

    vehicle = conn.execute(
        "SELECT * FROM vehicles WHERE id = ?",
        (vehicle_id,)
    ).fetchone()

    conn.close()

    if vehicle is None:
        return jsonify({
            "error": "Vehicle not found"
        }), 404

    return jsonify(dict(vehicle))


# ==============================
# V1 - CREATE VEHICLE
# ==============================

@app.route("/api/v1/vehicles", methods=["POST"])
def create_vehicle():

    data = request.get_json()

    if not data:
        return jsonify({
            "error": "Request body is required"
        }), 400

    required_fields = [
        "name",
        "vehicle_number",
        "vehicle_type",
        "price_per_day"
    ]

    for field in required_fields:
        if field not in data:
            return jsonify({
                "error": f"{field} is required"
            }), 400

    status = data.get("status", "AVAILABLE")

    if status not in ["AVAILABLE", "RESERVED", "MAINTENANCE"]:
        return jsonify({
            "error": "Invalid vehicle status"
        }), 400

    try:

        conn = get_db_connection()

        cursor = conn.execute("""
            INSERT INTO vehicles
            (
                name,
                vehicle_number,
                vehicle_type,
                price_per_day,
                status
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            data["name"],
            data["vehicle_number"],
            data["vehicle_type"],
            data["price_per_day"],
            status
        ))

        conn.commit()

        vehicle_id = cursor.lastrowid

        vehicle = conn.execute(
            "SELECT * FROM vehicles WHERE id = ?",
            (vehicle_id,)
        ).fetchone()

        conn.close()

        return jsonify({
            "message": "Vehicle created successfully",
            "vehicle": dict(vehicle)
        }), 201

    except sqlite3.IntegrityError:

        return jsonify({
            "error": "Vehicle number already exists"
        }), 409


# ==============================
# V1 - UPDATE VEHICLE
# ==============================

@app.route("/api/v1/vehicles/<int:vehicle_id>", methods=["PUT"])
def update_vehicle(vehicle_id):

    data = request.get_json()

    if not data:
        return jsonify({
            "error": "Request body is required"
        }), 400

    conn = get_db_connection()

    vehicle = conn.execute(
        "SELECT * FROM vehicles WHERE id = ?",
        (vehicle_id,)
    ).fetchone()

    if vehicle is None:
        conn.close()

        return jsonify({
            "error": "Vehicle not found"
        }), 404

    name = data.get("name", vehicle["name"])
    vehicle_number = data.get(
        "vehicle_number",
        vehicle["vehicle_number"]
    )
    vehicle_type = data.get(
        "vehicle_type",
        vehicle["vehicle_type"]
    )
    price_per_day = data.get(
        "price_per_day",
        vehicle["price_per_day"]
    )
    status = data.get(
        "status",
        vehicle["status"]
    )

    if status not in ["AVAILABLE", "RESERVED", "MAINTENANCE"]:
        conn.close()

        return jsonify({
            "error": "Invalid vehicle status"
        }), 400

    try:

        conn.execute("""
            UPDATE vehicles
            SET
                name = ?,
                vehicle_number = ?,
                vehicle_type = ?,
                price_per_day = ?,
                status = ?
            WHERE id = ?
        """, (
            name,
            vehicle_number,
            vehicle_type,
            price_per_day,
            status,
            vehicle_id
        ))

        conn.commit()

        updated_vehicle = conn.execute(
            "SELECT * FROM vehicles WHERE id = ?",
            (vehicle_id,)
        ).fetchone()

        conn.close()

        return jsonify({
            "message": "Vehicle updated successfully",
            "vehicle": dict(updated_vehicle)
        })

    except sqlite3.IntegrityError:

        conn.close()

        return jsonify({
            "error": "Vehicle number already exists"
        }), 409


# ==============================
# V1 - DELETE VEHICLE
# ==============================

@app.route("/api/v1/vehicles/<int:vehicle_id>", methods=["DELETE"])
def delete_vehicle(vehicle_id):

    conn = get_db_connection()

    vehicle = conn.execute(
        "SELECT * FROM vehicles WHERE id = ?",
        (vehicle_id,)
    ).fetchone()

    if vehicle is None:
        conn.close()

        return jsonify({
            "error": "Vehicle not found"
        }), 404

    conn.execute(
        "DELETE FROM vehicles WHERE id = ?",
        (vehicle_id,)
    )

    conn.commit()
    conn.close()

    return jsonify({
        "message": "Vehicle deleted successfully"
    })


# ==============================
# RESERVE VEHICLE
# ==============================

@app.route(
    "/api/v1/vehicles/<int:vehicle_id>/reserve",
    methods=["PUT"]
)
def reserve_vehicle(vehicle_id):

    conn = get_db_connection()

    vehicle = conn.execute(
        "SELECT * FROM vehicles WHERE id = ?",
        (vehicle_id,)
    ).fetchone()

    if vehicle is None:
        conn.close()

        return jsonify({
            "error": "Vehicle not found"
        }), 404

    if vehicle["status"] != "AVAILABLE":

        conn.close()

        return jsonify({
            "error": "Vehicle is not available",
            "status": vehicle["status"]
        }), 409

    conn.execute("""
        UPDATE vehicles
        SET status = 'RESERVED'
        WHERE id = ?
    """, (vehicle_id,))

    conn.commit()

    updated_vehicle = conn.execute(
        "SELECT * FROM vehicles WHERE id = ?",
        (vehicle_id,)
    ).fetchone()

    conn.close()

    return jsonify({
        "message": "Vehicle reserved successfully",
        "vehicle": dict(updated_vehicle)
    })


# ==============================
# RELEASE VEHICLE
# ==============================

@app.route(
    "/api/v1/vehicles/<int:vehicle_id>/release",
    methods=["PUT"]
)
def release_vehicle(vehicle_id):

    conn = get_db_connection()

    vehicle = conn.execute(
        "SELECT * FROM vehicles WHERE id = ?",
        (vehicle_id,)
    ).fetchone()

    if vehicle is None:
        conn.close()

        return jsonify({
            "error": "Vehicle not found"
        }), 404

    conn.execute("""
        UPDATE vehicles
        SET status = 'AVAILABLE'
        WHERE id = ?
    """, (vehicle_id,))

    conn.commit()

    updated_vehicle = conn.execute(
        "SELECT * FROM vehicles WHERE id = ?",
        (vehicle_id,)
    ).fetchone()

    conn.close()

    return jsonify({
        "message": "Vehicle released successfully",
        "vehicle": dict(updated_vehicle)
    })


# ==============================
# V2 - GET ALL VEHICLES
# ==============================

@app.route("/api/v2/vehicles", methods=["GET"])
def get_vehicles_v2():

    conn = get_db_connection()

    vehicles = conn.execute(
        "SELECT * FROM vehicles"
    ).fetchall()

    conn.close()

    vehicle_list = []

    for vehicle in vehicles:

        vehicle_data = dict(vehicle)

        # V2 field
        vehicle_data["daily_rate"] = vehicle_data["price_per_day"]

        vehicle_list.append(vehicle_data)

    return jsonify({
        "api_version": "v2",
        "count": len(vehicle_list),
        "vehicles": vehicle_list
    })


# ==============================
# V2 - GET VEHICLE BY ID
# ==============================

@app.route(
    "/api/v2/vehicles/<int:vehicle_id>",
    methods=["GET"]
)
def get_vehicle_v2(vehicle_id):

    conn = get_db_connection()

    vehicle = conn.execute(
        "SELECT * FROM vehicles WHERE id = ?",
        (vehicle_id,)
    ).fetchone()

    conn.close()

    if vehicle is None:

        return jsonify({
            "error": "Vehicle not found"
        }), 404

    vehicle_data = dict(vehicle)

    vehicle_data["daily_rate"] = vehicle_data["price_per_day"]

    return jsonify({
        "api_version": "v2",
        "vehicle": vehicle_data
    })


# ==============================
# V2 - VEHICLE SUMMARY
# ==============================

@app.route(
    "/api/v2/vehicles/<int:vehicle_id>/summary",
    methods=["GET"]
)
def vehicle_summary_v2(vehicle_id):

    conn = get_db_connection()

    vehicle = conn.execute(
        "SELECT * FROM vehicles WHERE id = ?",
        (vehicle_id,)
    ).fetchone()

    conn.close()

    if vehicle is None:

        return jsonify({
            "error": "Vehicle not found"
        }), 404

    vehicle_data = dict(vehicle)

    return jsonify({
        "api_version": "v2",
        "vehicle_id": vehicle_data["id"],
        "vehicle_name": vehicle_data["name"],
        "vehicle_number": vehicle_data["vehicle_number"],
        "type": vehicle_data["vehicle_type"],
        "daily_rate": vehicle_data["price_per_day"],
        "availability": vehicle_data["status"]
    })


# ==============================
# START SERVICE
# ==============================

if __name__ == "__main__":

    init_db()

    # Automatically register with Service Registry
    register_with_registry()

    app.run(
        host="0.0.0.0",
        port=5002,
        debug=True
    )