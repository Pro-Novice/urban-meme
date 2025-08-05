# Blockchain API Module

This module provides API endpoints for interacting with the Seed License Tracking smart contract deployed on the blockchain.

## Architecture

- **services.py**: Service layer that directly interacts with the blockchain using Web3.py
- **views.py**: API endpoint controllers that validate input and return responses
- **urls.py**: URL routing configuration

## Available Endpoints

### Admin Management

- **GET /api/blockchain/contract/admin/**: Get the current admin address
- **POST /api/blockchain/contract/admin/change/**: Change the admin address
  - Required fields: `new_admin_address` (string)

### Officer Management

- **POST /api/blockchain/contract/officers/add/**: Add a department officer
  - Required fields: 
    - `officer_address` (string)
    - `role_id` (int, 0-4)
- **POST /api/blockchain/contract/officers/remove/**: Remove a department officer
  - Required fields: `officer_address` (string)
- **GET /api/blockchain/contract/officers/{officer_address}/role/**: Get an officer's role
- **GET /api/blockchain/contract/officers/{officer_address}/is-authorized/**: Check if an address is authorized as an officer

### Certificate Operations

- **GET /api/blockchain/contract/certificates/{license_id}/hash/**: Generate certificate hash
- **GET /api/blockchain/contract/certificates/{license_id}/verify/**: Verify a certificate

## Department Roles

The following roles are defined in the smart contract:

- **0**: AGRICULTURE_OFFICER
- **1**: DISTRICT_COLLECTOR
- **2**: SEED_CERTIFICATION_OFFICER
- **3**: SUBSIDY_APPROVAL_OFFICER
- **4**: QUALITY_CONTROL_OFFICER

## License Types

The following license types are defined in the smart contract:

- **0**: SEED_PRODUCTION
- **1**: SEED_DISTRIBUTION
- **2**: SEED_CERTIFICATION
- **3**: HYBRID_SEED_PRODUCTION
- **4**: ORGANIC_SEED_PRODUCTION

## Examples

### Adding a Department Officer

```json
POST /api/blockchain/contract/officers/add/
{
  "officer_address": "0x123456789012345678901234567890abcdef1234",
  "role_id": 2
}
```

Response:
```json
{
  "data": {
    "transaction_hash": "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
    "block_number": 12345678,
    "officer_address": "0x123456789012345678901234567890abcdef1234",
    "role_id": 2,
    "role_name": "SEED_CERTIFICATION_OFFICER"
  },
  "message": null,
  "error": null
}
```

### Verifying a Certificate

```
GET /api/blockchain/contract/certificates/12345/verify/
```

Response:
```json
{
  "data": {
    "license_id": 12345,
    "is_valid": true,
    "license_type": 0,
    "license_type_name": "SEED_PRODUCTION",
    "farmer_name": "John Doe",
    "approval_date": "2023-06-15T14:30:00",
    "expiry_date": "2024-06-15T14:30:00"
  },
  "message": null,
  "error": null
}
```