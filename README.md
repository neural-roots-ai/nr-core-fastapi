# nr-auth-fastapi

Authentication + Razorpay payment/enrollment microservice for the Neural Roots edtech platform.

- **Auth** reuses Django's existing `auth_user` table in `NRDB` (this service never runs DDL against it — only Django migrates that table).
- **Payments** go through Razorpay's standard Checkout, which natively supports cards, UPI (incl. QR/scan-to-pay), netbanking, wallets, EMI and international cards in one integration — no per-method backend code needed.

## 1. One-time setup: run the SQL scripts

This service needs 7 new tables that don't exist in NRDB yet. Nothing here touches `auth_user` or any other Django-owned table — everything is additive, in `sql/`, guarded with `IF NOT EXISTS`, safe to re-run:

```bash
psql -h 147.93.102.99 -p 5430 -U neural_roots_stage -d NRDB -f sql/001_auth_support_tables.sql
psql -h 147.93.102.99 -p 5430 -U neural_roots_stage -d NRDB -f sql/002_payment_tables.sql
```

- `001_auth_support_tables.sql` → `auth_user_profile` (email-verified flag, phone, lockout counters — kept separate from `auth_user` so Django's own migrations never conflict with this service), `refresh_token`, `email_otp`, `login_audit`.
- `002_payment_tables.sql` → `payment_order`, `payment_transaction`, `course_enrollment`.

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
| GET | `/programs/{id}/fee?country_id=` | Public price lookup |
| POST | `/orders` | Auth required, creates Razorpay order |
| POST | `/orders/verify` | Client-side signature verification after Checkout |
| GET | `/orders/{id}` | Poll order status |
| GET | `/enrollments/me` | Auth required |
| POST | `/webhook` | Razorpay → server, signature-verified, no auth |

All errors return `{"error": {"code": "...", "message": "..."}}`.

## 6. Known data-quality note

`program_fee.program_fee` is stored as `varchar`, and `program_fee.discount` is a **flat amount in the same currency**, not a percentage (confirmed against live data — e.g. fee `7000`, discount `6500` → payable `500`). The service parses/validates this defensively; if you'd rather store these as proper `NUMERIC` columns, that's a Django-side migration, not something this service should alter.

## 7. What's intentionally not built

- Multi-currency by country: there's no currency column on `country`/`program_fee`, so every order uses `DEFAULT_CURRENCY` (INR). Add a `currency_code` column if you need real per-country pricing currencies.
- Redis-backed rate limiting: current limiter is in-memory (`slowapi`), fine for one instance — point it at Redis if you scale to multiple replicas.
