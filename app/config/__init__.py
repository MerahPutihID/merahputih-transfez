import os
from functools import lru_cache
from app.config.base import BaseConfig
from app.config.development import DevelopmentConfig
from app.config.production import ProductionConfig

def clear_environment():
    """Clear environment variables used by the application."""
    env_vars = [
        # "APP_ENV",
        "DATABASE_URL",
        "THIRD_PARTY_API_URL",
        "THIRD_PARTY_API_KEY",
        "API_BASE_URL",
        "GATEWAY_PUBLIC_URL",
        "SENDER_FIRSTNAME",
        "SENDER_LASTNAME",
        "SENDER_COUNTRY_ISO_CODE",
        "COMPLIANCE_SOURCE_OF_FUNDS",
        "COMPLIANCE_BENEFICIARY_RELATIONSHIPS",
        "COMPLIANCE_PURPOSE_OF_REMITTANCES",
        "BALANCE_ID"
    ]
    
    for var in env_vars:
        if var in os.environ:
            del os.environ[var]

@lru_cache()
def get_settings():
    """Get cached settings based on environment."""
    env = os.getenv("APP_ENV", "development")
    
    config_class = {
        "development": DevelopmentConfig,
        "production": ProductionConfig
    }.get(env, DevelopmentConfig)
    
    return config_class()

# Export what you need
__all__ = ['BaseConfig', 'get_settings', 'clear_environment']

# Clear settings cache and get fresh settings
get_settings.cache_clear()
settings = get_settings()