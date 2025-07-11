# API Key Setup for Rajasthan Agriculture Blockchain API

This document provides instructions for setting up and managing API keys for the blockchain API.

## Overview

The blockchain API uses API key authentication to secure all endpoints. Each client system that needs to access the API should be issued a unique API key.

## Configuration

API keys are configured in the Django settings file (`settings.py`):

```python
# API Keys for blockchain API access
# Format: 'api_key': 'client_name'
API_KEYS = {
    env('RAJ_AGRI_API_KEY', default='test_api_key_12345'): 'Rajasthan Agriculture Department',
    # Add more API keys as needed
}
```

## Setting Up API Keys in Production

For production environments, follow these steps:

1. Generate a secure, random API key for each client system:
   ```bash
   # Using Python
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

2. Set the API key in your environment variables:
   ```bash
   # In your .env file
   RAJ_AGRI_API_KEY=your_generated_key_here
   ```

3. Add additional API keys for different client systems:
   ```python
   # In settings.py
   API_KEYS = {
       env('RAJ_AGRI_API_KEY', default='test_api_key_12345'): 'Rajasthan Agriculture Department',
       env('OTHER_CLIENT_API_KEY'): 'Other Client Name',
       # More keys...
   }
   ```

## Security Best Practices

1. **Unique Keys**: Issue a unique API key for each client system
2. **Key Rotation**: Rotate API keys periodically (e.g., every 90 days)
3. **Secure Transfer**: Share API keys with clients through secure channels
4. **Revocation**: Have a process to quickly revoke API keys if compromised
5. **Monitoring**: Monitor API usage for suspicious activity
6. **Least Privilege**: Only issue API keys to systems that need them

## Client Setup

Instruct clients to include the API key in the `X-API-Key` header with every request:

```
X-API-Key: your_api_key_here
```

## Monitoring and Logging

All API requests are logged with the following information:
- Method and URL path
- Client IP address
- Partial API key (first 5 characters followed by "...")
- Request data (for POST requests)
- Response status code
- Request processing time

These logs are stored in the application log file and can be used for auditing and monitoring purposes.

## API Key Management

For managing API keys, consider:

1. Maintaining a separate document with:
   - Client name
   - API key assigned
   - Issue date
   - Expiration date
   - Contact person

2. Setting up a calendar reminder for key rotation

3. Implementing a notification system when keys are about to expire

## Testing

Use the test API key `test_api_key_12345` for development and testing environments only.