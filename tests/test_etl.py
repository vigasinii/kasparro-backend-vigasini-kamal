import pytest
from schemas.crypto import CoinPaprikaSchema, CoinGeckoSchema, CSVSchema
from pydantic import ValidationError


class TestSchemaValidation:
    """Test Pydantic schema validation"""
    
    def test_coinpaprika_schema_valid(self, sample_coinpaprika_data):
        """Test valid CoinPaprika data"""
        for item in sample_coinpaprika_data:
            schema = CoinPaprikaSchema(**item)
            assert schema.coin_id == item["id"]
            assert schema.name == item["name"]
            assert schema.symbol == item["symbol"]
            assert schema.price_usd == item["price_usd"]
    
    def test_coinpaprika_schema_missing_fields(self):
        """Test CoinPaprika schema with missing optional fields"""
        data = {
            "id": "btc-bitcoin",
            "name": "Bitcoin",
            "symbol": "BTC"
        }
        schema = CoinPaprikaSchema(**data)
        assert schema.coin_id == "btc-bitcoin"
        assert schema.price_usd is None
        assert schema.volume_24h_usd is None
    
    def test_coinpaprika_schema_invalid_numeric(self):
        """Test CoinPaprika schema with invalid numeric values"""
        data = {
            "id": "btc-bitcoin",
            "name": "Bitcoin",
            "symbol": "BTC",
            "price_usd": "invalid"
        }
        schema = CoinPaprikaSchema(**data)
        assert schema.price_usd is None  # Should convert to None
    
    def test_coingecko_schema_valid(self, sample_coingecko_data):
        """Test valid CoinGecko data"""
        for item in sample_coingecko_data:
            schema = CoinGeckoSchema(**item)
            assert schema.coin_id == item["id"]
            assert schema.name == item["name"]
            assert schema.symbol == item["symbol"]
            assert schema.current_price == item["current_price"]
    
    def test_csv_schema_valid(self, sample_csv_data):
        """Test valid CSV data"""
        for item in sample_csv_data:
            schema = CSVSchema(**item)
            assert schema.coin_id == item["coin_id"]
            assert schema.name == item["name"]
            assert schema.symbol == item["symbol"]
            assert schema.price == item["price"]


class TestDataTransformation:
    """Test ETL transformation logic"""
    
    def test_coinpaprika_to_unified(self, sample_coinpaprika_data):
        """Test transforming CoinPaprika data to unified schema"""
        from schemas.crypto import UnifiedCryptoSchema
        
        item = sample_coinpaprika_data[0]
        validated = CoinPaprikaSchema(**item)
        
        unified = UnifiedCryptoSchema(
            coin_id=validated.coin_id,
            name=validated.name,
            symbol=validated.symbol.upper(),
            price_usd=validated.price_usd,
            market_cap_usd=validated.market_cap_usd,
            volume_24h_usd=validated.volume_24h_usd,
            price_change_24h_percent=validated.percent_change_24h,
            rank=validated.rank,
            source="coinpaprika",
            source_updated_at=None
        )
        
        assert unified.coin_id == "btc-bitcoin"
        assert unified.symbol == "BTC"
        assert unified.source == "coinpaprika"
    
    def test_coingecko_to_unified(self, sample_coingecko_data):
        """Test transforming CoinGecko data to unified schema"""
        from schemas.crypto import UnifiedCryptoSchema
        
        item = sample_coingecko_data[0]
        validated = CoinGeckoSchema(**item)
        
        unified = UnifiedCryptoSchema(
            coin_id=validated.coin_id,
            name=validated.name,
            symbol=validated.symbol.upper(),
            price_usd=validated.current_price,
            market_cap_usd=validated.market_cap,
            volume_24h_usd=validated.total_volume,
            price_change_24h_percent=validated.price_change_percentage_24h,
            rank=None,
            source="coingecko",
            source_updated_at=None
        )
        
        assert unified.coin_id == "bitcoin"
        assert unified.symbol == "BTC"
        assert unified.source == "coingecko"
