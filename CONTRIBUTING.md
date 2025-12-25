# Contributing Guide

Thank you for your interest in contributing to the Kasparro ETL System!

## Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/kasparro-backend-vic.git
   cd kasparro-backend-vic
   ```

2. **Run setup script**
   ```bash
   ./setup.sh
   ```

3. **Start the system**
   ```bash
   make up
   ```

## Code Style

### Python
- Follow PEP 8
- Use type hints
- Maximum line length: 100 characters
- Use meaningful variable names

### Example
```python
from typing import List, Optional

def process_crypto_data(
    data: List[dict],
    source: str,
    validate: bool = True
) -> Optional[int]:
    """
    Process cryptocurrency data from a source.
    
    Args:
        data: List of crypto records
        source: Data source name
        validate: Whether to validate data
        
    Returns:
        Number of records processed, or None on failure
    """
    pass
```

## Testing

### Running Tests
```bash
# All tests
make test

# Specific test file
docker-compose exec api pytest tests/test_etl.py -v

# With coverage
docker-compose exec api pytest --cov=. tests/
```

### Writing Tests
- Place tests in `tests/` directory
- Use descriptive test names
- Follow AAA pattern: Arrange, Act, Assert
- Use fixtures from `conftest.py`

### Example Test
```python
def test_coinpaprika_ingestion(test_db, sample_coinpaprika_data):
    """Test CoinPaprika data ingestion"""
    # Arrange
    ingestion = CoinPaprikaIngestion(test_db)
    
    # Act
    ingestion.transform_and_load(sample_coinpaprika_data)
    
    # Assert
    assert ingestion.records_processed == 2
    assert ingestion.records_failed == 0
```

## Adding a New Data Source

1. **Create ingestion class**
   ```python
   # ingestion/newsource.py
   from ingestion.base import BaseIngestion
   
   class NewSourceIngestion(BaseIngestion):
       def __init__(self, db: Session):
           super().__init__("newsource", db)
           
       def fetch_data(self) -> List[dict]:
           # Fetch data from source
           pass
           
       def transform_and_load(self, data: List[dict]):
           # Transform and load data
           pass
   ```

2. **Add Pydantic schema**
   ```python
   # schemas/crypto.py
   class NewSourceSchema(BaseModel):
       coin_id: str
       # ... other fields
   ```

3. **Create database model**
   ```python
   # core/models.py
   class RawNewSource(Base):
       __tablename__ = "raw_newsource"
       # ... columns
   ```

4. **Update ETL runner**
   ```python
   # core/etl_runner.py
   from ingestion import NewSourceIngestion
   
   def run_etl():
       # ... existing sources
       newsource = NewSourceIngestion(db)
       newsource.run()
   ```

5. **Write tests**
   ```python
   # tests/test_newsource.py
   def test_newsource_ingestion():
       pass
   ```

## Database Migrations

### Creating a Migration
```bash
# Inside API container
docker-compose exec api alembic revision --autogenerate -m "Add new table"

# Review migration in migrations/versions/
# Edit if needed

# Apply migration
docker-compose exec api alembic upgrade head
```

### Rolling Back
```bash
docker-compose exec api alembic downgrade -1
```

## Adding New API Endpoints

1. **Add endpoint to API**
   ```python
   # api/main.py
   @app.get("/new-endpoint")
   async def new_endpoint(db: Session = Depends(get_db)):
       # Implementation
       pass
   ```

2. **Add response schema**
   ```python
   # schemas/crypto.py
   class NewEndpointResponse(BaseModel):
       # Fields
       pass
   ```

3. **Write tests**
   ```python
   # tests/test_api.py
   def test_new_endpoint():
       response = client.get("/new-endpoint")
       assert response.status_code == 200
   ```

## Commit Guidelines

### Commit Message Format
```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types
- **feat**: New feature
- **fix**: Bug fix
- **docs**: Documentation changes
- **style**: Code style changes (formatting)
- **refactor**: Code refactoring
- **test**: Adding tests
- **chore**: Maintenance tasks

### Examples
```
feat(ingestion): add CoinMarketCap data source

- Create CoinMarketCap ingestion class
- Add Pydantic schema for validation
- Update ETL runner to include new source

Closes #123
```

```
fix(api): fix pagination bug in /data endpoint

Page calculation was off by one, causing incorrect results
on last page.

Fixes #456
```

## Pull Request Process

1. **Create a branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make changes and commit**
   ```bash
   git add .
   git commit -m "feat: add new feature"
   ```

3. **Push to GitHub**
   ```bash
   git push origin feature/your-feature-name
   ```

4. **Create Pull Request**
   - Describe your changes
   - Reference any related issues
   - Ensure tests pass
   - Request review

5. **Address feedback**
   - Make requested changes
   - Push updates to same branch

## Code Review Checklist

- [ ] Code follows style guidelines
- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] No console.log or print statements
- [ ] Error handling implemented
- [ ] Type hints added
- [ ] Commit messages follow guidelines

## Questions?

- Join our Discord: [link]
- Open an issue
- Email: [email]

---

**Happy coding!** 🚀
