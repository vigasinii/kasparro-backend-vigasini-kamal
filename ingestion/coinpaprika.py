import requests
from typing import List
from datetime import datetime
from sqlalchemy.orm import Session
from ingestion.base import BaseIngestion
from core.models import RawCoinPaprika, UnifiedCrypto
from schemas.crypto import CoinPaprikaSchema, UnifiedCryptoSchema
from core.config import get_settings
from core.logging_config import logger
import time

settings = get_settings()


class CoinPaprikaIngestion(BaseIngestion):
    """Ingest data from CoinPaprika API"""
    
    def __init__(self, db: Session):
        super().__init__("coinpaprika", db)
        self.api_key = settings.coinpaprika_api_key
        self.base_url = "https://api.coinpaprika.com/v1"
        self.rate_limit_delay = 0.1  # 100ms between requests
        
    def fetch_data(self) -> List[dict]:
        """Fetch cryptocurrency data from CoinPaprika API"""
        logger.info("Fetching data from CoinPaprika API")
        
        headers = {}
        if self.api_key:
            headers["Authorization"] = self.api_key
        
        # Get list of coins
        response = requests.get(
            f"{self.base_url}/coins",
            headers=headers,
            timeout=30
        )
        response.raise_for_status()
        coins = response.json()
        
        # Get top 50 active coins
        active_coins = [c for c in coins if c.get("is_active", True)][:50]
        
        detailed_data = []
        for coin in active_coins:
            try:
                time.sleep(self.rate_limit_delay)
                
                # Get ticker data for each coin
                ticker_response = requests.get(
                    f"{self.base_url}/tickers/{coin['id']}",
                    headers=headers,
                    timeout=30
                )
                
                if ticker_response.status_code == 200:
                    ticker_data = ticker_response.json()
                    
                    # Extract USD quote data
                    usd_quote = ticker_data.get("quotes", {}).get("USD", {})
                    
                    detailed_data.append({
                        "id": ticker_data.get("id"),
                        "name": ticker_data.get("name"),
                        "symbol": ticker_data.get("symbol"),
                        "rank": ticker_data.get("rank"),
                        "price_usd": usd_quote.get("price"),
                        "volume_24h_usd": usd_quote.get("volume_24h"),
                        "market_cap_usd": usd_quote.get("market_cap"),
                        "percent_change_24h": usd_quote.get("percent_change_24h"),
                        "raw_data": ticker_data
                    })
                    
            except Exception as e:
                logger.warning(f"Failed to fetch ticker for {coin['id']}: {str(e)}")
                continue
        
        logger.info(f"Fetched {len(detailed_data)} coins from CoinPaprika")
        return detailed_data
    
    def transform_and_load(self, data: List[dict]):
        """Transform and load CoinPaprika data"""
        checkpoint = self.get_checkpoint()
        last_timestamp = checkpoint.last_processed_timestamp if checkpoint else None
        
        for item in data:
            try:
                # Validate with Pydantic
                validated = CoinPaprikaSchema(**item)
                
                # Store raw data
                raw_record = RawCoinPaprika(
                    coin_id=validated.coin_id,
                    name=validated.name,
                    symbol=validated.symbol,
                    rank=validated.rank,
                    price_usd=validated.price_usd,
                    volume_24h_usd=validated.volume_24h_usd,
                    market_cap_usd=validated.market_cap_usd,
                    percent_change_24h=validated.percent_change_24h,
                    raw_data=item.get("raw_data", {})
                )
                self.db.add(raw_record)
                
                # Transform to unified schema
                unified = UnifiedCrypto(
                    coin_id=validated.coin_id,
                    name=validated.name,
                    symbol=validated.symbol.upper(),
                    price_usd=validated.price_usd,
                    market_cap_usd=validated.market_cap_usd,
                    volume_24h_usd=validated.volume_24h_usd,
                    price_change_24h_percent=validated.percent_change_24h,
                    rank=validated.rank,
                    source="coinpaprika",
                    source_updated_at=datetime.utcnow()
                )
                
                # Check if record exists (upsert logic)
                existing = self.db.query(UnifiedCrypto).filter(
                    UnifiedCrypto.coin_id == validated.coin_id,
                    UnifiedCrypto.source == "coinpaprika"
                ).first()
                
                if existing:
                    existing.price_usd = unified.price_usd
                    existing.market_cap_usd = unified.market_cap_usd
                    existing.volume_24h_usd = unified.volume_24h_usd
                    existing.price_change_24h_percent = unified.price_change_24h_percent
                    existing.rank = unified.rank
                    existing.source_updated_at = unified.source_updated_at
                    existing.updated_at = datetime.utcnow()
                else:
                    self.db.add(unified)
                
                self.records_processed += 1
                
                # Commit in batches
                if self.records_processed % 10 == 0:
                    self.db.commit()
                    
            except Exception as e:
                logger.error(f"Failed to process CoinPaprika record: {str(e)}", extra={
                    "coin_id": item.get("id"),
                    "error": str(e)
                })
                self.records_failed += 1
                continue
        
        self.db.commit()
        logger.info(f"CoinPaprika ingestion completed: {self.records_processed} processed, {self.records_failed} failed")
