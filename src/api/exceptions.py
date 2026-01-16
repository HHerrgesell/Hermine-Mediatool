"""Custom exceptions for Hermine client."""


class HermineException(Exception):
    """Base exception for Hermine API errors"""
    pass


class AuthenticationError(HermineException):
    """Authentication failed"""
    pass


class APIError(HermineException):
    """API request failed"""
    pass


class DownloadError(HermineException):
    """File download failed"""
    pass


class ValidationError(HermineException):
    """Validation error"""
    pass
