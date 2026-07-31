-- Regional/multi-currency pricing support.
--
-- Additive only - does not touch any Django-owned table (country, program,
-- program_fee, ...). Safe to re-run (IF NOT EXISTS / ON CONFLICT guards).
--
-- Design:
--   currency              - ISO 4217 codes this service knows how to price/display in.
--   country_currency_map  - keyed by ISO 3166-1 alpha-2 country_code (what IP/CDN geo
--                            detection actually produces, see app/services/geo_service.py),
--                            with an optional bridge to the Django-owned `country.country_id`
--                            for backward compatibility with the legacy country_id-based
--                            program_fee lookups.
--   program_price         - the actual admin-managed regional price list: one row per
--                            (program_id, currency_code), independent of country.
--                            This replaces per-country program_fee as the source of
--                            truth for NEW pricing; program_fee is kept as-is for the
--                            legacy INR flow and as a fallback while this table is
--                            being backfilled (see payment_service.get_program_fee_details).
--
-- Prices here are admin-set fixed amounts per currency (e.g. $499 / £399 / S$649),
-- not live FX conversions - this avoids showing customers a price that moves every
-- time an FX rate ticks, and lets marketing set clean psychological price points.
-- Re-run periodically (e.g. quarterly) as FX rates drift.

CREATE TABLE IF NOT EXISTS currency (
    currency_code   VARCHAR(3) PRIMARY KEY,          -- ISO 4217, e.g. 'USD', 'INR', 'GBP'
    currency_name   VARCHAR(50) NOT NULL,
    symbol          VARCHAR(10) NOT NULL,
    decimal_digits  SMALLINT NOT NULL DEFAULT 2,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_on      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_on      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS country_currency_map (
    country_code    VARCHAR(2) PRIMARY KEY,          -- ISO 3166-1 alpha-2, e.g. 'GB', 'IN', 'SG'
    currency_code   VARCHAR(3) NOT NULL REFERENCES currency(currency_code),
    country_id      INTEGER UNIQUE REFERENCES country(country_id),  -- legacy program_fee bridge, nullable
    created_on      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_on      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS program_price (
    program_price_id  BIGSERIAL PRIMARY KEY,
    program_id        INTEGER NOT NULL REFERENCES program(program_id),
    currency_code     VARCHAR(3) NOT NULL REFERENCES currency(currency_code),
    base_amount       NUMERIC(12, 2) NOT NULL,
    discount_amount   NUMERIC(12, 2) NOT NULL DEFAULT 0,
    is_active         BOOLEAN NOT NULL DEFAULT TRUE,
    created_on        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_on        TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_program_price_program_currency UNIQUE (program_id, currency_code)
);

CREATE INDEX IF NOT EXISTS ix_program_price_program_id ON program_price (program_id);

-- --- Seed: currencies this service prices in day one. Extend as new
-- --- markets are added (each new currency also needs program_price rows
-- --- per program, entered by ops/admin - there is no auto-conversion).
INSERT INTO currency (currency_code, currency_name, symbol, decimal_digits) VALUES
    ('USD', 'US Dollar',        '$',  2),
    ('INR', 'Indian Rupee',     'Rs.',2),
    ('GBP', 'British Pound',    'GBP',2),
    ('EUR', 'Euro',             'EUR',2),
    ('SGD', 'Singapore Dollar', 'S$', 2),
    ('AUD', 'Australian Dollar','A$', 2),
    ('CAD', 'Canadian Dollar',  'C$', 2),
    ('AED', 'UAE Dirham',       'AED',2)
ON CONFLICT (currency_code) DO NOTHING;

-- --- Seed: ISO country_code -> currency, the primary key IP/CDN geo
-- --- detection resolves against. Extend this list as new markets launch.
INSERT INTO country_currency_map (country_code, currency_code) VALUES
    ('US', 'USD'),
    ('IN', 'INR'),
    ('GB', 'GBP'),
    ('SG', 'SGD'),
    ('AU', 'AUD'),
    ('CA', 'CAD'),
    ('AE', 'AED'),
    ('DE', 'EUR'),
    ('FR', 'EUR'),
    ('ES', 'EUR'),
    ('IT', 'EUR'),
    ('NL', 'EUR'),
    ('IE', 'EUR')
ON CONFLICT (country_code) DO UPDATE SET currency_code = EXCLUDED.currency_code, updated_on = now();

-- --- Bridge: fill in country_id where the Django-owned `country` table
-- --- already has a matching row by name, so legacy country_id-based
-- --- program_fee lookups (get_program_fee_details fallback) still resolve
-- --- a currency without duplicating this mapping. Safe to re-run; rows for
-- --- country names not present in `country` are simply left NULL.
UPDATE country_currency_map ccm
SET country_id = c.country_id, updated_on = now()
FROM country c
JOIN (VALUES
    ('United States', 'US'),
    ('India', 'IN'),
    ('United Kingdom', 'GB'),
    ('Singapore', 'SG'),
    ('Australia', 'AU'),
    ('Canada', 'CA'),
    ('United Arab Emirates', 'AE'),
    ('Germany', 'DE'),
    ('France', 'FR'),
    ('Spain', 'ES'),
    ('Italy', 'IT'),
    ('Netherlands', 'NL'),
    ('Ireland', 'IE')
) AS m(country_name, country_code) ON m.country_name = c.country
WHERE ccm.country_code = m.country_code;
