from .base import BaseConfig, EnvironmentType

class DevelopmentConfig(BaseConfig):
    ENV: EnvironmentType = EnvironmentType.DEVELOPMENT
    DEBUG: bool = True