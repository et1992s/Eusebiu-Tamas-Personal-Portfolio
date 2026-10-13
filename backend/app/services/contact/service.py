
import asyncio
import logging
import os
from pathlib import Path

import resend
from dotenv import load_dotenv
from fastapi import HTTPException

from app.services.contact.models import ContactRequest


logger = logging.getLogger(__name__)

# Resolve backend/.env independently of the process working directory.
BACKEND_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(dotenv_path=BACKEND_ENV_PATH, override=False)


class ContactService:
    """Validate configuration and deliver portfolio enquiries through Resend."""

    async def send(self, request: ContactRequest) -> None:
        api_key = os.getenv("RESEND_API_KEY")
        to_email = os.getenv("CONTACT_TO_EMAIL")
        from_email = os.getenv("CONTACT_FROM_EMAIL")

        missing = [
            name
            for name, value in (
                ("RESEND_API_KEY", api_key),
                ("CONTACT_TO_EMAIL", to_email),
                ("CONTACT_FROM_EMAIL", from_email),
            )
            if not value or not value.strip()
        ]

        if missing:
            logger.error(
                "Contact email configuration is missing: %s",
                ", ".join(missing),
            )
            raise HTTPException(
                status_code=503,
                detail="The contact service is not configured. Please try again later.",
            )

        resend.api_key = api_key

        text_body = (
            "New portfolio contact message\n"
            "\n"
            f"Name: {request.name}\n"
            f"Email: {request.email}\n"
            f"Subject: {request.subject}\n"
            "\n"
            "Message:\n"
            f"{request.message}\n"
        )

        params = {
            "from": from_email,
            "to": [to_email],
            "reply_to": str(request.email),
            "subject": f"Portfolio enquiry: {request.subject}",
            "text": text_body,
        }

        try:
            # Resend's SDK call is synchronous; keep it off the event loop.
            await asyncio.to_thread(resend.Emails.send, params)
        except Exception:
            logger.exception("Resend failed to deliver a portfolio contact message")
            raise HTTPException(
                status_code=502,
                detail="We could not send your message right now. Please try again later.",
            ) from None


contact_service = ContactService()
