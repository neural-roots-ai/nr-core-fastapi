-- Backfills program_price(currency_code='INR') from the existing India row
-- in the legacy program_fee table, one row per program.
--
-- Why this migration exists (found via end-to-end testing, not optional):
-- payment_service.create_order's settlement fallback re-prices in
-- SETTLEMENT_CURRENCY (INR) whenever the buyer's display currency can't be
-- charged directly by Razorpay. That re-pricing looks up program_price(INR)
-- first, falling back to the country-keyed program_fee ONLY if a country_id
-- is available. In practice, most buyers reach checkout with a currency
-- resolved by geo/cookie/explicit override and NO country_id at all - so
-- without an INR row in program_price, every non-natively-chargeable order
-- (i.e. nearly all of them, since RAZORPAY_CHARGE_CURRENCIES is INR-only by
-- default) fails with a 404 "no active price configured for INR", even
-- though an India price clearly exists in program_fee.
--
-- This is a one-time, additive, re-runnable backfill (ON CONFLICT DO
-- NOTHING - never overwrites a program_price(INR) row someone already set
-- deliberately). Run it immediately after 003_currency_pricing.sql; new
-- programs added after this point need their INR program_price row created
-- directly (see README §7 "Adding a new market").

INSERT INTO program_price (program_id, currency_code, base_amount, discount_amount, is_active)
SELECT
    pf.program_id,
    'INR',
    NULLIF(regexp_replace(pf.program_fee, '[^0-9.]', '', 'g'), '')::NUMERIC(12, 2),
    COALESCE(pf.discount, 0)::NUMERIC(12, 2),
    true
FROM program_fee pf
JOIN country c ON c.country_id = pf.country_id
JOIN program p ON p.program_id = pf.program_id
WHERE c.country = 'India'
  AND pf.is_active = true
  AND p.is_active = true
  AND NULLIF(regexp_replace(pf.program_fee, '[^0-9.]', '', 'g'), '') IS NOT NULL
ON CONFLICT (program_id, currency_code) DO NOTHING;
