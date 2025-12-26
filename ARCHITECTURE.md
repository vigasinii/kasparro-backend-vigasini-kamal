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

