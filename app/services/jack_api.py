"""Jack API client — bank account validation."""

import json
import logging
from typing import Any, Dict

import requests

from app.config import settings

logger = logging.getLogger(__name__)

INQUIRY_ENDPOINT = "/api/v1/validation_bank_account"


def validate_bank_account(bank_name: str, account_number: str) -> Dict[str, Any]:
    """
    Call Jack GET /api/v1/validation_bank_account?bank_name=...&account_number=...

    Uses JACK_API_BASE_URL + INQUIRY_ENDPOINT, authorized via JACK_API_KEY.

    Returns normalized dict:
      success → {"status": "success", "account_name": str, "raw": dict}
      failed  → {"status": "failed", "error_code": str, "error_response": str, "raw": dict}
    """
    url = f"{settings.JACK_API_BASE_URL.rstrip('/')}{INQUIRY_ENDPOINT}"
    params = {"bank_name": bank_name, "account_number": account_number}
    headers = {
        "Authorization": settings.JACK_API_KEY,
        "Content-Type": "application/json",
    }

    try:
        logger.info(
            "Jack inquiry: GET %s?bank_name=%s&account_number=%s",
            url,
            bank_name,
            account_number,
        )
        resp = requests.get(url, params=params, headers=headers, timeout=30)
        data = resp.json()
    except requests.RequestException as e:
        logger.error("Jack API request failed: %s", e)
        return {"status": "failed", "error_code": "HTTP_ERROR", "error_response": str(e), "raw": None}
    except json.JSONDecodeError:
        logger.error("Jack API non-JSON response (status %s): %s", resp.status_code, resp.text[:500])
        return {"status": "failed", "error_code": str(resp.status_code), "error_response": resp.text[:500], "raw": None}

    if resp.ok and data.get("data") and data["data"].get("account_name"):
        account_name = data["data"]["account_name"]
        logger.info("Jack inquiry success: account_name=%s", account_name)
        return {"status": "success", "account_name": account_name, "raw": data}

    # Extract error details
    error_code = str(resp.status_code)
    error_response = json.dumps(data.get("message") or data, ensure_ascii=False)
    if data.get("message") and isinstance(data["message"], dict) and "errors" in data["message"]:
        error_response = json.dumps(data["message"]["errors"], ensure_ascii=False)
    logger.warning("Jack inquiry failed (status %s): %s", resp.status_code, error_response[:300])
    return {"status": "failed", "error_code": error_code, "error_response": error_response[:500], "raw": data}
