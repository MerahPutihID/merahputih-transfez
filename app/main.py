import argparse
import logging
from fastapi import FastAPI
from app.database import engine, Base
from app.models import Log, VALog  # noqa: F401 — register tables before create_all
from app.routes import api
from app.scheduler.queue_processor import run_scheduler
from app.config import settings
from app.utils import update_all_schemas

# Initialize logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Enable SQLAlchemy debug logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.pool').setLevel(logging.WARNING)

# Initialize database tables managed by this service (Log + VALog)
logger.info("Initializing database (Log and VA callback log tables)")
Base.metadata.create_all(bind=engine)

# Ensure VA log table + Log column patches
logger.info("Checking and updating managed database schemas...")
update_all_schemas()

# Initialize FastAPI app
app = FastAPI(
    title="CDM Transfer Processing Service",
    description="Service for processing transactions with gateway integration",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Include routers
app.include_router(api.router)

# The settings will be loaded based on APP_ENV
logger.info(f"Service running in {settings.ENV} mode")

def run_api():
    """Run the FastAPI server."""
    import uvicorn
    # Run with direct app object to avoid stale module imports during reload on Windows.
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the application as an API or a Scheduler.")
    parser.add_argument(
        "mode",
        choices=["api", "scheduler"],
        help="Mode to run the application: 'api' for FastAPI server, 'scheduler' for background job processing."
    )
    args = parser.parse_args()

    if args.mode == "api":
        run_api()
    elif args.mode == "scheduler":
        run_scheduler()