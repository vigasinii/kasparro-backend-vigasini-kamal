from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean, JSON, Index
from sqlalchemy.sql import func
from core.database import Base


class RawCoinPaprika(Base):
    """Raw data from CoinPaprika API"""
    __tablename__ = "raw_coinpaprika"
    
    id = Column(Integer, primary_key=True, index=True)
    coin_id = Column(String(100), nullable=False, index=True)
    name = Column(String(255))
    symbol = Column(String(50))
    rank = Column(Integer)
    price_usd = Column(Float)
    volume_24h_usd = Column(Float)
    market_cap_usd = Column(Float)
    percent_change_24h = Column(Float)
    raw_data = Column(JSON)
    ingested_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    __table_args__ = (
        Index('idx_coinpaprika_coin_time', 'coin_id', 'ingested_at'),
    )


class RawCoinGecko(Base):
    """Raw data from CoinGecko API"""
    __tablename__ = "raw_coingecko"
    
    id = Column(Integer, primary_key=True, index=True)
    coin_id = Column(String(100), nullable=False, index=True)
    name = Column(String(255))
    symbol = Column(String(50))
    current_price = Column(Float)
    market_cap = Column(Float)
    total_volume = Column(Float)
    price_change_24h = Column(Float)
    price_change_percentage_24h = Column(Float)
    raw_data = Column(JSON)
    ingested_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    __table_args__ = (
        Index('idx_coingecko_coin_time', 'coin_id', 'ingested_at'),
    )


class RawCSV(Base):
    """Raw data from CSV source"""
    __tablename__ = "raw_csv"
    
    id = Column(Integer, primary_key=True, index=True)
    coin_id = Column(String(100), nullable=False, index=True)
    name = Column(String(255))
    symbol = Column(String(50))
    price = Column(Float)
    market_cap = Column(Float)
    volume = Column(Float)
    raw_data = Column(JSON)
    ingested_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    __table_args__ = (
        Index('idx_csv_coin_time', 'coin_id', 'ingested_at'),
    )


class UnifiedCrypto(Base):
    """Unified cryptocurrency data from all sources"""
    __tablename__ = "unified_crypto"
    
    id = Column(Integer, primary_key=True, index=True)
    coin_id = Column(String(100), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    symbol = Column(String(50), nullable=False, index=True)
    price_usd = Column(Float)
    market_cap_usd = Column(Float)
    volume_24h_usd = Column(Float)
    price_change_24h_percent = Column(Float)
    rank = Column(Integer)
    source = Column(String(50), nullable=False, index=True)
    source_updated_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        Index('idx_unified_coin_source', 'coin_id', 'source'),
        Index('idx_unified_symbol', 'symbol'),
    )


class ETLCheckpoint(Base):
    """Track ETL ingestion checkpoints for incremental loading"""
    __tablename__ = "etl_checkpoint"
    
    id = Column(Integer, primary_key=True, index=True)
    source_name = Column(String(100), nullable=False, unique=True, index=True)
    last_processed_id = Column(String(255))
    last_processed_timestamp = Column(DateTime(timezone=True))
    records_processed = Column(Integer, default=0)
    last_run_status = Column(String(50))  # success, failure, in_progress
    last_error = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ETLRun(Base):
    """Track ETL run metadata"""
    __tablename__ = "etl_run"
    
    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String(100), nullable=False, unique=True, index=True)
    source_name = Column(String(100), nullable=False, index=True)
    status = Column(String(50), nullable=False)  # started, success, failed
    records_processed = Column(Integer, default=0)
    records_failed = Column(Integer, default=0)
    duration_seconds = Column(Float)
    error_message = Column(Text)
    run_metadata = Column(JSON)
    started_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    completed_at = Column(DateTime(timezone=True))
    
    __table_args__ = (
        Index('idx_etl_run_source_status', 'source_name', 'status'),
    )


class SchemaDrift(Base):
    """Track schema changes detected in source data"""
    __tablename__ = "schema_drift"
    
    id = Column(Integer, primary_key=True, index=True)
    source_name = Column(String(100), nullable=False, index=True)
    drift_type = Column(String(50))  # new_field, missing_field, type_change
    field_name = Column(String(255))
    expected_type = Column(String(100))
    actual_type = Column(String(100))
    confidence_score = Column(Float)
    sample_value = Column(Text)
    detected_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    resolved = Column(Boolean, default=False)
