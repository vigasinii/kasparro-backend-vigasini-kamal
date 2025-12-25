import pytest
from datetime import datetime
from core.models import ETLCheckpoint, ETLRun, UnifiedCrypto
from ingestion.base import BaseIngestion
from unittest.mock import Mock


class TestIncrementalIngestion:
    """Test incremental ingestion logic"""
    
    def test_checkpoint_creation(self, test_db):
        """Test checkpoint creation"""
        # Create mock ingestion
        ingestion = BaseIngestion("test_source", test_db)
        ingestion.records_processed = 100
        
        # Update checkpoint
        ingestion.update_checkpoint(
            last_id="last_item_id",
            timestamp=datetime.utcnow(),
            status="success"
        )
        
        # Verify checkpoint
        checkpoint = test_db.query(ETLCheckpoint).filter(
            ETLCheckpoint.source_name == "test_source"
        ).first()
        
        assert checkpoint is not None
        assert checkpoint.last_processed_id == "last_item_id"
        assert checkpoint.records_processed == 100
        assert checkpoint.last_run_status == "success"
    
    def test_checkpoint_update(self, test_db):
        """Test checkpoint update"""
        # Create initial checkpoint
        checkpoint = ETLCheckpoint(
            source_name="test_source",
            last_processed_id="old_id",
            records_processed=50,
            last_run_status="success"
        )
        test_db.add(checkpoint)
        test_db.commit()
        
        # Update checkpoint
        ingestion = BaseIngestion("test_source", test_db)
        ingestion.records_processed = 150
        ingestion.update_checkpoint(
            last_id="new_id",
            timestamp=datetime.utcnow(),
            status="success"
        )
        
        # Verify update
        updated = test_db.query(ETLCheckpoint).filter(
            ETLCheckpoint.source_name == "test_source"
        ).first()
        
        assert updated.last_processed_id == "new_id"
        assert updated.records_processed == 150
    
    def test_run_tracking(self, test_db):
        """Test ETL run tracking"""
        ingestion = BaseIngestion("test_source", test_db)
        ingestion.records_processed = 100
        ingestion.records_failed = 5
        
        # Create run
        ingestion.create_run()
        
        # Verify run created
        run = test_db.query(ETLRun).filter(
            ETLRun.run_id == ingestion.run_id
        ).first()
        
        assert run is not None
        assert run.source_name == "test_source"
        assert run.status == "started"
        
        # Complete run
        ingestion.complete_run("success")
        
        # Verify completion
        test_db.refresh(run)
        assert run.status == "success"
        assert run.records_processed == 100
        assert run.records_failed == 5
        assert run.completed_at is not None
    
    def test_idempotent_writes(self, test_db):
        """Test idempotent writes (upsert logic)"""
        # First write
        crypto1 = UnifiedCrypto(
            coin_id="bitcoin",
            name="Bitcoin",
            symbol="BTC",
            price_usd=40000.0,
            source="test"
        )
        test_db.add(crypto1)
        test_db.commit()
        
        # Second write (update)
        existing = test_db.query(UnifiedCrypto).filter(
            UnifiedCrypto.coin_id == "bitcoin",
            UnifiedCrypto.source == "test"
        ).first()
        
        existing.price_usd = 45000.0
        test_db.commit()
        
        # Verify only one record exists
        count = test_db.query(UnifiedCrypto).filter(
            UnifiedCrypto.coin_id == "bitcoin",
            UnifiedCrypto.source == "test"
        ).count()
        
        assert count == 1
        
        # Verify price updated
        updated = test_db.query(UnifiedCrypto).filter(
            UnifiedCrypto.coin_id == "bitcoin",
            UnifiedCrypto.source == "test"
        ).first()
        
        assert updated.price_usd == 45000.0


class TestFailureRecovery:
    """Test failure recovery logic"""
    
    def test_run_failure_tracking(self, test_db):
        """Test tracking failed runs"""
        ingestion = BaseIngestion("test_source", test_db)
        ingestion.create_run()
        
        # Simulate failure
        error_msg = "Connection timeout"
        ingestion.complete_run("failed", error_msg)
        
        # Verify failure tracking
        run = test_db.query(ETLRun).filter(
            ETLRun.run_id == ingestion.run_id
        ).first()
        
        assert run.status == "failed"
        assert run.error_message == error_msg
        assert run.completed_at is not None
    
    def test_checkpoint_failure_tracking(self, test_db):
        """Test checkpoint tracks failures"""
        ingestion = BaseIngestion("test_source", test_db)
        
        error_msg = "API rate limit exceeded"
        ingestion.update_checkpoint(
            last_id="",
            timestamp=datetime.utcnow(),
            status="failure",
            error=error_msg
        )
        
        checkpoint = test_db.query(ETLCheckpoint).filter(
            ETLCheckpoint.source_name == "test_source"
        ).first()
        
        assert checkpoint.last_run_status == "failure"
        assert checkpoint.last_error == error_msg
    
    def test_resume_from_checkpoint(self, test_db):
        """Test resuming from last checkpoint"""
        # Create checkpoint
        checkpoint = ETLCheckpoint(
            source_name="test_source",
            last_processed_id="item_100",
            last_processed_timestamp=datetime.utcnow(),
            records_processed=100,
            last_run_status="success"
        )
        test_db.add(checkpoint)
        test_db.commit()
        
        # Get checkpoint in new ingestion
        ingestion = BaseIngestion("test_source", test_db)
        last_checkpoint = ingestion.get_checkpoint()
        
        assert last_checkpoint is not None
        assert last_checkpoint.last_processed_id == "item_100"
        assert last_checkpoint.records_processed == 100


class TestSchemaDrift:
    """Test schema drift detection"""
    
    def test_detect_missing_field(self, test_db):
        """Test detection of missing fields"""
        from core.models import SchemaDrift
        
        ingestion = BaseIngestion("test_source", test_db)
        
        expected_fields = {
            "id": "str",
            "name": "str",
            "price": "float"
        }
        
        actual_data = {
            "id": "bitcoin",
            "name": "Bitcoin"
            # price is missing
        }
        
        ingestion.detect_schema_drift(expected_fields, actual_data)
        
        # Verify drift recorded
        drift = test_db.query(SchemaDrift).filter(
            SchemaDrift.source_name == "test_source",
            SchemaDrift.drift_type == "missing_field"
        ).first()
        
        assert drift is not None
        assert drift.field_name == "price"
        assert drift.expected_type == "float"
    
    def test_detect_new_field(self, test_db):
        """Test detection of new fields"""
        from core.models import SchemaDrift
        
        ingestion = BaseIngestion("test_source", test_db)
        
        expected_fields = {
            "id": "str",
            "name": "str"
        }
        
        actual_data = {
            "id": "bitcoin",
            "name": "Bitcoin",
            "new_field": "unexpected_value"
        }
        
        ingestion.detect_schema_drift(expected_fields, actual_data)
        
        # Verify drift recorded
        drift = test_db.query(SchemaDrift).filter(
            SchemaDrift.source_name == "test_source",
            SchemaDrift.drift_type == "new_field"
        ).first()
        
        assert drift is not None
        assert drift.field_name == "new_field"
        assert drift.sample_value == "unexpected_value"
