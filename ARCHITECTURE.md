# System Architecture

## Overview

The Kasparro ETL system is a production-grade data pipeline built with a focus on reliability, scalability, and maintainability.

## Core Components

### 1. Data Ingestion Layer

**Location**: `ingestion/`

The ingestion layer implements a plugin architecture where each data source extends the `BaseIngestion` class.

#### BaseIngestion (Abstract Class)

Provides common functionality:
- **Checkpoint Management**: Track last successful ingestion
- **Run Tracking**: Record metadata for each ETL run
- **Retry Logic**: Exponential backoff for transient failures
- **Schema Drift Detection**: Alert on unexpected data structure changes
- **Error Handling**: Graceful failure with detailed logging

#### Source Implementations

1. **CoinPaprikaIngestion**
   - Fetches top 50 cryptocurrencies
   - Rate limit: 100ms between requests
   - Uses ticker endpoint for detailed data
   
2. **CoinGeckoIngestion**
   - Fetches markets data (top 50)
   - Rate limit: 1.5s between requests
   - Single API call for batch data
   
3. **CSVIngestion**
   - Reads from local CSV file
   - Creates sample data if file doesn't exist
   - Supports incremental updates

### 2. Data Validation Layer

**Location**: `schemas/`

Uses Pydantic v2 for:
- Type coercion (strings to floats)
- Null handling for missing fields
- Field validation
- Schema enforcement

#### Schema Flow

```
Raw Data → Source Schema → Validation → Unified Schema → Database
```

### 3. Database Layer

**Location**: `core/models.py`

#### Table Design

**Raw Tables** (3 tables):
- Store original API/CSV responses
- Preserve data lineage
- Enable debugging and auditing

**Unified Table**:
- Normalized cryptocurrency data
- Indexed for query performance
- Supports upsert operations

**Metadata Tables**:
- `etl_checkpoint`: Incremental loading state
- `etl_run`: Complete run history
- `schema_drift`: Detected schema changes

#### Index Strategy

```sql
-- Composite indexes for common queries
CREATE INDEX idx_unified_coin_source ON unified_crypto(coin_id, source);
CREATE INDEX idx_unified_symbol ON unified_crypto(symbol);

-- Time-based indexes for ETL operations
CREATE INDEX idx_coinpaprika_coin_time ON raw_coinpaprika(coin_id, ingested_at);
```

### 4. API Layer

**Location**: `api/`

FastAPI application with automatic OpenAPI documentation.

#### Endpoint Design

```
GET /              → System info
GET /health        → Health check + ETL status
GET /data          → Paginated cryptocurrency data
GET /stats         → ETL statistics
GET /runs          → ETL run history
GET /metrics       → Prometheus metrics
```

#### Middleware

- **CORS**: Allow cross-origin requests
- **Metrics**: Track request count and latency
- **Logging**: Structured JSON logs

### 5. Scheduler Layer

**Location**: `core/etl_runner.py`

Runs ETL pipeline on a schedule:
- Immediate run on startup
- Recurring runs every 6 hours
- Sequential execution (one source at a time)
- Independent failure handling per source

## Data Flow

### Ingestion Flow

```
┌─────────────┐
│ Data Source │
└──────┬──────┘
       │ fetch_data()
       ▼
┌──────────────┐
│  Validation  │ ◄── Pydantic Schema
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  Raw Table   │ ◄── Store original data
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Transformation│ ◄── Map to unified schema
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Unified Table│ ◄── Upsert logic
└──────────────┘
```

### Query Flow

```
Client Request
      │
      ▼
┌──────────────┐
│  API Layer   │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Query Builder│ ◄── Filtering, Pagination
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   Database   │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   Response   │ ◄── Serialization
└──────────────┘
```

## Design Decisions

### 1. Separate Raw and Unified Tables

**Why?**
- Preserve data lineage
- Enable re-processing without re-fetching
- Support schema evolution
- Facilitate debugging

**Trade-off**: Higher storage cost for better reliability

### 2. Checkpoint-Based Incremental Loading

**Why?**
- Minimize redundant API calls
- Enable resume-on-failure
- Reduce processing time
- Lower API costs

**Implementation**:
```python
checkpoint = get_checkpoint(source)
if checkpoint:
    last_id = checkpoint.last_processed_id
    # Only fetch data after last_id
```

### 3. Idempotent Writes (Upsert Logic)

**Why?**
- Safe to re-run ETL
- Handle duplicate data gracefully
- Enable at-least-once delivery semantics

**Implementation**:
```python
existing = query(coin_id, source)
if existing:
    update(existing, new_data)
else:
    insert(new_data)
```

### 4. Per-Source Rate Limiting

**Why?**
- Respect API rate limits
- Prevent service degradation
- Avoid getting blocked

**Configuration**:
- CoinPaprika: 100ms delay
- CoinGecko: 1.5s delay
- CSV: No delay

### 5. Structured JSON Logging

**Why?**
- Machine-readable logs
- Easy to parse and analyze
- Compatible with log aggregation tools
- Supports contextual metadata

**Format**:
```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "INFO",
  "message": "ETL run completed",
  "run_id": "uuid-here",
  "source": "coinpaprika",
  "records_processed": 50
}
```

### 6. Schema Drift Detection

**Why?**
- Early warning of API changes
- Prevent silent data corruption
- Enable proactive response

**Mechanism**:
- Compare expected vs actual fields
- Log missing/new/changed fields
- Store in `schema_drift` table

## Scalability Considerations

### Vertical Scaling
- Increase container CPU/memory
- Upgrade database instance
- Add read replicas

### Horizontal Scaling
- Run multiple API containers behind load balancer
- Shard data by cryptocurrency symbol
- Partition tables by time

### Performance Optimizations
- Database connection pooling
- Batch inserts (10 records at a time)
- Indexed queries
- Query result caching (future)

## Reliability Patterns

### 1. Retry with Exponential Backoff

```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10)
)
def fetch_with_retry():
    return fetch_data()
```

### 2. Circuit Breaker (Future)
Prevent cascading failures by opening circuit after N failures.

### 3. Graceful Degradation
One source failure doesn't stop other sources.

### 4. Health Checks
Container-level and application-level health endpoints.

## Security Architecture

### 1. Secrets Management
- API keys in environment variables
- Never committed to git
- Rotatable without code changes

### 2. Database Security
- Connection pooling with limits
- SQL injection prevention via ORM
- Principle of least privilege

### 3. API Security
- Input validation with Pydantic
- Rate limiting (future)
- CORS configuration

## Monitoring Strategy

### 1. Application Metrics
- Request count by endpoint
- Request latency distribution
- Error rates

### 2. ETL Metrics
- Records processed per run
- Run duration
- Success/failure rates
- Schema drift events

### 3. Infrastructure Metrics
- CPU/Memory utilization
- Database connections
- Disk usage
- Network I/O

## Testing Strategy

### Unit Tests
- Schema validation
- Data transformation logic
- Individual components

### Integration Tests
- API endpoints
- Database operations
- End-to-end flows

### Smoke Tests
- System health verification
- Basic functionality checks
- Performance benchmarks

## Future Enhancements

### Short Term
1. Implement caching layer (Redis)
2. Add WebSocket support for real-time updates
3. Implement rate limiting on API
4. Add more cryptocurrency sources

### Medium Term
1. Implement data quality checks
2. Add anomaly detection
3. Implement data versioning
4. Add GraphQL API

### Long Term
1. Implement streaming ingestion (Kafka)
2. Add machine learning for price prediction
3. Implement time-series analysis
4. Add multi-tenancy support

## Development Workflow

```
Local Development
       │
       ▼
  Unit Tests
       │
       ▼
  Integration Tests
       │
       ▼
  Docker Build
       │
       ▼
  Push to Registry
       │
       ▼
  Deploy to Staging
       │
       ▼
  Smoke Tests
       │
       ▼
  Deploy to Production
       │
       ▼
  Monitor
```

## Disaster Recovery

### Backup Strategy
- Automated daily database backups
- 7-day retention period
- Point-in-time recovery capability

### Recovery Procedures
1. Restore database from backup
2. Re-run ETL from checkpoint
3. Verify data integrity
4. Resume normal operations

### RPO/RTO Targets
- **RPO** (Recovery Point Objective): 6 hours
- **RTO** (Recovery Time Objective): 30 minutes

---

**Document Version**: 1.0  
**Last Updated**: 2024-01-15  
**Maintainer**: Vic
