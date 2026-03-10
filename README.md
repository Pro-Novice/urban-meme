# Rajasthan Agriculture Backend

This repository contains the **backend for Rajasthan Agriculture System**, built with **Django**, **Celery**, and **Redis**, and containerized with **Docker & Docker Compose**.

It supports asynchronous task execution using Celery workers, scheduled tasks with Celery Beat, and Redis as the message broker.

---

## 🚀 Tech Stack

* **Backend:** Python 3.11, Django, Gunicorn
* **Task Queue:** Celery, Celery Beat
* **Message Broker:** Redis
* **Database:** PostgreSQL (external)
* **Containerization:** Docker, Docker Compose

---

## 📂 Project Structure

```
RAJASTHAN-SEED-BACKEND/
├── apps/                 # Core Django apps
├── blockchain/           # Blockchain-related modules
├── config/               # Django settings & configurations
├── load_test/            # Load testing scripts
├── utils/                # Utility functions
├── venv/                 # Virtual environment (local only, not in Docker)
│
├── .env                  # Environment variables (ignored in Git)
├── .env.example          # Example env file for setup
├── .gitignore            # Git ignore rules
│
├── docker-manage.sh      # Deployment/Stopping automation script(for managing dockerised container)
├── docker-compose.yaml   # Multi-container definition
├── Dockerfile            # Web app Docker image
├── entrypoint.sh         # Entrypoint for migrations & collectstatic
│
├── manage.py             # Django entrypoint
├── requirements.txt      # Python dependencies
└── README.md             # Project documentation
```

---

## ⚙️ Services

* **web** → Django + Gunicorn application
* **redis** → Redis (with ACL support for secured access)
* **celery** → Celery worker for background tasks
* **celery-beat** → Celery scheduler for periodic tasks

---

## 🔑 Environment Variables

Create a `.env` file in the root directory:

```env
# Postgres
POSTGRES_HOST=your-db-host
POSTGRES_PORT=5432
POSTGRES_USER=your-db-user
POSTGRES_PASSWORD=your-db-password
POSTGRES_DB=your-db-name

# Redis
REDIS_USER=your-redis-user
REDIS_PASSWORD=your-redis-password

# Django
DJANGO_SECRET_KEY=your-secret-key
DJANGO_DEBUG=True
```
---

## 🛠️ Local Development (without Docker)

```bash
# Create venv
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Apply migrations
python manage.py migrate

# Start server
python manage.py runserver
```

---

## 🐳 Running with Docker

### Build & Start Services

```bash
docker compose up -d --build
```

### Stop Services

```bash
docker compose down -v
```

### View Logs

```bash
docker compose logs -f web
docker compose logs -f celery
```

---
## Testing

---

### ✅ Prerequisites

Ensure you have the following installed in your virtual environment:

* `pytest`
* `pytest-django`


### ⚙️ Configuration

Make sure your `pytest.ini` (or `pyproject.toml`) is configured properly. Example `pytest.ini`:

```ini
# pytest.ini
[pytest]
DJANGO_SETTINGS_MODULE = config.settings
python_files = tests.py test_*.py *_tests.py
```

### 🔍 Running Tests by following command


```bash
python -m pytest apps/seed_licenses/Tests/

```

## 📖 API Documentation (Swagger / OpenAPI 3.0)

### Overview

This project uses [`drf-spectacular`](https://github.com/tfranzel/drf-spectacular) to auto-generate an OpenAPI 3.0 schema directly from Django REST Framework views and serializers. The schema is served as an interactive Swagger UI and ReDoc page.

### Accessing the Docs

| Interface | URL |
|---|---|
| Swagger UI | http://localhost:8000/docs/ |
| ReDoc | http://localhost:8000/redoc/ |
| Raw OpenAPI YAML | http://localhost:8000/schema/ |

### Installation

`drf-spectacular` is listed in `requirements.txt`. If rebuilding a Docker image from scratch:
```bash
docker compose down
docker compose build --no-cache
docker compose up
```

For local development:
```bash
pip install drf-spectacular==0.27.2
```

#### Swagger / Schema Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/docs/` | Swagger UI — interactive API explorer |
| GET | `/redoc/` | ReDoc — clean API reference |
| GET | `/schema/` | Raw OpenAPI 3.0 YAML/JSON |

## 📜 Deployment

Use the provided `docker-manage.sh` script for automated deployment and removal of containers:

```bash
# For staging/dev
./docker-manage.sh

# For production
./docker-manage.sh production

# To stop everything
./docker-manage.sh stop
```

The script will:

1. Load environment variables from `.env`
2. Stop existing containers
3. Rebuild and start services
4. Configure Redis ACL with your `REDIS_USER` & `REDIS_PASSWORD`

---

## 📌 Notes

* Static and media files are stored in **Docker volumes**: `static_volume`, `media_volume`.
* Logs are mounted to `./logs` for easier debugging.
* Entrypoint ensures **migrations and collectstatic** run automatically before starting Gunicorn.

---

## 📡 API Example

### Submit License Application

**Endpoint**

`POST /license/create/`

**Required fields include `licenseNumber` (must be unique).**

```json
{
  "licenseCategory": "SEED",
  "licenseLevel": "STATE",
  "registeringAuthority": "Department of Agriculture",
  "registeringOfficeName": "District Agri Office, Jaipur",
  "licenseNumber": "RJSDST-EXAMPLE-001",
  "applicantName": "Ravi Kumar",
  "aadhaarNumber": "<encrypted_aadhaar>",
  "applicantPermanentAddress": "H.No 45, Green Colony, Jaipur",
  "firmName": "Ravi Agro Traders",
  "firmType": "Partnership",
  "firmAddress": "Plot No 22, Mandi Road, Jaipur",
  "salePointAddress": "Shop No 5, Krishi Market, Jaipur",
  "saleStorageAddress": "Warehouse No 3, Outer Ring Road, Jaipur",
  "cropName": "Wheat",
  "cropVariety": "HD2967",
  "isSeedSelfProduced": false,
  "productionCompany": "Agro Seeds Pvt Ltd"
}
```

**Success response (202)**

```json
{
  "success": true,
  "data": {
    "transactionHash": "0xabc123...",
    "status": "accepted",
    "message": "Transaction submitted successfully.",
    "licenseNumber": "RJSDST-EXAMPLE-001",
    "senderAddress": "0x..."
  }
}
```

### Get License Details By Number

**Endpoint**

`GET /license/info-by-number/<licenseNumber>/`

**Example**

`/license/info-by-number/RJSDST-EXAMPLE-001/`

### Get License Action History

**Endpoint**

`GET /license/history/<licenseId>/`

**Response includes submitted `licenseNumber` and `history` list.**

### Get License Action History By Number

**Endpoint**

`GET /license/history-by-number/<licenseNumber>/`

### Update License Status (By Number)

**Endpoint**

`POST /license/update-status/`

Use `licenseNumber` instead of `licenseId` in the payload.
