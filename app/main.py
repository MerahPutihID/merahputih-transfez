import argparse
import json
import logging
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
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


MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _loggable_headers(headers):
    # Never log the Authorization header value (JWT is sensitive).
    return {k: ("***" if k.lower() == "authorization" else v) for k, v in headers.items()}


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log request headers+body and response body.

    Needed because 422 validation errors happen before endpoint code runs, so
    endpoint-level logging never sees them. Full detail is logged only for
    mutating requests (POST/PUT/PATCH/DELETE) or any non-2xx response —
    GET /transaction/logs pagination would otherwise flood the logs.
    """
    body_bytes = await request.body()
    # Re-inject body so FastAPI can still parse it (request.body() caches on _body)
    request._body = body_bytes

    if request.method in MUTATING_METHODS:
        logger.info(
            "HTTP %s %s\n  headers=%s\n  body=%s",
            request.method,
            request.url.path,
            json.dumps(_loggable_headers(dict(request.headers)), indent=2),
            body_bytes.decode("utf-8", errors="replace"),
        )

    response = await call_next(request)

    needs_detail = request.method in MUTATING_METHODS or response.status_code >= 400
    if not needs_detail:
        return response

    response_body = b""
    try:
        async for chunk in response.body_iterator:
            response_body += chunk
    except Exception:
        pass

    logger.info(
        "HTTP %s %s -> %s body=%s",
        request.method,
        request.url.path,
        response.status_code,
        response_body.decode("utf-8", errors="replace"),
    )

    # Rebuild a fresh response since body_iterator was consumed
    return StreamingResponse(
        content=iter([response_body]),
        status_code=response.status_code,
        headers=dict(response.headers),
    )


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