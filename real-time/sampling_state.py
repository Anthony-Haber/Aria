"""Thread-safe sampling hyperparameter state with bounded adjustments."""

import threading


class SamplingState:
    """Holds temperature, top_p, min_p with thread-safe getters/setters."""

    def __init__(self, temperature: float, top_p: float, min_p: float | None):
        self._lock = threading.Lock()
        self.temperature = temperature
        self.top_p = top_p
        self.min_p = 0.0 if min_p is None else min_p

    # --- helpers ---
    def _clamp(self, val, lo, hi):
        return max(lo, min(hi, val))

    def increase_temperature(self):
        with self._lock:
            self.temperature = self._clamp(self.temperature + 0.05, 0.1, 2.0)
            return self.temperature

    def decrease_temperature(self):
        with self._lock:
            self.temperature = self._clamp(self.temperature - 0.05, 0.1, 2.0)
            return self.temperature

    def increase_top_p(self):
        with self._lock:
            self.top_p = self._clamp(self.top_p + 0.01, 0.1, 1.0)
            return self.top_p

    def decrease_top_p(self):
        with self._lock:
            self.top_p = self._clamp(self.top_p - 0.01, 0.1, 1.0)
            return self.top_p

    def increase_min_p(self):
        with self._lock:
            self.min_p = self._clamp(self.min_p + 0.01, 0.0, 0.2)
            return self.min_p

    def decrease_min_p(self):
        with self._lock:
            self.min_p = self._clamp(self.min_p - 0.01, 0.0, 0.2)
            return self.min_p

    def get_values(self):
        with self._lock:
            return self.temperature, self.top_p, self.min_p


class SessionState:
    """Thread-safe session status and last output path."""

    def __init__(self, mode: str = "manual"):
        self._lock = threading.Lock()
        self.status = "IDLE"
        self.mode = mode
        self.last_output_path = None

    def set_status(self, status: str):
        with self._lock:
            self.status = status

    def set_last_output(self, path: str | None):
        with self._lock:
            self.last_output_path = path

    def get_snapshot(self):
        with self._lock:
            return {"mode": self.mode, "status": self.status, "last_output_path": self.last_output_path}
