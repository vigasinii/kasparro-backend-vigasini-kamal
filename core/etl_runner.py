import time
import schedule
from core.database import SessionLocal
from ingestion import CoinPaprikaIngestion, CoinGeckoIngestion, CSVIngestion
from core.logging_config import logger


def run_etl():
    """Run ETL for all sources"""
    logger.info("Starting ETL run for all sources")
    
    db = SessionLocal()
    
    try:
        # Run CoinPaprika ingestion
        logger.info("Running CoinPaprika ingestion")
        coinpaprika = CoinPaprikaIngestion(db)
        coinpaprika.run()
        
        # Run CoinGecko ingestion
        logger.info("Running CoinGecko ingestion")
        coingecko = CoinGeckoIngestion(db)
        coingecko.run()
        
        # Run CSV ingestion
        logger.info("Running CSV ingestion")
        csv = CSVIngestion(db)
        csv.run()
        
        logger.info("ETL run completed for all sources")
        
    except Exception as e:
        logger.error(f"ETL run failed: {str(e)}", exc_info=True)
    finally:
        db.close()


def run_scheduler():
    """Run ETL scheduler"""
    logger.info("ETL Scheduler started")
    
    # Run immediately on startup
    logger.info("Running initial ETL on startup")
    run_etl()
    
    # Schedule ETL to run every 6 hours
    schedule.every(6).hours.do(run_etl)
    
    # Keep scheduler running
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute


if __name__ == "__main__":
    run_scheduler()
