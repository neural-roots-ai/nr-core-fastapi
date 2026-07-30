from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class CreateOrderRequest(BaseModel):
    program_id: int
    country_id: int


class CreateOrderResponse(BaseModel):
    order_id: int
    razorpay_order_id: str
    razorpay_key_id: str
    amount: Decimal
    amount_subunits: int
    currency: str
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
    country_id: int
    base_amount: Decimal
    amount: Decimal
    discount_amount: Decimal
    currency: str
