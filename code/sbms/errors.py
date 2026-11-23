"""Errors that carry a message we can show straight to the user."""


class SBMSError(Exception):
    """Base class. str(error) is a user-friendly message."""


class ValidationError(SBMSError):
    """Input is missing or not valid (negative price, bad date, etc.)."""


class BusinessRuleError(SBMSError):
    """The action breaks a bakery rule (not enough stock, wrong order status, etc.)."""


class PermissionDenied(SBMSError):
    """The logged-in user's role is not allowed to do this."""


class LoginFailed(SBMSError):
    pass
