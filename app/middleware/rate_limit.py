"""Per-IP rate limiting for sensitive endpoints (login, signup, OTP, ...).

Uses slowapi's in-memory storage, which is adequate for a single
instance. If this service is ever scaled to multiple replicas, point
slowapi at Redis (storage_uri="redis://...") so limits are shared
across instances instead of being tracked per-process.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
