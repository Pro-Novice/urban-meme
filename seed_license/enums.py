from enum import Enum

class OfficerRole(Enum):
    """
    Enum for Officer Roles in the licensing system.
    Used for validating and serializing officer roles.
    """
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
        """
        Convert a human-readable string into a valid OfficerRole enum.
        Raises ValueError if input is invalid.
        """
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
        return mapping[normalized]


class DivisionEnum(Enum):
    """
    Enum representing all administrative divisions in Rajasthan.
    """
    AJMER = 0
    BHARATPUR = 1
    BIKANER = 2
    JAIPUR = 3
    JODHPUR = 4
    KOTA = 5
    UDAIPUR = 6

    @staticmethod
    def from_string(div_str: str):
        """
        Convert a human-readable string into a DivisionEnum value.
        Returns division name as string. Raises ValueError if not found.
        """
        normalized = div_str.strip().lower().replace(" ", "_")
        mapping = {
            "ajmer": "AJMER",
            "bharatpur": "BHARATPUR",
            "bikaner": "BIKANER",
            "jaipur": "JAIPUR",
            "jodhpur": "JODHPUR",
            "kota": "KOTA",
            "udaipur": "UDAIPUR",
        }
        if normalized not in mapping:
            raise ValueError(f"Invalid division string: '{div_str}'")
        return mapping[normalized]


class LicenseStatusEnum(Enum):
    """
    Enum representing the various statuses a license can be in.
    Helps in controlling status transitions and validations.
    """
    DRAFT = 0
    SUBMITTED = 1
    UNDER_REVIEW = 2
    DOCUMENTS_VERIFIED = 3
    INSPECTION_SCHEDULED = 4
    INSPECTION_COMPLETED = 5
    APPROVED = 6
    REJECTED = 7
    REVOKED = 8
    EXPIRED = 9
    RENEWED = 10

    @classmethod
    def from_string(cls, value: str):
        """
        Convert a string to a valid LicenseStatusEnum value.
        Returns the corresponding integer value.
        """
        normalized = value.strip().upper().replace(" ", "_")
        try:
            return cls[normalized].value
        except KeyError:
            raise ValueError(f"Invalid license status: '{value}'")


class DoctypeEnum(Enum):
    """
    Enum for document types required in license application/verification.
    """
    AFFIDAVIT_SEED_QUALITY = 0
    ID_PROOF = 1
    SHOP_MAP = 2
    REGISTRATION_CERTIFICATE = 3
    MEMORANDUM_ARTICLES = 4
    PASSPORT_PHOTO = 5
    AUTHORIZATION_LETTER = 6


# Reverse mapping from integer status code to status name
LICENSE_STATUS_REVERSE = {
    status.value: status.name for status in LicenseStatusEnum
}

REVERSE_OFFICER_ROLE = {
    role.value: role.name for role in OfficerRole
}

LICENSE_CATEGORY_MAP = {
    "SEED": 0,
    "FERTILIZER": 1,
    "INSECTICIDE": 2
}

LEVEL_MAP = {
    "DISTRICT": 0,
    "DIVISION": 1,
    "STATE": 2
}

REVERSE_LICENSE_CATEGORY = {v: k for k, v in LICENSE_CATEGORY_MAP.items()}

REVERSE_LEVEL_MAP = {v: k for k, v in LEVEL_MAP.items()}