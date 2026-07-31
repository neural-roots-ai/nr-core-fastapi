-- Promo code / coupon support.
--
-- Additive only - does not touch any Django-owned table. Confirmed against
-- live NRDB (2026-07-31): no coupon/promo/discount/voucher table exists
-- anywhere in the schema, so this is new functionality, not a migration of
-- existing data.
--
-- Design:
--   promo_code            - the coupon definition: percentage or fixed-amount
--                            off, optionally scoped to one program and/or one
--                            currency, with usage limits and a validity window.
--   promo_code_redemption - one row per attempted use, tied 1:1 to a
--                            payment_order. This is what makes redemption
--                            atomic and auditable: usage limits are enforced
--                            by locking the promo_code row (SELECT ... FOR
--                            UPDATE) before counting/inserting, so concurrent
--                            checkouts against a limited-quantity code can't
--                            oversell it. status starts 'reserved' at order
--                            creation, moves to 'confirmed' when the order is
--                            paid, or 'released' (and times_used decremented)
--                            if the order fails - see app/services/promo_service.py.
--
-- Known gap (documented, not fixed here): an order that's simply abandoned
-- (stuck in payment_order.status='created', no failure event ever fires)
-- holds its reservation forever - there's no background sweeper in this
-- service. NRDB already has job_scheduler/job_execution tables from the
-- Django side; a periodic "release stale reservations older than N minutes"
-- job is the natural place to close this gap if/when it matters.

CREATE TABLE IF NOT EXISTS promo_code (
    promo_code_id             BIGSERIAL PRIMARY KEY,
    code                      VARCHAR(32) NOT NULL,        -- always stored/matched uppercase
    description               VARCHAR(255),
    discount_type             VARCHAR(20) NOT NULL,        -- 'PERCENTAGE' | 'FIXED_AMOUNT'
    discount_value            NUMERIC(12, 2) NOT NULL,     -- percentage: 0-100; fixed: amount in currency_code
    currency_code             VARCHAR(3) REFERENCES currency(currency_code),  -- NULL = valid in any currency; required for FIXED_AMOUNT
    max_discount_amount       NUMERIC(12, 2),              -- optional cap, mainly for PERCENTAGE (e.g. 20% off, capped at 100)
    min_order_amount          NUMERIC(12, 2),              -- optional floor on the pre-promo payable amount
    applicable_program_id     INTEGER REFERENCES program(program_id),  -- NULL = valid for any program
    max_redemptions           INTEGER,                     -- NULL = unlimited
    max_redemptions_per_user  INTEGER NOT NULL DEFAULT 1,
    times_used                INTEGER NOT NULL DEFAULT 0,  -- reserved + confirmed count; adjusted atomically
    starts_at                 TIMESTAMPTZ,
    expires_at                TIMESTAMPTZ,
    is_active                 BOOLEAN NOT NULL DEFAULT TRUE,
    created_on                TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_on                TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_promo_code_code UNIQUE (code),
    CONSTRAINT ck_promo_code_discount_type CHECK (discount_type IN ('PERCENTAGE', 'FIXED_AMOUNT')),
    CONSTRAINT ck_promo_code_discount_value_positive CHECK (discount_value > 0),
    CONSTRAINT ck_promo_code_percentage_range CHECK (discount_type <> 'PERCENTAGE' OR discount_value <= 100),
    CONSTRAINT ck_promo_code_fixed_requires_currency CHECK (discount_type <> 'FIXED_AMOUNT' OR currency_code IS NOT NULL),
    -- A max_discount_amount is a number in *some* currency; without
    -- currency_code pinning the promo to one currency, that number would be
    -- silently reused as a cap across USD/INR/GBP amounts, which is wrong
    -- (see app/services/promo_service.py "natively_chargeable" handling).
    CONSTRAINT ck_promo_code_capped_requires_currency CHECK (max_discount_amount IS NULL OR currency_code IS NOT NULL),
    CONSTRAINT ck_promo_code_validity_window CHECK (starts_at IS NULL OR expires_at IS NULL OR starts_at < expires_at)
);

CREATE TABLE IF NOT EXISTS promo_code_redemption (
    id                BIGSERIAL PRIMARY KEY,
    promo_code_id     BIGINT NOT NULL REFERENCES promo_code(promo_code_id),
    user_id           INTEGER NOT NULL REFERENCES auth_user(id),
    payment_order_id  BIGINT NOT NULL UNIQUE REFERENCES payment_order(id),
    discount_amount   NUMERIC(12, 2) NOT NULL,
    currency_code     VARCHAR(3) NOT NULL REFERENCES currency(currency_code),
    status            VARCHAR(20) NOT NULL DEFAULT 'reserved',  -- 'reserved' | 'confirmed' | 'released'
    created_on        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_on        TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_promo_code_redemption_status CHECK (status IN ('reserved', 'confirmed', 'released'))
);

CREATE INDEX IF NOT EXISTS ix_promo_code_redemption_promo_user ON promo_code_redemption (promo_code_id, user_id);
