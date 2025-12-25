from fastapi import FastAPI, Depends, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional
import time
import uuid
from datetime import datetime

from core.database import get_db, engine
from core.models import Base, UnifiedCrypto, ETLCheckpoint, ETLRun
from schemas.crypto import DataResponse, HealthResponse, StatsResponse, CryptoResponse, ETLRunResponse
from core.logging_config import logger
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response

# Create tables
Base.metadata.create_all(bind=engine)

# Initialize FastAPI app
app = FastAPI(
    title="Kasparro ETL System",
    description="Production-grade ETL system for cryptocurrency data",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus metrics
request_counter = Counter('api_requests_total', 'Total API requests', ['endpoint', 'method'])
request_duration = Histogram('api_request_duration_seconds', 'API request duration')


@app.middleware("http")
async def add_metrics(request, call_next):
    """Add Prometheus metrics to all requests"""
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    
    request_counter.labels(endpoint=request.url.path, method=request.method).inc()
    request_duration.observe(duration)
    
    return response


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint"""
    return {
        "message": "Kasparro ETL System API",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "data": "/data",
            "stats": "/stats",
            "runs": "/runs",
            "metrics": "/metrics",
            "docs": "/docs"
        }
    }


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check(db: Session = Depends(get_db)):
    """
    Health check endpoint
    - Checks database connectivity
    - Reports ETL status for all sources
    """
    start_time = time.time()
    
    try:
        # Check database connectivity
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        db_status = f"error: {str(e)}"
    
    # Get ETL status for all sources
    etl_status = {}
    sources = ["coinpaprika", "coingecko", "csv"]
    
    for source in sources:
        checkpoint = db.query(ETLCheckpoint).filter(
            ETLCheckpoint.source_name == source
        ).first()
        
        if checkpoint:
            etl_status[source] = {
                "last_run_status": checkpoint.last_run_status,
                "last_run_time": checkpoint.last_processed_timestamp.isoformat() if checkpoint.last_processed_timestamp else None,
                "records_processed": checkpoint.records_processed
            }
        else:
            etl_status[source] = {
                "last_run_status": "never_run",
                "last_run_time": None,
                "records_processed": 0
            }
    
    return HealthResponse(
        status="healthy" if db_status == "connected" else "unhealthy",
        database=db_status,
        etl_status=etl_status,
        timestamp=datetime.utcnow()
    )


@app.get("/data", response_model=DataResponse, tags=["Data"])
async def get_data(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    source: Optional[str] = Query(None, description="Filter by source (coinpaprika, coingecko, csv)"),
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    db: Session = Depends(get_db)
):
    """
    Get cryptocurrency data with pagination and filtering
    
    - **page**: Page number (starts at 1)
    - **page_size**: Number of items per page (max 100)
    - **source**: Filter by data source
    - **symbol**: Filter by cryptocurrency symbol
    """
    request_id = str(uuid.uuid4())
    start_time = time.time()
    
    try:
        # Build query
        query = db.query(UnifiedCrypto)
        
        # Apply filters
        if source:
            query = query.filter(UnifiedCrypto.source == source)
        if symbol:
            query = query.filter(UnifiedCrypto.symbol == symbol.upper())
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        offset = (page - 1) * page_size
        data = query.order_by(UnifiedCrypto.updated_at.desc()).offset(offset).limit(page_size).all()
        
        # Calculate latency
        api_latency_ms = (time.time() - start_time) * 1000
        
        return DataResponse(
            data=[CryptoResponse.model_validate(item) for item in data],
            total=total,
            page=page,
            page_size=page_size,
            request_id=request_id,
            api_latency_ms=round(api_latency_ms, 2)
        )
        
    except Exception as e:
        logger.error(f"Error fetching data: {str(e)}", extra={"request_id": request_id})
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats", response_model=list[StatsResponse], tags=["Stats"])
async def get_stats(db: Session = Depends(get_db)):
    """
    Get ETL statistics for all sources
    
    Returns:
    - Records processed
    - Last success/failure timestamps
    - Success rate
    - Run duration
    """
    sources = ["coinpaprika", "coingecko", "csv"]
    stats = []
    
    for source in sources:
        # Get checkpoint
        checkpoint = db.query(ETLCheckpoint).filter(
            ETLCheckpoint.source_name == source
        ).first()
        
        # Get run statistics
        runs = db.query(ETLRun).filter(ETLRun.source_name == source).all()
        total_runs = len(runs)
        successful_runs = len([r for r in runs if r.status == "success"])
        success_rate = (successful_runs / total_runs * 100) if total_runs > 0 else 0
        
        # Get last success and failure
        last_success = db.query(ETLRun).filter(
            ETLRun.source_name == source,
            ETLRun.status == "success"
        ).order_by(ETLRun.completed_at.desc()).first()
        
        last_failure = db.query(ETLRun).filter(
            ETLRun.source_name == source,
            ETLRun.status == "failed"
        ).order_by(ETLRun.completed_at.desc()).first()
        
        stats.append(StatsResponse(
            source=source,
            records_processed=checkpoint.records_processed if checkpoint else 0,
            last_success=last_success.completed_at if last_success else None,
            last_failure=last_failure.completed_at if last_failure else None,
            last_run_duration_seconds=last_success.duration_seconds if last_success else None,
            total_runs=total_runs,
            success_rate=round(success_rate, 2)
        ))
    
    return stats


@app.get("/runs", response_model=list[ETLRunResponse], tags=["Stats"])
async def get_runs(
    limit: int = Query(10, ge=1, le=100, description="Number of runs to return"),
    source: Optional[str] = Query(None, description="Filter by source"),
    db: Session = Depends(get_db)
):
    """
    Get recent ETL runs
    
    - **limit**: Number of runs to return (max 100)
    - **source**: Filter by data source
    """
    query = db.query(ETLRun)
    
    if source:
        query = query.filter(ETLRun.source_name == source)
    
    runs = query.order_by(ETLRun.started_at.desc()).limit(limit).all()
    
    return [ETLRunResponse.model_validate(run) for run in runs]


@app.get("/metrics", tags=["Metrics"])
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
