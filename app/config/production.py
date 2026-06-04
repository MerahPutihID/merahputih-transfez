from .base import BaseConfig, EnvironmentType

class ProductionConfig(BaseConfig):
    ENV: EnvironmentType = EnvironmentType.PRODUCTION
    DEBUG: bool = False

    class Config:
        env_file = ".env.production"