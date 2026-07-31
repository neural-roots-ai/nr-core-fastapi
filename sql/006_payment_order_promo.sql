-- payment_order is owned by this service - safe to ALTER directly (see
-- 004_payment_order_display_currency.sql for the same reasoning).
--
-- Denormalized promo summary for receipts/order history, same pattern as
-- display_amount/display_currency: promo_code_redemption is the source of
-- truth for enforcement (usage limits, per-user caps, reserved/confirmed/
-- released status), this is just a convenient snapshot on the order itself
-- so listing/receipt endpoints don't need an extra join.

ALTER TABLE payment_order
    ADD COLUMN IF NOT EXISTS promo_code_id        BIGINT REFERENCES promo_code(promo_code_id),
    ADD COLUMN IF NOT EXISTS promo_discount_amount NUMERIC(12, 2);
