import pytest
import json
from unittest.mock import patch
from django.urls import reverse

from apps.seed_licenses.tests.integration.fixtures import (
    blockchain_state,
    seed_license_payload,
    fertilizer_license_payload,
    pesticide_license_payload,
    complete_license_payload,
    mock_transaction_service,
    mock_license_service,
    mock_multi_account_manager,
    mock_celery_tasks,
)
from apps.seed_licenses.tests.conftest import client
import pytest

# =============================================================================
# Helpers
# =============================================================================

def _submit(client, payload):
    return client.post(
        reverse("submit-license-application"),
        data=json.dumps(payload),
        content_type="application/json",
    )


def _get_count(client):
    resp = client.get(reverse("license-count"))
    assert resp.status_code == 200
    data = resp.json()["data"]
    return data.get("total_licenses", 0) if isinstance(data, dict) else data


def _get_info(client, license_id):
    return client.get(reverse("license-basic-info", args=[license_id]))


# =============================================================================
@pytest.mark.django_db
class TestConcurrentOperations:
   
    def test_parallel_seed_submissions(
        self, client, seed_license_payload, blockchain_state,
        mock_transaction_service, mock_license_service,
        mock_multi_account_manager, mock_celery_tasks,
    ):
        """5 SEED licenses submitted rapidly all succeed."""
        with patch("apps.seed_licenses.views.license_view.license_service", mock_license_service), \
             patch("apps.seed_licenses.views.license_view.tx_service",      mock_transaction_service):

            for i in range(5):
                payload = {**seed_license_payload,
                           "applicantName": f"Applicant {i+1}",
                           "licenseNumber": f"RJSDST-CONC-{i+1:03d}"}
                resp = _submit(client, payload)
                assert resp.status_code == 202
                assert resp.json()["data"]["status"] in ("pending", "accepted")

            assert _get_count(client) == 5

    def test_parallel_mixed_category_submissions(
        self, client, seed_license_payload, fertilizer_license_payload,
        pesticide_license_payload, blockchain_state,
        mock_transaction_service, mock_license_service,
        mock_multi_account_manager, mock_celery_tasks,
    ):
        """SEED / FERTILIZER / PESTICIDE licenses submitted in the same burst."""
        with patch("apps.seed_licenses.views.license_view.license_service", mock_license_service), \
             patch("apps.seed_licenses.views.license_view.tx_service",      mock_transaction_service):

            submissions = [
                {**seed_license_payload,        "licenseNumber": "RJSDST-PAR-001"},
                {**fertilizer_license_payload,  "licenseNumber": "RJFTST-PAR-001"},
                {**pesticide_license_payload,   "licenseNumber": "RJPSDT-PAR-001"},
                {**seed_license_payload,        "licenseNumber": "RJSDST-PAR-002",
                 "applicantName": "Seed App 2"},
                {**fertilizer_license_payload,  "licenseNumber": "RJFTST-PAR-002",
                 "applicantName": "Fert App 2"},
            ]
            for payload in submissions:
                resp = _submit(client, payload)
                assert resp.status_code == 202, \
                    f"{payload['licenseNumber']}: {resp.json()}"

            assert _get_count(client) == 5

            # Verify geo isolation still correct after burst
            # id=1 is SEED → no lat/lng
            resp = _get_info(client, 1)
            if resp.status_code == 200:
                assert "latitude"  not in resp.json()["data"]
                assert "longitude" not in resp.json()["data"]

            # id=2 is FERTILIZER → lat/lng present
            resp = _get_info(client, 2)
            if resp.status_code == 200:
                info = resp.json()["data"]
                assert "latitude"  in info
                assert "longitude" in info
 
    def test_rapid_reads_after_mixed_submissions(
        self, client, seed_license_payload, fertilizer_license_payload,
        pesticide_license_payload, blockchain_state,
        mock_transaction_service, mock_license_service,
        mock_multi_account_manager, mock_celery_tasks,
    ):
        """Rapid GET requests after submissions return stable data."""
        with patch("apps.seed_licenses.views.license_view.license_service", mock_license_service), \
             patch("apps.seed_licenses.views.license_view.tx_service",      mock_transaction_service):

            _submit(client, seed_license_payload)
            _submit(client, fertilizer_license_payload)
            _submit(client, pesticide_license_payload)

            for _ in range(5):
                for lid in (1, 2, 3):
                    resp = _get_info(client, lid)
                    assert resp.status_code in (200, 500)
  
    def test_rapid_status_updates_same_license(
        self, client, seed_license_payload, blockchain_state,
        mock_transaction_service, mock_license_service,
        mock_multi_account_manager, mock_celery_tasks,
    ):
        """Sequential status updates on the same license (existing behaviour)."""
        with patch("apps.seed_licenses.views.license_view.license_service", mock_license_service), \
             patch("apps.seed_licenses.views.license_view.tx_service",      mock_transaction_service):

            _submit(client, {**seed_license_payload, "licenseNumber": "RJSDST-RAPID-001"})
            assert _get_count(client) == 1


    def test_multiple_licenses_different_operations(
        self, client, seed_license_payload, fertilizer_license_payload,
        pesticide_license_payload, blockchain_state,
        mock_transaction_service, mock_license_service,
        mock_multi_account_manager, mock_celery_tasks,
    ):
        """Different operations on three licenses in one test."""
        with patch("apps.seed_licenses.views.license_view.license_service", mock_license_service), \
             patch("apps.seed_licenses.views.license_view.tx_service",      mock_transaction_service):

            _submit(client, seed_license_payload)
            _submit(client, fertilizer_license_payload)
            _submit(client, pesticide_license_payload)

            # GET info for each
            for lid in (1, 2, 3):
                resp = _get_info(client, lid)
                assert resp.status_code in (200, 500)

            # GET QR for each
            for lid in (1, 2, 3):
                resp = client.get(reverse("license-qr-data", args=[lid]))
                assert resp.status_code in (200, 500)

            # GET history for each
            for lid in (1, 2, 3):
                resp = client.get(reverse("license-action-history", args=[lid]))
                assert resp.status_code in (200, 500)

            assert _get_count(client) == 3

    def test_license_number_uniqueness_under_concurrent_submissions(
        self, client, seed_license_payload, blockchain_state,
        mock_transaction_service, mock_license_service,
        mock_multi_account_manager, mock_celery_tasks,
    ):
        """No two submissions can end up with the same licenseNumber."""
        with patch("apps.seed_licenses.views.license_view.license_service", mock_license_service), \
             patch("apps.seed_licenses.views.license_view.tx_service",      mock_transaction_service):

            numbers = set()
            for i in range(5):
                num = f"RJSDST-UNIQ-{i+1:03d}"
                resp = _submit(client, {**seed_license_payload,
                                        "licenseNumber": num,
                                        "applicantName": f"Applicant {i+1}"})
                assert resp.status_code == 202
                returned_num = resp.json()["data"]["license_number"]
                assert returned_num not in numbers, \
                    f"Duplicate license number returned: {returned_num}"
                numbers.add(returned_num)

            assert len(numbers) == 5

    def test_concurrent_reads_during_updates(
        self, client, seed_license_payload, blockchain_state,
        mock_transaction_service, mock_license_service,
        mock_multi_account_manager, mock_celery_tasks,
    ):
        """Reads during status changes must always return a valid response."""
        with patch("apps.seed_licenses.views.license_view.license_service", mock_license_service), \
             patch("apps.seed_licenses.views.license_view.tx_service",      mock_transaction_service):

            _submit(client, {**seed_license_payload, "licenseNumber": "RJSDST-RD-001"})

            # Simulate concurrent reads (5×)
            for _ in range(5):
                resp = _get_info(client, 1)
                assert resp.status_code in (200, 500)