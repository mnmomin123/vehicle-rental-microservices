import time


class CircuitBreaker:

    def __init__(self, failure_threshold=3, recovery_timeout=10):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout

        self.failure_count = 0
        self.state = "CLOSED"
        self.last_failure_time = None

    # =========================
    # CHECK CIRCUIT STATE
    # =========================

    def can_execute(self):

        # CLOSED = normal operation
        if self.state == "CLOSED":
            return True

        # OPEN = check whether recovery timeout has passed
        if self.state == "OPEN":

            if self.last_failure_time is None:
                return False

            elapsed_time = time.time() - self.last_failure_time

            if elapsed_time >= self.recovery_timeout:
                self.state = "HALF-OPEN"

                print("Circuit Breaker: OPEN -> HALF-OPEN")

                return True

            return False

        # HALF-OPEN = allow one test request
        if self.state == "HALF-OPEN":
            return True

        return False

    # =========================
    # RECORD SUCCESS
    # =========================

    def record_success(self):

        self.failure_count = 0
        self.state = "CLOSED"
        self.last_failure_time = None

        print("Circuit Breaker: -> CLOSED")

    # =========================
    # RECORD FAILURE
    # =========================

    def record_failure(self):

        self.failure_count += 1
        self.last_failure_time = time.time()

        print(
            f"Circuit Breaker failure count: "
            f"{self.failure_count}"
        )

        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"

            print("Circuit Breaker: CLOSED -> OPEN")

    # =========================
    # GET STATUS
    # =========================

    def get_status(self):

        return {
            "state": self.state,
            "failure_count": self.failure_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout
        }