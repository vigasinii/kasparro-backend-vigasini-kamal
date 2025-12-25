from pydantic import BaseModel, Field, field_validator
from typing import Optional, Any
from datetime import datetime


class CoinPaprikaSchema(BaseModel):
    """Schema for CoinPaprika API data"""
    coin_id: str = Field(..., alias="id")
    name: str
    symbol: str
    rank: Optional[int] = None
    price_usd: Optional[float] = Field(None, alias="price_usd")
    volume_24h_usd: Optional[float] = Field(None, alias="volume_24h_usd")
    market_cap_usd: Optional[float] = Field(None, alias="market_cap_usd")
    percent_change_24h: Optional[float] = Field(None, alias="percent_change_24h")
    
    @field_validator('price_usd', 'volume_24h_usd', 'market_cap_usd', 'percent_change_24h', mode='before')
    @classmethod
    def validate_numeric(cls, v):
        if v is None or v == '':
            return None
        try:
            return float(v)
        except (ValueError, TypeError):
            return None
    
    class Config:
        populate_by_name = True


class CoinGeckoSchema(BaseModel):
    """Schema for CoinGecko API data"""
    coin_id: str = Field(..., alias="id")
    name: str
    symbol: str
    current_price: Optional[float] = None
    market_cap: Optional[float] = None
    total_volume: Optional[float] = None
    price_change_24h: Optional[float] = None
    price_change_percentage_24h: Optional[float] = None
    
    @field_validator('current_price', 'market_cap', 'total_volume', 'price_change_24h', 'price_change_percentage_24h', mode='before')
    @classmethod
    def validate_numeric(cls, v):
        if v is None or v == '':
            return None
        try:
            return float(v)
        except (ValueError, TypeError):
            return None
    
    class Config:
        populate_by_name = True


class CSVSchema(BaseModel):
    """Schema for CSV data"""
    coin_id: str
    name: str
    symbol: str
    price: Optional[float] = None
    market_cap: Optional[float] = None
    volume: Optional[float] = None
    
    @field_validator('price', 'market_cap', 'volume', mode='before')
    @classmethod
    def validate_numeric(cls, v):
        if v is None or v == '':
            return None
        try:
            return float(v)
        except (ValueError, TypeError):
            return None


class UnifiedCryptoSchema(BaseModel):
    """Unified schema for all cryptocurrency data"""
    coin_id: str
    name: str
    symbol: str
    price_usd: Optional[float] = None
    market_cap_usd: Optional[float] = None
    volume_24h_usd: Optional[float] = None
    price_change_24h_percent: Optional[float] = None
    rank: Optional[int] = None
    source: str
    source_updated_at: Optional[datetime] = None


class CryptoResponse(BaseModel):
    """API response schema for cryptocurrency data"""
    id: int
    coin_id: str
    name: str
    symbol: str
    price_usd: Optional[float]
    market_cap_usd: Optional[float]
    volume_24h_usd: Optional[float]
    price_change_24h_percent: Optional[float]
    rank: Optional[int]
    source: str
    updated_at: datetime
    
    class Config:
        from_attributes = True


class DataResponse(BaseModel):
    """Paginated data response"""
    data: list[CryptoResponse]
    total: int
    page: int
    page_size: int
    request_id: str
    api_latency_ms: float


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    database: str
    etl_status: dict[str, Any]
    timestamp: datetime


class StatsResponse(BaseModel):
    """ETL statistics response"""
    source: str
    records_processed: int
    last_success: Optional[datetime]
    last_failure: Optional[datetime]
    last_run_duration_seconds: Optional[float]
    total_runs: int
    success_rate: float


class ETLRunResponse(BaseModel):
    """ETL run details response"""
    run_id: str
    source_name: str
    status: str
    records_processed: int
    records_failed: int
    duration_seconds: Optional[float]
    started_at: datetime
    completed_at: Optional[datetime]
    error_message: Optional[str]
    
    class Config:
        from_attributes = True
