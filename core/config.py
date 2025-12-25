from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://kasparro:kasparro_pass@localhost:5432/kasparro_db"
    
    # API Keys
    coinpaprika_api_key: str = ""
    coingecko_api_key: str = ""
    
    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    
    # ETL Configuration
    etl_batch_size: int = 100
    etl_max_retries: int = 3
    
    # Logging
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()
