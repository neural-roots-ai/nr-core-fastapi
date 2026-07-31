# nr-auth-fastapi

Authentication + Razorpay payment/enrollment microservice for the Neural Roots edtech platform.

- **Auth** reuses Django's existing `auth_user` table in `NRDB` (this service never runs DDL against it — only Django migrates that table).
- **Payments** go through Razorpay's standard Checkout, which natively supports cards, UPI (incl. QR/scan-to-pay), netbanking, wallets, EMI and international cards in one integration — no per-method backend code needed.

## 1. One-time setup: run the SQL scripts

This service needs several new tables that don't exist in NRDB yet. Nothing here touches `auth_user` or any other Django-owned table — everything is additive, in `sql/`, guarded with `IF NOT EXISTS`, safe to re-run:

```bash
psql -h 147.93.102.99 -p 5430 -U neural_roots_stage -d NRDB -f sql/001_auth_support_tables.sql
psql -h 147.93.102.99 -p 5430 -U neural_roots_stage -d NRDB -f sql/002_payment_tables.sql
psql -h 147.93.102.99 -p 5430 -U neural_roots_stage -d NRDB -f sql/003_currency_pricing.sql
psql -h 147.93.102.99 -p 5430 -U neural_roots_stage -d NRDB -f sql/004_payment_order_display_currency.sql
psql -h 147.93.102.99 -p 5430 -U neural_roots_stage -d NRDB -f sql/005_promo_codes.sql
psql -h 147.93.102.99 -p 5430 -U neural_roots_stage -d NRDB -f sql/006_payment_order_promo.sql
psql -h 147.93.102.99 -p 5430 -U neural_roots_stage -d NRDB -f sql/007_backfill_inr_program_price.sql
```

- `001_auth_support_tables.sql` → `auth_user_profile` (email-verified flag, phone, lockout counters — kept separate from `auth_user` so Django's own migrations never conflict with this service), `refresh_token`, `email_otp`, `login_audit`.
- `002_payment_tables.sql` → `payment_order`, `payment_transaction`, `course_enrollment`.
- `003_currency_pricing.sql` → `currency`, `country_currency_map`, `program_price` (see §7, regional pricing).
- `004_payment_order_display_currency.sql` → alters `payment_order` for display-vs-settlement currency (also §7).
- `005_promo_codes.sql` → `promo_code`, `promo_code_redemption` (see §8, promo codes).
- `006_payment_order_promo.sql` → alters `payment_order` with a denormalized promo summary (also §8).
- `007_backfill_inr_program_price.sql` → **not optional**, run it right after `003`. Backfills `program_price(currency_code='INR')` from each program's existing India `program_fee` row. Without this, `create_order`'s INR settlement fallback (§7) 404s for any buyer whose currency was resolved without a `country_id` — i.e. most of them — found via end-to-end testing, see §7 for why.

**Until these are run, `/auth/signup` and everything under `/payments` will return a `503 database_error`** (verified locally — the app connects to NRDB fine and fails cleanly on the missing tables rather than crashing).

Note: any account that already exists in `auth_user` (e.g. a Django superuser created via `createsuperuser`) will need `is_email_verified` manually set once the profile table exists:
```sql
INSERT INTO auth_user_profile (user_id, is_email_verified)
SELECT id, true FROM auth_user WHERE is_superuser = true
ON CONFLICT (user_id) DO UPDATE SET is_email_verified = true;
```

## 2. Configuration

Copy `.env.example` → `.env` (a `.env` with your provided DB/SMTP/JWT values is already in place, gitignored). You still need to fill in:

```
RAZORPAY_KEY_ID=...
RAZORPAY_KEY_SECRET=...
RAZORPAY_WEBHOOK_SECRET=...
```

Get the key pair from the [Razorpay dashboard](https://dashboard.razorpay.com/app/keys) (start in **test mode**). The webhook secret is set when you register the webhook (step 5).

**Security note:** the DB password, SMTP password, and JWT `SECRET_KEY` were shared in plaintext in chat during this build. Recommend rotating the DB and SMTP passwords once this is deployed, since they're now sitting in a chat transcript. `.env` is gitignored — never commit it.

`DJANGO_SECRET_KEY` from your original list isn't used anywhere in this service — it's Django's own session/CSRF secret. This service issues its own JWTs signed with `SECRET_KEY`, and doesn't decode Django sessions.

## 3. Run it

Local (Python 3.11 or 3.12 — 3.14 doesn't yet have prebuilt wheels for `asyncpg`/`pydantic-core`):
```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Docker (production-shaped, gunicorn + uvicorn workers):
```bash
docker compose up --build
```

- `GET /healthz` — liveness check
- `GET /docs` — Swagger UI (disabled automatically when `ENVIRONMENT=production`)

## 4. The enroll → pay flow you asked for

This is a stateless JWT API — the frontend, not this service, decides whether to show a login modal:

1. User clicks **Enroll**.
2. Frontend checks for a stored access token. If present, call `GET /api/v1/auth/me`:
   - `200` → user is logged in → skip straight to step 4.
   - `401` → show login/signup modal.
3. After login/signup succeeds, store `access_token` + `refresh_token` from the response.
4. `GET /api/v1/payments/programs/{program_id}/fee?country_id=...` to show the price (server-computed from `program_fee`, discount included).
5. `POST /api/v1/payments/orders` with `{program_id, country_id}` (Bearer token) → returns `razorpay_order_id`, `amount`, `razorpay_key_id`.
6. Open Razorpay Checkout client-side with those values — the same modal shows card / UPI / QR / netbanking / wallet / EMI / international-card tabs automatically; nothing method-specific to build.
7. On Checkout success, call `POST /api/v1/payments/orders/verify` with the `razorpay_order_id`/`razorpay_payment_id`/`razorpay_signature` Checkout gives you. This confirms enrollment.
8. Independently, register `/api/v1/payments/webhook` in the Razorpay dashboard for `payment.captured` / `payment.failed` — this is the source of truth if the user closes the tab right after paying (e.g. UPI) before step 7 fires. Both paths are idempotent (guarded by a unique constraint on the Razorpay payment id), so whichever arrives first wins and the other is a no-op.

Access tokens expire in 15 minutes; use `POST /api/v1/auth/refresh` with the refresh token to get a new pair (refresh tokens rotate on every use, with reuse-detection that revokes the whole session family if an already-used token is replayed).

## 5. API reference

### Auth (`/api/v1/auth`)
| Method | Path | Notes |
|---|---|---|
| POST | `/signup` | Creates `auth_user` row (Django-compatible `pbkdf2_sha256` hash), emails a 6-digit OTP |
| POST | `/verify-email` | `{email, otp}` — required before login |
| POST | `/resend-otp` | `{email, purpose}`, 60s cooldown |
| POST | `/login` | `{identifier, password}` — username or email. Locks account for 15 min after 5 bad attempts |
| POST | `/refresh` | Rotates refresh token |
| POST | `/logout` | Revokes one refresh token |
| POST | `/logout-all` | Revokes all sessions (auth required) |
| POST | `/forgot-password` | Always returns generic success (no user enumeration) |
| POST | `/reset-password` | `{email, otp, new_password}`, revokes all sessions |
| POST | `/change-password` | Auth required, revokes all sessions |
| GET | `/me` | Current user — use this to decide "already logged in" |

### Payments (`/api/v1/payments`)
| Method | Path | Notes |
|---|---|---|
| GET | `/currency?currency=` | Detected/overridden region + currency, plus the full supported-currency list — call on page load for a currency switcher |
| GET | `/programs/{id}/fee?country_id=&currency=&promo_code=` | Public price lookup, all params optional; `promo_code` is a non-binding preview (invalid/expired just sets `promo_valid=false`, doesn't fail the request) |
| POST | `/orders` | Auth required, creates Razorpay order; body may include `promo_code` to redeem it for real |
| POST | `/orders/verify` | Client-side signature verification after Checkout |
| GET | `/orders/{id}` | Poll order status |
| GET | `/enrollments/me` | Auth required |
| POST | `/webhook` | Razorpay → server, signature-verified, no auth |

All errors return `{"error": {"code": "...", "message": "..."}}`.

## 6. Known data-quality note

`program_fee.program_fee` is stored as `varchar`, and `program_fee.discount` is a **flat amount in the same currency**, not a percentage (confirmed against live data — e.g. fee `7000`, discount `6500` → payable `500`). The service parses/validates this defensively; if you'd rather store these as proper `NUMERIC` columns, that's a Django-side migration, not something this service should alter.

## 7. Regional pricing (multi-currency)

A visitor's currency is resolved server-side, cheapest signal first, and every step is overridable:

1. Explicit `?currency=` (or `country_id=`, legacy) on the request.
2. The `preferred_currency` cookie from a previous explicit choice (180 days).
3. IP/CDN geo detection (`app/services/geo_service.py`): trusts an edge-injected country header first (`cf-ipcountry` behind Cloudflare, configurable via `CDN_COUNTRY_HEADER_NAME`/`TRUST_CDN_COUNTRY_HEADER`) — no outbound call, no added latency. Falls back to a local MaxMind `GeoLite2-Country.mmdb` if `GEOIP_DB_PATH` is set and `geoip2` is installed (both optional), then to the `Accept-Language` header, then gives up.
4. `DEFAULT_CURRENCY` (USD) if nothing resolved.

`GET /payments/currency` exposes this resolution (plus the supported-currency list) for a frontend currency switcher; `GET /payments/programs/{id}/fee` and `POST /payments/orders` use the same chain so the price shown and the price charged always agree, and `currency_source`/`is_estimated` on the response tell the frontend whether to present it as detected ("Prices shown in GBP for your region") vs. explicitly chosen.

**Pricing data**: `program_price` (new, `sql/003_currency_pricing.sql`) is a currency-keyed price list — one admin-managed row per `(program_id, currency_code)`, e.g. a fixed $499 / £399 / S$649, not a live FX conversion (conversions drift and produce ugly non-psychological prices; re-run the seed periodically instead as FX moves). The legacy country-keyed `program_fee` is still consulted as a fallback for `(program, country)` pairs that haven't been backfilled into `program_price` yet.

**`program_price(INR)` is mandatory, not optional**: `create_order`'s settlement fallback (next paragraph) looks up `program_price(INR)` by `program_id` alone — it only falls back further to the country-keyed `program_fee` table if a `country_id` happens to be available, which most checkouts won't have (currency is usually resolved by geo/cookie/explicit override, not a country selector). `sql/007_backfill_inr_program_price.sql` seeds this from each program's existing India `program_fee` row; without it, non-INR-display orders 404 instead of falling back to INR settlement.

**Charging**: Razorpay settles this merchant account in INR only (see §1's note on Razorpay Checkout) — `RAZORPAY_CHARGE_CURRENCIES` lists what it can actually charge (`INR` by default). If the resolved display currency isn't in that list, `create_order` re-prices the program in `SETTLEMENT_CURRENCY` (INR) for the real Razorpay order, while `payment_order.display_amount`/`display_currency` keep what the buyer was shown — surface both in the checkout UI ("You'll be charged ₹41,500 (≈ £399)") rather than silently switching currency at the last step. When a real multi-currency Razorpay approval is in place, add those currencies to `RAZORPAY_CHARGE_CURRENCIES` and they'll be charged natively with no code change.

**Adding a new market**: insert `currency` + `country_currency_map` rows (see the seed in `003_currency_pricing.sql` for the pattern), then add a `program_price` row per program in that currency. Nothing auto-generates prices — that's deliberate.

## 8. Promo codes

Confirmed against live NRDB (2026-07-31): no coupon/promo/discount/voucher table existed anywhere in the schema before this, so this is new functionality (`sql/005_promo_codes.sql`, `sql/006_payment_order_promo.sql`), not a migration of existing data. `program_fee`/`program_price` were **not** redesigned for this — a promo is a separate, stackable discount applied on top of whatever catalog price (`program_fee` or `program_price`) already resolved, not a change to how that catalog price itself is stored.

**Schema**: `promo_code` — one row per coupon: `PERCENTAGE` or `FIXED_AMOUNT`, optionally scoped to one `applicable_program_id` and/or one `currency_code`, an optional `min_order_amount` floor and `max_discount_amount` cap, a validity window (`starts_at`/`expires_at`), and both a global (`max_redemptions`) and per-user (`max_redemptions_per_user`, default 1) usage limit. `promo_code_redemption` — one row per attempted use, 1:1 with a `payment_order`, `status` moving `reserved` → `confirmed`/`released`.

**Currency safety**: a currency-scoped promo (`currency_code` set — always true for `FIXED_AMOUNT`, optionally true for a capped `PERCENTAGE`) can only be redeemed when the buyer is actually being charged in that exact currency. Since this Razorpay account still only settles in INR (§7), that means today a currency-scoped promo effectively only works for INR buyers — reapplying e.g. "£20 off" to an INR settlement amount would silently mismatch units, so it's rejected with a clear message instead. A currency-agnostic `PERCENTAGE` promo (no cap, no `currency_code`) has no such restriction — the ratio survives being applied to whichever currency the order actually settles in.

**Atomicity**: redemption (`app/services/promo_service.redeem`) locks the `promo_code` row (`SELECT ... FOR UPDATE`) before counting existing uses and incrementing `times_used`, and runs inside the exact same DB transaction as the `payment_order` insert (`payment_service.create_order`) — both commit together or neither does, so concurrent checkouts against a limited-quantity code can't oversell it. `GET /programs/{id}/fee?promo_code=` is a separate, lock-free preview path (`promo_service.quote`) used purely for "show the discounted price before checkout" — it never reserves a slot.

**Known gap**: an order that's simply abandoned (stuck in `payment_order.status='created'`, no failure event ever fires) holds its promo reservation forever — there's no background sweeper in this service to release it. NRDB already has Django's `job_scheduler`/`job_execution` tables; a periodic "release stale reservations older than N minutes" job is the natural place to close this if abandoned-cart volume on promo'd programs ever makes it worth building.

## 9. Also known

- Redis-backed rate limiting: current limiter is in-memory (`slowapi`), fine for one instance — point it at Redis if you scale to multiple replicas.
