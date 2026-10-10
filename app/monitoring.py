
import json
import logging
import time
from datetime import datetime, timezone
from threading import Lock
from typing import Any


class JSONFormatter(logging.Formatter):
    """Format log records as JSON."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
        }

        # Include custom structured data passed through extra={}
        extra_data = getattr(record, "extra_data", None)
        if isinstance(extra_data, dict):
            log_obj.update(extra_data)

        # Include exception information when available
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj, ensure_ascii=False, default=str)


def get_logger(name: str = "production-api") -> logging.Logger:
    """Create a structured JSON logger."""
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)

    logger.setLevel(logging.INFO)
    logger.propagate = False

    return logger


class MetricsCollector:
    """
    Collect application metrics in memory.

    For multi-worker production deployments, consider Prometheus.
    """

    def __init__(self) -> None:
        
        self._requests_total = 0
        self._errors_total = 0

        self._latency_sum = 0.0
        self._latency_count = 0

        self._tokens_input = 0
        self._tokens_output = 0

        self._cache_hits = 0
        self._cache_misses = 0

        self._lock = Lock()

    def record_request(
        self,
        latency_ms: float,
        input_tokens: int = 0,
        output_tokens: int = 0,
        error: bool = False,
        cache_hit: bool = False,
    ) -> None:
        """Record metrics for one completed request."""

        if latency_ms < 0:
            raise ValueError("latency_ms must be >= 0")

        if input_tokens < 0 or output_tokens < 0:
            raise ValueError("Token counts must be >= 0")

        with self._lock:
            self._requests_total += 1
            self._latency_sum += latency_ms
            self._latency_count += 1

            self._tokens_input += input_tokens
            self._tokens_output += output_tokens

            if error:
                self._errors_total += 1

            if cache_hit:
                self._cache_hits += 1
            else:
                self._cache_misses += 1

    @property
    def stats(self) -> dict[str, Any]:
        """Return a snapshot of current metrics."""

        with self._lock:
            requests = self._requests_total
            errors = self._errors_total
            latency_count = self._latency_count
            latency_sum = self._latency_sum
            hits = self._cache_hits
            misses = self._cache_misses

            total_cache_requests = hits + misses

            return {
                "total_requests": requests,
                "total_errors": errors,
                "error_rate": (
                    errors / requests if requests else 0.0
                ),
                "avg_latency_ms": (
                    latency_sum / latency_count
                    if latency_count else 0.0
                ),
                "latency_total_ms": latency_sum,
                "total_input_tokens": self._tokens_input,
                "total_output_tokens": self._tokens_output,
                "tokens_total": (
                    self._tokens_input + self._tokens_output
                ),
                "cache_hits": hits,
                "cache_misses": misses,
                "cache_hit_rate": (
                    hits / total_cache_requests
                    if total_cache_requests else 0.0
                ),
            }
        
class RequestTimer:
    def __enter__(self):
        self.start = time.time()
        return self
    def __exit__(self,*args):
        self.elapsed_ms = (time.time() - self.start)* 1000
        
        