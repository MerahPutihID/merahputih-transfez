from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import UUID

class TransactionFeeDetails(BaseModel):
    """Detailed transaction fee information"""
    reference_id: str
    original_amount: Optional[float] = None
    deduction_amount: Optional[float] = None
    final_amount: Optional[float] = None
    deduction_percentage: Optional[float] = None
    created_at: datetime
    
    class Config:
        from_attributes = True  # For Pydantic v2
