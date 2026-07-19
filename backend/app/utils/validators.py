import re

def validate_email(value: str) -> bool:
    return '@' in value and len(value) <= 254


def validate_username(value: str) -> bool:
    return 3 <= len(value) <= 30


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

