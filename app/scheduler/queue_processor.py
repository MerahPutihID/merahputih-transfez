import json
import logging
import string
import random
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import cast, String, desc
from datetime import datetime, timedelta

from app.database import get_db
from app.models import Queue, Transaction, TransactionDetail, Log, BeneficiaryAccount, Bank, CDTAdvTransaction, PjpurTagTransaction, CDTMachine
from app.services import create_transaction, confirm_transaction  # Import the functions directly
from app.utils import UUIDEncoder
from app.utils import calculate_transaction_fee  # Import the function directly
from app.constants import TRANSACTION_STATUS
from app.config import settings
from app.utils.transaction_splitter import prepare_split_transactions, generate_split_reference_ids
from app.utils.va_lookup import get_va_number_for_beneficiary

# Configure logging
logging.basicConfig(
    level=logging.INFO,  # Set the logging level
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Enable SQLAlchemy debug logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.pool').setLevel(logging.WARNING)

# Cron job scheduler
scheduler = BackgroundScheduler()

def generate_random_string(length=6):
    """Generate a random string of lowercase letters."""
    return ''.join(random.choices(string.ascii_lowercase, k=length))


def get_allowed_machine_ids(db):
    """
    Get list of machine IDs that should be processed based on maintenance_id configuration
    This filter is MANDATORY - processing only occurs for machines with the specified maintenance_id
    
    Args:
        db: Database session
        
    Returns:
        list: List of allowed machine IDs (UUIDs), or empty list if none found
        
    Raises:
        ValueError: If MAINTENANCE_ID is not configured
    """
    if not settings.MAINTENANCE_ID or not CDTMachine:
        raise ValueError("MAINTENANCE_ID configuration is required but not set")
    
    try:
        # Convert string UUID to UUID object for comparison
        from uuid import UUID
        maintenance_uuid = UUID(settings.MAINTENANCE_ID)
        
        # Query machines with the specified maintenance_id
        machines = db.query(CDTMachine.id).filter(
            CDTMachine.maintenance_id == maintenance_uuid
        ).all()
        
        machine_ids = [machine.id for machine in machines]
        
        if machine_ids:
            logger.info(f"Processing transactions for {len(machine_ids)} machines with maintenance_id: {settings.MAINTENANCE_ID}")
        else:
            logger.warning(f"No machines found with maintenance_id: {settings.MAINTENANCE_ID} - no transactions will be processed")
            
        return machine_ids
        
    except Exception as e:
        logger.error(f"Error getting machine IDs for maintenance_id {settings.MAINTENANCE_ID}: {str(e)}")
        raise ValueError(f"Failed to get machine IDs for maintenance_id {settings.MAINTENANCE_ID}: {str(e)}")

def _process_transaction_common(db, trx_detail, transaction_id, reference_id, log_prefix="", item_id=None):
    """Common transaction processing logic used by both queue and advanced transaction processors.
    
    This function:
    1. Creates a parent log entry for the transaction
    2. Calculates transaction fee based on customer tier
    3. For BI-Fast transactions (TRANSFER_SERVICE_CODE=1) exceeding max amount:
       - Splits the transaction AFTER fee deduction
       - Ensures each split is at least 10,000 IDR (except potentially the last one)
       - Applies fee tracking to the last split for reporting purposes
    4. For non-BI-Fast or transactions below max amount:
       - Processes as single transaction
    5. Creates API requests for each split transaction
    6. Updates parent log with final status based on split results
    
    Args:
        db: Database session
        trx_detail: Transaction detail object
        transaction_id: Transaction ID
        reference_id: Reference ID for the transaction
        log_prefix: Prefix for log messages (default: "")
        item_id: Optional item ID for logging purposes
        
    Returns:
        bool: True if processing was successful, False otherwise
    """
    processing_log = None
    try:
        # Initial log entry for processing
        init_message = f"Transaction processing initiated{' (from CDT Advanced Transaction)' if log_prefix == 'ADV ' else ''}"
        
        # Safely get the transaction amount before creating the log
        try:
            initial_amount = float(trx_detail.amount)
        except (ValueError, TypeError):
            initial_amount = 0.0  # Safe default
            
        processing_log = Log(
            cdt_trx_cdm_id=transaction_id,
            reference_id=reference_id,
            transaction_id=None,  # Will be set after successful creation
            status=TRANSACTION_STATUS["PENDING"],
            state=None,
            create_response=init_message,
            confirm_response=None,
            callback_data=None,
            # Initialize with split info, even though this will be updated later
            split_number=0,  # Parent/initial log gets split_number 0
            split_total=0,  # Will be updated after we know the total number of splits
            original_amount=initial_amount,  # Initial amount from transaction detail
            deduction_amount=0.0,  # Will be updated with actual fee
            final_amount=0.0,  # Will be updated with final amount
            amount=initial_amount,  # Initial amount from transaction detail
            parent_reference_id=None  # This is the parent log itself
        )
        db.add(processing_log)
        db.commit()

        # Fetch beneficiary data
        beneficiary_data = db.query(BeneficiaryAccount).filter(
            BeneficiaryAccount.id == trx_detail.beneficiary_account_id
        ).first()

        if not beneficiary_data:
            raise ValueError(f"Beneficiary account not found for ID: {trx_detail.beneficiary_account_id}")

        # Fetch bank data to get payer_id
        bank_data = db.query(Bank).filter(
            Bank.id == beneficiary_data.bank_id
        ).first()

        if not bank_data:
            raise ValueError(f"Bank not found for ID: {beneficiary_data.bank_id}")

        if not bank_data.bank_payer_id:
            raise ValueError(f"Bank payer ID not configured for bank: {bank_data.name}")

        va_number = get_va_number_for_beneficiary(db, beneficiary_data.id)
        transaction_notes = va_number or settings.NOTES
        if va_number:
            logger.info(
                "%sUsing VA number for Transfez notes: %s (beneficiary_id=%s)",
                log_prefix,
                va_number,
                beneficiary_data.id,
            )
        else:
            logger.warning(
                "%sVA not found for beneficiary_id=%s customer_id=%s; using default NOTES",
                log_prefix,
                beneficiary_data.id,
                beneficiary_data.customer_id,
            )
            
        # Get the transaction amount
        try:
            amount = float(trx_detail.amount)
            # Update the log with the verified amount
            processing_log.amount = amount
            processing_log.original_amount = amount
        except (ValueError, TypeError):
            raise ValueError(f"Invalid amount format: {trx_detail.amount}")
        
        # Calculate transaction fee based on customer_id
        deduction_amount, final_amount = calculate_transaction_fee(
            beneficiary_data.customer_id,
            amount
        )
        
        # Update the log with fee information
        processing_log.deduction_amount = deduction_amount
        processing_log.final_amount = final_amount
        db.commit()
        
        logger.info(f"{log_prefix}Transaction fee: {deduction_amount}, Final amount: {final_amount}")
        
        # Check if the amount exceeds the maximum transaction amount
        max_amount = float(settings.MAX_TRANSACTION_AMOUNT)
        
        # Prepare transaction data for the API call
        transaction_data = {
            'callback_url_base': f"{settings.API_BASE_URL}/callback/",
            'payer_id': bank_data.bank_payer_id,
            'destination': {
                'currency': "IDR",
                'country_iso_code': beneficiary_data.country_code
            },
            'beneficiary': {
                'firstname': beneficiary_data.firstname,
                'lastname': beneficiary_data.lastname,
                'country_iso_code': beneficiary_data.country_code,
                'account': beneficiary_data.account_number
            }
        }
        
        # Only split transactions for BI-Fast (TRANSFER_SERVICE_CODE = 1)
        # Also check if the amount exceeds the maximum transaction amount
        transfer_service_code = int(settings.TRANSFER_SERVICE_CODE)
        
        if transfer_service_code == 1 and final_amount > max_amount:
            # Split the amount AFTER fee deduction
            # This ensures all amounts sent are after the fee has been applied
            split_transactions = prepare_split_transactions(
                reference_id=reference_id,
                amount=float(final_amount),  # Use final amount (after deduction) for splitting
                max_amount=max_amount,
                **transaction_data
            )
            
            # Update parent log with split total
            processing_log.split_total = len(split_transactions)
            db.commit()
            
            logger.info(f"{log_prefix}Transaction will be processed in {len(split_transactions)} part(s)")
        else:
            # For non BI-Fast transactions or if amount is below max, don't split
            # Still use the split transaction structure for consistency
            single_split_reference_id = generate_split_reference_ids(reference_id, 1)[0]
            split_transactions = [{
                **transaction_data,
                'reference_id': single_split_reference_id,
                'amount': int(final_amount),  # Use final amount after deduction
                'split_number': 1,
                'split_total': 1,
                'original_amount': amount,
                'parent_reference_id': reference_id
            }]
            
            # Update parent log with split total
            processing_log.split_total = 1
            db.commit()
            
            logger.info(f"{log_prefix}Transaction will be processed as a single transaction")
        
        # Process each split transaction
        successful_splits = 0
        
        for split_tx in split_transactions:
            split_reference_id = split_tx['reference_id']
            split_amount = split_tx['amount']
            split_number = split_tx.get('split_number', 1)
            split_total = split_tx.get('split_total', 1)
            
            # Always create a split log entry for consistency
            # This matches our transaction_splitter logic that always creates split structure
            split_log = Log(
                cdt_trx_cdm_id=transaction_id,
                reference_id=split_reference_id,
                transaction_id=None,
                status=TRANSACTION_STATUS["PENDING"],
                state=None,
                create_response=f"Split {log_prefix.strip()}transaction {split_number}/{split_total} processing initiated",
                confirm_response=None,
                callback_data=None,
                split_number=split_number,
                split_total=split_total,
                original_amount=float(amount),  # Keep the original total amount
                parent_reference_id=reference_id,
                # Initially set all fee and amount fields
                # These will be updated for fee-bearing splits later
                deduction_amount=float(0.0),  # Initially set to 0, will update for fee-bearing splits
                amount=float(split_amount),    # Initial split amount - for fee-bearing splits, will be updated
                final_amount=float(split_amount)  # Initially same as amount - for fee-bearing splits, will reflect post-fee
            )
            db.add(split_log)
            db.commit()
            processing_log = split_log
            
            # For BI-Fast transactions with multiple splits, apply the fee to the last split
            if transfer_service_code == 1 and split_total > 1 and split_number == split_total:
                # This is the last split, apply the fee tracking here for reporting purposes
                processing_log.deduction_amount = float(deduction_amount)
                
                # For the last split with fee, we need to:
                # - Keep amount as the original split amount before fee
                # - Set final_amount as the amount after fee deduction
                # This corrects the reported values for proper accounting
                original_last_split_amount = float(split_amount) + float(deduction_amount)
                processing_log.amount = original_last_split_amount
                processing_log.final_amount = float(split_amount)
                db.commit()
                logger.info(f"Applied deduction fee {deduction_amount} to last split {split_number}/{split_total} (original amount: {original_last_split_amount}, final amount: {split_amount})")
            elif split_total == 1:
                # For single transactions, apply fee to the only split
                processing_log.deduction_amount = float(deduction_amount)
                # Ensure correct amount reporting - amount should be original (before deduction)
                original_amount = float(split_amount) + float(deduction_amount)
                processing_log.amount = original_amount  
                processing_log.final_amount = float(split_amount)
                db.commit()
                logger.info(f"Applied deduction fee {deduction_amount} to single transaction (original amount: {original_amount}, final amount: {split_amount})")
            
            logger.info(f"Processing {log_prefix}split {split_number}/{split_total}: {split_reference_id} with amount {split_amount}")
            
            # Send request to 3rd-party API with transaction details
            # Amount has already been adjusted for fee deduction
            response = create_transaction(
                reference_id=split_reference_id,
                callback_url=f"{settings.API_BASE_URL}/callback/{split_reference_id}",
                payer_id=split_tx['payer_id'],
                destination={
                    'amount': str(int(split_amount)),  # Send amount as integer string
                    'currency': split_tx['destination']['currency'],
                    'country_iso_code': split_tx['destination']['country_iso_code']
                },
                beneficiary=split_tx['beneficiary'],
                notes=transaction_notes,
            )

            # Update the log amount fields only for splits without fee applied
            # For splits with fee, we've already set these values correctly above
            if not (
                (transfer_service_code == 1 and split_total > 1 and split_number == split_total) or 
                (split_total == 1)
            ):
                # For non-fee splits, amount and final_amount are the same
                processing_log.amount = float(split_amount)
                processing_log.final_amount = float(split_amount)
                db.commit()

            # Log the response from the 3rd-party API
            logger.info(f"Response from 3rd-party API for {log_prefix}split {split_number}/{split_total}: {response}")

            # After successful transaction creation
            if response.get("status") == "success":
                # Update the log with create response
                processing_log.status = TRANSACTION_STATUS["CREATED"]
                processing_log.state = response.get("state", "created")
                processing_log.create_request = response.get("request_payload", None)
                processing_log.create_response = json.dumps(response, cls=UUIDEncoder)
                processing_log.transaction_id = response["transaction_id"]
                db.commit()

                # Attempt to confirm the transaction
                confirm_response = confirm_transaction(response["transaction_id"])
                
                # Update the log with confirm response
                processing_log.state = confirm_response.get("state", None)
                processing_log.confirm_response = json.dumps(confirm_response, cls=UUIDEncoder)
                
                if confirm_response.get("status") == "success":
                    processing_log.status = TRANSACTION_STATUS["CONFIRMED"]
                    successful_splits += 1
                else:
                    processing_log.status = TRANSACTION_STATUS["FAILED"]
            else:
                # Update log with failure details
                processing_log.status = TRANSACTION_STATUS["FAILED"]
                processing_log.create_request = response.get("request_payload", None)
                processing_log.create_response = json.dumps(response, cls=UUIDEncoder)

            db.commit()
        
        # Always update the parent log status based on the split transaction results
        # Since all transactions now use the split structure, including single-split transactions
        if processing_log.parent_reference_id:
            parent_log = db.query(Log).filter(
                Log.reference_id == processing_log.parent_reference_id
            ).first()
            
            if parent_log:
                if successful_splits == len(split_transactions):
                    parent_log.status = TRANSACTION_STATUS["CONFIRMED"]
                    parent_log.state = "split_all_confirmed"
                elif successful_splits > 0:
                    parent_log.status = TRANSACTION_STATUS["PARTIAL"]
                    parent_log.state = f"split_partial_{successful_splits}_of_{len(split_transactions)}"
                else:
                    parent_log.status = TRANSACTION_STATUS["FAILED"]
                    parent_log.state = "split_all_failed"
                
                parent_log.create_response = json.dumps({
                    "message": f"Split {log_prefix}transaction processing completed with {successful_splits}/{len(split_transactions)} successful splits",
                    "timestamp": datetime.now().isoformat()
                }, cls=UUIDEncoder)
                db.commit()

        if item_id:
            logger.info(f"{log_prefix}item {item_id} processed successfully")
        return True
    except Exception as e:
        # Log the error
        if processing_log:
            processing_log.status = TRANSACTION_STATUS["FAILED"]
            processing_log.create_response = json.dumps({
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }, cls=UUIDEncoder)
        else:
            # Try to safely get the transaction amount if available
            try:
                safe_amount = float(trx_detail.amount) if trx_detail else 0.0
            except (ValueError, TypeError, AttributeError):
                safe_amount = 0.0
                
            # Create a new log entry if one doesn't exist
            processing_log = Log(
                cdt_trx_cdm_id=transaction_id,
                reference_id=reference_id,
                transaction_id=None,
                status=TRANSACTION_STATUS["FAILED"],
                state=None,
                create_response=json.dumps({
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }, cls=UUIDEncoder),
                confirm_response=None,
                callback_data=None,
                deduction_amount=0.0,  # Set default values for fee fields as float
                final_amount=0.0,
                amount=safe_amount,  # Use safe amount value
                split_number=0,  # Parent log gets split_number 0
                split_total=0,  # No splits in error case
                original_amount=safe_amount,  # Use safe amount value
                parent_reference_id=None  # This is the parent log
            )
            db.add(processing_log)
        db.commit()
        
        if item_id:
            logger.error(f"Error processing {log_prefix}item {item_id}: {e}")
        return False

def process_queue():
    """Process pending transactions in the queue."""
    start_time = datetime.now()
    db = next(get_db())
    logger.info("Processing queue at %s", start_time)
    processed_count = 0
    try:
        # Calculate timestamp based on configured threshold
        hour_ago = datetime.now() - timedelta(hours=settings.QUEUE_PROCESSING_TIME_THRESHOLD_HOURS)
        
        # Get allowed machine IDs based on maintenance_id configuration (MANDATORY)
        try:
            allowed_machine_ids = get_allowed_machine_ids(db)
        except ValueError as e:
            logger.error(f"Queue processing skipped: {str(e)}")
            return
        
        # Skip processing if no machines found
        if not allowed_machine_ids:
            logger.info("No machines found with configured maintenance_id - skipping queue processing")
            return
        
        # Use a correlated subquery with EXISTS instead of IN to handle large Log tables
        # This approach is more efficient when the Log table contains a lot of data
        pending_transactions = (
            db.query(Queue, Transaction, TransactionDetail)
            .join(
                Transaction,
                Queue.cd_trx_cdm_id == Transaction.id
            )
            .join(
                TransactionDetail,
                Transaction.id == TransactionDetail.id
            )
            .filter(Queue.status == "SUCCESS")
            .filter(TransactionDetail.updated_on >= hour_ago)  # Add time filter
            .filter(TransactionDetail.machine_id.in_(allowed_machine_ids))  # Apply machine filter
            .filter(
                ~db.query(Log)
                .filter(Log.cdt_trx_cdm_id == Transaction.id)
                .exists()
            )  # More efficient check for large Log tables
            .order_by(TransactionDetail.updated_on.desc()) # Order by updated_on descending
            # .limit(1)  # Limit to 1 transactions for processing
        )

        for queue_item, transaction, trx_detail in pending_transactions:
            reference_id = trx_detail.cdm_trx_no
            if _process_transaction_common(db, trx_detail, transaction.id, reference_id, "", queue_item.id):
                processed_count += 1
    finally:
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info("Queue processing completed. Processed %s items in %.2f seconds", processed_count, duration)
        db.close()

def process_adv_transactions():
    """Process pending transactions from CDTAdvTransaction."""
    start_time = datetime.now()
    db = next(get_db())
    logger.info("Processing CDT Advanced Transactions at %s", start_time)
    processed_count = 0
    try:
        # Calculate timestamp based on configured threshold
        hour_ago = datetime.now() - timedelta(hours=settings.QUEUE_PROCESSING_TIME_THRESHOLD_HOURS)
        
        # Get allowed machine IDs based on maintenance_id configuration (MANDATORY)
        try:
            allowed_machine_ids = get_allowed_machine_ids(db)
        except ValueError as e:
            logger.error(f"ADV transaction processing skipped: {str(e)}")
            return
        
        # Skip processing if no machines found
        if not allowed_machine_ids:
            logger.info("No machines found with configured maintenance_id - skipping ADV processing")
            return
        
        # Use a correlated subquery with EXISTS instead of IN to handle large Log tables
        # This approach is more efficient when the Log table contains a lot of data
        pending_transactions = (
            db.query(CDTAdvTransaction, TransactionDetail)
            .join(
                TransactionDetail,
                CDTAdvTransaction.reference_id == TransactionDetail.cdm_trx_no
            )
            .filter(CDTAdvTransaction.status == "COMPLETED")  # Only process completed transactions
            .filter(CDTAdvTransaction.transaction_type == "DEPOSIT")  # Only process deposits
            .filter(
                # Use processed_at OR created_at if they're not None, otherwise filter by updated_at
                (CDTAdvTransaction.processed_at != None) & (CDTAdvTransaction.processed_at >= hour_ago) # |
                # ((CDTAdvTransaction.processed_at == None) & (CDTAdvTransaction.created_at != None) & (CDTAdvTransaction.created_at >= hour_ago))
            )
            .filter(TransactionDetail.machine_id.in_(allowed_machine_ids))  # Apply machine filter
            .filter(
                ~db.query(Log)
                .filter(Log.cdt_trx_cdm_id == TransactionDetail.id)
                .exists()
            )  # More efficient check for large Log tables
            .order_by(CDTAdvTransaction.processed_at.desc().nullsfirst())  # Order by processed_at descending, nulls first
        )
        
        # Fetch and process transactions
        for adv_transaction, trx_detail in pending_transactions:
            reference_id = adv_transaction.reference_id
            if _process_transaction_common(db, trx_detail, trx_detail.id, reference_id, "ADV ", adv_transaction.id):
                processed_count += 1
    finally:
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info("Advanced Transaction processing completed. Processed %s items in %.2f seconds", processed_count, duration)
        db.close()

def process_pjpur_tag_transactions():
    """Process pending transactions from PjpurTagTransaction."""
    start_time = datetime.now()
    db = next(get_db())
    logger.info("Processing PJPUR TAG Transactions at %s", start_time)
    processed_count = 0
    try:
        # Calculate timestamp based on configured threshold
        hour_ago = datetime.now() - timedelta(hours=settings.QUEUE_PROCESSING_TIME_THRESHOLD_HOURS)
        
        # Get allowed machine IDs based on maintenance_id configuration (MANDATORY)
        try:
            allowed_machine_ids = get_allowed_machine_ids(db)
        except ValueError as e:
            logger.error(f"PJPUR transaction processing skipped: {str(e)}")
            return
        
        # Skip processing if no machines found
        if not allowed_machine_ids:
            logger.info("No machines found with configured maintenance_id - skipping PJPUR processing")
            return
        
        # Use a correlated subquery with EXISTS instead of IN to handle large Log tables
        # This approach is more efficient when the Log table contains a lot of data
        pending_transactions = (
            db.query(PjpurTagTransaction, TransactionDetail)
            .join(
                TransactionDetail,
                PjpurTagTransaction.reference_id == TransactionDetail.cdm_trx_no
            )
            .filter(PjpurTagTransaction.status == "COMPLETED")  # Only process completed transactions
            .filter(PjpurTagTransaction.transaction_type == "DEPOSIT")  # Only process deposits
            .filter(
                # Use processed_at OR created_at if they're not None, otherwise filter by updated_at
                (PjpurTagTransaction.processed_at != None) & (PjpurTagTransaction.processed_at >= hour_ago)
            )
            .filter(TransactionDetail.machine_id.in_(allowed_machine_ids))  # Apply machine filter
            .filter(
                ~db.query(Log)
                .filter(Log.cdt_trx_cdm_id == TransactionDetail.id)
                .exists()
            )  # More efficient check for large Log tables
            .order_by(PjpurTagTransaction.processed_at.desc().nullsfirst())  # Order by processed_at descending, nulls first
        )
        
        # Fetch and process transactions
        for pjpur_tag_transaction, trx_detail in pending_transactions:
            reference_id = pjpur_tag_transaction.reference_id
            if _process_transaction_common(db, trx_detail, trx_detail.id, reference_id, "PJPUR ", pjpur_tag_transaction.id):
                processed_count += 1
    finally:
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info("PJPUR TAG Transaction processing completed. Processed %s items in %.2f seconds", processed_count, duration)
        db.close()

def run_scheduler():
    """Run the background scheduler."""
    logger.info("Starting the scheduler...")
    scheduler.add_job(process_queue, "interval", seconds=10)
    scheduler.add_job(process_adv_transactions, "interval", seconds=10)  # Process adv transactions every 10 seconds
    scheduler.add_job(process_pjpur_tag_transactions, "interval", seconds=10)  # Process PJPUR TAG transactions every 10 seconds
    scheduler.start()
    try:
        while True:
            pass  # Keep the scheduler running
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        logger.info("Scheduler stopped.")