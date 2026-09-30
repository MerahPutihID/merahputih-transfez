"""
Schema Updater Utility
---------------------
Automatically detects and adds missing columns to the Log model only,
without using migrations. All other models are managed by external services.
This utility is designed specifically for keeping the Log model schema updated
while respecting the external management of other tables.
"""

import logging
import json
from datetime import datetime
from sqlalchemy import inspect, text, create_engine
from sqlalchemy.sql import func
from app.database import get_db, engine
from app.config import settings
from app.models import VALog, JackBankInquiryLog, Commission

logger = logging.getLogger(__name__)

# Schema version to track changes
SCHEMA_VERSION = "1.2.0"

def ensure_log_columns_exist():
    """
    Ensures that all columns defined in the Log model exist in the database.
    This is the only model managed by this schema updater utility.
    This function should be called during application startup.
    
    Returns:
        bool: True if updates were made, False if no updates were needed
    """
    logger.info("Checking for missing columns in Log table...")
    db = next(get_db())
    
    try:
        # Get SQLAlchemy connection
        connection = db.connection()
        
        # Define expected columns with their SQL data types
        expected_columns = {
            # Split transaction fields
            "split_number": "INTEGER",
            "split_total": "INTEGER",
            "original_amount": "FLOAT",
            "parent_reference_id": "VARCHAR(255)",
            
            # Transaction fee fields
            "deduction_amount": "FLOAT",
            "deduction_amount_pre": "FLOAT",
            "vat": "FLOAT",
            "vat_amount": "FLOAT",
            "final_amount": "FLOAT",
            "amount": "FLOAT",
            "retry_count": "INTEGER",
        }
        
        # Get existing columns in the table
        inspector = inspect(db.get_bind())
        existing_columns = [column['name'] for column in inspector.get_columns('cdt_gateway_transaction_log')]
        
        # Identify missing columns
        missing_columns = {col: dtype for col, dtype in expected_columns.items() 
                          if col not in existing_columns}
        
        if not missing_columns:
            logger.info("All expected columns exist in the Log table.")
            return False
        
        logger.info(f"Found {len(missing_columns)} missing columns: {', '.join(missing_columns.keys())}")
        
        # Add missing columns
        for column_name, data_type in missing_columns.items():
            logger.info(f"Adding column '{column_name}' with type {data_type} to Log table...")
            
            try:
                alter_stmt = text(f"""
                    ALTER TABLE cdt_gateway_transaction_log 
                    ADD COLUMN {column_name} {data_type} NULL;
                """)
                
                db.execute(alter_stmt)
                logger.info(f"Successfully added column '{column_name}'")
            except Exception as e:
                logger.warning(f"Error adding column '{column_name}': {str(e)}. Attempting alternative approach...")
                try:
                    # Some databases may have different syntax
                    alter_stmt = text(f"""
                        ALTER TABLE cdt_gateway_transaction_log 
                        ADD {column_name} {data_type} NULL;
                    """)
                    
                    db.execute(alter_stmt)
                    logger.info(f"Successfully added column '{column_name}' using alternative approach")
                except Exception as inner_e:
                    logger.error(f"Failed to add column '{column_name}' with both approaches: {str(inner_e)}")
                    raise
        
        # Commit the changes
        db.commit()
        logger.info("Successfully updated Log table schema")
        return True
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating Log table schema: {str(e)}")
        raise
    finally:
        db.close()

def ensure_va_callback_log_table_exists() -> bool:
    """
    Create cdt_va_callback_log in public schema if it does not exist.
    """
    table_name = VALog.__tablename__
    inspector = inspect(engine)
    if table_name in inspector.get_table_names(schema="public"):
        logger.info("Table %s already exists in schema public.", table_name)
        return False

    logger.info("Creating table %s in schema public...", table_name)
    VALog.__table__.create(bind=engine, checkfirst=True)
    logger.info("Successfully created table %s.", table_name)
    return True


def ensure_jack_inquiry_log_table_exists() -> bool:
    """Create jack_transaction_bank_inquiry_log in public schema if not exists."""
    table_name = JackBankInquiryLog.__tablename__
    inspector = inspect(engine)
    if table_name in inspector.get_table_names(schema="public"):
        logger.info("Table %s already exists in schema public.", table_name)
        return False

    logger.info("Creating table %s in schema public...", table_name)
    JackBankInquiryLog.__table__.create(bind=engine, checkfirst=True)
    logger.info("Successfully created table %s.", table_name)
    return True


def ensure_commission_table_exists() -> bool:
    """Create cdt_commision in public schema if it does not exist."""
    table_name = Commission.__tablename__
    inspector = inspect(engine)
    if table_name in inspector.get_table_names(schema="public"):
        logger.info("Table %s already exists in schema public.", table_name)
        return False

    logger.info("Creating table %s in schema public...", table_name)
    Commission.__table__.create(bind=engine, checkfirst=True)
    logger.info("Successfully created table %s.", table_name)
    return True

def update_all_schemas():
    """
    Main function to update schemas managed by this service (Log columns + VA log table).
    Call this function during application startup.
    """
    try:
        logger.info(f"Starting schema update check (version {SCHEMA_VERSION})...")
        
        # Log schema update start for tracking
        log_schema_update("start", SCHEMA_VERSION)
        
        va_table_created = ensure_va_callback_log_table_exists()
        jack_table_created = ensure_jack_inquiry_log_table_exists()
        commission_table_created = ensure_commission_table_exists()
        log_updates = ensure_log_columns_exist()

        logger.info(
            "Managed schemas: cdt_gateway_transaction_log (columns), cdt_va_callback_log (table), jack_transaction_bank_inquiry_log (table), cdt_commision (table)"
        )

        # Log schema update completion
        success_message = "Schema update completed successfully"
        if log_updates or va_table_created or jack_table_created or commission_table_created:
            success_message += " with changes"
        else:
            success_message += " (no changes needed)"
            
        log_schema_update("complete", SCHEMA_VERSION, success_message)
        logger.info(success_message)
        return True
    except Exception as e:
        error_message = f"Schema update failed: {str(e)}"
        log_schema_update("failed", SCHEMA_VERSION, error_message)
        logger.error(error_message)
        return False

def log_schema_update(status, version, message=None):
    """
    Logs schema update activity for tracking purposes.
    Writes to the application log and optionally to a tracking file.
    
    Args:
        status (str): Status of the update ('start', 'complete', 'failed')
        version (str): Schema version being applied
        message (str, optional): Additional message about the update
    """
    timestamp = datetime.now().isoformat()
    log_entry = {
        "timestamp": timestamp,
        "status": status,
        "schema_version": version,
        "message": message
    }
    
    logger.info(f"Schema update {status} (v{version}): {message or ''}")
    
    try:
        # Optionally log to a file for persistent tracking
        # This is useful for tracking Log model schema changes over time
        import os
        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        log_file = os.path.join(log_dir, "log_model_schema_updates.log")
        with open(log_file, "a") as f:
            f.write(f"{json.dumps(log_entry)}\n")
    except Exception as e:
        # Don't fail if we can't write to the log file
        logger.warning(f"Could not write to Log model schema update log file: {str(e)}")
