#!/usr/bin/env python
"""
Run script with proper Python path setup.
This ensures that the app modules can be imported correctly.
"""
import os
import sys
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Add the project root directory to the Python path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from app.scheduler.queue_processor import run_scheduler
from app.utils import update_all_schemas
from app.database import engine, Base

if __name__ == "__main__":
    # Initialize database and update schema
    logger.info("Initializing database...")
    Base.metadata.create_all(bind=engine)
    
    # Run schema updates to ensure all columns exist
    logger.info("Checking and updating database schema...")
    update_all_schemas()
    
    # Start the scheduler
    run_scheduler()
