import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.database import Base
from core.models import *
import os

# Test database URL
TEST_DATABASE_URL = "postgresql://kasparro:kasparro_pass@db:5432/kasparro_test_db"


@pytest.fixture(scope="function")
def test_db():
    """Create a test database session"""
    engine = create_engine(TEST_DATABASE_URL)
    
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    # Create session
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    
    try:
        yield db
    finally:
        db.close()
        # Drop all tables after test
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def sample_coinpaprika_data():
    """Sample CoinPaprika API response"""
    return [
        {
            "id": "btc-bitcoin",
            "name": "Bitcoin",
            "symbol": "BTC",
            "rank": 1,
            "price_usd": 43250.50,
            "volume_24h_usd": 28000000000,
            "market_cap_usd": 846000000000,
            "percent_change_24h": 2.5
        },
        {
            "id": "eth-ethereum",
            "name": "Ethereum",
            "symbol": "ETH",
            "rank": 2,
            "price_usd": 2280.75,
            "volume_24h_usd": 15000000000,
            "market_cap_usd": 274000000000,
            "percent_change_24h": 3.2
        }
    ]


@pytest.fixture
def sample_coingecko_data():
    """Sample CoinGecko API response"""
    return [
        {
            "id": "bitcoin",
            "name": "Bitcoin",
            "symbol": "btc",
            "current_price": 43250.50,
            "market_cap": 846000000000,
            "total_volume": 28000000000,
            "price_change_24h": 1080.12,
            "price_change_percentage_24h": 2.5
        },
        {
            "id": "ethereum",
            "name": "Ethereum",
            "symbol": "eth",
            "current_price": 2280.75,
            "market_cap": 274000000000,
            "total_volume": 15000000000,
            "price_change_24h": 70.80,
            "price_change_percentage_24h": 3.2
        }
    ]


@pytest.fixture
def sample_csv_data():
    """Sample CSV data"""
    return [
        {
            "coin_id": "bitcoin",
            "name": "Bitcoin",
            "symbol": "BTC",
            "price": 43250.50,
            "market_cap": 846000000000,
            "volume": 28000000000
        },
        {
            "coin_id": "ethereum",
            "name": "Ethereum",
            "symbol": "ETH",
            "price": 2280.75,
            "market_cap": 274000000000,
            "volume": 15000000000
        }
    ]
