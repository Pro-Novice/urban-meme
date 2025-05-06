from enum import Enum

# Enum for Gender
class Gender(Enum):
    """Enum representing gender with possible values: MALE, FEMALE."""
    MALE = 'MALE'
    FEMALE = 'FEMALE'

    @classmethod
    def choices(cls):
        """Return a list of tuples representing the gender choices."""
        return [(tag.value, tag.value) for tag in cls]

# Enum for Status
class Status(Enum):
    """Enum representing the status of an entity, with values: PENDING, VERIFIED, REJECTED."""
    PENDING = 'PENDING'
    VERIFIED = 'VERIFIED'
    REJECTED = 'REJECTED'

    @classmethod
    def choices(cls):
        """Return a list of tuples representing the status choices."""
        return [(tag.value, tag.value) for tag in cls]

# Enum for User Type
class UserType(Enum):
    """Enum representing user types: USER and RAJKISAN_OFFICER."""
    USER = 'USER'
    RAJKISAN_OFFICER = 'RAJKISAN_OFFICER'
    ADMIN = "ADMIN"


    @classmethod
    def choices(cls):
        """Return a list of tuples representing the user type choices."""
        return [(tag.value, tag.value) for tag in cls]

# Enum for File Types
class FileTypes(Enum):
    """Enum representing different file types: PDF, JPG, JPEG, PNG."""
    PDF = 1
    JPG = 2
    JPEG = 3
    PNG = 4

    @classmethod
    def choices(cls):
        """Return a list of tuples representing the file type choices."""
        return [(tag.name, tag.name) for tag in cls]



class AddressFields(Enum):
    REQUIRED_FIELDS = ['address', 'city', 'state', 'postal_code', 'country']


class LicenseStatus(Enum):
    APPLIED = 0
    DOCUMENTS_VERIFIED = 1
    FIELD_INSPECTION_COMPLETED = 2
    QUALITY_VERIFIED = 3
    APPROVED = 4
    REJECTED = 5
    REVOKED = 6
    EXPIRED = 7


class LicenseType(Enum):
    SEED_PRODUCTION = 0
    SEED_DISTRIBUTION = 1
    SEED_CERTIFICATION = 2
    HYBRID_SEED_PRODUCTION = 3
    ORGANIC_SEED_PRODUCTION = 4


class DepartmentRole(Enum):
    AGRICULTURE_OFFICER = 0
    DISTRICT_COLLECTOR = 1
    SEED_CERTIFICATION_OFFICER = 2
    SUBSIDY_APPROVAL_OFFICER = 3
    QUALITY_CONTROL_OFFICER = 4