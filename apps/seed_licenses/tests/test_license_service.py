from unittest.mock import MagicMock

import pytest

from apps.seed_licenses.models import EventLog
from apps.seed_licenses.services.license_service import LicenseService


def _action(action_type, remarks=""):
    return {
        "timestamp": "14 July 2026",
        "actionType": action_type,
        "actorName": "Department of Agriculture",
        "actorRole": "JOINT_DIRECTOR",
        "remarks": remarks,
        "dataHash": f"hash-{action_type}",
    }


def test_update_details_forwards_application_license_type_to_contract():
    tx_service = MagicMock()
    tx_service.read.return_value = {"category": "SEED"}

    LicenseService(tx_service).update_details({
        "license_id": 7,
        "application_license_type": "OLD_APPLICATION",
        "role": 1,
    })

    tx_service.write.assert_called_once()
    method_name, params = tx_service.write.call_args.args
    assert method_name == "updateLicenseDetails"
    assert params[0] == 7
    assert params[1]["applicationLicenseType"] == "OLD_APPLICATION"
    assert params[2] == 1


def test_update_details_rejects_application_type_for_different_category():
    tx_service = MagicMock()
    tx_service.read.return_value = {"category": "SEED"}

    result = LicenseService(tx_service).update_details({
        "license_id": 7,
        "application_license_type": "RETAIL_DEALER",
        "role": 1,
    })

    assert result["success"] is False
    assert "Invalid application license type for SEED" in result["error"]
    tx_service.write.assert_not_called()


@pytest.mark.django_db
def test_action_history_matches_repeated_detail_updates_oldest_first():
    tx_service = MagicMock()
    tx_service.read.return_value = [
        _action("SUBMITTED", "License Application Successfully Submitted"),
        _action("UNDER_REVIEW", "Review started"),
        _action("LICENSE_DETAILS_UPDATED", "License details updated"),
        _action("LICENSE_DETAILS_UPDATED", "License details updated"),
    ]

    # Insert deliberately out of blockchain order. The service must use the
    # block number rather than EventLog's newest-first default ordering.
    EventLog.objects.create(
        transaction_hash="0xupdate-two",
        block_number=14,
        event_name="LicenseDetailsUpdated",
        event_data={"licenseId": 7, "lastModifiedDate": "14 July 2026"},
        license_id=7,
    )
    EventLog.objects.create(
        transaction_hash="0xsubmitted",
        block_number=10,
        event_name="LicenseApplicationSubmittedV2",
        event_data={"licenseId": 7},
        license_id=7,
    )
    EventLog.objects.create(
        transaction_hash="0xupdate-one",
        block_number=13,
        event_name="LicenseDetailsUpdated",
        event_data={"licenseId": 7, "lastModifiedDate": "14 July 2026"},
        license_id=7,
    )
    EventLog.objects.create(
        transaction_hash="0xreview",
        block_number=11,
        event_name="StatusChanged",
        event_data={"licenseId": 7, "newStatus": "UNDER_REVIEW"},
        license_id=7,
    )

    history = LicenseService(tx_service).get_action_history(7)

    assert [item["transactionHash"] for item in history] == [
        "0xsubmitted",
        "0xreview",
        "0xupdate-one",
        "0xupdate-two",
    ]


@pytest.mark.django_db
def test_action_history_consumes_each_event_log_only_once():
    tx_service = MagicMock()
    tx_service.read.return_value = [
        _action("LICENSE_DETAILS_UPDATED", "License details updated"),
        _action("LICENSE_DETAILS_UPDATED", "License details updated"),
    ]
    EventLog.objects.create(
        transaction_hash="0xonly-update",
        block_number=20,
        event_name="license_details_updated",
        event_data={"licenseId": 8},
        license_id=8,
    )

    history = LicenseService(tx_service).get_action_history(8)

    assert history[0]["transactionHash"] == "0xonly-update"
    assert history[1]["transactionHash"] is None


@pytest.mark.django_db
def test_action_history_does_not_match_unrelated_events_by_remarks():
    tx_service = MagicMock()
    tx_service.read.return_value = [
        _action("LICENSE_DETAILS_UPDATED", "License details updated"),
    ]
    EventLog.objects.create(
        transaction_hash="0xverification",
        block_number=30,
        event_name="LicenseVerificationStatus",
        event_data={"licenseId": 9, "remarks": "License details updated"},
        license_id=9,
    )

    history = LicenseService(tx_service).get_action_history(9)

    assert history[0]["transactionHash"] is None
