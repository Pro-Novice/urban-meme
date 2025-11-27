"""
Helper functions for seed license tests.
Place this file as: tests/test_helpers.py
"""


def get_error_message(resp):
    """
    Extract error message from response.
    
    Args:
        resp: Response object from API call
        
    Returns:
        str: Concatenated error message from response
    """
    data = resp.json()
    if isinstance(data, dict):
        parts = []

        def collect(k, v):
            if isinstance(v, str):
                parts.append(f"{k}: {v}")
            elif isinstance(v, list):
                for i in v:
                    collect(k, i)
            elif isinstance(v, dict):
                for subk, subv in v.items():
                    collect(subk, subv)

        for key, value in data.items():
            collect(key, value)

        return " ".join(parts)
    return str(data)


def assert_success_response(resp, expected_status=200):
    """
    Assert that response is successful.
    
    Args:
        resp: Response object
        expected_status: Expected HTTP status code
    """
    assert resp.status_code == expected_status
    data = resp.json()
    assert data.get("success") is True


def assert_error_response(resp, expected_status, keywords=None):
    """
    Assert that response contains an error.
    
    Args:
        resp: Response object
        expected_status: Expected HTTP status code
        keywords: List of keywords that should appear in error message
    """
    assert resp.status_code == expected_status
    
    if keywords:
        error_msg = get_error_message(resp).lower()
        for keyword in keywords:
            assert keyword.lower() in error_msg, f"Expected '{keyword}' in error message"


def assert_has_keys(data, expected_keys):
    """
    Assert that data contains all expected keys.
    
    Args:
        data: Dictionary to check
        expected_keys: Set or list of expected keys
    """
    if isinstance(expected_keys, list):
        expected_keys = set(expected_keys)
    
    missing_keys = expected_keys - set(data.keys())
    assert not missing_keys, f"Missing keys: {missing_keys}"


def assert_transaction_accepted(resp):
    """
    Assert that a blockchain transaction was accepted.
    
    Args:
        resp: Response object
    """
    assert resp.status_code == 202
    data = resp.json()["data"]
    assert "transaction_hash" in data or "transactionHash" in data


def create_mock_service_response(success=True, **kwargs):
    """
    Create a mock service response.
    
    Args:
        success: Whether the operation was successful
        **kwargs: Additional fields to include in response
        
    Returns:
        dict: Mock service response
    """
    response = {"success": success}
    response.update(kwargs)
    return response
def assert_error_contains(response, expected_text, status_code=400):
    """Helper to assert error response contains expected text"""
    assert response.status_code == status_code
    error = response.json().get("error", "")
    assert expected_text in str(error)