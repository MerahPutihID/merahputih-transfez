# Merahputih Transfez Integration

## Table of Contents

- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
  - [Environment Variables](#environment-variables)
- [Running the Service](#running-the-service)
  - [API Mode](#api-mode)
  - [Scheduler Mode](#scheduler-mode)
- [Project Structure](#project-structure)
  - [Key Components](#key-components)
  - [Configuration Files](#configuration-files)
- [API Endpoints](#api-endpoints)
  - [Transaction Endpoints](#transaction-endpoints)
  - [Transaction States](#transaction-states)
- [Docker Deployment](#docker-deployment)
  - [Prerequisites](#docker-prerequisites)
  - [Service Management](#service-management)
  - [Environment Configuration](#environment-configuration)
  - [Docker Image Management](#docker-image-management)
  - [Health Checks](#health-checks)
  - [Troubleshooting](#troubleshooting)

## Features

- RESTful API endpoints for transaction processing
- Background job scheduler for queue processing
- PostgreSQL database integration
- Comprehensive logging system
- Environment-based configuration
- H2H integration support

## Prerequisites

- Python 3.9 or higher
- PostgreSQL 13 or higher
- pip (Python package installer)

## Installation

1. Clone the repository:
```bash
git clone git@github.com:your-org/merahputih-transfez.git
cd merahputih-transfez
```

2. Create and activate virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Configuration

1. Copy example environment file:
```bash
cp .env.example .env
```

2. Configure environment variables:
```properties
# App Configuration
APP_ENV=development
LOG_LEVEL=DEBUG
HTTP_DEBUG=True

# Database Configuration
DATABASE_URL=postgresql://user:password@localhost:5432/dbname
SQLALCHEMY_ECHO=FALSE
SQLALCHEMY_POOL_SIZE=5
SQLALCHEMY_POOL_TIMEOUT=30

# API Configuration
API_BASE_URL=http://localhost:8000
THIRD_PARTY_API_URL=https://api.thirdparty.com
THIRD_PARTY_API_KEY=your_api_key

# Transaction Settings
BALANCE_ID=7
TRANSFER_SERVICE_CODE=1  # Options: 1-BiFAST, 2-SKN, 3-RTGS, 4-Smart Route
NOTES="Transaction processed via CDT Gateway"

# Queue Processing Settings
QUEUE_PROCESSING_TIME_THRESHOLD_HOURS=24  # How many hours back to look for transactions

# Transaction Splitting Settings
MAX_TRANSACTION_AMOUNT=250000  # Maximum amount per transaction in IDR

# Sender Information
SENDER_FIRSTNAME=John
SENDER_LASTNAME=Doe
SENDER_COUNTRY_ISO_CODE=IDN

# Compliance Information
COMPLIANCE_SOURCE_OF_FUNDS=SALARY_INCOME
COMPLIANCE_BENEFICIARY_RELATIONSHIPS=SIBLING_BROTHER_SISTER
COMPLIANCE_PURPOSE_OF_REMITTANCES=FAMILY_SUPPORT
```

3. Environment Variables Description:

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `APP_ENV` | Application environment (development/production) | Yes | development |
| `LOG_LEVEL` | Logging level (DEBUG/INFO/WARNING/ERROR) | No | INFO |
| `HTTP_DEBUG` | Enable HTTP request/response debugging | No | False |
| `DATABASE_URL` | PostgreSQL connection string | Yes | None |
| `SQLALCHEMY_ECHO` | Enable SQLAlchemy query logging | No | FALSE |
| `SQLALCHEMY_POOL_SIZE` | Connection pool size | No | 5 |
| `SQLALCHEMY_POOL_TIMEOUT` | Connection timeout in seconds | No | 30 |
| `API_BASE_URL` | Base URL for **remittance** callbacks (scheduler → BMP transaction service, e.g. `.../transaction/callback/{id}`) | Yes | None |
| `GATEWAY_PUBLIC_URL` | Public base URL of **this** merahputih-transfez app (VA callback → `{GATEWAY_PUBLIC_URL}/va/callback/{partner_trx_id}`) | No | None |
| `THIRD_PARTY_API_URL` | Third-party API base URL | Yes | None |
| `THIRD_PARTY_API_KEY` | API key for authentication | Yes | None |
| `BALANCE_ID` | Balance ID for transactions | Yes | None |
| `TRANSFER_SERVICE_CODE` | Transfer service type | No | 1 |
| `NOTES` | Default transaction notes | No | "Transaction processed via CDT Gateway" |
| `QUEUE_PROCESSING_TIME_THRESHOLD_HOURS` | How many hours back to look for transactions | No | 24 |
| `MAX_TRANSACTION_AMOUNT` | Maximum amount per transaction in IDR | Yes | None |
| `SENDER_FIRSTNAME` | Sender's first name | Yes | None |
| `SENDER_LASTNAME` | Sender's last name | Yes | None |
| `SENDER_COUNTRY_ISO_CODE` | Sender's country code | Yes | None |
| `COMPLIANCE_SOURCE_OF_FUNDS` | Source of funds category | Yes | None |
| `COMPLIANCE_BENEFICIARY_RELATIONSHIPS` | Relationship with beneficiary | Yes | None |
| `COMPLIANCE_PURPOSE_OF_REMITTANCES` | Purpose of transaction | Yes | None |

## Running the Service

### API Mode
```bash
# Original method
python -m app.main api

# Alternative method with proper Python path
python run_app.py
```

The API will be available at:
- API Documentation: http://localhost:8000/docs
- ReDoc Interface: http://localhost:8000/redoc

### Scheduler Mode
```bash
# Original method
python -m app.main scheduler

# Alternative method with proper Python path
python run_scheduler.py
```

## Project Structure

```
merahputih-transfez/
├── app/                            # Application package
│   ├── config/                     # Configuration module
│   │   ├── __init__.py            # Config initialization
│   │   ├── base.py                # Base configuration class
│   │   ├── development.py         # Development settings
│   │   └── production.py          # Production settings
│   ├── routes/                    # API routes module
│   │   ├── __init__.py           # Routes initialization
│   │   └── api.py                # API endpoint definitions
│   ├── scheduler/                 # Background jobs module
│   │   ├── __init__.py           # Scheduler initialization
│   │   └── queue_processor.py     # Queue processing logic
│   ├── utils/                     # Utility functions module
│   │   ├── __init__.py           # Utils initialization
│   │   ├── fee_calculator.py     # Transaction fee calculation
│   │   ├── transaction_splitter.py # Large transaction handling
│   │   └── schema_updater.py     # Database schema management
│   ├── database.py               # Database configuration
│   ├── main.py                   # Application entry point
│   ├── models.py                 # Database models
│   ├── schemas.py                # Pydantic schemas
│   ├── services.py               # Business logic
│   └── constants.py              # Application constants
├── .env                         # Environment variables
├── .env.example                 # Example environment file
├── .gitignore                  # Git ignore rules
├── Dockerfile                  # Main Dockerfile
├── README.md                  # Project documentation
├── docker-compose.yml        # Docker Compose config
├── run_app.py               # Script to run the API service
├── run_scheduler.py        # Script to run the scheduler service
└── requirements.txt        # Project dependencies
```

### Key Components

- **app/**: Main application package
  - **config/**: Environment-specific configurations
  - **routes/**: API endpoint definitions
  - **scheduler/**: Background job processing
  - **utils/**: Helper functions and utilities
    - **fee_calculator.py**: Calculates transaction fees based on customer configuration
    - **transaction_splitter.py**: Handles splitting large transactions into smaller parts
    - **schema_updater.py**: Manages database schema updates for the Log model
  - **models.py**: Database model definitions
  - **schemas.py**: Request/Response schemas
  - **services.py**: Business logic implementation
  - **constants.py**: Application constants and status codes

### Configuration Files

- **.env**: Environment-specific variables
- **Dockerfile**: Container configuration
- **docker-compose.yml**: Service orchestration
- **requirements.txt**: Python dependencies

## API Endpoints

### Transaction Endpoints
- `GET /transaction/logs`
  - Get transaction logs with pagination
  - Query parameters:
    - `skip` (optional): Number of records to skip (default: 0)
    - `limit` (optional): Maximum number of records to return (default: 100)
  - Response: List of transaction logs ordered by creation date (newest first)

- `POST /transaction/callback/{reference_id}`
  - Handle transaction callbacks from 3rd-party service
  - Path parameters:
    - `reference_id`: Unique reference ID of the transaction
  - Request body: Callback data with transaction status and details
  - Response: Callback processing status and transaction details

- `POST /va_numbers`
  - Create Virtual Account to Transfez endpoint `/va_numbers`
  - Validation rules:
    - `amount` must be `0` when `is_open=true`
    - `virtual_account` must be exactly 15 chars when provided
    - `trx_expiration_time` must be lower than `expiration_time` when provided
  - Response:
    - Returns Transfez response payload in `data`

### Transaction States
- `PENDING`: Initial state
- `PROCESSING`: Transaction is being processed
- `CONFIRMED`: Transaction confirmed with 3rd party
- `SUCCESS`: Transaction completed successfully
- `FAILED`: Transaction failed to process

### Transaction Splitting

The service includes a transaction splitting mechanism that handles large transactions by dividing them into smaller parts:

1. **How Splitting Works**:
   - Only BI-Fast transactions (TRANSFER_SERVICE_CODE=1) are eligible for splitting
   - Transactions are split if they exceed the `MAX_TRANSACTION_AMOUNT` value
   - Each split maintains a reference to the parent transaction
   - All transactions use a consistent split structure for simplified processing
   - Split reference IDs follow the pattern: `{original-id}-{XX}` (e.g., `TRX123-01`, `TRX123-02`)
   - Minimum split amount is 10,000 IDR (except potentially the last split)

2. **Fee Handling**:
   - Transaction fee is calculated first, before splitting
   - Fee tracking is applied to the last split for reporting purposes
   - The system calculates fees based on customer configuration
   - Fees can be percentage-based or fixed amounts
   - The final amount (after fee deduction) is used for splitting to ensure the correct total is sent

3. **Example**:
   - Original amount: 600,000 IDR
   - Fee: 1,000 IDR
   - Amount after fee deduction: 599,000 IDR
   - Maximum transaction amount: 250,000 IDR
   - Result: Three splits (250,000 IDR, 250,000 IDR, 99,000 IDR)
   - Fee tracking applied to last split (99,000 IDR)
   - Total sent: 599,000 IDR (original amount minus fee)

4. **Parent-Child Relationship**:
   - Parent transaction logs track all splits
   - Parent status updates based on child transaction status
   - Success requires all splits to succeed
   - Partial success is recorded if some splits succeed

## Docker Deployment

### Prerequisites
- Docker 20.10 or higher
- Docker Compose v2.0 or higher

### Service Management

Start specific services:
```bash
# Run API service only
docker compose up api -d

# Run scheduler service only
docker compose up scheduler -d
```

Check service status:
```bash
# List running services
docker compose ps

# View service logs
docker compose logs -f api
docker compose logs -f scheduler
```

Stop services:
```bash
# Stop all services
docker compose down

# Stop specific service
docker compose stop api
docker compose stop scheduler
```

### Environment Configuration

1. Development environment:
```bash
# Start services in development mode
APP_ENV=development docker compose up -d
```

2. Production environment:
```bash
# Start services in production mode
APP_ENV=production docker compose up -d
```

### Docker Image Management

1. Build and tag images:
```bash
# Build base images
docker compose build

# Tag API service
docker tag merahputih-transfez-api:latest merahputih-transfez-api:1.0.0
docker tag merahputih-transfez-api:latest merahputih-transfez-api:dev

# Tag Scheduler service
docker tag merahputih-transfez-scheduler:latest merahputih-transfez-scheduler:1.0.0
docker tag merahputih-transfez-scheduler:latest merahputih-transfez-scheduler:dev
```

2. List available images:
```bash
# View all tagged images
docker images | grep merahputih-transfez

# View specific service images
docker images merahputih-transfez-api
docker images merahputih-transfez-scheduler
```

3. Run specific versions:
```bash
# Run with version tag
docker compose up -d \
  --build \
  -e IMAGE_TAG=1.0.0

# Run with environment tag
docker compose up -d \
  --build \
  -e IMAGE_TAG=dev
```

4. Tag naming conventions:
- Release versions: `1.0.0`, `1.0.1`, etc.
- Development: `dev`
- Latest: `latest`

5. Clean up old images:
```bash
# Remove unused images
docker image prune -f

# Remove specific tag
docker rmi merahputih-transfez-api:1.0.0
docker rmi merahputih-transfez-scheduler:1.0.0
```

### Health Checks

API service health:
```bash
curl http://localhost:8000/health
```

### Troubleshooting

1. Database connection issues:
```bash
# Test database connection
docker compose exec api python -c "from app.database import engine; engine.connect()"
```

2. Service logs:
```bash
# View real-time logs
docker compose logs -f

# View specific service logs with timestamps
docker compose logs -f --timestamps api
```

3. Error Handling:
- The system has robust error handling at all stages of transaction processing
- Errors are captured in transaction logs with detailed error messages
- Parent transactions reflect the status of all child splits
- Safe initialization ensures data consistency even if errors occur early

4. Common issues:
- Ensure PostgreSQL is running and accessible
- Check database credentials in `.env`
- Verify network connectivity to external services
- Ensure required ports are not in use
- Validate transaction amount format (must be numeric)
- Check customer configuration for fee calculation
