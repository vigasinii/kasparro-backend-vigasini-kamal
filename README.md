# Kasparro Backend & ETL System

Production-grade ETL pipeline and API system for cryptocurrency data ingestion from multiple sources.

##  Architecture Overview

This system implements a robust ETL (Extract, Transform, Load) pipeline that:
- Ingests data from 3 sources: CoinPaprika API, CoinGecko API, and CSV files
- Normalizes data into a unified schema
- Stores both raw and transformed data
- Exposes REST API endpoints for data access
- Implements incremental loading with checkpoint management
- Provides comprehensive observability and monitoring

### System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Data Sources                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ CoinPaprika  │  │  CoinGecko   │  │  CSV File    │      │
│  │     API      │  │     API      │  │              │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
└─────────┼──────────────────┼──────────────────┼─────────────┘
          │                  │                  │
          └──────────┬───────┴──────────────────┘
                     │
          ┌──────────▼─────────────┐
          │  ETL Ingestion Layer   │
          │  ┌──────────────────┐  │
          │  │  BaseIngestion   │  │
          │  │  - Retry Logic   │  │
          │  │  - Rate Limiting │  │
          │  │  - Checkpoints   │  │
          │  └──────────────────┘  │
          └──────────┬─────────────┘
                     │
          ┌──────────▼─────────────┐
          │   Validation Layer     │
          │  (Pydantic Schemas)    │
          └──────────┬─────────────┘
                     │
          ┌──────────▼─────────────┐
          │    PostgreSQL DB       │
          │  ┌──────────────────┐  │
          │  │  Raw Tables      │  │
          │  │  Unified Table   │  │
          │  │  Checkpoint Tbl  │  │
          │  │  ETL Run Tbl     │  │
          │  └──────────────────┘  │
          └──────────┬─────────────┘
                     │
          ┌──────────▼─────────────┐
          │    FastAPI Server      │
          │  ┌──────────────────┐  │
          │  │  GET /data       │  │
          │  │  GET /health     │  │
          │  │  GET /stats      │  │
          │  │  GET /runs       │  │
          │  │  GET /metrics    │  │
          │  └──────────────────┘  │
          └────────────────────────┘
```

##  Quick Start

### Prerequisites
- Docker and Docker Compose
- API Keys:
  - CoinPaprika API key ([Get here](https://coinpaprika.com/api))
  - CoinGecko API key (optional, has free tier)

### Setup

1. **Clone the repository**
```bash
git clone https://github.com/vigasinii/kasparro-backend-vigasini-kamal.git
cd  kasparro-backend-vigasini-kamal
```

2. **Configure environment variables**
```bash
cp .env.example .env
# Edit .env and add your API keys
```

3. **Start the system**
```bash
make up
```

This will:
- Build Docker images
- Start PostgreSQL database
- Run database migrations
- Start ETL scheduler (runs every 6 hours)
- Start FastAPI server on port 8000

4. **Verify the system**
```bash
# Check health
curl http://localhost:8000/health

# View API documentation
open http://localhost:8000/docs
```

### Available Commands

```bash
make up         # Start all services
make down       # Stop all services
make test       # Run test suite
make logs       # View API logs
make clean      # Clean up containers and volumes
make restart    # Restart API service
make health     # Check system health
make stats      # View ETL statistics
make data       # Fetch sample data
```

##  Project Structure

```
kasparro-backend-vic/
├── api/                    # FastAPI application
│   ├── main.py            # Main API endpoints
│   └── __init__.py
├── ingestion/             # ETL ingestion modules
│   ├── base.py           # Base ingestion class
│   ├── coinpaprika.py    # CoinPaprika ingestion
│   ├── coingecko.py      # CoinGecko ingestion
│   ├── csv_source.py     # CSV ingestion
│   └── __init__.py
├── schemas/               # Pydantic schemas
│   ├── crypto.py         # Data validation schemas
│   └── __init__.py
├── core/                  # Core utilities
│   ├── config.py         # Configuration management
│   ├── database.py       # Database connection
│   ├── models.py         # SQLAlchemy models
│   ├── logging_config.py # Structured logging
│   ├── etl_runner.py     # ETL scheduler
│   └── __init__.py
├── tests/                 # Test suite
│   ├── conftest.py       # Test fixtures
│   ├── test_etl.py       # ETL tests
│   ├── test_api.py       # API tests
│   └── test_incremental.py # Incremental loading tests
├── migrations/            # Alembic migrations
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
├── data/                  # CSV data directory
├── docker-compose.yml     # Docker orchestration
├── Dockerfile            # Container definition
├── Makefile              # Build automation
├── requirements.txt      # Python dependencies
├── alembic.ini          # Migration config
└── README.md            # This file
```

##  API Endpoints

### GET /health
Health check endpoint reporting system status.

**Response:**
```json
{
  "status": "healthy",
  "database": "connected",
  "etl_status": {
    "coinpaprika": {
      "last_run_status": "success",
      "last_run_time": "2024-01-15T10:30:00",
      "records_processed": 50
    },
    "coingecko": {...},
    "csv": {...}
  },
  "timestamp": "2024-01-15T10:35:00"
}
```

### GET /data
Retrieve cryptocurrency data with pagination and filtering.

**Query Parameters:**
- `page` (int): Page number (default: 1)
- `page_size` (int): Items per page (default: 20, max: 100)
- `source` (str): Filter by source (coinpaprika, coingecko, csv)
- `symbol` (str): Filter by cryptocurrency symbol

**Response:**
```json
{
  "data": [
    {
      "id": 1,
      "coin_id": "btc-bitcoin",
      "name": "Bitcoin",
      "symbol": "BTC",
      "price_usd": 43250.50,
      "market_cap_usd": 846000000000,
      "volume_24h_usd": 28000000000,
      "price_change_24h_percent": 2.5,
      "rank": 1,
      "source": "coinpaprika",
      "updated_at": "2024-01-15T10:30:00"
    }
  ],
  "total": 150,
  "page": 1,
  "page_size": 20,
  "request_id": "uuid-here",
  "api_latency_ms": 45.23
}
```

### GET /stats
ETL statistics for all data sources.

**Response:**
```json
[
  {
    "source": "coinpaprika",
    "records_processed": 50,
    "last_success": "2024-01-15T10:30:00",
    "last_failure": null,
    "last_run_duration_seconds": 45.5,
    "total_runs": 10,
    "success_rate": 100.0
  }
]
```

### GET /runs
Recent ETL run history.

**Query Parameters:**
- `limit` (int): Number of runs (default: 10, max: 100)
- `source` (str): Filter by source

**Response:**
```json
[
  {
    "run_id": "uuid-here",
    "source_name": "coinpaprika",
    "status": "success",
    "records_processed": 50,
    "records_failed": 0,
    "duration_seconds": 45.5,
    "started_at": "2024-01-15T10:30:00",
    "completed_at": "2024-01-15T10:31:00",
    "error_message": null
  }
]
```

### GET /metrics
Prometheus-compatible metrics endpoint.

##  Database Schema

### Raw Tables
- `raw_coinpaprika`: Raw CoinPaprika API data
- `raw_coingecko`: Raw CoinGecko API data
- `raw_csv`: Raw CSV file data

### Unified Table
- `unified_crypto`: Normalized cryptocurrency data from all sources

### Metadata Tables
- `etl_checkpoint`: Track last successful ingestion for each source
- `etl_run`: Complete history of ETL runs
- `schema_drift`: Detected schema changes

## 🔄 ETL Process

### Incremental Ingestion
- Each source maintains a checkpoint of last processed data
- On failure, ETL resumes from last checkpoint
- Implements idempotent writes (upsert logic)
- Batch processing for optimal performance

### Error Handling
- Automatic retry with exponential backoff
- Comprehensive error logging
- Graceful degradation (one source failure doesn't stop others)
- Schema drift detection and logging

### Rate Limiting
- Per-source rate limiting
- Configurable delays between API calls
- Respects API rate limits:
  - CoinPaprika: ~100ms delay
  - CoinGecko: ~1.5s delay (free tier)

## 🧪 Testing

### Run All Tests
```bash
make test
```

### Test Coverage
- **ETL Transformation Tests**: Schema validation, data transformation
- **API Endpoint Tests**: All endpoints, pagination, filtering
- **Incremental Ingestion Tests**: Checkpoints, idempotent writes
- **Failure Recovery Tests**: Error handling, resume logic
- **Schema Drift Tests**: Drift detection

### Test Database
Tests use a separate test database (`kasparro_test_db`) that is created and destroyed for each test.

## 📊 Monitoring & Observability

### Structured Logging
All logs are in JSON format with:
- Timestamp
- Log level
- Component name
- Contextual metadata

### Prometheus Metrics
Available at `/metrics`:
- `api_requests_total`: Total API requests by endpoint
- `api_request_duration_seconds`: API latency histogram

### ETL Monitoring
- Track success/failure rates
- Monitor processing times
- Alert on schema drift
- Record checkpoint status

## 🚢 Deployment

### Local Development
```bash
make up
```

### Cloud Deployment (AWS)

#### Option 1: ECS + RDS
```bash
# 1. Build and push Docker image
docker build -t kasparro-etl:latest .
docker tag kasparro-etl:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/kasparro-etl:latest
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/kasparro-etl:latest

# 2. Create RDS PostgreSQL instance
# 3. Create ECS task definition
# 4. Create ECS service
# 5. Set up EventBridge cron for ETL scheduling
```

#### Option 2: EC2 + Docker Compose
```bash
# On EC2 instance
git clone <repo>
cd kasparro-backend-vic
cp .env.example .env
# Edit .env with production values
make up
```

### Environment Variables (Production)
```bash
DATABASE_URL=postgresql://user:pass@prod-db:5432/kasparro_db
COINPAPRIKA_API_KEY=prod_key_here
COINGECKO_API_KEY=prod_key_here
LOG_LEVEL=INFO
```

## 🏆 Key Features Implemented

### ✅ P0 - Foundation (Required)
- [x] P0.1: Data ingestion from API + CSV
- [x] P0.2: Backend API with /data and /health endpoints
- [x] P0.3: Fully Dockerized system (make up/down/test)
- [x] P0.4: Basic test suite

### ✅ P1 - Growth Layer (Required)
- [x] P1.1: Third data source (CoinGecko)
- [x] P1.2: Checkpoint table + resume-on-failure
- [x] P1.3: /stats endpoint with ETL summaries
- [x] P1.4: Comprehensive test coverage
- [x] P1.5: Clean architecture with separation of concerns

### ✅ P2 - Differentiator Layer (Optional)
- [x] P2.1: Schema drift detection
- [x] P2.2: Failure injection + recovery testing
- [x] P2.3: Rate limiting + exponential backoff
- [x] P2.4: Observability (Prometheus metrics, structured logs)
- [x] P2.6: /runs endpoint for run comparison

## 🛠️ Technology Stack

- **Language**: Python 3.11
- **Web Framework**: FastAPI
- **Database**: PostgreSQL 15
- **ORM**: SQLAlchemy 2.0
- **Migrations**: Alembic
- **Validation**: Pydantic v2
- **Testing**: Pytest
- **Containerization**: Docker & Docker Compose
- **Monitoring**: Prometheus + JSON logging
- **Scheduling**: Python schedule library

## 📈 Performance Characteristics

- **API Latency**: < 100ms for most queries
- **ETL Runtime**: ~2-3 minutes for all sources
- **Data Freshness**: 6-hour update cycle
- **Fault Tolerance**: Automatic retry with exponential backoff
- **Scalability**: Batch processing + connection pooling

## 🔐 Security

- API keys stored in environment variables
- No hardcoded credentials
- Database connection pooling
- SQL injection protection via ORM
- Input validation with Pydantic

## 📚 Design Decisions

### Why FastAPI?
- Built-in OpenAPI documentation
- Async support for better performance
- Type hints and validation
- Modern, production-ready

### Why PostgreSQL?
- ACID compliance for data integrity
- JSON support for raw data storage
- Robust indexing for query performance
- Battle-tested reliability

### Why Separate Raw and Unified Tables?
- Preserve original data for auditing
- Enable schema evolution
- Support multiple source formats
- Facilitate debugging

### Why Checkpoint-Based Incremental Loading?
- Minimize redundant processing
- Enable resume-on-failure
- Reduce API calls
- Improve efficiency

