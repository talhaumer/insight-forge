import time
from typing import Callable, Any, Dict


def retry_with_backoff(
    func: Callable, max_retries: int = 3, base_delay: float = 1.0
) -> Any:
    """Retry function with exponential backoff"""
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            delay = base_delay * (2**attempt)
            time.sleep(delay)
    return None


def circuit_breaker(failures: int, threshold: int = 3) -> bool:
    """Simple circuit breaker pattern"""
    return failures >= threshold


def create_fallback_response(query: str, error: str) -> Dict[str, Any]:
    """Create fallback response when all else fails"""
    return {
        "topic": query,
        "summary": f"Unable to complete research for '{query}'. Error: {error}",
        "references": [],
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "facts": [],
        "error": error,
    }
