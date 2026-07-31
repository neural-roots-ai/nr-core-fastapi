"""Resolves a visitor's country from the incoming request, with no required
external dependency or per-request network call.

Priority order (first hit wins):
  1. Edge/CDN-injected country header (Cloudflare `cf-ipcountry` and
     equivalents) - free, zero extra latency, what most production
     deployments behind a CDN already get for every request.
  2. A local MaxMind GeoLite2-Country database, if `GEOIP_DB_PATH` is
     configured and the optional `geoip2` package is installed. Local file
     lookup - no outbound HTTP call in the request path.
  3. `Accept-Language` region subtag (e.g. `en-GB` -> `GB`) - weak signal,
     last resort before giving up.

Returns None (never raises) when no signal is available; callers fall back
to `settings.DEFAULT_CURRENCY`. Detection is inherently approximate (VPNs,
corporate proxies, missing headers) - this is why currency_service always
allows an explicit override on top of whatever this resolves.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from fastapi import Request

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

try:
    import geoip2.database
    import geoip2.errors
except ImportError:  # optional dependency - see requirements.txt
    geoip2 = None  # type: ignore[assignment]


@lru_cache
def _geoip_reader():
    if geoip2 is None or not settings.GEOIP_DB_PATH:
        return None
    try:
        return geoip2.database.Reader(settings.GEOIP_DB_PATH)
    except OSError:
        logger.warning("GEOIP_DB_PATH=%s could not be opened; GeoIP lookups disabled.", settings.GEOIP_DB_PATH)
        return None


def _get_client_ip(request: Request) -> str | None:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


def _from_cdn_header(request: Request) -> str | None:
    if not settings.TRUST_CDN_COUNTRY_HEADER:
        return None
    value = request.headers.get(settings.CDN_COUNTRY_HEADER_NAME)
    if not value or value.upper() in {"XX", "T1"}:  # Cloudflare's "unknown"/Tor sentinels
        return None
    return value.upper()


def _from_geoip_db(request: Request) -> str | None:
    reader = _geoip_reader()
    if reader is None:
        return None
    ip = _get_client_ip(request)
    if not ip:
        return None
    try:
        return reader.country(ip).country.iso_code
    except (geoip2.errors.AddressNotFoundError, ValueError):
        return None


def _from_accept_language(request: Request) -> str | None:
    header = request.headers.get("accept-language")
    if not header:
        return None
    primary_tag = header.split(",")[0].strip()
    if "-" in primary_tag:
        region = primary_tag.split("-", 1)[1].strip()
        if len(region) == 2 and region.isalpha():
            return region.upper()
    return None


def resolve_country_code(request: Request) -> str | None:
    """Best-effort ISO 3166-1 alpha-2 country code for this request, or None."""
    for resolver in (_from_cdn_header, _from_geoip_db, _from_accept_language):
        code = resolver(request)
        if code:
            return code
    return None
