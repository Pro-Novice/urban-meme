from enum import Enum


class UserType(Enum):
    ADMIN = "ADMIN"
    USER = "USER"


class AddressFields(Enum):
    REQUIRED_FIELDS = ['address', 'city', 'state', 'postal_code', 'country']

class UserRoles(Enum):
    NONE = 0
    FARMER = 1
    PUBLIC = 2