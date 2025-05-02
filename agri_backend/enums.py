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

