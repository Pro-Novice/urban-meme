"""
This module defines the error handling class of the system
There are three braod category of the exceptions
    * Server Error if the error is due to the malfunctioning of the server
    * User Error if the error is due to the incorrect data from user
    * OtpError if the error is related to OTP
"""
from rest_framework import status

from backend.services.response_messages.response_messages import ErrorMessage


class ServerError(Exception):
    """
    Exception raised when a server error occurs.
    """

    def __init__(self, message, status=status.HTTP_400_BAD_REQUEST, errors=None):
        """
        Initializes the exception with a message, status, and optional errors.
        :param message: A string describing the error.
        :param status: HTTP status code associated with the error.
        :param errors: A dictionary of error messages.
        """
        self.status = status
        message = message.name if isinstance(message, ErrorMessage) else message
        super().__init__(message)
        self.errors = errors


class UserError(Exception):
    """
    Exception raised when a error due to user actions
    """

    def __init__(self, message, status=status.HTTP_400_BAD_REQUEST, errors=None):
        """
        Initializes the exception with a message, status, and optional errors.
        :param message: A string describing the error.
        :param status: HTTP status code associated with the error.
        :param errors: A dictionary of error messages.
        """
        self.status = status
        message = message.name if isinstance(message, ErrorMessage) else message
        super().__init__(message)
        self.errors = errors


class OtpError(Exception):
    """
    Exception raised when an error related to OTP (One-Time Password) occurs.
    """

    def __init__(self, message, status=status.HTTP_400_BAD_REQUEST, errors=None):
        """
        Initializes the exception with a message, status, and optional errors.
        :param message: A string describing the error.
        :param status: HTTP status code associated with the error.
        :param errors: A dictionary of error messages.
        """
        self.status = status
        message = message.name if isinstance(message, ErrorMessage) else message
        super().__init__(message)
        self.errors = errors


class ServiceNotAvailableError(ServerError):
    """
    Exception raised when a server not found
    """

    def __init__(self, message, status=status.HTTP_503_SERVICE_UNAVAILABLE, errors=None):
        """
        Initializes the exception with a message, status, and optional errors.
        :param message: A string describing the error.
        :param status: HTTP status code associated with the error.
        :param errors: A dictionary of error messages.
        """
        self.status = status
        super().__init__(message, status, errors)
        self.errors = errors


class BlockchainError(ServerError):
    """
    Exception raised when a server error occurs.
    """

    def __init__(self, message, status=status.HTTP_400_BAD_REQUEST, errors=None):
        """
        Initializes the exception with a message, status, and optional errors.
        :param message: A string describing the error.
        :param status: HTTP status code associated with the error.
        :param errors: A dictionary of error messages.
        """
        self.status = status
        super().__init__(message, status, errors)
        self.errors = errors


class DataFormatError(ServerError):
    """
    Exception raised when a server error occurs.
    """

    def __init__(self, message, status=status.HTTP_400_BAD_REQUEST, errors=None):
        """
        Initializes the exception with a message, status, and optional errors.
        :param message: A string describing the error.
        :param status: HTTP status code associated with the error.
        :param errors: A dictionary of error messages.
        """
        self.status = status
        super().__init__(message, status, errors)
        self.errors = errors


class DataReadError(ServerError):
    """
    Exception raised when data fetch from blockchain fails
    """

    def __init__(self, message, status=status.HTTP_400_BAD_REQUEST, errors=None):
        """
        Initializes the exception with a message, status, and optional errors.
        :param message: A string describing the error.
        :param status: HTTP status code associated with the error.
        :param errors: A dictionary of error messages.
        """
        self.status = status
        super().__init__(message, status, errors)
        self.errors = errors


class InvalidUserError(UserError):
    """
    Exception raised when a user is not found in database.
    """

    def __init__(self, message, status=status.HTTP_400_BAD_REQUEST, errors=None):
        """
        Initializes the exception with a message, status, and optional errors.
        :param message: A string describing the error.
        :param status: HTTP status code associated with the error.
        :param errors: A dictionary of error messages.
        """
        self.status = status
        super().__init__(message, status, errors)
        self.errors = errors


class InvalidDataError(UserError):
    """
    Exception raised when a user provided data is invalid or missing
    """

    def __init__(self, message, status=status.HTTP_400_BAD_REQUEST, errors=None):
        """
        Initializes the exception with a message, status, and optional errors.
        :param message: A string describing the error.
        :param status: HTTP status code associated with the error.
        :param errors: A dictionary of error messages.
        """
        # self.status = status
        super().__init__(message, status, errors)
        # self.errors = errors


class VaultError(Exception):
    """
    Exception raised when a reference is not found in vault provided data is invalid or missing
    """

    def __init__(self, message, status=status.HTTP_400_BAD_REQUEST, errors=None):
        """
        Initializes the exception with a message, status, and optional errors.
        :param message: A string describing the error.
        :param status: HTTP status code associated with the error.
        :param errors: A dictionary of error messages.
        """
        # self.status = status
        super().__init__(message, status, errors)
        # self.errors = errors
