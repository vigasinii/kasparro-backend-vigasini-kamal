from ingestion.base import BaseIngestion
from ingestion.coinpaprika import CoinPaprikaIngestion
from ingestion.coingecko import CoinGeckoIngestion
from ingestion.csv_source import CSVIngestion

__all__ = [
    'BaseIngestion',
    'CoinPaprikaIngestion',
    'CoinGeckoIngestion',
    'CSVIngestion'
]
