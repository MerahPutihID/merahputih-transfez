"""Build public callback URLs for this gateway service."""

from typing import Optional

from fastapi import HTTPException

from app.config import settings

VA_CALLBACK_PATH = "/va/callback"


def build_va_callback_url(
    explicit_callback_url: Optional[str] = None,
    partner_trx_id: Optional[str] = None,
) -> str:
    """
    Resolve callback URL for create VA.

    Priority:
    1. explicit_callback_url from request body
    2. GATEWAY_PUBLIC_URL + /va/callback/{partner_trx_id} from .env
    """
    if explicit_callback_url and explicit_callback_url.strip():
        return explicit_callback_url.strip()

    if not partner_trx_id or not str(partner_trx_id).strip():
        raise HTTPException(
            status_code=400,
            detail=(
                "partner_trx_id is required when callback_url is omitted, "
                "or provide callback_url explicitly in request body"
            ),
        )

    base = settings.GATEWAY_PUBLIC_URL
    if not base or not str(base).strip():
        raise HTTPException(
            status_code=400,
            detail=(
                "callback_url is required in request body, or set GATEWAY_PUBLIC_URL in .env "
                "(public URL of this merahputih-transfez service, e.g. http://localhost:8001)"
            ),
        )

    return f"{str(base).rstrip('/')}{VA_CALLBACK_PATH}/{str(partner_trx_id).strip()}"
