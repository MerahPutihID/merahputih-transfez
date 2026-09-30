import uuid
import json
from sqlalchemy import Boolean, Column, Integer, String, Text, DateTime, Date, Time, UUID, ForeignKey, Float, JSON, Numeric
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
from uuid import uuid4

# Note: This service only actively manages the Log model.
# All other models are included for reference and mapping to external tables
# but are managed by other services.

class Transaction(Base):
    __tablename__ = "processed_transactions"
    __table_args__ = {'extend_existing': True}  # Add this for existing table

    id = id = Column(UUID(as_uuid=True), primary_key=True)
    processed_on = Column(String, nullable=True)

class Queue(Base):
    __tablename__ = "cdt_nak_trx"
    __table_args__ = {'extend_existing': True}

    id = Column(String, primary_key=True)
    cd_trx_cdm_id = Column(UUID(as_uuid=True), nullable=True)
    trxrefno = Column(String, nullable=True)
    jwt_data = Column(Text, nullable=True)
    status = Column(String, nullable=True)
    external_response = Column(Text, nullable=True)
    insert_on = Column(String, nullable=True)
    update_on = Column(String, nullable=True)

class CDTMachine(Base):
    """Reference model for cdt_machine table (managed externally)"""
    __tablename__ = "cdt_machine"
    __table_args__ = {'extend_existing': True}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    code = Column(String(255), unique=True, index=True)
    description = Column(String(255))
    name = Column(String(255))
    maintenance_id = Column(UUID(as_uuid=True), nullable=True)
    payment_gateway_id = Column(UUID(as_uuid=True), nullable=True)
    is_direct = Column(Boolean, nullable=True)
    direct_type = Column(String(30), nullable=True)

class Log(Base):
    __tablename__ = "cdt_gateway_transaction_log"
    __table_args__ = {'extend_existing': True}

    # This is the only model actively managed by this service's schema updater
    # All other models are managed by external services

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    cdt_trx_cdm_id = Column(UUID(as_uuid=True), index=True)
    reference_id = Column(String(255), index=True, unique=True)
    transaction_id = Column(Integer, index=True)
    status = Column(String, index=True)  # success, failed
    state = Column(String)  # pending, success, failed
    create_request = Column(Text)
    create_response = Column(Text)
    confirm_response = Column(Text)
    callback_data = Column(Text)
    # Split transaction fields
    split_number = Column(Integer, nullable=True)  # Which split is this (1, 2, etc.)
    split_total = Column(Integer, nullable=True)   # Total number of splits
    original_amount = Column(Float, nullable=True)  # Original amount before splitting
    parent_reference_id = Column(String(255), nullable=True)  # Original reference ID for split transactions
    # Transaction fee fields
    deduction_amount = Column(Float, nullable=True)  # Transaction fee amount (base fee + VAT)
    deduction_amount_pre = Column(Float, nullable=True)  # Base tier fee before VAT
    vat = Column(Float, nullable=True)  # VAT percentage from tier_rules
    vat_amount = Column(Float, nullable=True)  # Computed VAT on the base fee
    final_amount = Column(Float, nullable=True)  # Final amount after deduction
    amount = Column(Float, nullable=True)  # Original amount for this specific request to 3rd-party
    retry_count = Column(Integer, nullable=True, default=0)  # Failed transfer retry attempts
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class VALog(Base):
    """Callback audit log for Transfez Virtual Account events."""

    __tablename__ = "cdt_va_callback_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    transfez_id = Column(Integer, index=True, nullable=True)
    va_number_id = Column(Integer, nullable=True)
    va_status = Column(String(64), index=True, nullable=True)
    va_number = Column(String(32), index=True, nullable=True)
    partner_trx_id = Column(String(255), index=True, nullable=True)
    bank_code = Column(String(16), nullable=True)
    amount = Column(Float, nullable=True)
    amount_detected = Column(Float, nullable=True)
    success = Column(String(16), nullable=True)
    tx_date = Column(String(64), nullable=True)
    payload_shape = Column(String(32), nullable=True)  # flat | payment
    raw_payload = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

class TransactionDetail(Base):
    __tablename__ = "cdt_trx_cdm"
    __table_args__ = {'extend_existing': True}

    id = Column(UUID(as_uuid=True), primary_key=True)
    created_on = Column(DateTime(6))
    updated_on = Column(DateTime(6))

    amount = Column(String(255), nullable=False)
    cdm_trx_date = Column(Date)
    cdm_trx_datetime = Column(DateTime(6))
    cdm_trx_no = Column(String(255))
    cdm_trx_time = Column(Time(6))
    cdm_trx_type = Column(String(255))
    machine_info = Column(String(255))
    signature = Column(String(255))
    status = Column(String(255))
    token = Column(String(255))

    beneficiary_account_id = Column(UUID(as_uuid=True))
    code_id = Column(UUID(as_uuid=True))
    machine_id = Column(UUID(as_uuid=True))
    service_product_id = Column(UUID(as_uuid=True))
    service_transaction_id = Column(UUID(as_uuid=True))
    user_id = Column(UUID(as_uuid=True))
    pjpur_status = Column(String(255))

class BeneficiaryAccount(Base):
    __tablename__ = "cdt_beneficiary_account"
    __table_args__ = {'extend_existing': True}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    account_name = Column(String(255))
    account_number = Column(String(255))
    firstname = Column(String(255))
    lastname = Column(String(255))
    account_type = Column(String(255))
    bank_id = Column(UUID(as_uuid=True))
    branch_id = Column(UUID(as_uuid=True))
    country_code = Column(String(255))
    customer_id = Column(UUID(as_uuid=True))
    customer_status = Column(String(255))
    customer_type = Column(String(255))
    cr_code_id = Column(UUID(as_uuid=True))
    region_code = Column(String(255))


class MerchantAccount(Base):
    """Reference model for custmp.m_account (managed by Portal Account Management)."""

    __tablename__ = "m_account"
    __table_args__ = {"schema": "custmp", "extend_existing": True}

    id = Column(UUID(as_uuid=True), primary_key=True)
    account_no = Column(String(30), nullable=True)
    uuid_be = Column(String(255), nullable=True)


class MerchantVirtualAccount(Base):
    """Reference model for custmp.m_account_virtual_account (managed by Portal)."""

    __tablename__ = "m_account_virtual_account"
    __table_args__ = {"schema": "custmp", "extend_existing": True}

    id = Column(UUID(as_uuid=True), primary_key=True)
    account_id = Column(UUID(as_uuid=True), index=True)
    account_no = Column(String(30))
    va_number = Column(String(50))


class MachineVirtualAccount(Base):
    """Reference model for public.cdt_machine_virtual_account (managed by Portal)."""

    __tablename__ = "cdt_machine_virtual_account"
    __table_args__ = {"schema": "public", "extend_existing": True}

    id = Column(UUID(as_uuid=True), primary_key=True)
    machine_id = Column(UUID(as_uuid=True), index=True)
    machine_code = Column(String(50))
    va_number = Column(String(50))


class BeneficiaryAccountTemp(Base):
    """Temp beneficiary accounts awaiting bank validation (managed by this service)."""

    __tablename__ = "cdt_beneficiary_account_temp"
    __table_args__ = {"extend_existing": True}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    created_by = Column(String(255))
    created_on = Column(DateTime(6))
    deleted_at = Column(DateTime(6))
    updated_by = Column(String(255))
    updated_on = Column(DateTime(6))
    account_name = Column(String(255))
    account_number = Column(String(255))
    firstname = Column(String(255))
    lastname = Column(String(255))
    account_type = Column(String(255))
    bank_id = Column(UUID(as_uuid=True))
    branch_id = Column(UUID(as_uuid=True))
    country_code = Column(String(255))
    customer_id = Column(UUID(as_uuid=True))
    customer_status = Column(String(255))
    customer_type = Column(String(255))
    cr_code_id = Column(UUID(as_uuid=True))
    region_code = Column(String(255))
    validated_bank = Column(String(16))  #  'true' | 'false' | NULL
    validated_bank_on = Column(DateTime)
    validated_mp = Column(String(16))
    validated_mp_on = Column(DateTime)
    validated_mp_by = Column(String(100))
    request_approval = Column(String(16))
    request_approval_on = Column(DateTime)
    request_approval_by = Column(String(100))
    account_number_bank = Column(String(255))
    account_name_bank = Column(String(255))
    inquiry_key = Column(String(255))
    error_code = Column(String(255))
    error_response = Column(String(255))
    status = Column(String(255))


class JackBankInquiryLog(Base):
    """Audit log for Jack /validation_bank_account API calls."""

    __tablename__ = "jack_transaction_bank_inquiry_log"
    __table_args__ = {"extend_existing": True}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    cdt_beneficiary_account_id = Column(UUID(as_uuid=True), index=True)
    inquiry_key = Column(String(255), index=True)
    status = Column(String)
    create_request = Column(Text)
    create_response = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class Commission(Base):
    """Per-transaction commission snapshot from the customer hierarchy (managed by this service)."""

    __tablename__ = "cdt_commision"
    __table_args__ = {"extend_existing": True}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    cdt_trx_cdm_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    customer_id = Column(UUID(as_uuid=True), nullable=False)
    commission_type = Column(String(50), nullable=False)
    commission_rate = Column(Numeric(5, 2))
    rate_type = Column(String(50))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class Bank(Base):
    __tablename__ = "cdt_bank"
    __table_args__ = {'extend_existing': True}

    id = Column(UUID(as_uuid=True), primary_key=True)
    building = Column(String(255))
    city = Column(String(255))
    country = Column(String(255))
    region = Column(String(255))
    state = Column(String(255))
    street = Column(String(255))
    zip_code = Column(String(255))
    code = Column(String(255))
    name = Column(String(255))
    bank_payer_id = Column(Integer)

class CDTAdvTransaction(Base):
    __tablename__ = "cdt_adv_transactions"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    reference_id = Column(String(255), unique=True, index=True)
    transaction_type = Column(String(255), nullable=False)
    status = Column(String(255), nullable=False)
    amount = Column(String(255), nullable=False)
    denomination_details = Column(Text, nullable=True)
    request_data = Column(Text, nullable=True)
    response_data = Column(Text, nullable=True)
    http_request = Column(Text, nullable=True)
    http_response = Column(Text, nullable=True)
    callback_data = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Virtual relationship to TransactionDetail based on reference_id = cdm_trx_no
    transaction_detail = relationship(
        "TransactionDetail",
        primaryjoin="CDTAdvTransaction.reference_id == foreign(TransactionDetail.cdm_trx_no)",
        uselist=False,
        viewonly=True
    )

class BijakTransaction(Base):
    """Reference model for cdt_bijak_transaction (managed by Bijak service)."""

    __tablename__ = "cdt_bijak_transaction"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    reference_id = Column(String(255), unique=True, index=True)
    transaction_type = Column(String(50), nullable=False)
    amount = Column(Float, nullable=False)
    denomination_details = Column(JSON, nullable=True)
    status = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=True)
    request_data = Column(JSON, nullable=True)
    response_data = Column(JSON, nullable=True)
    http_request = Column(JSON, nullable=True)
    http_response = Column(JSON, nullable=True)
    error_message = Column(String(255), nullable=True)
    retry_count = Column(Integer, nullable=True)
    processed_at = Column(DateTime(timezone=True), nullable=True)

    transaction_detail = relationship(
        "TransactionDetail",
        primaryjoin="BijakTransaction.reference_id == foreign(TransactionDetail.cdm_trx_no)",
        uselist=False,
        viewonly=True,
    )


class PjpurTagTransaction(Base):
    __tablename__ = "pjpur_tag_transactions"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    reference_id = Column(String(255), nullable=True, index=True)
    transaction_type = Column(String(255), nullable=False)  # transactiontype enum
    amount = Column(Float, nullable=False)
    denomination_details = Column(JSON, nullable=True)
    status = Column(String(255), nullable=False)  # transactionstatus enum
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=True)
    request_data = Column(JSON, nullable=True)
    response_data = Column(JSON, nullable=True)
    callback_data = Column(JSON, nullable=True)
    http_request = Column(JSON, nullable=True)
    http_response = Column(JSON, nullable=True)
    error_message = Column(String(255), nullable=True)
    retry_count = Column(Integer, nullable=True)
    processed_at = Column(DateTime(timezone=True), nullable=True)

    # Virtual relationship to TransactionDetail based on reference_id = cdm_trx_no
    transaction_detail = relationship(
        "TransactionDetail",
        primaryjoin="PjpurTagTransaction.reference_id == foreign(TransactionDetail.cdm_trx_no)",
        uselist=False,
        viewonly=True
    )

class Deduction(Base):
    __tablename__ = "deductions"
    __table_args__ = {'extend_existing': True}

    # Note: This model is managed by another service and is included here for reference.
    # Changes here should reflect the actual database structure.

    id = Column(UUID(as_uuid=True), primary_key=True)
    customer_id = Column(String(255), nullable=False)  # Changed from UUID to String to match actual DB type
    deduction_active_type = Column(String, nullable=False)  # PERCENT or NOMINAL
    value_percentage = Column(Float, nullable=True)
    value_nominal = Column(Float, nullable=True)
    created_on = Column(DateTime, nullable=True)
    updated_on = Column(DateTime, nullable=True)
    last_update_history = Column(JSON, nullable=True)

