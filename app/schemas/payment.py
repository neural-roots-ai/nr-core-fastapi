from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class CreateOrderRequest(BaseModel):
    program_id: int
    # Both optional: if omitted, the buyer's currency is resolved the same
    # way as the /fee lookup (explicit currency > country_id > cookie > geo >
    # DEFAULT_CURRENCY). Pass whichever the frontend already has on hand -
    # ideally the same values the preceding /fee call resolved, so the price
    # the buyer saw is exactly the price they're charged.
    country_id: int | None = None
    currency: str | None = None
    # Ideally the same code the preceding /fee?promo_code= call already
    # validated, so the discount the buyer saw is exactly what's applied.
    promo_code: str | None = None


class CreateOrderResponse(BaseModel):
    order_id: int
    razorpay_order_id: str
    razorpay_key_id: str
    # What Razorpay actually charges/settles (currently always INR - see
    # settings.SETTLEMENT_CURRENCY).
    amount: Decimal
    amount_subunits: int
    currency: str
    # What the buyer was shown before checkout - equal to amount/currency
    # unless settlement forced a conversion (e.g. a GBP-priced program
    # charged in INR). The frontend should surface both whenever they differ.
    display_amount: Decimal
    display_currency: str
    promo_code: str | None
    promo_discount_amount: Decimal | None
    program_name: str
    receipt: str


class VerifyPaymentRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class VerifyPaymentResponse(BaseModel):
    status: str
    enrollment_status: str
    message: str


class OrderStatusResponse(BaseModel):
    status: str
    amount: Decimal
    currency: str
    program_name: str


class EnrollmentOut(BaseModel):
    program_id: int
    program_name: str
    status: str
    enrolled_on: datetime | None

    model_config = {"from_attributes": True}


class ProgramFeeOut(BaseModel):
    program_id: int
    program_name: str
    country_id: int | None
    base_amount: Decimal
    amount: Decimal
    discount_amount: Decimal
    currency: str
    currency_symbol: str
    # How `currency` was decided: "override" (explicit ?currency=), "country_id"
    # (explicit ?country_id=, legacy), "cookie" (remembered past choice), "geo"
    # (IP/CDN detected), or "default" (DEFAULT_CURRENCY, nothing else resolved).
    currency_source: str
    # True when the currency was detected rather than explicitly chosen -
    # frontend should show a "prices shown in GBP for your region [change]"
    # affordance rather than presenting it as a firm user decision.
    is_estimated: bool
    # Populated only when a `promo_code` query param was passed. A bad/
    # expired/inapplicable code doesn't fail the request - promo_valid=False
    # with promo_message explaining why, so the price lookup still succeeds.
    promo_code: str | None = None
    promo_valid: bool | None = None
    promo_message: str | None = None
    promo_discount_amount: Decimal | None = None
    # Final amount after both the catalog discount (`discount_amount` above)
    # and the promo code, if any. Equal to `amount` when no promo was applied.
    payable_amount: Decimal


class CurrencyOut(BaseModel):
    currency_code: str
    currency_name: str
    symbol: str
    decimal_digits: int


class DetectedRegionOut(BaseModel):
    currency: str
    currency_symbol: str
    country_id: int | None
    currency_source: str
    is_estimated: bool
    supported_currencies: list[CurrencyOut]
