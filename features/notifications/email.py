"""Email notification delivery service.

Implements standard SMTP email sending with credentials from environment variables.
Falls back to writing email files locally in mock mode if unconfigured.
"""

import os
import smtplib
from email.message import EmailMessage
from features.shared.observability import BackendObservability


async def send_email(
    to_email: str,
    subject: str,
    html_content: str,
    text_content: str,
) -> bool:
    """Sends an email using standard SMTP.

    If SMTP_SERVER, SMTP_PORT, SMTP_USERNAME, and SMTP_PASSWORD environment
    variables are not set, falls back to mock mode and writes email files
    locally under .antigravity_app_data/emails/.
    """
    server = os.environ.get("SMTP_SERVER")
    port_str = os.environ.get("SMTP_PORT")
    username = os.environ.get("SMTP_USERNAME")
    password = os.environ.get("SMTP_PASSWORD")

    # Check if SMTP configuration is fully provided
    is_configured = all([server, port_str, username, password])

    if not is_configured:
        # Fall back to local mock file output
        BackendObservability.warning(
            "SMTP credentials not fully configured. Falling back to local email mock mode."
        )
        try:
            emails_dir = os.path.abspath("./.antigravity_app_data/emails")
            os.makedirs(emails_dir, exist_ok=True)

            # Use timestamp to make filename unique
            import time
            timestamp = int(time.time())

            # Save HTML version
            html_path = os.path.join(emails_dir, f"email_{timestamp}.html")
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html_content)

            # Save Text version
            text_path = os.path.join(emails_dir, f"email_{timestamp}.txt")
            with open(text_path, "w", encoding="utf-8") as f:
                f.write(f"Subject: {subject}\nTo: {to_email}\n\n{text_content}")

            BackendObservability.info(
                f"Mock email written to files locally under: {emails_dir}",
                html_file=html_path,
                text_file=text_path,
            )
            return True
        except Exception as exc:
            BackendObservability.error(
                "Failed to write mock email locally.", exception=exc
            )
            return False

    # Standard SMTP flow
    try:
        port = int(port_str)
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = username
        msg["To"] = to_email

        # Set plain text version
        msg.set_content(text_content)

        # Set HTML version
        msg.add_alternative(html_content, subtype="html")

        # Establish SMTP connection
        # Check port to decide between SMTP_SSL or starttls
        if port == 465:
            with smtplib.SMTP_SSL(server, port) as smtp:
                smtp.login(username, password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(server, port) as smtp:
                smtp.starttls()
                smtp.login(username, password)
                smtp.send_message(msg)

        BackendObservability.info(
            f"Successfully sent summary email to {to_email} via SMTP.",
            server=server,
            port=port,
        )
        return True
    except Exception as exc:
        BackendObservability.error(
            f"Failed to send email via SMTP to {to_email}.",
            exception=exc,
            server=server,
            port=port_str,
        )
        return False
