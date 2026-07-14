from enum import Enum


class OfficerRole(Enum):
    CITIZEN = 0
    AGRICULTURE_OFFICER = 1
    ASSISTANT_AGRICULTURE_OFFICER = 2
    ASSISTANT_DIRECTOR = 3
    DEPUTY_DIRECTOR = 4
    JOINT_DIRECTOR = 5
    JOINT_DIRECTOR_INPUT = 6
    FIELD_INSPECTOR = 7

    @staticmethod
    def from_string(role_str: str):
        normalized = role_str.strip().lower().replace(" ", "_")
        mapping = {
            "citizen": OfficerRole.CITIZEN,
            "agriculture_officer": OfficerRole.AGRICULTURE_OFFICER,
            "assistant_agriculture_officer": OfficerRole.ASSISTANT_AGRICULTURE_OFFICER,
            "assistant_director": OfficerRole.ASSISTANT_DIRECTOR,
            "deputy_director": OfficerRole.DEPUTY_DIRECTOR,
            "joint_director": OfficerRole.JOINT_DIRECTOR,
            "joint_director_input": OfficerRole.JOINT_DIRECTOR_INPUT,
            "field_inspector": OfficerRole.FIELD_INSPECTOR,
        }
        if normalized not in mapping:
            raise ValueError(f"Invalid officer role string: '{role_str}'")
        return mapping[normalized].value  # 🔥 Return int for blockchain


class LicenseStatusEnum(Enum):
    SUBMITTED = 0
    UNDER_REVIEW = 1
    DOCUMENTS_VERIFIED = 2
    INSPECTION_SCHEDULED = 3
    INSPECTION_COMPLETED = 4
    APPROVED = 5
    REJECTED = 6
    REVOKED = 7
    EXPIRED = 8
    RENEWED = 9

    @classmethod
    def from_string(cls, value: str) -> int:
        """Convert status string to blockchain integer enum."""
        normalized = value.strip().upper().replace(" ", "_")
        try:
            return cls[normalized].value
        except KeyError:
            raise ValueError(f"Invalid license status: '{value}'")


# Reverse mapping from integer → status name
LICENSE_STATUS_REVERSE = {status.value: status.name for status in LicenseStatusEnum}

REVERSE_OFFICER_ROLE = {role.value: role.name for role in OfficerRole}

LICENSE_CATEGORY_MAP = {"SEED": 0, "FERTILIZER": 1, "PESTICIDE": 2}
LEVEL_MAP = {"STATE": 0, "DIVISION": 1, "DISTRICT": 2}

APPLICATION_LICENSE_TYPES = {
    LICENSE_CATEGORY_MAP["SEED"]: {
        "NEW_APPLICATION",
        "OLD_APPLICATION",
    },
    LICENSE_CATEGORY_MAP["FERTILIZER"]: {
        "MANUFACTURER",
        "RETAIL_DEALER",
        "WHOLESALER_DEALER",
    },
    LICENSE_CATEGORY_MAP["PESTICIDE"]: {
        "SALES_LICENSE",
        "COMMERCIAL_PEST_CONTROL",
        "INSECTICIDE_MANUFACTURER",
    },
}

REVERSE_LICENSE_CATEGORY = {v: k for k, v in LICENSE_CATEGORY_MAP.items()}
REVERSE_LEVEL_MAP = {v: k for k, v in LEVEL_MAP.items()}

LICENSE_CATEGORIES = ["SEED", "FERTILIZER", "PESTICIDE"]
USER_ROLE = [
    "CITIZEN",
    "AGRICULTURE_OFFICER",
    "ASSISTANT_AGRICULTURE_OFFICER",
    "ASSISTANT_DIRECTOR",
    "DEPUTY_DIRECTOR",
    "JOINT_DIRECTOR",
    "JOINT_DIRECTOR_INPUT",
    "FIELD_INSPECTOR",
]
LICENSE_LEVELS = ["STATE", "DIVISION", "DISTRICT"]
LICENSE_STATUSES = [
    "SUBMITTED",
    "UNDER_REVIEW",
    "DOCUMENTS_VERIFIED",
    "INSPECTION_SCHEDULED",
    "INSPECTION_COMPLETED",
    "APPROVED",
    "REJECTED",
    "REVOKED",
    "EXPIRED",
    "RENEWED",
]

LICENSE_ACTION_TYPES = LICENSE_STATUSES + ["LICENSE_DETAILS_UPDATED"]
