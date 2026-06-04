"""Build public callback URLs for this gateway service."""

from typing import Optional

from fastapi import HTTPException

from app.config import settings

VA_CALLBACK_PATH = "/va/callback"


def build_va_callback_url(
    explicit_callback_url: Optional[str] = None,
    virtual_account: Optional[str] = None,
) -> str:
    """
    Resolve callback URL for create VA.

    Priority:
    1. explicit_callback_url from request body
    2. GATEWAY_PUBLIC_URL + /va/callback/{virtual_account} from .env (if virtual_account provided)
    3. GATEWAY_PUBLIC_URL + /va/callback from .env
    """
    if explicit_callback_url and explicit_callback_url.strip():
        return explicit_callback_url.strip()

    base = settings.GATEWAY_PUBLIC_URL
    if not base or not str(base).strip():
        raise HTTPException(
            status_code=400,
            detail=(
                "callback_url is required in request body, or set GATEWAY_PUBLIC_URL in .env "
                "(public URL of this merahputih-transfez service, e.g. http://localhost:8001)"
            ),
        )

    base_url = f"{str(base).rstrip('/')}{VA_CALLBACK_PATH}"
    if virtual_account and str(virtual_account).strip():
        return f"{base_url}/{str(virtual_account).strip()}"
    return base_url
