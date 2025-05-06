from enum import Enum
class ErrorMessage(Enum):
    pass
class UserErrorMessage(Enum):
    # Authentication errors
    INVALID_CREDENTIALS = "Invalid credentials"
    ACCOUNT_INACTIVE = "User account is inactive"
    LOGIN_NOT_ALLOWED = "Login not allowed for this user type"
    TOKEN_EXPIRED = "Token has expired"
    INVALID_TOKEN = "Invalid token"
    TOKEN_BLACKLISTED = "Token is already blacklisted"
    AUTH_HEADER_MISSING = "Authorization header is required"
    INVALID_AUTH_HEADER = "Invalid Authorization header format"
    MISSING_FIELDS = "Required fields are missing"
    # User errors
    USERNAME_EXISTS = "Username already exists"
    EMAIL_EXISTS = "Email already exists"
    PHONE_EXISTS = "Phone number already exists"
    AADHAAR_EXISTS = "Aadhaar number already exists"
    USER_NOT_FOUND = "User not found"

    # Validation errors
    INVALID_EMAIL = "Invalid email address"
    INVALID_PINCODE = "Pincode must be 6 digits (no leading zero)"
    INVALID_AADHAAR = "Aadhaar must be 12 digits (no leading zero)"
    INVALID_MOBILE = "Invalid phone number"
    INVALID_USERNAME = "Username may contain only letters, digits and @/./+/-/_"
    INVALID_NAME = "Name must be 2-100 characters with valid characters"
    INVALID_PASSWORD = "Password must be at least 8 characters with uppercase, lowercase and digit"
    INVALID_ADDRESS = "Address must be a valid dictionary with required fields"
    INVALID_USER_TYPE = "Invalid user type"

    # Permission errors
    ADMIN_REQUIRED = "Admin access required"
    PERMISSION_DENIED = "Permission denied"

    # System errors
    SERVER_ERROR = "Internal server error"
    DATABASE_ERROR = "Database operation failed"
    CACHE_ERROR = "Cache operation failed"