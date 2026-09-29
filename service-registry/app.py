from flask import Flask, request, jsonify

app = Flask(__name__)

# =========================
# SERVICE REGISTRY
# =========================

services = {}


# =========================
# HEALTH CHECK
# =========================

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "service": "service-registry",
        "status": "UP"
    })


# =========================
# REGISTER SERVICE
# =========================

@app.route("/register", methods=["POST"])
def register_service():
    data = request.get_json()

    if not data:
        return jsonify({
            "error": "Request body is required"
        }), 400

    service_name = data.get("service_name")
    service_url = data.get("service_url")

    if not service_name or not service_url:
        return jsonify({
            "error": "service_name and service_url are required"
        }), 400

    services[service_name] = service_url

    return jsonify({
        "message": "Service registered successfully",
        "service_name": service_name,
        "service_url": service_url
    }), 201


# =========================
# GET SERVICE URL
# =========================

@app.route("/services/<service_name>", methods=["GET"])
def get_service(service_name):

    if service_name not in services:
        return jsonify({
            "error": "Service not found"
        }), 404

    return jsonify({
        "service_name": service_name,
        "service_url": services[service_name]
    })


# =========================
# GET ALL SERVICES
# =========================

@app.route("/services", methods=["GET"])
def get_services():
    return jsonify(services)


# =========================
# START SERVICE
# =========================

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5005,
        debug=True
    )