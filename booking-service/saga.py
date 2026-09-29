import requests


# =========================
# SAGA COMPENSATION
# =========================

def release_vehicle(vehicle_service_url, vehicle_id):
    """
    Compensation action for the Saga.

    If payment fails after the vehicle has been reserved,
    release the vehicle so that it becomes AVAILABLE again.
    """

    try:
        response = requests.put(
            f"{vehicle_service_url}/api/v1/vehicles/{vehicle_id}/release",
            timeout=3
        )

        if response.status_code == 200:
            return {
                "success": True,
                "message": "Vehicle released successfully",
                "vehicle": response.json().get("vehicle")
            }

        return {
            "success": False,
            "message": "Vehicle release failed"
        }

    except requests.RequestException as error:
        return {
            "success": False,
            "message": "Could not communicate with Vehicle Service",
            "error": str(error)
        }