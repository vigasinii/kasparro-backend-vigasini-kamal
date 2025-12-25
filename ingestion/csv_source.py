import pandas as pd
from typing import List
from datetime import datetime
from sqlalchemy.orm import Session
from ingestion.base import BaseIngestion
from core.models import RawCSV, UnifiedCrypto
from schemas.crypto import CSVSchema
from core.logging_config import logger
import os


class CSVIngestion(BaseIngestion):
    """Ingest data from CSV file"""
    
    def __init__(self, db: Session, csv_path: str = "/app/data/crypto_data.csv"):
        super().__init__("csv", db)
        self.csv_path = csv_path
        
    def fetch_data(self) -> List[dict]:
        """Read data from CSV file"""
        logger.info(f"Reading data from CSV: {self.csv_path}")
        
        if not os.path.exists(self.csv_path):
            logger.warning(f"CSV file not found: {self.csv_path}")
            # Create sample CSV if it doesn't exist
            self.create_sample_csv()
        
        try:
            df = pd.read_csv(self.csv_path)
            data = df.to_dict('records')
            logger.info(f"Read {len(data)} records from CSV")
            return data
        except Exception as e:
            logger.error(f"Failed to read CSV: {str(e)}")
            raise
    
    def create_sample_csv(self):
        """Create a sample CSV file with cryptocurrency data"""
        sample_data = {
            'coin_id': ['bitcoin', 'ethereum', 'binancecoin', 'cardano', 'solana'],
            'name': ['Bitcoin', 'Ethereum', 'Binance Coin', 'Cardano', 'Solana'],
            'symbol': ['BTC', 'ETH', 'BNB', 'ADA', 'SOL'],
            'price': [43250.50, 2280.75, 312.40, 0.58, 98.25],
            'market_cap': [846000000000, 274000000000, 48000000000, 20500000000, 42000000000],
            'volume': [28000000000, 15000000000, 1200000000, 450000000, 2100000000]
        }
        
        df = pd.DataFrame(sample_data)
        os.makedirs(os.path.dirname(self.csv_path), exist_ok=True)
        df.to_csv(self.csv_path, index=False)
        logger.info(f"Created sample CSV at {self.csv_path}")
    
    def transform_and_load(self, data: List[dict]):
        """Transform and load CSV data"""
        checkpoint = self.get_checkpoint()
        last_timestamp = checkpoint.last_processed_timestamp if checkpoint else None
        
        for item in data:
            try:
                # Validate with Pydantic
                validated = CSVSchema(**item)
                
                # Store raw data
                raw_record = RawCSV(
                    coin_id=validated.coin_id,
                    name=validated.name,
                    symbol=validated.symbol,
                    price=validated.price,
                    market_cap=validated.market_cap,
                    volume=validated.volume,
                    raw_data=item
                )
                self.db.add(raw_record)
                
                # Transform to unified schema
                unified = UnifiedCrypto(
                    coin_id=validated.coin_id,
                    name=validated.name,
                    symbol=validated.symbol.upper(),
                    price_usd=validated.price,
                    market_cap_usd=validated.market_cap,
                    volume_24h_usd=validated.volume,
                    price_change_24h_percent=None,
                    rank=None,
                    source="csv",
                    source_updated_at=datetime.utcnow()
                )
                
                # Check if record exists (upsert logic)
                existing = self.db.query(UnifiedCrypto).filter(
                    UnifiedCrypto.coin_id == validated.coin_id,
                    UnifiedCrypto.source == "csv"
                ).first()
                
                if existing:
                    existing.price_usd = unified.price_usd
                    existing.market_cap_usd = unified.market_cap_usd
                    existing.volume_24h_usd = unified.volume_24h_usd
                    existing.source_updated_at = unified.source_updated_at
                    existing.updated_at = datetime.utcnow()
                else:
                    self.db.add(unified)
                
                self.records_processed += 1
                
            except Exception as e:
                logger.error(f"Failed to process CSV record: {str(e)}", extra={
                    "coin_id": item.get("coin_id"),
                    "error": str(e)
                })
                self.records_failed += 1
                continue
        
        self.db.commit()
        logger.info(f"CSV ingestion completed: {self.records_processed} processed, {self.records_failed} failed")
