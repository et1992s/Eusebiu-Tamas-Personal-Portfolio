from fastapi import APIRouter

from app.services.contact.models import ContactRequest
from app.services.contact.service import contact_service


router = APIRouter(
    prefix="/api/v1/contact",
    tags=["Contact"],
)


@router.post("")
async def submit_contact(request: ContactRequest):
    """
    Receive, validate, and process a portfolio contact request.
    """

    await contact_service.send(request)

    return {
        "success": True,
        "message": "Contact request received.",
    }