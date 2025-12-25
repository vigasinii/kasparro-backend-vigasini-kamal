from abc import ABC, abstractmethod
from typing import List, Optional, Any
from datetime import datetime
import uuid
from sqlalchemy.orm import Session
from core.models import ETLCheckpoint, ETLRun, SchemaDrift
from core.logging_config import logger
from tenacity import retry, stop_after_attempt, wait_exponential
import time


class BaseIngestion(ABC):
    """Base class for all data ingestion sources"""
    
    def __init__(self, source_name: str, db: Session):
        self.source_name = source_name
        self.db = db
        self.run_id = str(uuid.uuid4())
        self.records_processed = 0
        self.records_failed = 0
        self.start_time = None
        
    def get_checkpoint(self) -> Optional[ETLCheckpoint]:
        """Get last checkpoint for this source"""
        return self.db.query(ETLCheckpoint).filter(
            ETLCheckpoint.source_name == self.source_name
        ).first()
    
    def update_checkpoint(self, last_id: str, timestamp: datetime, status: str, error: str = None):
        """Update checkpoint for this source"""
        checkpoint = self.get_checkpoint()
        if not checkpoint:
            checkpoint = ETLCheckpoint(source_name=self.source_name)
            self.db.add(checkpoint)
        
        checkpoint.last_processed_id = last_id
        checkpoint.last_processed_timestamp = timestamp
        checkpoint.records_processed = self.records_processed
        checkpoint.last_run_status = status
        checkpoint.last_error = error
        self.db.commit()
    
    def create_run(self):
        """Create ETL run record"""
        run = ETLRun(
            run_id=self.run_id,
            source_name=self.source_name,
            status="started",
            run_metadata={"started_by": "etl_scheduler"}
        )
        self.db.add(run)
        self.db.commit()
        logger.info(f"ETL run started", extra={
            "run_id": self.run_id,
            "source": self.source_name
        })
    
    def complete_run(self, status: str, error: str = None):
        """Mark ETL run as complete"""
        run = self.db.query(ETLRun).filter(ETLRun.run_id == self.run_id).first()
        if run:
            run.status = status
            run.records_processed = self.records_processed
            run.records_failed = self.records_failed
            run.completed_at = datetime.utcnow()
            run.error_message = error
            
            if self.start_time:
                run.duration_seconds = time.time() - self.start_time
            
            self.db.commit()
            
            logger.info(f"ETL run completed", extra={
                "run_id": self.run_id,
                "source": self.source_name,
                "status": status,
                "records_processed": self.records_processed,
                "records_failed": self.records_failed
            })
    
    def detect_schema_drift(self, expected_fields: dict, actual_data: dict):
        """Detect schema changes in source data"""
        # Check for missing fields
        for field, expected_type in expected_fields.items():
            if field not in actual_data:
                drift = SchemaDrift(
                    source_name=self.source_name,
                    drift_type="missing_field",
                    field_name=field,
                    expected_type=expected_type,
                    confidence_score=1.0
                )
                self.db.add(drift)
                logger.warning(f"Schema drift detected: missing field", extra={
                    "source": self.source_name,
                    "field": field,
                    "expected_type": expected_type
                })
        
        # Check for new fields
        for field, value in actual_data.items():
            if field not in expected_fields:
                drift = SchemaDrift(
                    source_name=self.source_name,
                    drift_type="new_field",
                    field_name=field,
                    actual_type=type(value).__name__,
                    sample_value=str(value)[:200],
                    confidence_score=0.8
                )
                self.db.add(drift)
                logger.warning(f"Schema drift detected: new field", extra={
                    "source": self.source_name,
                    "field": field,
                    "actual_type": type(value).__name__
                })
        
        self.db.commit()
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    def fetch_with_retry(self, *args, **kwargs):
        """Fetch data with retry logic"""
        return self.fetch_data(*args, **kwargs)
    
    @abstractmethod
    def fetch_data(self) -> List[Any]:
        """Fetch data from source - must be implemented by subclasses"""
        pass
    
    @abstractmethod
    def transform_and_load(self, data: List[Any]):
        """Transform and load data - must be implemented by subclasses"""
        pass
    
    def run(self):
        """Execute the full ETL pipeline"""
        self.start_time = time.time()
        self.create_run()
        
        try:
            logger.info(f"Starting ingestion", extra={"source": self.source_name})
            
            # Fetch data
            data = self.fetch_with_retry()
            
            if not data:
                logger.warning(f"No data fetched", extra={"source": self.source_name})
                self.complete_run("success")
                self.update_checkpoint("", datetime.utcnow(), "success")
                return
            
            # Transform and load
            self.transform_and_load(data)
            
            # Update checkpoint and complete
            self.update_checkpoint(
                str(len(data)),
                datetime.utcnow(),
                "success"
            )
            self.complete_run("success")
            
            logger.info(f"Ingestion completed successfully", extra={
                "source": self.source_name,
                "records_processed": self.records_processed
            })
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Ingestion failed", extra={
                "source": self.source_name,
                "error": error_msg
            }, exc_info=True)
            
            self.update_checkpoint("", datetime.utcnow(), "failure", error_msg)
            self.complete_run("failed", error_msg)
            raise
