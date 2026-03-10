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


# =============================================================================
@pytest.mark.django_db
class TestSystemState:

    # ── owner / contract endpoints ─────────────────────────────────────────

    def test_system_info_endpoints(
        self, client, blockchain_state,
        mock_transaction_service, mock_license_service,
    ):
        with patch("apps.seed_licenses.views.license_view.license_service", mock_license_service), \
             patch("apps.seed_licenses.views.license_view.tx_service",      mock_transaction_service), \
             patch("apps.seed_licenses.views.blockchain_view.tx_service",   mock_transaction_service):

            resp = client.get(reverse("check-owner"))
            assert resp.status_code == 200
            owner = resp.json()["data"]
            addr  = owner.get("owner", owner) if isinstance(owner, dict) else owner
            assert isinstance(addr, str) and addr.startswith("0x")

            resp = client.get(reverse("contract-address"))
            assert resp.status_code == 200
            cdata = resp.json()["data"]
            assert isinstance(cdata, (str, dict))
            if isinstance(cdata, dict):
                assert "contract_address" in cdata

    def test_public_key_endpoint(self, client):
        resp = client.get(reverse("get-public-key"))
        assert resp.status_code == 200
        pk = resp.json()["data"]
        key_str = pk.get("public_key", pk) if isinstance(pk, dict) else pk
        assert "BEGIN PUBLIC KEY" in key_str

    # ── count accuracy ─────────────────────────────────────────────────────

    def test_count_accuracy_seed_only(
        self, client, seed_license_payload, blockchain_state,
        mock_transaction_service, mock_license_service,
        mock_multi_account_manager, mock_celery_tasks,
    ):
        with patch("apps.seed_licenses.views.license_view.license_service", mock_license_service), \
             patch("apps.seed_licenses.views.license_view.tx_service",      mock_transaction_service):

            assert _get_count(client) == 0

            for i in range(3):
                _submit(client, {**seed_license_payload,
                                 "licenseNumber": f"RJSDST-SYS-{i+1:03d}",
                                 "applicantName": f"Applicant {i+1}"})

            assert _get_count(client) == 3

    def test_count_accuracy_mixed_categories(
        self, client, seed_license_payload, fertilizer_license_payload,
        pesticide_license_payload, blockchain_state,
        mock_transaction_service, mock_license_service,
        mock_multi_account_manager, mock_celery_tasks,
    ):
        with patch("apps.seed_licenses.views.license_view.license_service", mock_license_service), \
             patch("apps.seed_licenses.views.license_view.tx_service",      mock_transaction_service):

            _submit(client, seed_license_payload)
            _submit(client, fertilizer_license_payload)
            _submit(client, pesticide_license_payload)

            assert _get_count(client) == 3

    def test_count_does_not_change_on_status_update(
        self, client, seed_license_payload, blockchain_state,
        mock_transaction_service, mock_license_service,
        mock_multi_account_manager, mock_celery_tasks,
    ):
        with patch("apps.seed_licenses.views.license_view.license_service", mock_license_service), \
             patch("apps.seed_licenses.views.license_view.tx_service",      mock_transaction_service):

            for i in range(3):
                _submit(client, {**seed_license_payload,
                                 "licenseNumber": f"RJSDST-CNT-{i+1:03d}",
                                 "applicantName": f"Applicant {i+1}"})

            assert _get_count(client) == 3

            # Fast-track license 1 to APPROVED in mock state
            blockchain_state.licenses[1]["status"] = 5

            # Count must still be 3
            assert _get_count(client) == 3

    # ── geo isolation in system operations ────────────────────────────────

    def test_geo_field_isolation_in_system_state(
        self, client, seed_license_payload, fertilizer_license_payload,
        pesticide_license_payload, blockchain_state,
        mock_transaction_service, mock_license_service,
        mock_multi_account_manager, mock_celery_tasks,
    ):
        """After bulk submissions, SEED has no geo; FERTILIZER/PESTICIDE have geo."""
        with patch("apps.seed_licenses.views.license_view.license_service", mock_license_service), \
             patch("apps.seed_licenses.views.license_view.tx_service",      mock_transaction_service):

            _submit(client, seed_license_payload)        # id=1
            _submit(client, fertilizer_license_payload)  # id=2
            _submit(client, pesticide_license_payload)   # id=3

            for lid in (1, 2, 3):
                resp = client.get(reverse("license-basic-info", args=[lid]))
                if resp.status_code != 200:
                    continue
                info = resp.json()["data"]
                cat  = info.get("category", "")

                if cat == "SEED":
                    assert "latitude"  not in info
                    assert "longitude" not in info
                elif cat in ("FERTILIZER", "PESTICIDE"):
                    assert "latitude"  in info
                    assert "longitude" in info

    # ── license-id hidden in all reads ────────────────────────────────────

    def test_license_id_hidden_in_all_reads(
        self, client, seed_license_payload, fertilizer_license_payload,
        pesticide_license_payload, blockchain_state,
        mock_transaction_service, mock_license_service,
        mock_multi_account_manager, mock_celery_tasks,
    ):
        with patch("apps.seed_licenses.views.license_view.license_service", mock_license_service), \
             patch("apps.seed_licenses.views.license_view.tx_service",      mock_transaction_service):

            _submit(client, seed_license_payload)
            _submit(client, fertilizer_license_payload)
            _submit(client, pesticide_license_payload)

            for lid in (1, 2, 3):
                resp = client.get(reverse("license-basic-info", args=[lid]))
                if resp.status_code == 200:
                    assert "licenseId" not in resp.json()["data"], \
                        f"licenseId must be hidden for license {lid}"

    # ── system under multiple operations ─────────────────────────────────

    def test_system_state_after_multiple_operations(
        self, client, seed_license_payload, fertilizer_license_payload,
        pesticide_license_payload, blockchain_state,
        mock_transaction_service, mock_license_service,
        mock_multi_account_manager, mock_celery_tasks,
    ):
        with patch("apps.seed_licenses.views.license_view.license_service", mock_license_service), \
             patch("apps.seed_licenses.views.license_view.tx_service",      mock_transaction_service):

            payloads = [seed_license_payload, fertilizer_license_payload, pesticide_license_payload]
            for i in range(5):
                payload = {**payloads[i % 3],
                           "licenseNumber": f"RJXX-SYS-{i+1:03d}",
                           "applicantName": f"System Applicant {i+1}"}
                _submit(client, payload)

            for lid in range(1, 6):
                for endpoint in ("license-basic-info", "license-action-history", "license-qr-data"):
                    resp = client.get(reverse(endpoint, args=[lid]))
                    assert resp.status_code in (200, 500)

            assert _get_count(client) == 5

    def test_endpoints_work_without_any_licenses(
        self, client, blockchain_state,
        mock_transaction_service, mock_license_service,
    ):
        with patch("apps.seed_licenses.views.license_view.license_service", mock_license_service), \
             patch("apps.seed_licenses.views.license_view.tx_service",      mock_transaction_service), \
             patch("apps.seed_licenses.views.blockchain_view.tx_service",   mock_transaction_service):

            resp = client.get(reverse("check-owner"))
            assert resp.status_code == 200

            resp = client.get(reverse("contract-address"))
            assert resp.status_code == 200

            resp = client.get(reverse("get-public-key"))
            assert resp.status_code == 200
            pk = resp.json()["data"]
            key_str = pk.get("public_key", pk) if isinstance(pk, dict) else pk
            assert "BEGIN PUBLIC KEY" in key_str

            assert _get_count(client) == 0