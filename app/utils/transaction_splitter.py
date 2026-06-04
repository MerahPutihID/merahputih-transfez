import math
from typing import List, Dict, Any

def split_transaction_amount(amount: float, max_amount: float) -> List[float]:
    """
    Split a transaction amount into chunks that don't exceed the maximum amount.
    
    Args:
        amount (float): The total transaction amount
        max_amount (float): The maximum amount allowed per transaction
        
    Returns:
        List[float]: A list of split amounts
    """
    if amount <= max_amount:
        return [amount]
        
    # Create splits of maximum size, with the last one containing the remainder
    num_full_splits = int(amount // max_amount)
    remainder = amount % max_amount
    
    # Create the splits: maximum amount for each full split
    split_amounts = [max_amount] * num_full_splits
    
    # Handle remainder - always add it as a separate split
    if remainder > 0:
        split_amounts.append(remainder)
    
    return split_amounts

def generate_split_reference_ids(reference_id: str, num_splits: int) -> List[str]:
    """
    Generate reference IDs for split transactions.
    
    Args:
        reference_id (str): The original reference ID
        num_splits (int): The number of splits
        
    Returns:
        List[str]: A list of reference IDs with split suffixes
    """
    # Always use the same format for consistency, even with only one split
    return [f"{reference_id}-{str(i+1).zfill(2)}" for i in range(num_splits)]

def prepare_split_transactions(
    reference_id: str, 
    amount: float, 
    max_amount: float,
    **transaction_data
) -> List[Dict[str, Any]]:
    """
    Prepare the data for split transactions.
    
    This function:
    1. Always creates a consistent split transaction structure, even for amounts below max_amount
    2. Generates unique reference IDs for each split using the format: original-XX 
    3. For amounts > max_amount, creates multiple splits with max_amount, with remainder in the last split
       Example: 120,000 with max 50,000 → splits of 50,000, 50,000, 20,000
    
    Args:
        reference_id (str): The original reference ID
        amount (float): The total transaction amount (original amount before any fee deduction)
        max_amount (float): The maximum amount allowed per transaction
        **transaction_data: Additional transaction data like callback_url, payer_id, etc.
        
    Returns:
        List[Dict[str, Any]]: A list of transaction data with split amounts and reference IDs
                             Each contains amount, reference_id, split_number, split_total, etc.
    
    Note: 
        The fee deduction should be applied separately, typically to the last split.
        This function only handles the splitting logic based on the original amount.
    """
    # Even if amount is less than max, we still create a split structure
    # for consistency, but with only one split
    if amount <= max_amount:
        # Generate a split reference ID even for single transactions
        split_reference_id = generate_split_reference_ids(reference_id, 1)[0]
        
        return [{
            **transaction_data, 
            'reference_id': split_reference_id,  # Use the generated split reference ID
            'amount': int(amount),  # Convert to integer 
            'split_number': 1,
            'split_total': 1,
            'original_amount': amount,
            'parent_reference_id': reference_id
        }]
    
    # Split the amount
    split_amounts = split_transaction_amount(amount, max_amount)
    num_splits = len(split_amounts)
    
    # Generate reference IDs for each split
    split_reference_ids = generate_split_reference_ids(reference_id, num_splits)
    
    # Prepare the split transactions
    split_transactions = []
    for i, (split_amount, split_ref_id) in enumerate(zip(split_amounts, split_reference_ids)):
        split_transactions.append({
            **transaction_data,
            'reference_id': split_ref_id,
            'amount': int(split_amount),  # Ensure amount is an integer
            'split_number': i + 1,
            'split_total': num_splits,
            'original_amount': amount,
            'parent_reference_id': reference_id
        })
    
    return split_transactions
