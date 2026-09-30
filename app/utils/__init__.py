"""
Utility modules for the CDT Gateway Service.
"""

from uuid import UUID
import json

class UUIDEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles UUID objects."""
    def default(self, obj):
        if isinstance(obj, UUID):
            # Convert UUID to string
            return str(obj)
        return json.JSONEncoder.default(self, obj)

# Import utility functions to make them available through the utils package
from app.utils.deduction_helper import create_or_update_deduction, get_deduction, delete_deduction
from app.utils.schema_updater import update_all_schemas, ensure_log_columns_exist
from app.utils.fee_calculator import calculate_transaction_fee
from app.utils.commission_helper import record_commissions

# Import the UUIDEncoder directly from this file
# to avoid circular imports
