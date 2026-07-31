"""Resolves which currency to price/display a request in, and caches the
rarely-changing currency/country_currency_map tables in-process.

Resolution order (first hit wins) - explicit choices always beat detection:
  1. `currency` explicitly passed by the caller (query param / request body).
  2. `country_id` explicitly passed (legacy clients that already select a
     country, e.g. the original country_id-based /programs/{id}/fee callers).
  3. `preferred_currency` cookie from a previous explicit choice.
  4. IP/CDN/Accept-Language geo detection (see geo_service).
  5. settings.DEFAULT_CURRENCY (USD), with no resolved country.

Every step is validated against the `currency`/`country_currency_map` tables
so a bad/unsupported override can never silently produce an uncharged order -
it falls through to the next step in the chain instead.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Literal

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.pricing import CountryCurrencyMap, Currency
from app.services import geo_service

settings = get_settings()

ResolutionSource = Literal["override", "country_id", "cookie", "geo", "default"]

PREFERRED_CURRENCY_COOKIE = "preferred_currency"


@dataclass(frozen=True)
class ResolvedCurrency:
    currency_code: str
    country_id: int | None
    source: ResolutionSource
    is_estimated: bool  # True when detected, not explicitly chosen by the user


class _CurrencyMapCache:
    """Tiny in-process TTL cache - this data changes on ops timescales
    (adding a market), not per-request, so a DB round trip per price lookup
    would be pure waste."""

    def __init__(self) -> None:
        self._active_codes: set[str] | None = None
        self._by_country_code: dict[str, tuple[str, int | None]] | None = None
        self._by_country_id: dict[int, str] | None = None
        self._loaded_at: float = 0.0

    def _is_fresh(self) -> bool:
        return (time.monotonic() - self._loaded_at) < settings.CURRENCY_MAP_CACHE_TTL_SECONDS

    async def _ensure_loaded(self, db: AsyncSession) -> None:
        if self._active_codes is not None and self._is_fresh():
            return

        currency_rows = (await db.execute(select(Currency.currency_code).where(Currency.is_active.is_(True)))).scalars().all()
        map_rows = (await db.execute(select(CountryCurrencyMap))).scalars().all()

        self._active_codes = set(currency_rows)
        self._by_country_code = {row.country_code: (row.currency_code, row.country_id) for row in map_rows}
        self._by_country_id = {row.country_id: row.currency_code for row in map_rows if row.country_id is not None}
        self._loaded_at = time.monotonic()

    async def is_supported(self, db: AsyncSession, currency_code: str) -> bool:
        await self._ensure_loaded(db)
        assert self._active_codes is not None
        return currency_code.upper() in self._active_codes

    async def for_country_code(self, db: AsyncSession, country_code: str) -> tuple[str, int | None] | None:
        await self._ensure_loaded(db)
        assert self._by_country_code is not None
        return self._by_country_code.get(country_code.upper())

    async def for_country_id(self, db: AsyncSession, country_id: int) -> str | None:
        await self._ensure_loaded(db)
        assert self._by_country_id is not None
        return self._by_country_id.get(country_id)


_cache = _CurrencyMapCache()


async def get_active_currencies(db: AsyncSession) -> list[Currency]:
    return list((await db.execute(select(Currency).where(Currency.is_active.is_(True)).order_by(Currency.currency_code))).scalars().all())


async def get_currency(db: AsyncSession, currency_code: str) -> Currency | None:
    return await db.get(Currency, currency_code.upper())


async def resolve(
    db: AsyncSession,
    request: Request,
    *,
    currency_override: str | None = None,
    country_id_override: int | None = None,
    cookie_currency: str | None = None,
) -> ResolvedCurrency:
    if currency_override and await _cache.is_supported(db, currency_override):
        return ResolvedCurrency(currency_override.upper(), country_id_override, "override", is_estimated=False)

    if country_id_override is not None:
        mapped_code = await _cache.for_country_id(db, country_id_override)
        if mapped_code:
            return ResolvedCurrency(mapped_code, country_id_override, "country_id", is_estimated=False)

    if cookie_currency and await _cache.is_supported(db, cookie_currency):
        return ResolvedCurrency(cookie_currency.upper(), None, "cookie", is_estimated=False)

    country_code = geo_service.resolve_country_code(request)
    if country_code:
        mapping = await _cache.for_country_code(db, country_code)
        if mapping:
            currency_code, country_id = mapping
            return ResolvedCurrency(currency_code, country_id, "geo", is_estimated=True)

    return ResolvedCurrency(settings.DEFAULT_CURRENCY, None, "default", is_estimated=True)
