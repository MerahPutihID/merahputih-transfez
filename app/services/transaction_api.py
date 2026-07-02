import requests
import logging
from http.client import HTTPConnection
import json
from app.config import settings
from app.schemas import TransactionResponse
from typing import Optional, Dict, Any, Union
from pydantic import ValidationError


# Set up detailed HTTP request logging
HTTPConnection.debuglevel = 1
logging.basicConfig(    
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)
# Set up logging for HTTP requests
logging.getLogger("urllib3").setLevel(logging.DEBUG)
logging.getLogger("requests").setLevel(logging.DEBUG)
logging.getLogger("http.client").setLevel(logging.DEBUG)
# Enable HTTP debugging if specified in settings
if settings.HTTP_DEBUG:
    logging.getLogger("http.client").setLevel(logging.DEBUG)
# Set up logging for the application
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)

# Create a custom logger for HTTP debugging
http_logger = logging.getLogger("http.client")
http_logger.setLevel(logging.DEBUG)

def log_request_details(method: str, url: str, headers: dict, payload: dict = None):
    """Log HTTP request details"""
    logging.debug(f"\n{'='*50}\nRequest Details:\n{'='*50}")
    logging.debug(f"Method: {method}")
    logging.debug(f"URL: {url}")
    logging.debug(f"Headers: {json.dumps(headers, indent=2)}")
    if payload:
        logging.debug(f"Payload: {json.dumps(payload, indent=2)}")

def log_response_details(response: requests.Response):
    """Log HTTP response details"""
    logging.debug(f"\n{'='*50}\nResponse Details:\n{'='*50}")
    logging.debug(f"Status Code: {response.status_code}")
    logging.debug(f"Headers: {json.dumps(dict(response.headers), indent=2)}")
    try:
        logging.debug(f"Body: {json.dumps(response.json(), indent=2)}")
    except:
        logging.debug(f"Body: {response.text}")

def confirm_transaction(transaction_id: int):
    """
    Confirm transaction using API Key authentication.
    """
    url = f"{settings.THIRD_PARTY_API_URL}/transactions/{transaction_id}/confirm"
    headers = {
        "Authorization": settings.THIRD_PARTY_API_KEY,
        "Content-Type": "application/json"
    }
    
    try:
        # Log request details before sending
        log_request_details("POST", url, headers, None)

        # Use headers instead of auth parameter
        response = requests.post(url, None, headers=headers)
        
        # Log response details
        log_response_details(response)

        response.raise_for_status()
        
        # Parse the response using Pydantic model
        parsed_response = TransactionResponse(**response.json())
        
        # Log successful transaction
        logging.info(
            "Confirmation processed successfully. Reference ID: %s, Status: %s, State: %s",
            parsed_response.data.reference_id,
            parsed_response.status,
            parsed_response.data.state
        )

        # Return dictionary representation of the response
        return {
            "status": "success",
            "transaction_id": parsed_response.data.id,
            "reference_id": parsed_response.data.reference_id,
            "state": parsed_response.data.state,
            "amount": parsed_response.data.amount,
            "fee": parsed_response.data.fee,
            "total_amount": parsed_response.data.sent_amount,
            "created_at": parsed_response.data.created_at,
            "error_code": parsed_response.data.error_code,
            "error_message": parsed_response.data.error_message
        }

    except requests.exceptions.RequestException as e:
        error_response = None
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_response = e.response.json()
                logging.error(
                    "3rd-party API error response: Status=%s, Body=%s", 
                    e.response.status_code, 
                    json.dumps(error_response, indent=2)
                )
            except json.JSONDecodeError:
                error_response = e.response.text
                logging.error(
                    "3rd-party API error response (non-JSON): Status=%s, Body=%s", 
                    e.response.status_code, 
                    error_response
                )

        return {
            "status": "failed",
            "message": str(e),
            "transaction_id": transaction_id,
            "status_code": e.response.status_code if hasattr(e, 'response') else None,
            "error_response": error_response
        }

    except ValidationError as e:
        logging.error(f"Error parsing response from 3rd-party API: {e}")
        return {
            "status": "failed",
            "message": "Invalid response format from 3rd-party API",
            "transaction_id": transaction_id,
            "errors": e.errors()
        }

def create_transaction(
    reference_id: str,
    callback_url: str,
    payer_id: int,
    destination: dict,
    beneficiary: dict,
    notes: Optional[str] = None,
    include_balance_and_transfer_service: bool = True,
) -> Dict[str, Any]:
    """
    Send request to 3rd-party API with detailed transaction information.
    Uses API Key authentication in Authorization header.

    For Bijak transfers, set include_balance_and_transfer_service=False to omit
    balance_id and source.transfer_service_code (not used by Transfez for Bijak).
    """
    url = f"{settings.THIRD_PARTY_API_URL}/transactions"
    
    # Set up headers with API Key
    headers = {
        "Authorization": settings.THIRD_PARTY_API_KEY,
        "Content-Type": "application/json"
    }

    # Construct the payload using environment variables
    payload = {
        "reference_id": reference_id,
        "callback_url": callback_url,
        "payer_id": payer_id,
        "mode": "DESTINATION",
        "sender": {
            "firstname": settings.SENDER_FIRSTNAME,
            "lastname": settings.SENDER_LASTNAME,
            "country_iso_code": settings.SENDER_COUNTRY_ISO_CODE
        },
        "source": {
            "amount": str(int(destination["amount"])),  # Convert to integer string
            "currency": "IDR",
            "country_iso_code": settings.SENDER_COUNTRY_ISO_CODE,
        },
        "destination": destination,
        "beneficiary": beneficiary,
        "compliance": {
            "source_of_funds": settings.COMPLIANCE_SOURCE_OF_FUNDS,
            "beneficiary_relationship": settings.COMPLIANCE_BENEFICIARY_RELATIONSHIPS,
            "purpose_of_remittance": settings.COMPLIANCE_PURPOSE_OF_REMITTANCES
        },
        "notes": notes if notes is not None else settings.NOTES
    }

    if include_balance_and_transfer_service:
        payload["balance_id"] = int(settings.BALANCE_ID)
        payload["source"]["transfer_service_code"] = settings.TRANSFER_SERVICE_CODE

    try:
        # Log request details before sending
        log_request_details("POST", url, headers, payload)

        # Use headers instead of auth parameter
        response = requests.post(url, json=payload, headers=headers)
        
        # Log response details
        log_response_details(response)

        response.raise_for_status()
        
        # Parse the response using Pydantic model
        parsed_response = TransactionResponse(**response.json())
        
        # Log successful transaction
        logging.info(
            "Transaction processed successfully. Reference ID: %s, Status: %s, State: %s",
            parsed_response.data.reference_id,
            parsed_response.status,
            parsed_response.data.state
        )

        # Return dictionary representation of the response
        return {
            "status": "success",
            "transaction_id": parsed_response.data.id,
            "reference_id": parsed_response.data.reference_id,
            "state": parsed_response.data.state,
            "amount": parsed_response.data.amount,
            "fee": parsed_response.data.fee,
            "total_amount": parsed_response.data.sent_amount,
            "created_at": parsed_response.data.created_at,
            "error_code": parsed_response.data.error_code,
            "error_message": parsed_response.data.error_message,
            "request_payload": json.dumps(payload, indent=2)
        }

    except requests.exceptions.RequestException as e:
        error_response = None
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_response = e.response.json()
                logging.error(
                    "3rd-party API error response: Status=%s, Body=%s", 
                    e.response.status_code, 
                    json.dumps(error_response, indent=2)
                )
            except json.JSONDecodeError:
                error_response = e.response.text
                logging.error(
                    "3rd-party API error response (non-JSON): Status=%s, Body=%s", 
                    e.response.status_code, 
                    error_response
                )

        return {
            "status": "failed",
            "message": str(e),
            "reference_id": reference_id,
            "status_code": e.response.status_code if hasattr(e, 'response') else None,
            "error_response": error_response,
            "request_payload": json.dumps(payload, indent=2)  # Convert payload to JSON string
        }

    except ValidationError as e:
        logging.error(f"Error parsing response from 3rd-party API: {e}")
        return {
            "status": "failed",
            "message": "Invalid response format from 3rd-party API",
            "reference_id": reference_id,
            "errors": e.errors(),
            "request_payload": json.dumps(payload, indent=2)  # Convert payload to JSON string
        }


def create_virtual_account(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create Virtual Account to Transfez /va_numbers endpoint.
    Uses API Key authentication in Authorization header.
    """
    url = f"{settings.THIRD_PARTY_API_URL}/api/v1/va_numbers"
    headers = {
        "Authorization": settings.THIRD_PARTY_API_KEY,
        "Content-Type": "application/json"
    }

    try:
        log_request_details("POST", url, headers, payload)
        response = requests.post(url, json=payload, headers=headers)
        log_response_details(response)
        response.raise_for_status()

        try:
            response_data = response.json()
        except json.JSONDecodeError:
            return {
                "status": "failed",
                "message": "Invalid JSON response from Transfez",
                "status_code": response.status_code,
                "error_response": response.text,
                "request_payload": json.dumps(payload, indent=2)
            }

        return {
            "status": "success",
            "status_code": response.status_code,
            "data": response_data,
            "request_payload": json.dumps(payload, indent=2)
        }

    except requests.exceptions.RequestException as e:
        error_response = None
        status_code = None

        if hasattr(e, "response") and e.response is not None:
            status_code = e.response.status_code
            try:
                error_response = e.response.json()
            except json.JSONDecodeError:
                error_response = e.response.text

        return {
            "status": "failed",
            "message": str(e),
            "status_code": status_code,
            "error_response": error_response,
            "request_payload": json.dumps(payload, indent=2)
        }
