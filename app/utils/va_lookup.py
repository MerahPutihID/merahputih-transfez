"""Lookup Virtual Account number from Portal tables (custmp schema)."""

from typing import Optional
from uuid import UUID

from sqlalchemy import cast
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Session

from app.models import BeneficiaryAccount, MerchantAccount, MerchantVirtualAccount


def get_va_number_by_customer_id(db: Session, customer_id: Optional[UUID]) -> Optional[str]:
    """Resolve VA number via m_account.uuid_be -> m_account_virtual_account."""
    if customer_id is None:
        return None

    row = (
        db.query(MerchantVirtualAccount.va_number)
        .join(MerchantAccount, MerchantVirtualAccount.account_id == MerchantAccount.id)
        .filter(cast(MerchantAccount.uuid_be, PGUUID) == customer_id)
        .first()
    )
    return row[0] if row else None


def get_va_number_for_beneficiary(db: Session, beneficiary_account_id: Optional[UUID]) -> Optional[str]:
    """Resolve VA number from cdt_beneficiary_account.id."""
    if beneficiary_account_id is None:
        return None

    beneficiary = (
        db.query(BeneficiaryAccount.customer_id)
        .filter(BeneficiaryAccount.id == beneficiary_account_id)
        .first()
    )
    if not beneficiary or not beneficiary.customer_id:
        return None

    return get_va_number_by_customer_id(db, beneficiary.customer_id)
