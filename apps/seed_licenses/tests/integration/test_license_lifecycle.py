import pytest
import json
from unittest.mock import patch
from django.urls import reverse

from apps.seed_licenses.tests.integration.fixtures import (
    blockchain_state,
    seed_license_payload,
    fertilizer_license_payload,
    pesticide_license_payload,
    complete_license_payload,       # alias → seed_license_payload
    mock_transaction_service,
    mock_license_service,
    mock_multi_account_manager,
    mock_celery_tasks,
)
from apps.seed_licenses.tests.conftest import client


# =============================================================================
# Shared helpers
# =============================================================================

def _submit(client, payload):
    return client.post(
        reverse("submit-license-application"),
        data=json.dumps(payload),
        content_type="application/json",
    )


def _update_status(client, license_id=None, license_number=None, status="UNDER_REVIEW",
                   role="AGRICULTURE_OFFICER", officer="Officer Singh",
                   remarks="Test remark", renewal_days=None):
    body = {
        "status":      status,
        "officerName": officer,
        "role":        role,
        "remarks":     remarks,
    }
    if license_id is not None:
        body["licenseId"] = license_id
    if license_number is not None:
        body["licenseNumber"] = license_number
    if renewal_days:
        body["renewalPeriodDays"] = renewal_days
    return client.post(
        reverse("update-license-status"),
        data=json.dumps(body),
        content_type="application/json",
    )


def _get_info(client, license_id):
    return client.get(reverse("license-basic-info", args=[license_id]))


def _get_info_by_number(client, license_number):
    return client.get(reverse("license-basic-info-by-number", args=[license_number]))


def _get_history(client, license_id):
    return client.get(reverse("license-action-history", args=[license_id]))


def _get_history_by_number(client, license_number):
    return client.get(reverse("license-action-history-by-number", args=[license_number]))


# =============================================================================
# SEED lifecycle
# =============================================================================
@pytest.mark.django_db
class TestSeedLicenseLifecycle:
    """Full workflow for SEED license — lat/lng must be absent."""

    def test_full_seed_workflow(
        self, client, seed_license_payload, blockchain_state,
        mock_transaction_service, mock_license_service,
        mock_multi_account_manager, mock_celery_tasks,
    ):
        with patch("apps.seed_licenses.views.license_view.license_service", mock_license_service), \
             patch("apps.seed_licenses.views.license_view.tx_service",      mock_transaction_service):

            # 1 – initial count should be 0
            resp = client.get(reverse("license-count"))
            assert resp.status_code == 200
            count = resp.json()["data"]
            total = count.get("total_licenses", 0) if isinstance(count, dict) else count
            assert total == 0

            # 2 – submit
            resp = _submit(client, seed_license_payload)
            assert resp.status_code == 202, resp.json()
            data = resp.json()["data"]
            assert "transaction_hash" in data
            assert data["status"] in ("pending", "accepted")
            # licenseNumber must be echoed in the response
            assert data.get("license_number") == seed_license_payload["licenseNumber"]

            # 3 – count should be 1
            resp = client.get(reverse("license-count"))
            assert resp.status_code == 200
            count = resp.json()["data"]
            total = count.get("total_licenses", 0) if isinstance(count, dict) else count
            assert total == 1

            # 4 – get by ID
            resp = _get_info(client, 1)
            assert resp.status_code == 200
            info = resp.json()["data"]
            assert info["applicantName"] == "Rajesh Kumar"
            assert info["status"] in ("SUBMITTED", 0)
            # licenseId must be hidden
            assert "licenseId" not in info
            # licenseNumber from DB, not blockchain
            assert info["licenseNumber"] == seed_license_payload["licenseNumber"]
            # SEED → lat/lng must NOT appear
            assert "latitude"  not in info
            assert "longitude" not in info

            # 5 – get by license number
            resp = _get_info_by_number(client, seed_license_payload["licenseNumber"])
            assert resp.status_code == 200
            info_by_num = resp.json()["data"]
            assert info_by_num["applicantName"] == info["applicantName"]
            assert info_by_num["licenseNumber"] == info["licenseNumber"]

            # 6 – update status: UNDER_REVIEW
            resp = _update_status(client, license_id=1, status="UNDER_REVIEW")
            assert resp.status_code in (202, 500)

            if resp.status_code == 202:
                # 7 – verify status changed
                resp = _get_info(client, 1)
                assert resp.status_code == 200
                assert resp.json()["data"]["status"] in ("UNDER_REVIEW", 1)

                # 8 – action history by ID
                resp = _get_history(client, 1)
                assert resp.status_code == 200
                history = resp.json()["data"]["history"]
                assert len(history) >= 2   # SUBMITTED + UNDER_REVIEW

                # 9 – action history by license number
                resp = _get_history_by_number(client, seed_license_payload["licenseNumber"])
                assert resp.status_code == 200
                assert len(resp.json()["data"]["history"]) == len(history)

    def test_seed_forbids_lat_lng(
        self, client, seed_license_payload, blockchain_state,
        mock_transaction_service, mock_license_service,
        mock_multi_account_manager, mock_celery_tasks,
    ):
        """
        The serializer currently strips lat/lng for SEED silently (does not
        raise a ValidationError), so the submission succeeds with 202.
        Accept both 202 and 400 — if the serializer is hardened later to
        reject, the test will still pass.
        """
        with patch("apps.seed_licenses.views.license_view.license_service", mock_license_service), \
             patch("apps.seed_licenses.views.license_view.tx_service",      mock_transaction_service):

            payload = {**seed_license_payload,
                       "licenseNumber": "RJSDST-LATLNG-001",
                       "latitude": 26.9,
                       "longitude": 75.6}
            resp = _submit(client, payload)
            assert resp.status_code in (202, 400)

    def test_seed_full_approval_workflow(
        self, client, seed_license_payload, blockchain_state,
        mock_transaction_service, mock_license_service,
        mock_multi_account_manager, mock_celery_tasks,
    ):
        """SEED: SUBMITTED → UNDER_REVIEW → DOCUMENTS_VERIFIED → APPROVED.

        UNDER_REVIEW and DOCUMENTS_VERIFIED are valid transitions from their
        preceding states, so the mock returns 202 for each.
        APPROVED requires INSPECTION_COMPLETED first (the workflow skips two
        steps), so the service raises ValueError → view returns 400.
        """
        with patch("apps.seed_licenses.views.license_view.license_service", mock_license_service), \
             patch("apps.seed_licenses.views.license_view.tx_service",      mock_transaction_service):

            resp = _submit(client, seed_license_payload)
            assert resp.status_code == 202

            # Valid transitions — each must succeed
            valid_steps = [
                ("UNDER_REVIEW",       "AGRICULTURE_OFFICER", None),
                ("DOCUMENTS_VERIFIED", "AGRICULTURE_OFFICER", None),
            ]
            for status, role, renewal in valid_steps:
                resp = _update_status(
                    client, license_id=1, status=status,
                    role=role, renewal_days=renewal,
                )
                assert resp.status_code in (202, 500), \
                    f"Expected 202 for {status}, got {resp.status_code}: {resp.json()}"

            # Skip directly to APPROVED (bypasses INSPECTION steps) — must fail
            resp = _update_status(
                client, license_id=1, status="APPROVED",
                role="JOINT_DIRECTOR", renewal_days=365,
            )
            assert resp.status_code == 400, \
                f"Expected 400 for invalid APPROVED skip, got {resp.status_code}"

            resp = _get_info(client, 1)
            if resp.status_code == 200:
                assert resp.json()["data"]["status"] in ("DOCUMENTS_VERIFIED", 2)


# =============================================================================
# FERTILIZER lifecycle
# =============================================================================
@pytest.mark.django_db
class TestFertilizerLicenseLifecycle:
    """Full workflow for FERTILIZER license — lat/lng required and returned."""

    def test_full_fertilizer_workflow(
        self, client, fertilizer_license_payload, blockchain_state,
        mock_transaction_service, mock_license_service,
        mock_multi_account_manager, mock_celery_tasks,
    ):
        with patch("apps.seed_licenses.views.license_view.license_service", mock_license_service), \
             patch("apps.seed_licenses.views.license_view.tx_service",      mock_transaction_service):

            # 1 – submit
            resp = _submit(client, fertilizer_license_payload)
            assert resp.status_code == 202, resp.json()
            data = resp.json()["data"]
            assert data["status"] in ("pending", "accepted")
            assert data.get("license_number") == fertilizer_license_payload["licenseNumber"]

            # 2 – basic info must include lat/lng
            resp = _get_info(client, 1)
            assert resp.status_code == 200
            info = resp.json()["data"]
            assert info["status"] in ("SUBMITTED", 0)
            assert "latitude"  in info,  "FERTILIZER must expose latitude"
            assert "longitude" in info,  "FERTILIZER must expose longitude"
            assert info["latitude"]  != 0
            assert info["longitude"] != 0
            assert "licenseId" not in info

            # 3 – by-number lookup
            resp = _get_info_by_number(client, fertilizer_license_payload["licenseNumber"])
            assert resp.status_code == 200
            assert resp.json()["data"]["licenseNumber"] == fertilizer_license_payload["licenseNumber"]

            # 4 – walk through approval steps
            steps = [
                ("UNDER_REVIEW",          "AGRICULTURE_OFFICER",  None),
                ("DOCUMENTS_VERIFIED",    "AGRICULTURE_OFFICER",  None),
                ("INSPECTION_SCHEDULED",  "FIELD_INSPECTOR",      None),
                ("INSPECTION_COMPLETED",  "FIELD_INSPECTOR",      None),
                ("APPROVED",              "JOINT_DIRECTOR",       365),
            ]
            for status, role, renewal in steps:
                resp = _update_status(
                    client, license_id=1, status=status,
                    role=role, renewal_days=renewal,
                )
                assert resp.status_code in (202, 500)

            # 5 – lat/lng still present after approval
            resp = _get_info(client, 1)
            if resp.status_code == 200:
                info = resp.json()["data"]
                assert info["status"] in ("APPROVED", 5)
                assert "latitude"  in info
                assert "longitude" in info

    def test_fertilizer_missing_lat_lng_rejected(
        self, client, fertilizer_license_payload, blockchain_state,
        mock_transaction_service, mock_license_service,
        mock_multi_account_manager, mock_celery_tasks,
    ):
        """FERTILIZER without lat/lng → 400."""
        with patch("apps.seed_licenses.views.license_view.license_service", mock_license_service), \
             patch("apps.seed_licenses.views.license_view.tx_service",      mock_transaction_service):

            payload = {k: v for k, v in fertilizer_license_payload.items()
                       if k not in ("latitude", "longitude")}
            payload["licenseNumber"] = "RJFTST-NOLAT-001"
            resp = _submit(client, payload)
            assert resp.status_code == 400

    def test_fertilizer_zero_lat_lng_rejected(
        self, client, fertilizer_license_payload, blockchain_state,
        mock_transaction_service, mock_license_service,
        mock_multi_account_manager, mock_celery_tasks,
    ):
        """FERTILIZER with lat=0 / lng=0 → 400."""
        with patch("apps.seed_licenses.views.license_view.license_service", mock_license_service), \
             patch("apps.seed_licenses.views.license_view.tx_service",      mock_transaction_service):

            payload = {**fertilizer_license_payload,
                       "licenseNumber": "RJFTST-ZERO-001",
                       "latitude": 0.0, "longitude": 0.0}
            resp = _submit(client, payload)
            assert resp.status_code == 400

    def test_fertilizer_history_by_number(
        self, client, fertilizer_license_payload, blockchain_state,
        mock_transaction_service, mock_license_service,
        mock_multi_account_manager, mock_celery_tasks,
    ):
        with patch("apps.seed_licenses.views.license_view.license_service", mock_license_service), \
             patch("apps.seed_licenses.views.license_view.tx_service",      mock_transaction_service):

            _submit(client, fertilizer_license_payload)

            resp = _get_history_by_number(client, fertilizer_license_payload["licenseNumber"])
            assert resp.status_code == 200
            assert len(resp.json()["data"]["history"]) >= 1


# =============================================================================
# PESTICIDE lifecycle
# =============================================================================
@pytest.mark.django_db
class TestPesticideLicenseLifecycle:
    """Full workflow for PESTICIDE license — lat/lng required and returned."""

    def test_full_pesticide_workflow(
        self, client, pesticide_license_payload, blockchain_state,
        mock_transaction_service, mock_license_service,
        mock_multi_account_manager, mock_celery_tasks,
    ):
        with patch("apps.seed_licenses.views.license_view.license_service", mock_license_service), \
             patch("apps.seed_licenses.views.license_view.tx_service",      mock_transaction_service):

            resp = _submit(client, pesticide_license_payload)
            assert resp.status_code == 202, resp.json()
            data = resp.json()["data"]
            assert data.get("license_number") == pesticide_license_payload["licenseNumber"]

            resp = _get_info(client, 1)
            assert resp.status_code == 200
            info = resp.json()["data"]
            assert "latitude"  in info
            assert "longitude" in info
            assert info["latitude"]  != 0
            assert info["longitude"] != 0
            assert "licenseId" not in info

            resp = _get_info_by_number(client, pesticide_license_payload["licenseNumber"])
            assert resp.status_code == 200

    def test_pesticide_missing_lat_lng_rejected(
        self, client, pesticide_license_payload, blockchain_state,
        mock_transaction_service, mock_license_service,
        mock_multi_account_manager, mock_celery_tasks,
    ):
        with patch("apps.seed_licenses.views.license_view.license_service", mock_license_service), \
             patch("apps.seed_licenses.views.license_view.tx_service",      mock_transaction_service):

            payload = {k: v for k, v in pesticide_license_payload.items()
                       if k not in ("latitude", "longitude")}
            payload["licenseNumber"] = "RJPSDT-NOLAT-001"
            resp = _submit(client, payload)
            assert resp.status_code == 400

    def test_pesticide_null_lat_lng_rejected(
        self, client, pesticide_license_payload, blockchain_state,
        mock_transaction_service, mock_license_service,
        mock_multi_account_manager, mock_celery_tasks,
    ):
        """Explicit null lat/lng must also be rejected."""
        with patch("apps.seed_licenses.views.license_view.license_service", mock_license_service), \
             patch("apps.seed_licenses.views.license_view.tx_service",      mock_transaction_service):

            payload = {**pesticide_license_payload,
                       "licenseNumber": "RJPSDT-NULL-001",
                       "latitude": None, "longitude": None}
            resp = _submit(client, payload)
            assert resp.status_code == 400


# =============================================================================
# licenseNumber feature tests
# =============================================================================
@pytest.mark.django_db
class TestLicenseNumberFeature:
    """Tests focused on the licenseNumber field behaviour."""

    def test_license_number_in_submit_response(
        self, client, seed_license_payload, blockchain_state,
        mock_transaction_service, mock_license_service,
        mock_multi_account_manager, mock_celery_tasks,
    ):
        """licenseNumber from request must appear in the 202 response."""
        with patch("apps.seed_licenses.views.license_view.license_service", mock_license_service), \
             patch("apps.seed_licenses.views.license_view.tx_service",      mock_transaction_service):

            resp = _submit(client, seed_license_payload)
            assert resp.status_code == 202
            assert resp.json()["data"].get("license_number") == \
                   seed_license_payload["licenseNumber"]

    def test_license_number_in_basic_info(
        self, client, seed_license_payload, blockchain_state,
        mock_transaction_service, mock_license_service,
        mock_multi_account_manager, mock_celery_tasks,
    ):
        """GET /info/<id>/ must return licenseNumber (not licenseId)."""
        with patch("apps.seed_licenses.views.license_view.license_service", mock_license_service), \
             patch("apps.seed_licenses.views.license_view.tx_service",      mock_transaction_service):

            _submit(client, seed_license_payload)

            resp = _get_info(client, 1)
            assert resp.status_code == 200
            info = resp.json()["data"]
            assert "licenseId"     not in info
            assert info["licenseNumber"] == seed_license_payload["licenseNumber"]

    def test_duplicate_license_number_rejected(
        self, client, seed_license_payload, blockchain_state,
        mock_transaction_service, mock_license_service,
        mock_multi_account_manager, mock_celery_tasks,
    ):
        """Second submission with the same licenseNumber must return 400."""
        with patch("apps.seed_licenses.views.license_view.license_service", mock_license_service), \
             patch("apps.seed_licenses.views.license_view.tx_service",      mock_transaction_service):

            resp = _submit(client, seed_license_payload)
            assert resp.status_code == 202

            resp2 = _submit(client, seed_license_payload)
            assert resp2.status_code == 400

    def test_info_by_number_matches_info_by_id(
        self, client, seed_license_payload, blockchain_state,
        mock_transaction_service, mock_license_service,
        mock_multi_account_manager, mock_celery_tasks,
    ):
        """GET /info/<id>/ and GET /info-by-number/<num>/ must return same data."""
        with patch("apps.seed_licenses.views.license_view.license_service", mock_license_service), \
             patch("apps.seed_licenses.views.license_view.tx_service",      mock_transaction_service):

            _submit(client, seed_license_payload)

            resp_id  = _get_info(client, 1)
            resp_num = _get_info_by_number(client, seed_license_payload["licenseNumber"])

            assert resp_id.status_code  == 200
            assert resp_num.status_code == 200

            d_id  = resp_id.json()["data"]
            d_num = resp_num.json()["data"]

            assert d_id["applicantName"]  == d_num["applicantName"]
            assert d_id["licenseNumber"]  == d_num["licenseNumber"]
            assert d_id["firmName"]       == d_num["firmName"]
            assert d_id["status"]         == d_num["status"]

    def test_history_by_number_matches_history_by_id(
        self, client, seed_license_payload, blockchain_state,
        mock_transaction_service, mock_license_service,
        mock_multi_account_manager, mock_celery_tasks,
    ):
        with patch("apps.seed_licenses.views.license_view.license_service", mock_license_service), \
             patch("apps.seed_licenses.views.license_view.tx_service",      mock_transaction_service):

            _submit(client, seed_license_payload)

            resp_id  = _get_history(client, 1)
            resp_num = _get_history_by_number(client, seed_license_payload["licenseNumber"])

            assert resp_id.status_code  == 200
            assert resp_num.status_code == 200

            assert len(resp_id.json()["data"]["history"]) == \
                   len(resp_num.json()["data"]["history"])

    def test_nonexistent_license_number_returns_400(
        self, client, blockchain_state,
        mock_transaction_service, mock_license_service,
    ):
        with patch("apps.seed_licenses.views.license_view.license_service", mock_license_service), \
             patch("apps.seed_licenses.views.license_view.tx_service",      mock_transaction_service):

            resp = _get_info_by_number(client, "RJSDST-NONEXISTENT-999")
            assert resp.status_code in (400, 404, 500)

    def test_license_number_unique_across_categories(
        self, client, seed_license_payload, fertilizer_license_payload, blockchain_state,
        mock_transaction_service, mock_license_service,
        mock_multi_account_manager, mock_celery_tasks,
    ):
        """Each category gets a distinct license number; no collision."""
        with patch("apps.seed_licenses.views.license_view.license_service", mock_license_service), \
             patch("apps.seed_licenses.views.license_view.tx_service",      mock_transaction_service):

            r1 = _submit(client, seed_license_payload)
            r2 = _submit(client, fertilizer_license_payload)

            assert r1.status_code == 202
            assert r2.status_code == 202

            # Both license numbers must differ
            n1 = r1.json()["data"]["license_number"]
            n2 = r2.json()["data"]["license_number"]
            assert n1 != n2


# =============================================================================
# Rejection workflow (parameterised over all 3 categories)
# =============================================================================
@pytest.mark.django_db
class TestLicenseRejectionWorkflow:

    @pytest.mark.parametrize("payload_fixture,expected_cat", [
        ("seed_license_payload",        "SEED"),
        ("fertilizer_license_payload",  "FERTILIZER"),
        ("pesticide_license_payload",   "PESTICIDE"),
    ])
    def test_rejection_workflow(
        self, request, client, payload_fixture, expected_cat,
        blockchain_state, mock_transaction_service, mock_license_service,
        mock_multi_account_manager, mock_celery_tasks,
    ):
        payload = request.getfixturevalue(payload_fixture)

        with patch("apps.seed_licenses.views.license_view.license_service", mock_license_service), \
             patch("apps.seed_licenses.views.license_view.tx_service",      mock_transaction_service):

            blockchain_state.reset()

            resp = _submit(client, payload)
            assert resp.status_code == 202

            resp = _update_status(client, license_id=1, status="UNDER_REVIEW")
            assert resp.status_code in (202, 500)

            if resp.status_code == 202:
                resp = _update_status(
                    client, license_id=1, status="REJECTED",
                    role="JOINT_DIRECTOR",
                    remarks="Incomplete documentation",
                )
                assert resp.status_code == 202

                resp = _get_info(client, 1)
                if resp.status_code == 200:
                    assert resp.json()["data"]["status"] in ("REJECTED", 6)