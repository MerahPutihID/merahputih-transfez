import logging
import json
from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Path, Request, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Log, VALog
from app.schemas import LogResponse, CallbackRequest, VACallbackResponse
from app.utils import UUIDEncoder
from app.utils.va_callback import parse_va_callback_payload
from app.utils.gateway_urls import build_va_callback_url
from app.constants import TRANSACTION_STATE, TRANSACTION_STATUS
from app.services import create_virtual_account
from app.schemas import CreateVARequest

router = APIRouter()

# Configure logging
logging.basicConfig(
    level=logging.INFO,  # Set the logging level
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Enable SQLAlchemy debug logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.DEBUG)
logging.getLogger('sqlalchemy.pool').setLevel(logging.DEBUG)


@router.post("/va_numbers")
def create_va(payload: CreateVARequest):
    """Create virtual account via Transfez API."""
    request_data = payload.model_dump(exclude_none=True)
    request_data["callback_url"] = build_va_callback_url(
        payload.callback_url,
        payload.virtual_account,
    )
    response = create_virtual_account(request_data)

    if response.get("status") == "success":
        return {
            "status": "success",
            "message": "Virtual account created successfully",
            "data": response.get("data"),
        }

    raise HTTPException(
        status_code=response.get("status_code") or 500,
        detail={
            "message": response.get("message", "Failed to create virtual account"),
            "error_response": response.get("error_response"),
        },
    )


@router.post("/va/callback/{va_number}", response_model=VACallbackResponse)
async def handle_va_callback(
    request: Request,
    va_number: str = Path(..., description="VA number from callback URL"),
    db: Session = Depends(get_db),
):
    """Receive Transfez VA callbacks; persist to cdt_va_callback_log; return 200."""
    try:
        raw_body = await request.json()
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON body: {exc}") from exc

    if not isinstance(raw_body, dict):
        raise HTTPException(status_code=400, detail="Callback body must be a JSON object")

    logger.info(
        "Received VA callback: %s",
        json.dumps(raw_body, indent=2),
    )

    parsed = parse_va_callback_payload(raw_body)
    payload_va_number = parsed.get("va_number")
    if payload_va_number and str(payload_va_number) != va_number:
        logger.warning(
            "VA callback URL and payload mismatch: url=%s payload=%s",
            va_number,
            payload_va_number,
        )

    resolved_va_number = str(payload_va_number) if payload_va_number else va_number
    success_value = parsed.get("success")
    if success_value is not None and not isinstance(success_value, str):
        success_value = str(success_value)

    log_entry = VALog(
        transfez_id=parsed.get("transfez_id"),
        va_number_id=parsed.get("va_number_id"),
        va_status=parsed.get("va_status"),
        va_number=resolved_va_number,
        partner_trx_id=parsed.get("partner_trx_id"),
        bank_code=parsed.get("bank_code"),
        amount=parsed.get("amount"),
        amount_detected=parsed.get("amount_detected"),
        success=success_value,
        tx_date=str(parsed["tx_date"]) if parsed.get("tx_date") is not None else None,
        payload_shape=parsed.get("payload_shape"),
        raw_payload=json.dumps(raw_body, cls=UUIDEncoder),
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)

    return {
        "status": "success",
        "message": "VA callback received",
        "id": log_entry.id,
        "va_status": log_entry.va_status,
        "va_number": log_entry.va_number,
        "partner_trx_id": log_entry.partner_trx_id,
    }


@router.get("/transaction/logs", response_model=List[LogResponse])
def get_logs(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    parent_reference_id: str = None,
    reference_id: str = None
):
    """Get a list of logs from the log table."""
    query = db.query(Log)
    
    # Filter options
    if parent_reference_id:
        query = query.filter(Log.parent_reference_id == parent_reference_id)
    
    if reference_id:
        query = query.filter(Log.reference_id == reference_id)
        
    logs = query.order_by(Log.created_at.desc()).offset(skip).limit(limit).all()
    return logs

@router.get("/transaction/split-logs/{parent_reference_id}", response_model=List[LogResponse])
def get_split_logs(
    parent_reference_id: str = Path(..., description="Parent reference ID of the transaction"),
    db: Session = Depends(get_db)
):
    """Get all transaction logs for a parent reference ID, including single-split transactions."""
    # Get the parent log
    parent_log = db.query(Log).filter(
        Log.reference_id == parent_reference_id
    ).first()
    
    if not parent_log:
        raise HTTPException(
            status_code=404,
            detail=f"No transaction log found for reference_id {parent_reference_id}"
        )
    
    # Get all child logs
    child_logs = db.query(Log).filter(
        Log.parent_reference_id == parent_reference_id
    ).order_by(Log.split_number).all()
    
    # Return both parent and children
    result = [parent_log] + child_logs
    return result

@router.post("/transaction/callback/{reference_id}")
async def handle_callback(
    request: Request,
    reference_id: str = Path(..., description="Reference ID of the transaction"),
    callback_data: CallbackRequest = None,
    db: Session = Depends(get_db)
):
    """Handle callback from 3rd-party service."""
    # Get original request body
    raw_body = await request.json()
    
    logger.info(
        "Received callback for reference_id: %s with raw data: %s",
        reference_id,
        json.dumps(raw_body, indent=2)
    )
    
    try:
        # Validate reference_id matches callback data
        if callback_data.reference_id != reference_id:
            raise HTTPException(
                status_code=400,
                detail=f"Reference ID mismatch: URL path ({reference_id}) != payload ({callback_data.reference_id})"
            )

        # Find the existing log entry for this transaction
        log_entry = db.query(Log).filter(
            Log.reference_id == reference_id
        ).order_by(Log.created_at.desc()).first()
        
        if not log_entry:
            raise HTTPException(
                status_code=404,
                detail=f"No transaction log found for reference_id {reference_id}"
            )

        # Update log entry with callback data
        log_entry.status = TRANSACTION_STATUS["SUCCESS"] if callback_data.state.lower() == TRANSACTION_STATE["COMPLETED"] else TRANSACTION_STATUS["FAILED"]
        log_entry.state = callback_data.state
        log_entry.callback_data = json.dumps(raw_body, cls=UUIDEncoder)
        
        # Handle transaction parent-child relationship
        # Always check for parent reference since all transactions now use split structure
        if log_entry.parent_reference_id:
            # This is a split transaction (could be 1 of 1 or part of multiple splits)
            parent_ref_id = log_entry.parent_reference_id
            
            # Find the parent log entry
            parent_log = db.query(Log).filter(
                Log.reference_id == parent_ref_id
            ).first()
            
            if parent_log:
                # Get all split transactions for this parent
                all_splits = db.query(Log).filter(
                    Log.parent_reference_id == parent_ref_id
                ).all()
                
                total_splits = len(all_splits)  # More reliable than log_entry.split_total
                completed_splits = sum(1 for split in all_splits if split.callback_data is not None)
                successful_splits = sum(1 for split in all_splits if split.status == TRANSACTION_STATUS["SUCCESS"])
                
                logger.info(
                    "Transaction update: %s/%s splits completed, %s successful",
                    completed_splits, total_splits, successful_splits
                )
                
                # If all splits have callbacks, update parent status
                if completed_splits == total_splits:
                    if successful_splits == total_splits:
                        parent_log.status = TRANSACTION_STATUS["SUCCESS"]
                        parent_log.state = "split_all_completed"
                    elif successful_splits > 0:
                        parent_log.status = TRANSACTION_STATUS["PARTIAL"]
                        parent_log.state = f"split_partial_{successful_splits}_of_{total_splits}"
                    else:
                        parent_log.status = TRANSACTION_STATUS["FAILED"]
                        parent_log.state = "split_all_failed"
                    
                    # Update parent log with summary
                    parent_log.callback_data = json.dumps({
                        "message": f"Transaction processing completed with {successful_splits}/{total_splits} successful splits",
                        "timestamp": datetime.now().isoformat(),
                        "splits": [{"reference_id": split.reference_id, 
                                   "status": split.status, 
                                   "amount": float(split.amount) if split.amount is not None else 0.0,
                                   "final_amount": float(split.final_amount) if split.final_amount is not None else 0.0} 
                                  for split in all_splits]
                    }, cls=UUIDEncoder)
        
        db.commit()

        logger.info(
            "Successfully processed callback for reference_id: %s with status: %s",
            reference_id,
            callback_data.state
        )

        return {
            "status": "success",
            "message": "Callback processed successfully",
            "data": {
                "id": callback_data.id,
                "reference_id": reference_id,
                "state": callback_data.state,
                "amount": callback_data.amount,
                "timestamp": datetime.now().isoformat()
            }
        }

    except Exception as e:
        logger.error(
            "Error processing callback for reference_id %s: %s",
            reference_id,
            str(e)
        )
        raise HTTPException(
            status_code=500,
            detail=f"Error processing callback: {str(e)}"
        )