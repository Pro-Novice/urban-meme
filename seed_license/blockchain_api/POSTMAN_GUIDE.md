# Postman Collection Guide for Rajasthan Agriculture Blockchain API

This guide will help you set up and use the Postman collection for testing the Rajasthan Agriculture Blockchain API.

## Importing the Collection and Environment

1. Open Postman
2. Click on "Import" in the top-left corner
3. Select the `postman_collection.json` and `postman_environment.json` files
4. Both the collection and environment will be imported

## Setting Up the Environment

1. In Postman, click on the environment dropdown in the top-right corner
2. Select "Rajasthan Agriculture Dev Environment"
3. Make sure the `baseUrl` is set correctly (default: `http://127.0.0.1:8000`)
4. Configure your API key in the environment (default: `test_api_key_12345`)

## API Key Authentication

All blockchain API endpoints are secured with API key authentication. The API key needs to be sent in the `X-API-Key` header with every request. The Postman collection is already configured to include this header using the environment variable `apiKey`.

To obtain an API key for production use, contact the system administrator.

## Using the Collection

The collection is organized into the following folders:

1. **Admin Management**
   - Get Admin Address - Get the current smart contract admin address
   - Change Admin Address - Change the admin address

2. **Officer Management**
   - Add Department Officer - Add a new department officer with role
   - Remove Department Officer - Remove a department officer
   - Get Officer Role - Get the role of an officer
   - Check Officer Authorization - Check if an address is authorized as an officer

3. **Certificate Operations**
   - Generate Certificate Hash - Generate a hash for a license certificate
   - Verify Certificate - Verify a license certificate

4. **License Operations**
   - Apply for License - Apply for a new seed license
   - Get License Status - Check the status of a license
   - Update License Status - Update a license status
   - Get License Details - Get detailed information about a license
   - Get License History - Get the status change history of a license
   - Download Certificate - Get the certificate for an approved license

5. **Blockchain Transactions**
   - Get Transaction Status - Check the status of a blockchain transaction
   - Get Transaction History - Get transaction history

## Role IDs and Status Codes

### Department Roles

| Role ID | Role Name |
|---------|-----------|
| 0 | AGRICULTURE_OFFICER |
| 1 | DISTRICT_COLLECTOR |
| 2 | SEED_CERTIFICATION_OFFICER |
| 3 | SUBSIDY_APPROVAL_OFFICER |
| 4 | QUALITY_CONTROL_OFFICER |

### License Types

| Type ID | Type Name |
|---------|-----------|
| 0 | SEED_PRODUCTION |
| 1 | SEED_DISTRIBUTION |
| 2 | SEED_CERTIFICATION |
| 3 | HYBRID_SEED_PRODUCTION |
| 4 | ORGANIC_SEED_PRODUCTION |

### License Statuses

| Status ID | Status Name |
|-----------|-------------|
| 0 | APPLIED |
| 1 | DOCUMENTS_VERIFIED |
| 2 | FIELD_INSPECTION_COMPLETED |
| 3 | QUALITY_VERIFIED |
| 4 | APPROVED |
| 5 | REJECTED |
| 6 | REVOKED |
| 7 | EXPIRED |

## Example Workflow

Here's a typical workflow for testing the blockchain API:

1. Check the current admin address
2. Add a department officer
3. Verify the officer was added by checking their role
4. Apply for a license
5. Update the license status
6. Verify the certificate once approved
7. Check transaction history

## Tips

- Always check the response status and error messages
- All endpoints require API key authentication with the `X-API-Key` header
- For field validation, check the error messages returned in the response
- Make sure to use properly formatted Ethereum addresses in the requests
- In production, keep your API key secure and only share it with authorized systems
- The API includes request logging for security and audit purposes