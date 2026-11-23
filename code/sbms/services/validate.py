"""Input checks shared by all modules. Each returns a clean value or raises ValidationError."""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from ..errors import ValidationError


def required_text(value, field, max_len=100):
    value = (value or "").strip()
    if not value:
        raise ValidationError(f"{field} is required.")
    if len(value) > max_len:
        raise ValidationError(f"{field} must be {max_len} characters or fewer.")
    return value


def money(value, field="Price"):
    try:
        amount = Decimal(str(value).strip())
    except (InvalidOperation, AttributeError):
        raise ValidationError(f"{field} must be a number, for example 12.50.")
    if amount < 0:
        raise ValidationError(f"{field} cannot be negative.")
    if amount.as_tuple().exponent < -2:
        raise ValidationError(f"{field} can have at most 2 decimal places.")
    return amount


def positive_int(value, field="Quantity", allow_zero=False):
    try:
        number = int(str(value).strip())
    except (ValueError, AttributeError):
        raise ValidationError(f"{field} must be a whole number.")
    if number < 0 or (number == 0 and not allow_zero):
        raise ValidationError(f"{field} must be {'0 or more' if allow_zero else 'more than 0'}.")
    return number


def positive_decimal(value, field="Quantity"):
    try:
        number = Decimal(str(value).strip())
    except (InvalidOperation, AttributeError):
        raise ValidationError(f"{field} must be a number.")
    if number <= 0:
        raise ValidationError(f"{field} must be more than 0.")
    return number


def parse_date(value, field="Date"):
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value).strip(), "%Y-%m-%d").date()
    except ValueError:
        raise ValidationError(f"{field} must be a real date in the format YYYY-MM-DD.")


def parse_datetime(value, field="Date and time"):
    if isinstance(value, datetime):
        return value
    try:
        return datetime.strptime(str(value).strip(), "%Y-%m-%d %H:%M")
    except ValueError:
        raise ValidationError(f"{field} must be in the format YYYY-MM-DD HH:MM.")
