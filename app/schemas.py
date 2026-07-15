from pydantic import BaseModel, model_validator, Field
from typing import Optional, Dict, Any
from datetime import datetime
from uuid import UUID

class TransactionCreate(BaseModel):
    amount: int

class TransactionResponse(BaseModel):
    status: int
    data: "TransactionData"

class LogResponse(BaseModel):
    id: UUID
    cdt_trx_cdm_id: UUID
    reference_id: str
    transaction_id: Optional[int]
    status: str
    state: Optional[str]
    create_request: Optional[str]
    create_response: Optional[str]
    confirm_response: Optional[str]
    callback_data: Optional[str]
    # Split transaction fields
    split_number: Optional[int] = None
    split_total: Optional[int] = None
    original_amount: Optional[float] = None
    parent_reference_id: Optional[str] = None
    # Transaction fee fields
    deduction_amount: Optional[float] = None
    final_amount: Optional[float] = None
    amount: Optional[float] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True  # For Pydantic v2

class SenderInfo(BaseModel):
    firstname: str
    lastname: str
    country_iso_code: str

class SourceInfo(BaseModel):
    amount: Optional[str] = None
    currency: str
    country_iso_code: str

class DestinationInfo(BaseModel):
    amount: str
    currency: str

class BeneficiaryInfo(BaseModel):
    firstname: str
    lastname: str
    account: str

class ComplianceInfo(BaseModel):
    source_of_funds: str
    beneficiary_relationship: str
    purpose_of_remittance: str

class CallbackRequest(BaseModel):
    id: int
    reference_id: str
    state_id: int
    state: str
    amount: float


class CreateVARequest(BaseModel):
    partner_user_id: str = Field(..., description="Partner unique ID for specific user", examples=["testing-va"])
    bank_code: str = Field(..., description="Bank code based on Transfez bank list", examples=["022"])
    amount: int = Field(..., description="VA amount. Must be 0 when is_open=true", examples=[0])
    is_open: bool = Field(..., description="true=open amount, false=closed amount", examples=[True])
    is_single_use: bool = Field(..., description="true=single use, false=multiple use", examples=[False])
    is_lifetime: bool = Field(..., description="true=static VA, false=dynamic VA", examples=[True])
    expiration_time: int = Field(..., description="VA expiration time in minutes", examples=[50000])
    trx_expiration_time: Optional[int] = Field(
        default=None,
        description="Transaction expiration in minutes, must be lower than expiration_time",
        examples=[30000],
    )
    username_display: str = Field(..., description="Display name for VA", examples=["Transfez testing"])
    partner_trx_id: Optional[str] = Field(default=None, description="Partner unique identifier for VA", examples=["TRX0001"])
    virtual_account: Optional[str] = Field(
        default=None,
        description="Custom VA number for selected banks, must be 15 chars when provided",
        examples=["746100000000007"],
    )
    callback_url: Optional[str] = Field(
        default=None,
        description=(
            "URL where Transfez sends VA callbacks. "
            "If omitted, uses GATEWAY_PUBLIC_URL from .env + /va/callback/{partner_trx_id}. "
            "partner_trx_id must be provided when callback_url is omitted. "
            "(NOT API_BASE_URL — that is for remittance transaction callbacks)."
        ),
        examples=["http://localhost:8001/va/callback/251014-0001"],
    )

    @model_validator(mode="after")
    def validate_business_rules(self):
        if self.is_open and self.amount != 0:
            raise ValueError("amount must be 0 when is_open is true")

        if self.virtual_account and len(self.virtual_account) != 15:
            raise ValueError("virtual_account must be exactly 15 characters")

        if self.trx_expiration_time is not None and self.trx_expiration_time >= self.expiration_time:
            raise ValueError("trx_expiration_time must be lower than expiration_time")

        return self


class VACallbackResponse(BaseModel):
    status: str
    message: str
    id: UUID
    va_status: Optional[str] = None
    va_number: Optional[str] = None
    partner_trx_id: Optional[str] = None

class SenderResponse(BaseModel):
    firstname: str
    lastname: str
    country_iso_code: str

class SourceResponse(BaseModel):
    currency: str
    country_iso_code: str
    transfer_service_code: Optional[int] = None

class DestinationResponse(BaseModel):
    amount: str
    currency: str
    country_iso_code: str

class BeneficiaryResponse(BaseModel):
    firstname: str
    lastname: str
    country_iso_code: str
    account: str

class ComplianceResponse(BaseModel):
    source_of_funds: str
    beneficiary_relationship: str
    purpose_of_remittance: str

class TransactionData(BaseModel):
    id: int
    reference_id: str
    callback_url: str
    payer_id: int
    mode: str
    sender: SenderResponse
    source: SourceResponse
    destination: DestinationResponse
    beneficiary: BeneficiaryResponse
    compliance: ComplianceResponse
    created_at: str
    updated_at: str
    user_id: int
    state: str
    amount: int
    paid_at: Optional[str] = None
    rate: str
    fee: str
    partner_id: int
    completion_date: Optional[str] = None
    sent_amount: str
    state_id: Optional[int] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    notes: str
    transaction_type: str
    balance_id: int
    payment_channel: Optional[str] = None
    is_regenerated: bool
    receipt_url: Optional[str] = None