from app import db
from app.models import AppSetting


def get_setting(key: str, default: str | None = None) -> str | None:
    setting = AppSetting.query.filter_by(key=key).first()
    if setting:
        return setting.value
    return default


def get_int_setting(key: str, default: int) -> int:
    value = get_setting(key)
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def set_setting(key: str, value: str) -> AppSetting:
    setting = AppSetting.query.filter_by(key=key).first()
    if not setting:
        setting = AppSetting(key=key, value=value)
        db.session.add(setting)
    else:
        setting.value = value
    return setting
