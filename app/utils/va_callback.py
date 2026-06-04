"""Parse Transfez VA callback payloads (flat vs payment-with-va_data shapes)."""

from typing import Any, Dict, Optional


def _coerce_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_va_callback_payload(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize EXPIRED/STATIC_TRX_EXPIRED (flat) and COMPLETE/PAYMENT_DETECTED (nested) payloads.
    """
    if "va_data" in body and isinstance(body.get("va_data"), dict):
        va = body["va_data"]
        return {
            "payload_shape": "payment",
            "transfez_id": body.get("id") or va.get("id"),
            "va_number_id": body.get("va_number_id"),
            "va_status": va.get("va_status"),
            "va_number": va.get("va_number"),
            "partner_trx_id": va.get("partner_trx_id"),
            "bank_code": va.get("bank_code"),
            "amount": _coerce_float(body.get("amount") if body.get("amount") is not None else va.get("amount")),
            "amount_detected": _coerce_float(va.get("amount_detected")),
            "success": body.get("success"),
            "tx_date": body.get("tx_date"),
        }

    return {
        "payload_shape": "flat",
        "transfez_id": body.get("id"),
        "va_number_id": None,
        "va_status": body.get("va_status"),
        "va_number": body.get("va_number"),
        "partner_trx_id": body.get("partner_trx_id"),
        "bank_code": body.get("bank_code"),
        "amount": _coerce_float(body.get("amount")),
        "amount_detected": _coerce_float(body.get("amount_detected")),
        "success": body.get("success"),
        "tx_date": body.get("tx_date"),
    }
