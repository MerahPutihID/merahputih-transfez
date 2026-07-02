"""Lookup Virtual Account number from machine VA table (public.cdt_machine_virtual_account)."""

from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import MachineVirtualAccount


def get_va_number_by_machine_id(db: Session, machine_id: Optional[UUID]) -> Optional[str]:
    """Resolve VA number from cdt_machine.id."""
    if machine_id is None:
        return None

    row = (
        db.query(MachineVirtualAccount.va_number)
        .filter(MachineVirtualAccount.machine_id == machine_id)
        .first()
    )
    return row[0] if row else None
