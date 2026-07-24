import re
from decimal import Decimal, InvalidOperation

def validate_email(value: str) -> bool:
    if not value or len(value) > 254:
        return False
    pattern = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
    return re.fullmatch(pattern, value) is not None


def validate_username(value: str) -> bool:
    if not value or not (3 <= len(value) <= 30):
        return False
    return re.fullmatch(r"[A-Za-z0-9_]+", value) is not None


def validate_password(value: str) -> bool:
    # At least 8 characters, at least one uppercase, one lowercase, one digit, and one special character
    if len(value) < 8:
        return False
    if not re.search(r'[A-Z]', value):
        return False
    if not re.search(r'[a-z]', value):
        return False
    if not re.search(r'[0-9]', value):
        return False
    if not re.search(r'[^a-zA-Z0-9]', value):
        return False
    return True


def validate_item_title(value: str) -> tuple[bool, str]:
    if value is None:
        return False, 'title is required'
    normalized = value.strip()
    if not normalized:
        return False, 'title cannot be empty'
    if len(normalized) > 100:
        return False, 'title must be 100 characters or fewer'
    return True, normalized


def validate_item_description(value: str) -> tuple[bool, str]:
    if value is None:
        return False, 'description is required'
    normalized = value.strip()
    if not normalized:
        return False, 'description cannot be empty'
    if len(normalized) > 2000:
        return False, 'description must be 2000 characters or fewer'
    return True, normalized


def validate_item_price(value: str) -> tuple[bool, Decimal | None, str]:
    if value is None:
        return False, None, 'price is required'
    try:
        normalized = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return False, None, 'invalid price format'
    if normalized <= 0:
        return False, None, 'price must be positive'
    if normalized > Decimal('1000000000'):
        return False, None, 'price exceeds allowed maximum'
    quantized = normalized.quantize(Decimal('0.01'))
    return True, quantized, ''
