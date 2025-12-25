import logging
import sys
from pythonjsonlogger import jsonlogger
from core.config import get_settings

settings = get_settings()


def setup_logging():
    """Configure structured JSON logging"""
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, settings.log_level.upper()))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # JSON formatter
    logHandler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter(
        '%(asctime)s %(name)s %(levelname)s %(message)s',
        timestamp=True
    )
    logHandler.setFormatter(formatter)
    logger.addHandler(logHandler)
    
    return logger


# Global logger instance
logger = setup_logging()
