"""
Helper functions for working with the Deductions model.
This module provides utilities to manage deduction fee configurations in the master data table.
"""
import json
from datetime import datetime
from uuid import uuid4
from app.database import get_db
from app.models import Deduction

def get_deduction(customer_id):
    """
    Get the deduction record for a customer from the master data.
    
    Args:
        customer_id (str): The customer's ID
        
    Returns:
        Deduction: The deduction record, or None if not found
    """
    db = next(get_db())
    
    try:
        return db.query(Deduction).filter(
            Deduction.customer_id == str(customer_id)
        ).first()
    
    finally:
        db.close()

def create_or_update_deduction(customer_id, deduction_type, value, admin_info=None):
    """
    Create or update a deduction record in the master data table.
    
    Args:
        customer_id (str): The customer's ID
        deduction_type (str): Either 'PERCENT' or 'NOMINAL'
        value (float): The deduction value (percentage or nominal amount)
        admin_info (dict): Information about the admin making the change
        
    Returns:
        Deduction: The created/updated deduction record
    """
    if deduction_type not in ["PERCENT", "NOMINAL"]:
        raise ValueError("deduction_type must be either 'PERCENT' or 'NOMINAL'")
    
    db = next(get_db())
    
    try:
        # Check if deduction already exists for this customer
        existing = db.query(Deduction).filter(
            Deduction.customer_id == str(customer_id)
        ).first()
        
        # Prepare update history
        update_info = {
            "timestamp": datetime.now().isoformat(),
            "admin_info": admin_info or {}
        }
        
        if existing:
            # Store old values for history
            update_info["old_type"] = existing.deduction_active_type
            update_info["old_value"] = existing.value_percentage if existing.deduction_active_type == "PERCENT" else existing.value_nominal
            
            # Update existing record
            existing.deduction_active_type = deduction_type
            
            # Clear existing values first
            existing.value_percentage = None
            existing.value_nominal = None
            
            # Set the appropriate value based on type
            if deduction_type == "PERCENT":
                existing.value_percentage = float(value)
                update_info["new_type"] = "PERCENT"
                update_info["new_value"] = float(value)
            elif deduction_type == "NOMINAL":
                existing.value_nominal = float(value)
                update_info["new_type"] = "NOMINAL"
                update_info["new_value"] = float(value)
                
            # Update metadata
            existing.updated_on = datetime.now()
            
            # Update history
            history = json.loads(existing.last_update_history or "[]")
            if not isinstance(history, list):
                history = []
            
            history.append(update_info)
            existing.last_update_history = json.dumps(history)
            
            deduction = existing
        else:
            # Create new deduction record
            deduction = Deduction(
                id=uuid4(),
                customer_id=str(customer_id),
                deduction_active_type=deduction_type,
                value_percentage=float(value) if deduction_type == "PERCENT" else None,
                value_nominal=float(value) if deduction_type == "NOMINAL" else None,
                created_on=datetime.now(),
                updated_on=datetime.now(),
                last_update_history=json.dumps([{
                    "timestamp": datetime.now().isoformat(),
                    "type": deduction_type,
                    "value": float(value),
                    "admin_info": admin_info or {}
                }])
            )
            db.add(deduction)
            
        db.commit()
        return deduction
    
    finally:
        db.close()

def delete_deduction(customer_id):
    """
    Delete a deduction record from the master data.
    
    Args:
        customer_id (str): The customer's ID
        
    Returns:
        bool: True if deleted, False if not found
    """
    db = next(get_db())
    
    try:
        deduction = db.query(Deduction).filter(
            Deduction.customer_id == str(customer_id)
        ).first()
        
        if deduction:
            db.delete(deduction)
            db.commit()
            return True
        
        return False
    
    finally:
        db.close()
