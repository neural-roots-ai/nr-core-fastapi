-- payment_order is owned by this service (created by 002_payment_tables.sql),
-- so unlike the catalog tables it's safe to ALTER directly.
--
-- 1. display_amount/display_currency: Razorpay settles this merchant account
--    in INR only (see README - no multi-currency Razorpay approval yet).
--    `amount`/`currency` stay exactly what's actually charged/settled
--    through Razorpay. These record what was *shown* to the buyer before
--    checkout (e.g. GBP), so the frontend can render "You'll be charged
--    Rs.41,500 (~ GBP 399)" instead of silently switching currency between
--    the price page and the Razorpay checkout modal. Equal to amount+currency
--    whenever display == settlement (e.g. a buyer already priced in INR).
--
-- 2. country_id/program_fee_id become nullable, and program_price_id is
--    added: orders priced via the new region-agnostic program_price table
--    (see 003_currency_pricing.sql) may have no country_id at all (a
--    currency was resolved straight from geo/cookie, no country lookup)
--    and no legacy program_fee row to point at.

ALTER TABLE payment_order
    ADD COLUMN IF NOT EXISTS display_amount    NUMERIC(12, 2),
    ADD COLUMN IF NOT EXISTS display_currency  VARCHAR(10),
    ADD COLUMN IF NOT EXISTS program_price_id  BIGINT REFERENCES program_price(program_price_id),
    ALTER COLUMN country_id DROP NOT NULL,
    ALTER COLUMN program_fee_id DROP NOT NULL;

-- Backfill existing rows so display_* is never NULL for historical orders.
UPDATE payment_order
SET display_amount = amount, display_currency = currency
WHERE display_amount IS NULL;

ALTER TABLE payment_order
    ALTER COLUMN display_amount SET NOT NULL,
    ALTER COLUMN display_currency SET NOT NULL;
