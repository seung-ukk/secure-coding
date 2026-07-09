def validate_email(value: str) -> bool:
    return '@' in value and len(value) <= 254


def validate_username(value: str) -> bool:
    return 3 <= len(value) <= 30
