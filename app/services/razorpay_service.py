"""Thin async wrapper around the (synchronous) official razorpay SDK.

Razorpay's Python SDK is a blocking `requests`-based client. To avoid
blocking the event loop, every call is dispatched to FastAPI/Starlette's
worker thread pool via `run_in_threadpool`.
"""

from __future__ import annotations

import logging
from typing import Any

import razorpay
from razorpay.errors import SignatureVerificationError
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.core.exceptions import PaymentGatewayError

logger = logging.getLogger(__name__)
settings = get_settings()

_client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


async def create_order(*, amount_subunits: int, currency: str, receipt: str, notes: dict[str, Any]) -> dict[str, Any]:
    try:
        return await run_in_threadpool(
            _client.order.create,
            {
                "amount": amount_subunits,
                "currency": currency,
                "receipt": receipt,
                "notes": notes,
                "payment_capture": 1,  # auto-capture on successful authorization
            },
        )
    except Exception as exc:  # razorpay.errors.BadRequestError, connection errors, etc.
        logger.exception("Razorpay order creation failed")
        raise PaymentGatewayError("Could not create payment order. Please try again.") from exc


def verify_payment_signature(*, razorpay_order_id: str, razorpay_payment_id: str, razorpay_signature: str) -> bool:
    try:
        _client.utility.verify_payment_signature(
            {
                "razorpay_order_id": razorpay_order_id,
                "razorpay_payment_id": razorpay_payment_id,
                "razorpay_signature": razorpay_signature,
            }
        )
        return True
    except SignatureVerificationError:
        return False


def verify_webhook_signature(*, raw_body: bytes, signature: str) -> bool:
    try:
        _client.utility.verify_webhook_signature(
            raw_body.decode("utf-8"), signature, settings.RAZORPAY_WEBHOOK_SECRET
        )
        return True
    except SignatureVerificationError:
        return False


async def fetch_payment(razorpay_payment_id: str) -> dict[str, Any]:
    try:
        return await run_in_threadpool(_client.payment.fetch, razorpay_payment_id)
    except Exception as exc:
        logger.exception("Razorpay payment fetch failed for %s", razorpay_payment_id)
        raise PaymentGatewayError("Could not verify payment with Razorpay.") from exc
