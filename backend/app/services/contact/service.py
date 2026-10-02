from app.services.contact.models import ContactRequest


class ContactService:
    """
    Handles contact-message processing and delivery.

    The API layer is deliberately kept separate from the delivery
    implementation so the email provider can be changed without
    modifying the HTTP endpoint.
    """

    async def send(self, request: ContactRequest) -> None:
        """
        Deliver a validated contact request.

        Email delivery will be implemented behind this service
        boundary.
        """
        raise NotImplementedError(
            "Contact email delivery has not been configured yet."
        )


contact_service = ContactService()