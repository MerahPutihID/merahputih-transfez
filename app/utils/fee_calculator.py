"""
Transaction Fee Calculator
-------------------------
Calculates transaction fees based on customer tier rules.

Features:
- Single-tier match: pick the one tier whose range contains the amount
  (max_amount NULL = unbounded above)
- Support for percentage and nominal fee types (mixable across tiers)
- VAT on top of the base tier fee when tier_rules.vat > 0
- Configurable safety cap on total fees (MAX_FEE_PERCENTAGE)
"""

import logging
from uuid import UUID
from datetime import datetime
from sqlalchemy import text
from app.database import get_db
from app.config.base import BaseConfig

logger = logging.getLogger(__name__)

# Load configuration settings
settings = BaseConfig()

def calculate_transaction_fee(customer_id, amount):
    """
    Calculate transaction fee based on customer tier rules.

    Single-tier match: pick the ONE tier whose range contains the amount
    (max_amount NULL = unbounded above). Tier fee can be nominal (fixed) or
    percentage of the whole amount. VAT is applied on top of the base fee
    when tier_rules.vat > 0: vat_amount = base_fee * (vat / 100).

    Args:
        customer_id (str or UUID): Customer's unique identifier
        amount (float): Original transaction amount

    Returns:
        dict: {
            "deduction_amount": final fee (base + VAT, capped by MAX_FEE_PERCENTAGE),
            "final_amount": amount - deduction_amount,
            "vat": tier vat percentage,
            "vat_amount": VAT computed on the base fee,
            "deduction_amount_pre": base tier fee before VAT,
        }
    """
    # Convert amount to float for calculation
    try:
        amount_float = float(amount)
    except (ValueError, TypeError):
        raise ValueError(f"Invalid amount format: {amount}")

    # Get database session
    db = next(get_db())

    try:
        # Use raw SQL query to find applicable fee based on tier rules
        try:
            # Convert customer_id to string for the query
            customer_id_str = str(customer_id)

            logger.info(f"Calculating fee: customer={customer_id_str}, amount={amount_float}")

            # Raw SQL query to get fee based on tier rules
            query = text("""
                SELECT tr.tier_type, tr.fee, tr.min_amount, tr.max_amount, tr.vat
                FROM deduction_management.ddt_customers dc
                JOIN deduction_management.tier_rule_assignments tra ON dc.customer_id = tra.customer_id  and dc.is_deleted = false and tra.is_deleted = false
                JOIN deduction_management.tier_rules tr ON tra.tier_rule_id = tr.id and tr.is_deleted = false
                WHERE tra.customer_id = :customer_id
                AND NOW() BETWEEN tr.valid_from AND tr.valid_to
                AND dc.charging_method_type = 'AUTO_DEDUCT'
                ORDER BY tr.min_amount DESC
            """)

            # Execute the query with parameters
            results = db.execute(query, {"customer_id": customer_id_str}).fetchall()

            fee_amount = 0.0
            vat = 0.0
            vat_amount = 0.0
            deduction_amount_pre = 0.0

            if not results:
                # No matching tier rules found, use default fee (0)
                logger.info(f"No tier rules found for customer {customer_id}")
            else:
                logger.info(f"Found {len(results)} tier rules")

                # Single-tier match: results sorted by min_amount DESC, pick the
                # highest tier whose range contains the amount. max_amount NULL
                # means unbounded above, so any amount >= min_amount matches.
                for tier_type, fee, min_amount, max_amount, tier_vat in results:
                    if amount_float < min_amount:
                        continue
                    if max_amount is not None and amount_float > max_amount:
                        continue

                    if tier_type == "percentage":
                        base_fee = amount_float * (fee / 100.0)
                    elif tier_type == "nominal":
                        base_fee = fee
                    else:
                        logger.warning(f"Unknown tier type: {tier_type}")
                        continue

                    deduction_amount_pre = base_fee
                    vat = float(tier_vat or 0.0)
                    if vat > 0:
                        vat_amount = base_fee * (vat / 100.0)

                    fee_amount = base_fee + vat_amount

                    logger.info(
                        f"Matched tier (type={tier_type}, min={min_amount}, max={max_amount}): "
                        f"base_fee={base_fee}, vat={vat}%, vat_amount={vat_amount}, total_fee={fee_amount}"
                    )
                    break
                else:
                    logger.warning(f"Amount {amount_float:,} does not fall within any tier range")
        except Exception as e:
            # Handle any database errors gracefully
            logger.error(f"Fee calculation error: {str(e)}")
            fee_amount = 0.0

        # Ensure fee doesn't exceed the configured maximum percentage of the transaction amount
        max_fee_percentage = settings.MAX_FEE_PERCENTAGE / 100.0  # Convert percentage to decimal
        max_fee = amount_float * max_fee_percentage
        if fee_amount > max_fee:
            logger.warning(f"Fee {fee_amount} exceeds max {max_fee} ({settings.MAX_FEE_PERCENTAGE}%), capping")
            fee_amount = max_fee

        # Calculate final amount
        final_amount = amount_float - fee_amount

        # Log the final calculation results
        logger.info(f"Final: Amount={amount_float}, Fee={fee_amount}, Final={final_amount}")

        return {
            "deduction_amount": round(fee_amount, 2),
            "final_amount": round(final_amount, 2),
            "vat": vat,
            "vat_amount": round(vat_amount, 2),
            "deduction_amount_pre": round(deduction_amount_pre, 2),
        }

    finally:
        db.close()


# BACKUP PERHITUNGAN YG LAMA, TAPI MASIH BISA DIGUNAKAN UNTUK REFERENSI
# def calculate_transaction_fee(customer_id, amount):
#     """
#     Calculate transaction fee based on customer tier rules.

#     Args:
#         customer_id (str or UUID): Customer's unique identifier
#         amount (float): Original transaction amount

#     Returns:
#         tuple: (fee_amount, final_amount) rounded to 2 decimal places
#     """
#     # Convert amount to float for calculation
#     try:
#         amount_float = float(amount)
#     except (ValueError, TypeError):
#         raise ValueError(f"Invalid amount format: {amount}")

#     # Get database session
#     db = next(get_db())

#     try:
#         # Use raw SQL query to find applicable fee based on tier rules
#         try:
#             # Convert customer_id to string for the query
#             customer_id_str = str(customer_id)

#             logger.info(f"Calculating fee: customer={customer_id_str}, amount={amount_float}")

#             # Raw SQL query to get fee based on tier rules
#             query = text("""
#                 SELECT tr.tier_type, tr.fee, tr.min_amount, tr.max_amount
#                 FROM deduction_management.ddt_customers dc
#                 JOIN deduction_management.tier_rule_assignments tra ON dc.customer_id = tra.customer_id  and dc.is_deleted = false and tra.is_deleted = false
#                 JOIN deduction_management.tier_rules tr ON tra.tier_rule_id = tr.id AND dc.deduction_active_type = tr.tier_type and tr.is_deleted = false
#                 WHERE tra.customer_id = :customer_id
#                 AND NOW() BETWEEN tr.valid_from AND tr.valid_to
#                 ORDER BY tr.min_amount DESC
#             """)

#             # Execute the query with parameters
#             results = db.execute(query, {"customer_id": customer_id_str}).fetchall()

#             fee_amount = 0.0

#             if results:
#                 logger.info(f"Found {len(results)} tier rules")

#                 # High-to-low tier processing: apply tiers from highest to lowest
#                 # Each tier can be applied multiple times until transaction amount is consumed
#                 fee_amount = 0.0
#                 tiers_applied = []
#                 remaining_amount = amount_float

#                 # Process tiers from high to low (results already sorted by min_amount DESC)
#                 i = 0
#                 while remaining_amount > 0 and i < len(results):
#                     tier_type, fee, min_amount, max_amount = results[i]

#                     # Check if remaining amount falls within or above this tier's range
#                     if remaining_amount >= min_amount:
#                         # This tier applies - calculate how much to charge and subtract

#                         tier_fee = 0.0
#                         amount_to_subtract = 0.0

#                         if tier_type == "percentage":
#                             # For percentage: apply to the portion that fits in this tier
#                             applicable_amount = min(remaining_amount, max_amount)
#                             tier_fee = applicable_amount * (fee / 100.0)
#                             amount_to_subtract = applicable_amount

#                         elif tier_type == "nominal":
#                             # For nominal: apply the fixed fee
#                             tier_fee = fee
#                             # Subtract the tier's max range amount (or remaining if less)
#                             amount_to_subtract = min(remaining_amount, max_amount)

#                         else:
#                             # Unknown tier type
#                             logger.warning(f"Unknown tier type: {tier_type}")
#                             i += 1  # Move to next tier
#                             continue

#                         # Apply this tier
#                         fee_amount += tier_fee
#                         remaining_amount -= amount_to_subtract

#                         # Track for logging
#                         tiers_applied.append({
#                             "tier": f"Tier {len(results)-i} ({tier_type}:{min_amount:,}-{max_amount:,})",
#                             "fee": tier_fee,
#                             "subtracted": amount_to_subtract,
#                             "remaining": remaining_amount
#                         })

#                         logger.debug(f"Applied Tier {len(results)-i}: fee={tier_fee}, subtracted={amount_to_subtract:,}, remaining={remaining_amount:,}")

#                     else:
#                         # Remaining amount is less than this tier's min_amount, move to next tier
#                         i += 1

#                 # Log the tiers applied
#                 if tiers_applied:
#                     logger.info(f"Applied {len(tiers_applied)} tier applications:")
#                     for tier_info in tiers_applied:
#                         logger.info(f"  {tier_info['tier']}: +{tier_info['fee']} (subtracted {tier_info['subtracted']:,}, remaining {tier_info['remaining']:,})")
#                     logger.info(f"Total fee: {fee_amount}")
#                 else:
#                     logger.info("No tiers applicable for this amount")

#                 # If there's still remaining amount, log a warning
#                 if remaining_amount > 0:
#                     logger.warning(f"Remaining amount {remaining_amount:,} could not be processed by any tier")
#             else:
#                 # No matching tier rules found, use default fee (0)
#                 logger.info(f"No tier rules found for customer {customer_id}")
#                 fee_amount = 0.0
#         except Exception as e:
#             # Handle any database errors gracefully
#             logger.error(f"Fee calculation error: {str(e)}")
#             fee_amount = 0.0

#         # Ensure fee doesn't exceed the configured maximum percentage of the transaction amount
#         max_fee_percentage = settings.MAX_FEE_PERCENTAGE / 100.0  # Convert percentage to decimal
#         max_fee = amount_float * max_fee_percentage
#         if fee_amount > max_fee:
#             logger.warning(f"Fee {fee_amount} exceeds max {max_fee} ({settings.MAX_FEE_PERCENTAGE}%), capping")
#             fee_amount = max_fee

#         # Calculate final amount
#         final_amount = amount_float - fee_amount

#         # Log the final calculation results
#         logger.info(f"Final: Amount={amount_float}, Fee={fee_amount}, Final={final_amount}")

#         return round(fee_amount, 2), round(final_amount, 2)

#     finally:
#         db.close()
