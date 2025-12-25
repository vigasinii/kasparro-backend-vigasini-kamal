import pytest
from fastapi.testclient import TestClient
from api.main import app
from core.models import UnifiedCrypto, ETLCheckpoint, ETLRun
from datetime import datetime

client = TestClient(app)


class TestAPIEndpoints:
    """Test API endpoints"""
    
    def test_root_endpoint(self):
        """Test root endpoint"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "version" in data
        assert "endpoints" in data
    
    def test_health_endpoint(self):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "database" in data
        assert "etl_status" in data
        assert "timestamp" in data
    
    def test_data_endpoint_pagination(self, test_db):
        """Test data endpoint with pagination"""
        # Add sample data
        for i in range(25):
            crypto = UnifiedCrypto(
                coin_id=f"coin_{i}",
                name=f"Coin {i}",
                symbol=f"C{i}",
                price_usd=100.0 + i,
                market_cap_usd=1000000 + i * 1000,
                volume_24h_usd=50000 + i * 100,
                source="test"
            )
            test_db.add(crypto)
        test_db.commit()
        
        # Test first page
        response = client.get("/data?page=1&page_size=10")
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 10
        assert data["total"] == 25
        assert data["page"] == 1
        assert "request_id" in data
        assert "api_latency_ms" in data
        
        # Test second page
        response = client.get("/data?page=2&page_size=10")
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 10
        assert data["page"] == 2
    
    def test_data_endpoint_filtering(self, test_db):
        """Test data endpoint with filtering"""
        # Add sample data
        crypto1 = UnifiedCrypto(
            coin_id="bitcoin",
            name="Bitcoin",
            symbol="BTC",
            price_usd=43250.0,
            source="coinpaprika"
        )
        crypto2 = UnifiedCrypto(
            coin_id="ethereum",
            name="Ethereum",
            symbol="ETH",
            price_usd=2280.0,
            source="coingecko"
        )
        test_db.add_all([crypto1, crypto2])
        test_db.commit()
        
        # Filter by source
        response = client.get("/data?source=coinpaprika")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["data"][0]["source"] == "coinpaprika"
        
        # Filter by symbol
        response = client.get("/data?symbol=ETH")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["data"][0]["symbol"] == "ETH"
    
    def test_stats_endpoint(self, test_db):
        """Test stats endpoint"""
        # Add sample checkpoint
        checkpoint = ETLCheckpoint(
            source_name="coinpaprika",
            records_processed=100,
            last_run_status="success"
        )
        test_db.add(checkpoint)
        
        # Add sample runs
        run = ETLRun(
            run_id="test-run-1",
            source_name="coinpaprika",
            status="success",
            records_processed=100,
            duration_seconds=45.5,
            completed_at=datetime.utcnow()
        )
        test_db.add(run)
        test_db.commit()
        
        response = client.get("/stats")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3  # Three sources
        
        # Check coinpaprika stats
        coinpaprika_stats = next(s for s in data if s["source"] == "coinpaprika")
        assert coinpaprika_stats["records_processed"] == 100
        assert coinpaprika_stats["total_runs"] == 1
        assert coinpaprika_stats["success_rate"] == 100.0
    
    def test_runs_endpoint(self, test_db):
        """Test runs endpoint"""
        # Add sample runs
        for i in range(5):
            run = ETLRun(
                run_id=f"test-run-{i}",
                source_name="coinpaprika",
                status="success" if i % 2 == 0 else "failed",
                records_processed=100 + i,
                completed_at=datetime.utcnow()
            )
            test_db.add(run)
        test_db.commit()
        
        response = client.get("/runs?limit=3")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        
        # Filter by source
        response = client.get("/runs?source=coinpaprika")
        assert response.status_code == 200
        data = response.json()
        assert all(run["source_name"] == "coinpaprika" for run in data)
    
    def test_metrics_endpoint(self):
        """Test Prometheus metrics endpoint"""
        response = client.get("/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]


class TestAPIErrorHandling:
    """Test API error handling"""
    
    def test_data_endpoint_invalid_pagination(self):
        """Test data endpoint with invalid pagination parameters"""
        response = client.get("/data?page=0")
        assert response.status_code == 422  # Validation error
        
        response = client.get("/data?page_size=200")
        assert response.status_code == 422  # Exceeds max
    
    def test_data_endpoint_invalid_filter(self):
        """Test data endpoint with invalid filter"""
        response = client.get("/data?source=invalid_source")
        assert response.status_code == 200  # Should return empty results
        data = response.json()
        assert data["total"] == 0
