import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logger
from settings import SMTP_SERVER, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD
# Database configuration (adjust as needed)

SMTP_SERVER = "smtpout.secureserver.net"  
SMTP_PORT = 465  # For TLS
SMTP_USERNAME = "info@neuralroots.in"  # Your email address
SMTP_PASSWORD = "Prateek@97"  # Your email password or app password (recommended)

@logger.trace_execution
def send_email(client_information, email_content):
    status = False
    """Sends an email."""
    message = MIMEMultipart()
    message["From"] = SMTP_USERNAME
    message["To"] = client_information.email_address
    message["Subject"] = email_content.subject

    message.attach(MIMEText(email_content.content, "plain"))
    with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.sendmail(SMTP_USERNAME, email_to, message.as_string())
        status = True
    return status