"""Helper functions for seed_licenses tests"""

import apps.seed_licenses.views as views_module
from .fixtures import client, valid_license_payload, valid_update_status_payload



# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def assert_error_contains(response, expected_text, status_code=400):
    """Helper to assert error response contains expected text"""
    assert response.status_code == status_code
    error = response.json().get("error", "")
    assert expected_text.lower() in str(error).lower()


def mock_contract_read(monkeypatch, return_value=None, side_effect=None):
    """Helper to mock read_from_contract"""
    if side_effect:
        monkeypatch.setattr(views_module, "read_from_contract", lambda *args, **kwargs: (_ for _ in ()).throw(side_effect))
    else:
        monkeypatch.setattr(views_module, "read_from_contract", lambda *args, **kwargs: return_value)


def mock_contract_write(monkeypatch, return_value=None, side_effect=None):
    """Helper to mock write_to_contract"""
    if side_effect:
        monkeypatch.setattr(views_module, "write_to_contract", lambda *args, **kwargs: (_ for _ in ()).throw(side_effect))
    else:
        monkeypatch.setattr(views_module, "write_to_contract", lambda *args, **kwargs: return_value)
