# Rajasthan_Agri_Backend License Authentication System (Django Backend)

A Django-based backend for managing role-based authentication of agriculture license holders in Rajasthan, supporting PostgreSQL, JWT, Redis, and secure API development.

## Setup Guide (Local)
# Rajasthan Agriculture Blockchain License System

A Django-based backend for managing agriculture licenses in Rajasthan using blockchain technology for authentication and verification.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.10+-brightgreen.svg)
![Django](https://img.shields.io/badge/django-4.2+-green.svg)

## Running Local Blockchain Node
1. Check current node version with below command
```
node --version
npm --version  
```

2. Create a new folder for initilizing the dummy project for running hardhat


# Create project directory
mkdir my-hardhat-project
cd my-hardhat-project

# Initialize npm project
npm init -y

# Install Hardhat
npm install --save-dev hardhat

# Initialize Hardhat project
npx hardhat init project

3. Run Hardhat node in a new terminal
```
npx hardhat node
```

4.After this you should be able to deploy contracts on the local blockchain


## 🏗️ Smart Contract Architecture

The system uses UUPS (Universal Upgradeable Proxy Standard) pattern for smart contracts:

### Smart Contract Components:

1. **LicenseStorage.sol** - Storage contract with all state variables
2. **LicenseSystemV1.sol** - Initial implementation with core functionality
3. **LicenseSystemV2.sol** - Upgraded version with bulk operations
4. **ERC1967Proxy.sol** - Proxy contract for upgradeability

### License Categories:
- SEED
- FERTILIZER
- INSECTICIDE

### License Workflow States:
- DRAFT
- SUBMITTED
- UNDER_REVIEW
- DOCUMENTS_VERIFIED
- PAYMENT_PENDING
- PAYMENT_COMPLETED
- INSPECTION_SCHEDULED
- INSPECTION_COMPLETED
- APPROVED
- REJECTED
- REVOKED
- EXPIRED
- RENEWAL_PENDING

### Smart Contract Features:
- **Multi-level Administration**: STATE, DIVISION, DISTRICT levels
- **Document Management**: IPFS integration for document storage
- **Payment Tracking**: Complete payment lifecycle management
- **Inspection System**: GPS-enabled inspection reports with photo evidence
- **Audit Trail**: Immutable action history for compliance
- **Role-Based Access**: Officers with specific permissions
- **Bulk Operations**: Process multiple licenses simultaneously

## 🚀 Quick Start with Docker (Recommended)

The easiest way to run this application is using Docker:

### Prerequisites
- Docker and Docker Compose installed on your system

### Running with Docker

1. **Clone the repository**:
   ```bash
   git clone https://github.com/C3I-blockchain/rajasthan_agri_backend.git
   cd rajasthan_agri_backend
   ```

2. **Configure environment variables**:
   ```bash
   cp .env.docker .env
   ```
   
   Edit the `.env` file with your specific settings, especially:
   - Blockchain settings (BLOCKCHAIN_URL, CONTRACT_ADDRESS, PRIVATE_KEY)
   - API key configuration

3. **Run the application**:
   ```bash
   docker-compose up -d
   ```
   
   This will start:
   - Web application (Django backend)
   - PostgreSQL database
   - Redis cache

4. **Create a superuser** (if needed):
   ```bash
   docker-compose exec web python manage.py createsuperuser
   ```

5. **Access the application**:
   - API Endpoints: http://localhost:8000/api/
   - Admin Interface: http://localhost:8000/admin/

### Managing the Docker Application

**View logs**:
```bash
docker-compose logs -f
```

**Stop the application**:
```bash
docker-compose down
```

**Stop and remove all data** (including database):
```bash
docker-compose down -v
```

## 🔧 Local Development Setup
# Rajasthan_Agri_Backend License Authentication System (Django Backend)

A Django-based backend for managing role-based authentication of agriculture license holders in Rajasthan, supporting PostgreSQL, JWT, Redis, and secure API development.

## Setup Guide (Local)

### Prerequisites

- Python 3.10+
- PostgreSQL
- Redis
- Ethereum/Polygon wallet with funds for transaction fees

### Setup Steps

1. **Clone the repository**:
   ```bash
   git clone https://github.com/C3I-blockchain/rajasthan_agri_backend.git
   cd rajasthan_agri_backend
   ```

2. **Create and activate virtual environment**:
   ```bash
   # macOS/Linux
   python3 -m venv env
   source env/bin/activate
   
   # Windows
   python -m venv env
   env\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**:
   Create a `.env` file in the root directory with:
   ```
   SECRET_KEY=your_secret_key
   POSTGRES_DB=your_db_name
   POSTGRES_USER=your_db_user
   POSTGRES_PASSWORD=your_db_password
   POSTGRES_HOST=localhost
   POSTGRES_PORT=5432
   REDIS_URL=redis://localhost:6379/0
   EMAIL_HOST=smtp.gmail.com
   EMAIL_PORT=587
   EMAIL_USE_TLS=True
   EMAIL_HOST_USER=your_email@example.com
   EMAIL_HOST_PASSWORD=your_email_password
   BLOCKCHAIN_URL=https://rpc-amoy.polygon.technology/
   CONTRACT_ADDRESS=your_contract_address
   PRIVATE_KEY=your_wallet_private_key
   RAJ_AGRI_API_KEY=your_api_key
   ```

5. **Apply database migrations**:
   ```bash
   python manage.py makemigrations seed_license
   python manage.py migrate
   ```

6. **Create superuser**:
   ```bash
   python manage.py createsuperuser
   ```

7. **Run the development server**:
   ```bash
   python manage.py runserver
   ```

## 🔑 API Key Authentication

This system uses API key authentication instead of user-based authentication to secure all blockchain interactions.

### How It Works

1. API keys are configured in settings.py:
   ```python
   API_KEYS = {
       env('RAJ_AGRI_API_KEY', default='test_api_key_12345'): 'Rajasthan Agriculture Department',
   }
   ```

2. To use API endpoints, include the API key in your request header:
   ```
   X-API-Key: your_api_key
   ```

3. The system logs API usage and validates the API key with each request.


## 📁 Project Structure

```
rajasthan_agri_backend/
├── agri_backend/              # Django project settings
├── Services/                  # Common services including blockchain
│   ├── api_response.py
│   ├── blockchain/
│   │   └── contracts/         # Smart contract ABIs and addresses
│   ├── exceptions.py
│   └── logger.py
├── seed_license/              # Main app for license operations
│   ├── blockchain_api/        # Blockchain API endpoints
│   ├── blockchain_services.py # Services for blockchain interactions
│   ├── models.py              # Database models
│   ├── seed_license_handler.py # Core business logic
│   ├── urls.py                # URL routing
│   └── views.py               # API views
├── manage.py
├── Dockerfile
├── docker-compose.yaml
└── requirements.txt
```

## 📊 Testing

Test the APIs using the Postman collection:

[Rajasthan Agri Backend API Collection](https://api.postman.com/collections/43756014-4e680ff3-8491-4a4c-add8-67caf1c4567f?access_key=PMAT-01JRYRERX1VYS278G4YXHR03QC)

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgements

- Rajasthan Agriculture Department
- C3I Blockchain Team