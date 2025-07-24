from enum import Enum

class OfficerRole(Enum):
    """
    Enum for Officer Roles in the licensing system.
    Used for validating and serializing officer roles.
    """
    AGRICULTURE_OFFICER = 0
    ASSISTANT_AGRICULTURE_OFFICER = 1
    ASSISTANT_DIRECTOR = 2
    DEPUTY_DIRECTOR = 3
    JOINT_DIRECTOR = 4
    JOINT_DIRECTOR_INPUT = 5

    @staticmethod
    def from_string(role_str: str):
        """
        Convert a human-readable string into a valid OfficerRole enum.
        Raises ValueError if input is invalid.
        """
        normalized = role_str.strip().lower().replace(" ", "_")
        mapping = {
            "agriculture_officer": OfficerRole.AGRICULTURE_OFFICER,
            "assistant_agriculture_officer": OfficerRole.ASSISTANT_AGRICULTURE_OFFICER,
            "assistant_director": OfficerRole.ASSISTANT_DIRECTOR,
            "deputy_director": OfficerRole.DEPUTY_DIRECTOR,
            "joint_director": OfficerRole.JOINT_DIRECTOR,
            "joint_director_input": OfficerRole.JOINT_DIRECTOR_INPUT,
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
    RENEWAL = 10

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


# Reverse mapping from integer status code to status name (for response serialization)
LICENSE_STATUS_REVERSE = {
    status.value: status.name for status in LicenseStatusEnum
}


# The CityEnum is commented out for now. Uncomment and use if city-level granularity is needed.
# It follows the same pattern with from_string conversion logic.
#
# class CityEnum(Enum):
#     # Cities grouped by administrative divisions
#     AJMER = 0
#     BEAWAR = 1
#     BHILWARA = 2
#     DIDWANA_KUCHAMAN = 3
#     NAGAUR = 4
#     TONK = 5
#
#     # Bharatpur Division
#     BHARATPUR = 6
#     DEEG = 7
#     DHOLPUR = 8
#     KARAULI = 9
#     SAWAI_MADHOPUR = 10
#
#     # Bikaner Division
#     BIKANER = 11
#     CHURU = 12
#     HANUMANGARH = 13
#     SRI_GANGANAGAR = 14
#
#     # Jaipur Division
#     ALWAR = 15
#     DAUSA = 16
#     JAIPUR = 17
#     JHUNJHUNU = 18
#     KHAIRTHAL_TIARA = 19
#     KOTPUTLI_BEHROR = 20
#     SIKAR = 21
#
#     # Jodhpur Division
#     BALOTRA = 22
#     BARMER = 23
#     JAISALMER = 24
#     JALORE = 25
#     JODHPUR = 26
#     PALI = 27
#     PHALODI = 28
#     SIROHI = 29
#
#     # Kota Division
#     BARAN = 30
#     BUNDI = 31
#     JHALAWAR = 32
#     KOTA = 33
#
#     # Udaipur Division
#     BANSWARA = 34
#     CHITTORGARH = 35
#     DUNGARPUR = 36
#     PRATAPGARH = 37
#     RAJSAMAND = 38
#     SALUMBAR = 39
#
#     @staticmethod
#     def from_string(city_str: str):
#         normalized = city_str.strip().lower().replace(" ", "_").replace("-", "_")
#         mapping = {c.name.lower(): c for c in CityEnum}
#         if normalized not in mapping:
#             raise ValueError(f"Invalid city string: '{city_str}'")
#         return mapping[normalized]