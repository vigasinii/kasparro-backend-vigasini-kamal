import requests
from typing import List
from datetime import datetime
from sqlalchemy.orm import Session
from ingestion.base import BaseIngestion
from core.models import RawCoinGecko, UnifiedCrypto
from schemas.crypto import CoinGeckoSchema
from core.config import get_settings
from core.logging_config import logger
import time

settings = get_settings()


class CoinGeckoIngestion(BaseIngestion):
    """Ingest data from CoinGecko API"""
    
    def __init__(self, db: Session):
        super().__init__("coingecko", db)
        self.api_key = settings.coingecko_api_key
        self.base_url = "https://api.coingecko.com/api/v3"
        self.rate_limit_delay = 1.5  # CoinGecko free tier: ~10-50 calls/min
        
    def fetch_data(self) -> List[dict]:
        """Fetch cryptocurrency data from CoinGecko API"""
        logger.info("Fetching data from CoinGecko API")
        
        headers = {}
        if self.api_key:
            headers["x-cg-demo-api-key"] = self.api_key
        
        params = {
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": 50,
            "page": 1,
            "sparkline": False,
            "price_change_percentage": "24h"
        }
        
        response = requests.get(
            f"{self.base_url}/coins/markets",
            headers=headers,
            params=params,
            timeout=30
        )
        response.raise_for_status()
        data = response.json()
        
        logger.info(f"Fetched {len(data)} coins from CoinGecko")
        return data
    
    def transform_and_load(self, data: List[dict]):
        """Transform and load CoinGecko data"""
        checkpoint = self.get_checkpoint()
        last_timestamp = checkpoint.last_processed_timestamp if checkpoint else None
        
        for item in data:
            try:
                # Validate with Pydantic
                validated = CoinGeckoSchema(**item)
                
                # Store raw data
                raw_record = RawCoinGecko(
                    coin_id=validated.coin_id,
                    name=validated.name,
                    symbol=validated.symbol,
                    current_price=validated.current_price,
                    market_cap=validated.market_cap,
                    total_volume=validated.total_volume,
                    price_change_24h=validated.price_change_24h,
                    price_change_percentage_24h=validated.price_change_percentage_24h,
                    raw_data=item
                )
                self.db.add(raw_record)
                
                # Transform to unified schema
                unified = UnifiedCrypto(
                    coin_id=validated.coin_id,
                    name=validated.name,
                    symbol=validated.symbol.upper(),
                    price_usd=validated.current_price,
                    market_cap_usd=validated.market_cap,
                    volume_24h_usd=validated.total_volume,
                    price_change_24h_percent=validated.price_change_percentage_24h,
                    rank=None,
                    source="coingecko",
                    source_updated_at=datetime.utcnow()
                )
                
                # Check if record exists (upsert logic)
                existing = self.db.query(UnifiedCrypto).filter(
                    UnifiedCrypto.coin_id == validated.coin_id,
                    UnifiedCrypto.source == "coingecko"
                ).first()
                
                if existing:
                    existing.price_usd = unified.price_usd
                    existing.market_cap_usd = unified.market_cap_usd
                    existing.volume_24h_usd = unified.volume_24h_usd
                    existing.price_change_24h_percent = unified.price_change_24h_percent
                    existing.source_updated_at = unified.source_updated_at
                    existing.updated_at = datetime.utcnow()
                else:
                    self.db.add(unified)
                
                self.records_processed += 1
                
                # Commit in batches
                if self.records_processed % 10 == 0:
                    self.db.commit()
                    
            except Exception as e:
                logger.error(f"Failed to process CoinGecko record: {str(e)}", extra={
                    "coin_id": item.get("id"),
                    "error": str(e)
                })
                self.records_failed += 1
                continue
        
        self.db.commit()
        logger.info(f"CoinGecko ingestion completed: {self.records_processed} processed, {self.records_failed} failed")
