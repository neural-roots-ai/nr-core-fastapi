import logging

import aiosmtplib
from email.message import EmailMessage

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def _send(to_email: str, subject: str, html_body: str) -> None:
    message = EmailMessage()
    message["From"] = f"{settings.EMAIL_FROM_NAME} <{settings.email_from}>"
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content("This email requires an HTML-capable client.")
    message.add_alternative(html_body, subtype="html")

    try:
        await aiosmtplib.send(
            message,
            hostname=settings.SMTP_SERVER,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USERNAME,
            password=settings.SMTP_PASSWORD,
            use_tls=settings.SMTP_PORT == 465,
            start_tls=settings.SMTP_PORT == 587,
        )
    except Exception:
        # Do not let a flaky SMTP relay take down signup/login flows.
        # The OTP row still exists and resend-otp lets the user retry.
        logger.exception("Failed to send email to %s", to_email)


async def send_otp_email(to_email: str, otp: str, purpose: str) -> None:
    if purpose == "signup_verify":
        subject = "Verify your email"
        heading = "Verify your email address"
        body_line = "Use the code below to verify your email and activate your account."
    else:
        subject = "Reset your password"
        heading = "Reset your password"
        body_line = "Use the code below to reset your password."

    html_body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 480px; margin: auto;">
      <h2>{heading}</h2>
      <p>{body_line}</p>
      <p style="font-size: 32px; font-weight: bold; letter-spacing: 4px;">{otp}</p>
      <p>This code expires in {settings.OTP_EXPIRE_MINUTES} minutes. If you did not request this, you can ignore this email.</p>
    </div>
    """
    await _send(to_email, subject, html_body)


async def send_payment_confirmation_email(to_email: str, program_name: str, amount: str, currency: str) -> None:
    html_body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 480px; margin: auto;">
      <h2>Payment received</h2>
      <p>We've received your payment of {currency} {amount} for <strong>{program_name}</strong>.</p>
      <p>You're enrolled! We'll be in touch with next steps.</p>
    </div>
    """
    await _send(to_email, f"Payment confirmed - {program_name}", html_body)
