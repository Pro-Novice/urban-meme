from enum import Enum

class UserType(Enum):
    ADMIN = "ADMIN"
    USER = "USER"
   
    

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