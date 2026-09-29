from flask import Flask, request, Response, jsonify
import requests

app = Flask(__name__)

REGISTRY_URL = "http://localhost:5005"


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

        return response.json().get("service_url")

    except requests.RequestException:
        return None


# =========================
# HEALTH CHECK
# =========================

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "service": "API Gateway",
        "status": "UP"
    })


# =========================
# GATEWAY ROUTER
# =========================

SERVICE_MAP = {
    "users": "user-service",
    "vehicles": "vehicle-service",
    "bookings": "booking-service",
    "payments": "payment-service"
}


# Handles:
# /api/v1/users
# /api/v1/vehicles
# /api/v1/bookings
# /api/v1/payments

@app.route("/api/v1/<service>", methods=["GET", "POST", "PUT", "DELETE"])
def gateway_root(service):

    return forward_request(service, "")


# Handles:
# /api/v1/users/1
# /api/v1/vehicles/1
# /api/v1/bookings/1
# /api/v1/bookings/circuit-breaker
# etc.

@app.route(
    "/api/v1/<service>/<path:path>",
    methods=["GET", "POST", "PUT", "DELETE"]
)
def gateway_path(service, path):

    return forward_request(service, path)


# =========================
# FORWARD REQUEST
# =========================

def forward_request(service, path):

    if service not in SERVICE_MAP:
        return jsonify({
            "error": "Unknown service",
            "service": service
        }), 404

    service_name = SERVICE_MAP[service]

    # Discover service through Registry
    service_url = get_service_url(service_name)

    if not service_url:
        return jsonify({
            "error": "Service unavailable",
            "service": service_name
        }), 503

    # Build target URL
    target_url = f"{service_url}/api/v1/{service}"

    if path:
        target_url += f"/{path}"

    # Forward useful headers
    headers = {}

    for key, value in request.headers:
        if key.lower() not in ["host", "content-length"]:
            headers[key] = value

    try:

        response = requests.request(
            method=request.method,
            url=target_url,
            headers=headers,
            params=request.args,
            data=request.get_data(),
            timeout=20
        )

        # Return service response to client
        return Response(
            response.content,
            status=response.status_code,
            content_type=response.headers.get(
                "Content-Type",
                "application/json"
            )
        )

    except requests.RequestException as error:

        return jsonify({
            "error": "Unable to communicate with service",
            "service": service_name,
            "details": str(error)
        }), 503


# =========================
# API V2 GATEWAY
# =========================

@app.route(
    "/api/v2/<service>",
    methods=["GET", "POST", "PUT", "DELETE"]
)
def gateway_v2_root(service):

    return forward_v2_request(service, "")


@app.route(
    "/api/v2/<service>/<path:path>",
    methods=["GET", "POST", "PUT", "DELETE"]
)
def gateway_v2_path(service, path):

    return forward_v2_request(service, path)


def forward_v2_request(service, path):

    if service != "vehicles":
        return jsonify({
            "error": "V2 is currently available only for Vehicle Service"
        }), 404

    service_name = "vehicle-service"

    service_url = get_service_url(service_name)

    if not service_url:
        return jsonify({
            "error": "Service unavailable",
            "service": service_name
        }), 503

    target_url = f"{service_url}/api/v2/{service}"

    if path:
        target_url += f"/{path}"

    headers = {}

    for key, value in request.headers:
        if key.lower() not in ["host", "content-length"]:
            headers[key] = value

    try:

        response = requests.request(
            method=request.method,
            url=target_url,
            headers=headers,
            params=request.args,
            data=request.get_data(),
            timeout=20
        )

        return Response(
            response.content,
            status=response.status_code,
            content_type=response.headers.get(
                "Content-Type",
                "application/json"
            )
        )

    except requests.RequestException as error:

        return jsonify({
            "error": "Unable to communicate with service",
            "service": service_name,
            "details": str(error)
        }), 503

# =========================
# START SERVER
# =========================

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )