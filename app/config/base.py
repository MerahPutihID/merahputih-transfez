from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import ConfigDict, field_validator
from functools import lru_cache
from enum import Enum

class EnvironmentType(str, Enum):
    DEVELOPMENT = "development"
    PRODUCTION = "production"

class BaseConfig(BaseSettings):
    model_config = ConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra='allow',
    )
    
    LOG_LEVEL: str = "INFO"
    HTTP_DEBUG: bool = False

    ENV: EnvironmentType = EnvironmentType.DEVELOPMENT
    APP_NAME: str = "CDT Gateway Service"
    DEBUG: bool = False

    # Database settings
    DATABASE_URL: str

    # Third party API settings
    THIRD_PARTY_API_URL: str

    # Queue processing settings
    QUEUE_PROCESSING_TIME_THRESHOLD_HOURS: int = 6
    # NAK queue (cdt_nak_trx) — existing flow, enabled by default.
    ENABLE_NAK_QUEUE_PROCESSING: bool = True
    # Bijak COMPLETED deposit → local transfer (additional trigger for PJPUR Bijak machines).
    ENABLE_BIJAK_TRANSFER_PROCESSING: bool = True

    # Bank inquiry (Jack API) settings
    ENABLE_BANK_INQUIRY_PROCESSING: bool = False
    JACK_API_BASE_URL: str = "https://staging.api.disbursement.transfez.tech"
    JACK_API_KEY: str = ""
    JACK_INQUIRY_POLL_INTERVAL_SECONDS: int = 30

    # Failed local transfer retry (gateway log status FAILED)
    MAX_TRANSFER_RETRY_COUNT: int = 3
    TRANSFER_RETRY_INTERVAL_MINUTES: int = 5
    
    # Machine Filter Configuration
    MAINTENANCE_ID: str  # REQUIRED: Filter transactions by specific maintenance_id
    
    # Transaction splitting settings
    MAX_TRANSACTION_AMOUNT: int = 5000000  # Maximum amount per transaction in IDR
    
    # Fee calculation settings
    MAX_FEE_PERCENTAGE: int = 20  # Maximum fee as percentage of transaction amount (default 20%)
    
    # Declare all your config fields
    THIRD_PARTY_API_KEY: str
    # Base URL for remittance callbacks sent TO another BMP transaction service (not this app).
    API_BASE_URL: str
    # Public base URL of THIS merahputih-transfez service (for Transfez VA callbacks).
    GATEWAY_PUBLIC_URL: Optional[str] = None
    SENDER_FIRSTNAME: str
    SENDER_LASTNAME: str
    SENDER_COUNTRY_ISO_CODE: str
    COMPLIANCE_SOURCE_OF_FUNDS: str
    COMPLIANCE_BENEFICIARY_RELATIONSHIPS: str
    COMPLIANCE_PURPOSE_OF_REMITTANCES: str
    BALANCE_ID: int  # Change type from str to int

    # Transaction Settings
    TRANSFER_SERVICE_CODE: int = 1  # Default to 1 (Bi-FAST)
    NOTES: str = "BMPS-Deposit"  # Default notes

    # SQLAlchemy settings
    SQLALCHEMY_ECHO: bool = False  # Set to True to enable SQL debug logging
    SQLALCHEMY_POOL_SIZE: int = 5
    SQLALCHEMY_POOL_TIMEOUT: int = 30
    
    @field_validator('MAX_FEE_PERCENTAGE')
    @classmethod
    def validate_max_fee_percentage(cls, v):
        """Validate that maximum fee percentage is not larger than 100%"""
        if v > 100:
            raise ValueError(f"MAX_FEE_PERCENTAGE cannot be larger than 100%, got {v}%")
        if v < 0:
            raise ValueError(f"MAX_FEE_PERCENTAGE cannot be negative, got {v}%")
        return v